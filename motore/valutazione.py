# -*- coding: utf-8 -*-
"""Valutazione live: da punti attesi a prezzo consigliato, ricalcolato a ogni acquisto.

Tre livelli:

  1. punti totali    = punti attesi individuali + contributo al modificatore di difesa
  2. VOR             = punti sopra il giocatore di rimpiazzo, con rimpiazzo dinamico
  3. prezzo mercato  = quota del pool discrezionale ancora in circolo, proporzionale al VOR

La proprieta' che rende affidabile il terzo livello: la somma dei prezzi
consigliati su tutti i giocatori ancora prendibili e' esattamente uguale ai
crediti ancora in mano alla lega. Il mercato si chiude per costruzione, e non
c'e' nessuna costante da tarare a mano.

Il modificatore di difesa rompe l'additivita': il valore di un difensore
dipende dagli altri difensori della rosa. Qui viene approssimato come
contributo marginale su una difesa di riferimento; il valore esatto per la
propria rosa lo calcolera' l'ottimizzatore.
"""
import collections, math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modificatore import Modificatore

RUOLI = ('P', 'D', 'C', 'A')
GIORNATE = 38.0

# Semiampiezza della finestra usata per stimare il livello di rimpiazzo.
AMPIEZZA_RIMPIAZZO = 2

# Quanti crediti di "prudenza" pesano contro quello che un avversario ha gia'
# speso, quando si stima quanto e' aggressivo. Con questo valore, chi ha
# comprato per trenta crediti roba che ne valeva venti risulta appena sopra la
# media; chi lo fa per trecento risulta un compratore caro sul serio. E' il
# modo di dire "un acquisto non fa una tendenza" senza dover contare gli
# acquisti: conta i crediti, che e' la misura giusta di quanto ha scoperto le
# carte.
PRUDENZA_AGGRESSIVITA = 80.0

# Entro che limiti puo' muoversi il moltiplicatore. Serve a impedire che un
# solo colpo di testa a inizio asta faccia sembrare un avversario disposto a
# pagare il triplo di tutto per il resto della serata.
AGGRESSIVITA_MIN = 0.65
AGGRESSIVITA_MAX = 1.75


# Il livello di rimpiazzo si prende sull'ultimo slot di rosa che verra'
# assegnato in tutta la lega, non sull'ultimo titolare schierato.
#
# La scelta e' stata verificata contro i prezzi realmente pagati in asta:
# mettendo la linea ai soli titolari la correlazione di rango scende a 0.23 e
# i primi dieci giocatori si mangiano il 42% del budget della lega; portandola
# alla rosa piena la correlazione sale a 0.51 e la quota scende al 25%.
# La ragione e' che la panchina non vale zero: quando il titolare salta, e'
# lei a scendere in campo, e con 5 sostituzioni concesse questo pesa.


# ----------------------------------------------------- la curva dei prezzi
# Sotto questa cifra un prezzo storico e' fondo scala: dice che il giocatore
# non lo voleva nessuno, non quanto la stanza lo valuti.
SOGLIA_STORICO = 4.0
QI_MINIMO = 3
# Sotto venti osservazioni una retta e' rumore, e un peso sbagliato sposta
# crediti veri. Il reparto che non ci arriva torna alla spartizione a merito.
OSSERVAZIONI_MINIME = 20
# Nessun peso puo' valere piu' di mezzo budget di squadra: fuori dalla nuvola
# dei prezzi osservati la retta estrapola, e in scala logaritmica estrapola in
# fretta.
TETTO_PESO = 0.5
# Quanto pesa la curva dei prezzi accanto al merito, in media geometrica fra
# i due prezzi. Non e' una preferenza: e' il valore che sbaglia meno sui prezzi
# realmente pagati, misurato sui 225 giocatori che hanno uno storico d'asta.
#
#   curva   errore tipico   errore pesato per i crediti in gioco
#     0,0        34%                    40%      (solo merito, com'era)
#     0,3        29%                    31%
#     0,6        32%                    28%      <-
#     1,0        40%                    30%      (solo curva)
#
# Si guarda soprattutto la seconda colonna: sbagliare del trenta per cento su
# un attaccante da cento crediti costa trenta crediti, sbagliarlo su un
# riempitivo da due ne costa meno di uno. Per reparto, l'attacco passa da 70%
# a 29% di errore, la difesa da 33% a 29%; il centrocampo peggiora da 29% a
# 35%, ed e' il prezzo del compromesso, pagato dove le cifre in gioco sono la
# meta'.
#
# I portieri restano fuori dalla curva: con le riserve a un credito lo storico
# d'asta descrive un'altra lega.
PESO_CURVA = 0.6


def _regressione(righe):
    """Minimi quadrati su due variabili piu' costante. `righe` = (x1, x2, y).

    Tre incognite, quindi un sistema 3x3 risolto per eliminazione. Il caso
    singolare &mdash; due colonne che dicono la stessa cosa &mdash; non alza
    un'eccezione: restituisce None, e il chiamante torna al criterio di prima.
    """
    n = len(righe)
    X = [(1.0, r[0], r[1]) for r in righe]
    y = [r[2] for r in righe]
    M = [[sum(X[i][a] * X[i][b] for i in range(n)) for b in range(3)]
         + [sum(X[i][a] * y[i] for i in range(n))] for a in range(3)]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(M[r][i]))
        if abs(M[p][i]) < 1e-9:
            return None
        M[i], M[p] = M[p], M[i]
        for r in range(3):
            if r != i:
                f = M[r][i] / M[i][i]
                for c in range(4):
                    M[r][c] -= f * M[i][c]
    return tuple(M[i][3] / M[i][i] for i in range(3))

class Giocatore(object):
    __slots__ = ('id', 'nome', 'squadra', 'ruolo', 'qi', 'punti_base', 'mv',
                 'metodo', 'affidabilita', 'punti_mod', 'punti', 'vor',
                 'prezzo_mercato', 'prezzo_riferimento', 'presenze', 'fm',
                 'prezzo_atteso', 'prezzo_base', 'titolare_por', 'riserve_por',
                 # gerarchia di reparto: chi gioca davvero
                 'titolarita', 'posto_reparto', 'in_reparto', 'grado',
                 'certezza', 'nuovo', 'rigorista', 'fuori_lista',
                 # peso del giocatore nella spartizione dei crediti del reparto
                 'peso_prezzo', 'prezzo_piano')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def sicuro(self):
        """Titolare, e con poco margine di dubbio."""
        return self.grado == 'titolare' and (self.certezza or 0) >= 0.55

    @property
    def etichetta_grado(self):
        return {'titolare': 'Titolare', 'ballottaggio': 'Ballottaggio',
                'rotazione': 'Rotazione', 'riserva': 'Riserva'}.get(
                    self.grado, 'Da verificare')

    def __repr__(self):
        return '<%s %s %s punti=%.0f vor=%.0f prezzo=%.0f>' % (
            self.ruolo, self.nome, self.squadra, self.punti or 0,
            self.vor or 0, self.prezzo_mercato or 0)


class Valutatore(object):

    def __init__(self, con, regole, stato):
        self.con = con
        self.reg = regole
        self.stato = stato
        self.mod = Modificatore(regole)
        self.g = {}
        self._carica()
        self._carica_coppie()
        self._struttura_portieri()
        self._contributo_modificatore()
        self.riferimento = None   # rapporto D/V a inizio asta, per l'inflazione
        self._pool_iniziale = 0
        self._curva_prezzi()
        self._prezzi_base()
        self.aggiorna()
        self.riferimento = self._densita
        self._pool_iniziale = max(1, self.reg.crediti_totali - self.reg.slot_lega)

    # ------------------------------------------------------------- caricamento
    def _carica(self):
        for r in self.con.execute("""
                SELECT g.id, g.nome, g.squadra, g.ruolo, g.qi,
                       COALESCE(g.nuovo_acquisto, 0) nuovo,
                       p.punti_attesi, p.mv_attesa, p.metodo, p.affidabilita,
                       p.presenze_attese, p.fantamedia_attesa,
                       p.titolarita, p.posto_reparto, p.in_reparto,
                       p.grado, p.certezza,
                       COALESCE(p.fuori_lista, 0) fuori_lista,
                       c.rigorista,
                       pa.prezzo_medio_per_1000
                FROM giocatori g
                LEFT JOIN proiezioni p ON p.id = g.id
                LEFT JOIN contesto c ON c.id = g.id
                LEFT JOIN prezzi_asta pa ON pa.id = g.id
                WHERE g.attivo = 1"""):
            self.g[r['id']] = Giocatore(
                id=r['id'], nome=r['nome'], squadra=r['squadra'], ruolo=r['ruolo'],
                qi=r['qi'] or 1, punti_base=r['punti_attesi'] or 0.0,
                mv=r['mv_attesa'] or 0.0, metodo=r['metodo'] or 'ignoto',
                affidabilita=r['affidabilita'] or 0.0, punti_mod=0.0,
                presenze=r['presenze_attese'] or 0.0,
                fm=r['fantamedia_attesa'] or 0.0,
                titolarita=r['titolarita'], posto_reparto=r['posto_reparto'],
                in_reparto=r['in_reparto'], grado=r['grado'],
                certezza=r['certezza'], nuovo=bool(r['nuovo']),
                fuori_lista=bool(r['fuori_lista']),
                rigorista=r['rigorista'] or 0,
                prezzo_riferimento=(r['prezzo_medio_per_1000'] or 0.0)
                                   * self.reg.crediti / 1000.0)

    # ------------------------------------------------- coppie complementari
    def _carica_coppie(self):
        """Chi si divide la maglia con chi.

        Due giocatori della stessa squadra per lo stesso posto: quando non
        gioca l'uno gioca l'altro. In asta e' l'informazione che vale di piu'
        e che nessun listone scrive, perche' permette di comprare la seconda
        meta' di una maglia a un decimo del prezzo della prima.

        **La copertura si ricalcola qui, non si legge dal file.** Il file la
        stima quando le guide vengono lette, e a quel punto per un giocatore
        che nessuna guida nomina puo' solo usare la media dei non titolari:
        tredici o quattordici partite. Poi le proiezioni tagliano i minuti del
        reparto e quel giocatore scende a tre presenze, ma nel file resta
        scritto quattordici. Sommate a quelle del titolare facevano il 95% di
        stagione coperta da una coppia in cui il secondo gioca tre partite.

        E soprattutto cambia la domanda a cui il numero risponde. Non serve
        sapere quante giornate coprono in due &mdash; se il primo e' titolare
        e' comunque un numero alto, e non distingue niente &mdash; ma **quanti
        dei buchi del titolare il secondo riempie davvero**. E' quello che si
        compra quando si compra la seconda meta' di una maglia.
        """
        self.coppie = collections.defaultdict(list)
        try:
            righe = self.con.execute('SELECT * FROM accoppiate').fetchall()
        except Exception:
            return
        for r in righe:
            a, b = r['id_titolare'], r['id_vice']
            if a not in self.g or b not in self.g:
                continue
            pa = self.g[a].presenze or 0.0
            pb = self.g[b].presenze or 0.0
            buchi = max(0.0, GIORNATE - pa)
            tappati = min(pb, buchi)
            comune = {'tipo': r['tipo'],
                      'copertura': (pa + tappati) / GIORNATE,
                      'giornate_coperte': pa + tappati,
                      'buchi': buchi, 'buchi_coperti': tappati,
                      'copertura_buchi': (tappati / buchi) if buchi > 0 else 0.0,
                      'fonti': r['fonti'] or '', 'nota': r['nota'] or ''}
            self.coppie[a].append(dict(comune, altro=b, ruolo_nella_coppia='titolare'))
            self.coppie[b].append(dict(comune, altro=a, ruolo_nella_coppia='vice'))
        for k in self.coppie:
            self.coppie[k].sort(key=lambda d: -d['copertura_buchi'])

    def compagni_di_maglia(self, giocatore_id):
        """Le coppie di cui quel giocatore fa parte, dalla piu' solida."""
        return list(self.coppie.get(giocatore_id, ()))

    # -------------------------------------------------- portieri a pacchetto
    def _struttura_portieri(self):
        """Chi e' il titolare di ogni squadra di serie A, e chi gli sta dietro.

        La lega assegna il secondo e il terzo portiere a chi si prende il
        titolare, a un credito l'uno. Cambia la natura del reparto: non sono
        piu' ventiquattro scelte su settantacinque portieri, sono **otto
        pacchetti su venti squadre**. Il rimpiazzo di un portiere non e' il
        ventiquattresimo portiere del listone, e' il nono titolare: quello che
        ti tocca se i primi otto se li prendono gli altri.
        """
        per_squadra = collections.defaultdict(list)
        for x in self.g.values():
            x.titolare_por = False
            x.riserve_por = ()
            if x.ruolo == 'P':
                per_squadra[x.squadra].append(x)
        self.pacchetto = bool(getattr(self.reg, 'portieri_pacchetto', False))
        if not self.pacchetto:
            return
        for lista in per_squadra.values():
            # Titolare = quello che rende di piu' in stagione, non quello con
            # la media piu' alta: un secondo portiere con tre partite buone ha
            # spesso la media migliore.
            lista.sort(key=lambda y: -(y.presenze * y.fm))
            lista[0].titolare_por = True
            lista[0].riserve_por = tuple(y.id for y in lista[1:])

    def riserve_di(self, giocatore_id):
        """Le riserve che seguono il titolare nello stesso acquisto."""
        x = self.g.get(giocatore_id)
        if not x or not getattr(x, 'titolare_por', False):
            return []
        return [i for i in (x.riserve_por or ())]

    # ------------------------------------------------ la curva dei prezzi
    def _curva_prezzi(self):
        """Come si trasforma un giocatore nel prezzo che la stanza gli fa.

        Fino a ieri i crediti del reparto si spartivano in proporzione al VOR:
        quanto vale, tanto costa. E' il modello a dire il prezzo, ed e' un
        errore misurabile, perche' **il prezzo non e' il valore**. Sui prezzi
        realmente pagati (195 giocatori con uno storico d'asta) il conto e'
        questo, fuori campione, su duecento divisioni a meta' del campione:

            solo il nostro modello ........ 48% di errore tipico
            solo la quotazione ufficiale .. 40%
            i due insieme ................. 34%

        Il nostro modello, da solo, e' il peggiore dei tre. Non perche' sbagli
        i giocatori &mdash; l'ordine dentro il reparto lo azzecca (correlazione
        di rango 0,86-0,89) &mdash; ma perche' la stanza non paga in
        proporzione al merito. Paga in proporzione alla quotazione, e la paga
        **piu' che proporzionalmente**: l'esponente stimato sugli attaccanti e'
        1,77, cioe' un attaccante quotato il doppio non costa il doppio, costa
        tre volte e mezzo. Nessuna spartizione lineare puo' produrre quella
        curva.

        E il nostro modello serve lo stesso: al netto della quotazione, il suo
        scarto e' correlato +0,41 con lo scarto del mercato. Sa qualcosa che il
        listone non scrive &mdash; i minuti, i ballottaggi, il modificatore
        &mdash; solo che ne sa molto meno di quanto pesasse finora.

        Quindi il peso non si sceglie: si stima, reparto per reparto, sui
        prezzi che quei giocatori hanno gia' fatto.

            log(prezzo) = a + b log(quotazione) + c log(punti attesi)

        Il risultato e' un **peso**, non un prezzo. Quanto si spende davvero
        resta deciso altrove &mdash; dal budget del reparto e da quanto e' gia'
        stato speso &mdash; e qui si decide solo come quella cifra si divide.
        """
        self.curva = {}
        for ruolo in RUOLI:
            righe = []
            for x in self.g.values():
                if x.ruolo != ruolo:
                    continue
                prezzo = x.prezzo_riferimento or 0.0
                # Sotto i quattro crediti il prezzo e' fondo scala e non dice
                # niente: la meta' del listone sta li' perche' costa un
                # credito, non perche' la stanza l'abbia valutata.
                if prezzo < SOGLIA_STORICO or (x.qi or 0) < QI_MINIMO:
                    continue
                # Chi non puo' giocare porta il prezzo che aveva quando
                # giocava e zero punti: e' esattamente la coppia che
                # storce la retta. Leao, quotato 18 e con zero presenze
                # attese, direbbe alla curva che un attaccante da 18
                # crediti non vale niente.
                if x.fuori_lista:
                    continue
                righe.append((math.log(x.qi),
                              math.log(max(1.0, self._punti_grezzi(x))),
                              math.log(prezzo)))
            if len(righe) >= OSSERVAZIONI_MINIME:
                self.curva[ruolo] = _regressione(righe)

        for x in self.g.values():
            c = self.curva.get(x.ruolo)
            if c is None:
                # Senza abbastanza storico si torna al criterio di prima: il
                # merito. Meglio un peso discutibile che un peso inventato.
                x.peso_prezzo = None
                continue
            a, b, k = c
            grezzo = (a + b * math.log(max(1.0, float(x.qi or 1)))
                      + k * math.log(max(1.0, self._punti_grezzi(x))))
            # Il tetto tiene fuori l'estrapolazione: un giocatore fuori dalla
            # nuvola su cui la retta e' stata stimata riceverebbe un peso che
            # nessun prezzo osservato giustifica.
            x.peso_prezzo = min(math.exp(grezzo), TETTO_PESO * self.reg.crediti)
        return self

    def _tetto_reparto(self, ruolo, slot_res):
        """Il massimo che la stanza puo' ancora spendere in quel reparto.

        Serve solo dove una regola di lega mette un prezzo fisso su parte del
        listone. Coi portieri a pacchetto, un titolare ancora libero puo'
        costare qualunque cifra, ma le riserve costano un credito e basta:
        finiti i titolari, il tetto del reparto e' il numero di slot.
        """
        if not (self.pacchetto and ruolo == 'P'):
            return float('inf')
        venduti = self.stato.venduti()
        liberi = [x for x in self.g.values()
                  if x.ruolo == 'P' and x.titolare_por and x.id not in venduti]
        if liberi:
            return float('inf')
        return float(slot_res)

    def _ripiego_prezzo(self, x):
        """La graduatoria di riserva quando il merito si azzera per tutti.

        Punti di stagione, non punti sopra il rimpiazzo: e' la stessa scala
        con cui si ordina il listone, ed e' positiva finche' il giocatore
        gioca. Le riserve dei portieri a pacchetto restano a zero anche qui:
        arrivano col titolare e costano un credito comunque.
        """
        if self.pacchetto and x.ruolo == 'P' and not x.titolare_por:
            return 0.0
        return max(0.0, (x.presenze or 0.0) * (x.fm or 0.0))

    def _pesi(self, vor, pool, slot_residui):
        """I crediti del reparto, spartiti fra due pareri che si mediano.

        I due pareri sono il **merito** (punti sopra il rimpiazzo) e la
        **curva dei prezzi** (quanto la stanza paga uno cosi'). Vivono su
        scale diverse &mdash; punti contro crediti &mdash; e mediarli come
        stanno non si puo'.

        La prima versione ne faceva la media geometrica dei numeri grezzi, e
        sbagliava proprio sui giocatori per cui la curva esisteva. Un
        giocatore che il modello valuta **sotto il livello di rimpiazzo** ha
        merito zero, e la media geometrica di zero e' zero: il prodotto
        veniva schiacciato da un `max(0.01, ...)` messo li' solo perche' il
        logaritmo di zero non esiste. Colombo &mdash; mercato 30 crediti,
        curva 19 &mdash; usciva a **3,5**, cioe' quasi il valore che aveva
        prima che la curva ci fosse. Erano esattamente i casi che la curva
        doveva sistemare.

        Adesso i due pareri si portano **prima** ognuno sul proprio prezzo, e
        si media fra due prezzi. Un prezzo non e' mai sotto un credito, quindi
        il logaritmo e' sempre definito e il pavimento non e' piu' un numero
        scelto per far tornare i conti: e' il credito, che e' quanto costa
        davvero il giocatore piu' scarso del listone.

        Le riserve dei portieri a pacchetto restano fuori: non si comprano,
        arrivano col titolare a un credito.
        """
        def quote(valori):
            """Da un criterio ai crediti che gli toccano, reparto per reparto.

            Con una rete che serve piu' spesso di quanto sembri. Il criterio
            del merito e' il valore **sopra il livello di rimpiazzo**, e quando
            l'offerta di un reparto scende fino a pareggiare la domanda quel
            valore va a zero per tutti insieme: se restano sei pacchetti di
            portieri e sei rose da completare, nessuno di quei sei e' sopra il
            rimpiazzo, perche' il rimpiazzo sono loro.

            Matematicamente giusto, e come prezzo assurdo: il motore diceva
            **un credito** per ognuno dei diciotto portieri rimasti mentre la
            stanza aveva ancora duecentododici crediti destinati a quel
            reparto. Nella lega di Davide i portieri chiudono per primi, quindi
            capitava ogni asta, e quei 194 crediti non comparivano in nessun
            prezzo.

            Quando il criterio si azzera in blocco si ripiega sui punti di
            stagione, che una graduatoria ce l'hanno sempre.
            """
            fuori = {}
            for ruolo in RUOLI:
                # Chi non puo' scendere in campo non prende una fetta
                # del reparto: se la prendesse, sarebbe tolta a chi
                # gioca davvero. Con sessantaquattro nomi fuori lista
                # non e' un dettaglio.
                dentro = [x for x in self.g.values()
                          if x.ruolo == ruolo and not x.fuori_lista]
                somma = sum(max(0.0, valori.get(x.id, 0.0)) for x in dentro)
                usa = valori
                if somma <= 0:
                    usa = dict((x.id, self._ripiego_prezzo(x)) for x in dentro)
                    somma = sum(max(0.0, usa[x.id]) for x in dentro)
                libero = max(0.0, pool.get(ruolo, 0.0))
                for x in dentro:
                    if somma > 0 and libero > 0:
                        fuori[x.id] = 1.0 + max(0.0, usa[x.id]) / somma * libero
                    else:
                        fuori[x.id] = 1.0
            for x in self.g.values():
                fuori.setdefault(x.id, 1.0)
            return fuori

        merito = quote(vor)
        curva = quote(dict((x.id, x.peso_prezzo or 0.0) for x in self.g.values()))

        peso = {}
        for x in self.g.values():
            if x.fuori_lista:
                peso[x.id] = 0.0
            elif self.pacchetto and x.ruolo == 'P' and not x.titolare_por:
                peso[x.id] = 0.0
            elif x.peso_prezzo is None:
                peso[x.id] = max(0.0, merito[x.id] - 1.0)
            else:
                prezzo = math.exp((1.0 - PESO_CURVA) * math.log(merito[x.id])
                                  + PESO_CURVA * math.log(curva[x.id]))
                peso[x.id] = max(0.0, prezzo - 1.0)
        return peso

    def _punti_grezzi(self, x):
        """I punti attesi al lordo del modificatore, disponibili da subito.

        `punti` esiste solo dopo il primo `aggiorna()`, e la curva si stima
        prima: userebbe None su ogni giocatore e non se ne accorgerebbe
        nessuno, perche' una regressione su zeri restituisce comunque tre
        numeri.
        """
        return (x.punti_base or 0.0) + (x.punti_mod or 0.0)

    # --------------------------------------------- il prezzo che non si muove
    def _prezzi_base(self):
        """Quanto sarebbe costato ogni giocatore in una stanza normale, da zero.

        `prezzo_atteso` risponde a "quanto costera' **adesso**", e per farlo si
        aggiorna: divide i crediti che restano fra gli slot che restano. E'
        giusto per decidere quanto offrire, ed e' **sbagliato come metro di
        giudizio a posteriori**, per una ragione che si vede bene sui portieri.
        Quando l'ultimo portiere della lega e' assegnato non ne resta nessuno
        da comprare: i crediti destinati al reparto sono finiti, e il prezzo
        atteso di tutti i portieri collassa a un credito. Da quel momento
        chiunque avesse pagato quaranta crediti il suo portiere &mdash; cioe'
        tutti &mdash; risultava in perdita di trentanove. Non era un giudizio
        sull'asta: era il metro che si accorciava.

        Questo prezzo invece non si muove mai. Si calcola una volta sola, sul
        listone intero e sul budget intero della lega, come se l'asta dovesse
        ancora cominciare. E' la domanda giusta da fare a un acquisto gia'
        fatto: **in una stanza normale, quanto sarebbe costato?**

        Il calcolo e' deliberatamente separato da quello vivo, anche se gli
        somiglia. Metterli in comune vorrebbe dire che una modifica pensata per
        il prezzo del momento &mdash; e ce ne saranno &mdash; si porterebbe
        dietro anche il metro, che invece deve restare fermo.
        """
        reg = self.reg

        # Livello di rimpiazzo sul listone intero, con tutti gli slot della
        # lega ancora da assegnare.
        rimpiazzo = {}
        for ruolo in RUOLI:
            pool = sorted([x for x in self.g.values() if x.ruolo == ruolo],
                          key=lambda x: -((x.presenze or 0) * (x.fm or 0)))
            n = reg.slot[ruolo] * reg.partecipanti
            if ruolo == 'P' and self.pacchetto:
                pool = [x for x in pool if x.titolare_por]
                n = max(1, n // max(1, reg.slot['P']))
            if not pool:
                rimpiazzo[ruolo] = 0.0
                continue
            i = min(n, len(pool) - 1)
            finestra = pool[max(0, i - AMPIEZZA_RIMPIAZZO):
                            min(len(pool), i + AMPIEZZA_RIMPIAZZO + 1)]
            rimpiazzo[ruolo] = sum(x.fm for x in finestra) / float(len(finestra))

        # Punti sopra il rimpiazzo, e loro somma per ruolo sui soli giocatori
        # che in una lega di questa taglia finirebbero davvero in una rosa.
        vor = {}
        for x in self.g.values():
            v = ((x.presenze or 0.0) * ((x.fm or 0.0) - rimpiazzo[x.ruolo])
                 + (x.punti_mod or 0.0))
            if self.pacchetto and x.ruolo == 'P' and not x.titolare_por:
                v = 0.0          # le riserve arrivano in dote, valgono 1
            vor[x.id] = max(0.0, v)

        # Il peso con cui si spartiscono i crediti del reparto: la curva dei
        # prezzi dove c'e', il merito dove la curva non si e' potuta stimare.
        # I due pareri si mediano da prezzo a prezzo, quindi al peso serve
        # sapere quanti crediti ci sono in ballo per reparto.
        # Questo e' un metro di giudizio, non un piano: la domanda e' quanto
        # sarebbe costato nella stanza, quindi la ripartizione da usare e'
        # quella che la stanza usa davvero.
        pool_iniziale = {}
        for ruolo in RUOLI:
            slot = reg.slot[ruolo] * reg.partecipanti
            pool_iniziale[ruolo] = max(
                0.0, reg.quota_mercato[ruolo] * reg.crediti_totali - slot)
        peso = self._pesi(vor, pool_iniziale,
                          dict((r, reg.slot[r] * reg.partecipanti)
                               for r in RUOLI))

        somma = dict((r, 0.0) for r in RUOLI)
        for ruolo in RUOLI:
            ordinati = sorted([x for x in self.g.values() if x.ruolo == ruolo],
                              key=lambda x: -peso[x.id])
            somma[ruolo] = sum(peso[x.id] for x in
                               ordinati[:reg.slot[ruolo] * reg.partecipanti])

        # I crediti si dividono prima fra i reparti, secondo come la stanza
        # spende davvero, e poi dentro il reparto in proporzione al merito.
        for ruolo in RUOLI:
            slot = reg.slot[ruolo] * reg.partecipanti
            budget = reg.quota_mercato[ruolo] * reg.crediti_totali
            pool_r = max(0.0, budget - slot)
            for x in self.g.values():
                if x.ruolo != ruolo:
                    continue
                if somma[ruolo] > 0 and pool_r > 0:
                    x.prezzo_base = 1.0 + peso[x.id] / somma[ruolo] * pool_r
                else:
                    x.prezzo_base = 1.0
        return self

    # ------------------------------------------- contributo al modificatore
    def _contributo_modificatore(self):
        """Quanto vale ciascun difensore/portiere per il modificatore di difesa.

        Solo i migliori entrano nel calcolo: il quarto difensore di una rosa non
        tocca la media. L'inclusione vale 1 per chi rientra nei posti utili di
        tutta la lega e scende linearmente a 0 fino all'ultimo assegnato.
        """
        if not self.mod.attivo:
            return
        P = self.reg.partecipanti
        posti = {'P': self.reg.mod_dif_n_por * P, 'D': self.reg.mod_dif_n_dif * P}
        rif = {}
        for ruolo in ('P', 'D'):
            n_utili = posti[ruolo]
            if n_utili <= 0:
                continue
            ordinati = sorted([x for x in self.g.values() if x.ruolo == ruolo],
                              key=lambda x: -x.mv)
            # Media di riferimento: il livello medio di chi occupa i posti utili.
            utili = ordinati[:n_utili] or ordinati[:1]
            rif[ruolo] = (sum(x.mv for x in utili) / len(utili),
                          ordinati[min(n_utili, len(ordinati)) - 1].mv)
        if 'D' not in rif:
            return
        n_por = self.reg.mod_dif_n_por
        n_dif = self.reg.mod_dif_n_dif
        media_rif = ((n_por * rif.get('P', rif['D'])[0] + n_dif * rif['D'][0])
                     / float(n_por + n_dif))

        for ruolo in ('P', 'D'):
            if ruolo not in rif:
                continue
            n_utili = posti[ruolo]
            n_totali = max(self.reg.slot_lega_ruolo(ruolo), n_utili + 1)
            mv_marginale = rif[ruolo][1]
            ordinati = sorted([x for x in self.g.values() if x.ruolo == ruolo],
                              key=lambda x: -x.mv)
            for rango, x in enumerate(ordinati, start=1):
                if x.fuori_lista:
                    # Chi non puo' scendere in campo non alza nessuna media.
                    x.punti_mod = 0.0
                    continue
                if rango <= n_utili:
                    inclusione = 1.0
                elif rango <= n_totali:
                    inclusione = 1.0 - float(rango - n_utili) / (n_totali - n_utili)
                else:
                    inclusione = 0.0
                if inclusione <= 0:
                    continue
                x.punti_mod = inclusione * self.mod.contributo_marginale(
                    x.mv, mv_marginale, media_rif)

    # ------------------------------------------------------------ ricalcolo
    def aggiorna(self):
        """Ricalcola rimpiazzi, VOR e prezzi sullo stato corrente dell'asta.

        Va richiamato dopo ogni acquisto registrato.
        """
        self._concorrenti_per_ruolo = {}
        venduti = self.stato.venduti()
        disponibili = [x for x in self.g.values() if x.id not in venduti]

        # --- livello di rimpiazzo, per ruolo, sui soli giocatori liberi ----
        # Il confronto e' sulla FANTAMEDIA, non sui punti stagionali. Ogni
        # giornata schieri undici giocatori: cio' che conta e' quanto uno rende
        # rispetto a chi metteresti al suo posto, moltiplicato per quante volte
        # puoi effettivamente schierarlo. Confrontare i totali di stagione
        # premierebbe chi gioca sempre a prescindere da come rende, e infatti
        # sopravvalutava i portieri.
        self.rimpiazzo_fm = {}
        self.candidati = {}
        for ruolo in RUOLI:
            # L'ordinamento e' per PUNTI attesi, non per fantamedia. Ordinando
            # per media, sulla linea di rimpiazzo finiscono riserve con quattro
            # presenze attese e una media gonfiata dal campione minuscolo: fra
            # i primi 48 attaccanti per media ce ne sono undici che giocheranno
            # meno di quindici partite. Alzavano la soglia degli attaccanti a
            # 6,73 e schiacciavano il valore di chi gioca davvero.
            pool = sorted([x for x in disponibili if x.ruolo == ruolo],
                          key=lambda x: -(x.presenze * x.fm))
            n = self.stato.slot_residui_ruolo(ruolo)
            if ruolo == 'P' and self.pacchetto:
                # Otto pacchetti su venti squadre: contano solo i titolari, e
                # il rimpiazzo e' il nono di loro.
                pool = [x for x in pool if x.titolare_por]
                n = max(0, n // max(1, self.reg.slot['P']))
            if not pool:
                self.rimpiazzo_fm[ruolo] = 0.0
            elif n <= 0:
                # Ruolo saturo in tutta la lega: nessuno vale piu' di un credito.
                self.rimpiazzo_fm[ruolo] = pool[0].fm
            else:
                # Media locale attorno alla linea invece del singolo giocatore
                # marginale: le fantamedie si accavallano a decimi di punto e
                # capita che due giocatori siano appaiati, oppure che sulla
                # linea capiti un fondo-rosa con pochissime presenze attese e
                # una media gonfiata dal campione piccolo. La finestra assorbe
                # entrambi i casi senza spostare il livello.
                i = min(n, len(pool) - 1)
                finestra = pool[max(0, i - AMPIEZZA_RIMPIAZZO):
                                min(len(pool), i + AMPIEZZA_RIMPIAZZO + 1)]
                self.rimpiazzo_fm[ruolo] = (sum(x.fm for x in finestra)
                                            / float(len(finestra)))

        for x in self.g.values():
            # Punti che aggiunge alla formazione nell'arco della stagione,
            # piu' il contributo al modificatore di difesa.
            x.punti = (x.presenze * (x.fm - self.rimpiazzo_fm[x.ruolo])
                       + (x.punti_mod or 0.0))
            x.vor = max(0.0, x.punti)
            if self.pacchetto and x.ruolo == 'P' and not x.titolare_por:
                # Le riserve arrivano in dote col titolare: non si comprano,
                # e non vale la pena pagarle piu' di un credito.
                x.vor = 0.0

        self._pesa_col_mercato(disponibili)
        self._aggressivita()

        # Chi entrera' davvero in una rosa: i migliori per ogni ruolo, fino a
        # coprire gli slot ancora da assegnare in tutta la lega.
        for ruolo in RUOLI:
            pool = sorted([x for x in disponibili if x.ruolo == ruolo],
                          key=lambda x: -x.vor)
            n = max(self.stato.slot_residui_ruolo(ruolo), 0)
            if ruolo == 'P' and self.pacchetto:
                # Chi finira' in una rosa non sono i primi 24 portieri: sono
                # gli 8 titolari scelti PIU' le riserve che si portano dietro.
                # Tenerli tutti dentro e' cio' che fa tornare i conti: la somma
                # dei prezzi consigliati deve restare uguale ai crediti in
                # circolo, e le riserve un credito lo costano.
                titolari = [x for x in pool if x.titolare_por]
                quanti = max(0, n // max(1, self.reg.slot['P']))
                scelti = titolari[:quanti]
                assegnati = list(scelti)
                for t in scelti:
                    for rid in (t.riserve_por or ()):
                        y = self.g.get(rid)
                        if y is not None and y.id not in venduti:
                            assegnati.append(y)
                if len(assegnati) < n:
                    # Qualche squadra ha solo due portieri a listone: gli slot
                    # scoperti si riempiono comunque, dal fondo del listone.
                    gia = set(x.id for x in assegnati)
                    for y in pool:
                        if len(assegnati) >= n:
                            break
                        if y.id not in gia:
                            assegnati.append(y)
                self.candidati[ruolo] = assegnati[:n]
                continue
            self.candidati[ruolo] = pool[:n]

        # --- prezzi di mercato ---------------------------------------------
        self.crediti_residui = self.stato.crediti_residui_lega
        self.slot_residui = self.stato.slot_residui_lega
        self.pool_discrezionale = max(0, self.crediti_residui - self.slot_residui)
        self.vor_totale = sum(x.vor for r in RUOLI for x in self.candidati[r])

        for x in self.g.values():
            if self.vor_totale > 0 and self.pool_discrezionale > 0:
                x.prezzo_mercato = 1.0 + x.vor / self.vor_totale * self.pool_discrezionale
            else:
                x.prezzo_mercato = 1.0
        self._densita = (self.pool_discrezionale / self.vor_totale
                         if self.vor_totale > 0 else 0.0)
        self._prezzi_attesi()
        return self

    # ---------------------------------------------- il parere del mercato
    def _aggressivita(self):
        """Quanto paga sopra il dovuto ognuno degli altri, misurato sul campo.

        Fino a ieri il motore stimava il prezzo di chiusura assumendo che tutti
        in sala valutassero allo stesso modo: il consenso di mercato. Ma a un
        tavolo vero non e' cosi', e la differenza si vede dopo tre chiamate.
        C'e' chi paga il trenta per cento sopra qualunque cosa gli piaccia e
        chi aspetta gli avanzi, e stimare la chiusura con lo stesso numero per
        entrambi vuol dire sbagliare in due direzioni opposte: si perde
        l'obiettivo contro il primo e si paga troppo contro il secondo.

        La misura c'e' gia' ed e' la stessa che l'interfaccia mostra accanto a
        ogni squadra: quanto ha speso diviso quanto quella roba sarebbe costata
        in una stanza normale. Qui diventa un moltiplicatore, tirato verso 1
        finche' i crediti spesi sono pochi &mdash; **un acquisto non fa una
        tendenza** &mdash; e tenuto dentro limiti larghi ma non assurdi.
        """
        speso = {}
        atteso = {}
        for a in self.stato.acquisti():
            pid = a['presidente_id']
            x = self.g.get(a['giocatore_id'])
            if x is None:
                continue
            speso[pid] = speso.get(pid, 0.0) + a['prezzo']
            atteso[pid] = atteso.get(pid, 0.0) + (x.prezzo_base or 1.0)
        self.aggressivita = {}
        for p in self.stato.presidenti():
            pid = p['id']
            sp, at = speso.get(pid, 0.0), atteso.get(pid, 0.0)
            k = PRUDENZA_AGGRESSIVITA
            valore = (sp + k) / (at + k) if (at + k) > 0 else 1.0
            self.aggressivita[pid] = min(AGGRESSIVITA_MAX,
                                         max(AGGRESSIVITA_MIN, valore))
        return self.aggressivita

    def _pesa_col_mercato(self, disponibili):
        """Media fra quanto dice il mio modello e quanto dice il mercato.

        Il modello e il mercato sbagliano in modi diversi, e nessuno dei due
        merita fiducia cieca.

        Il modello conosce xG, minuti giocati e modificatore, ma **non sa chi
        e' titolare**: quel campo del database e' vuoto, non esiste una fonte
        strutturata. Il risultato e' che al fondo del listone vede attaccanti
        di riserva quasi buoni come i migliori, e quindi consiglia di comprarne
        sei da un credito e mettere tutto sulla difesa. E' una rosa di ottimi
        affari con cui si perde il campionato.

        Il mercato la titolarita' la conosce, ma paga gli attaccanti molto piu'
        di quanto rendano in punti: e' un'inefficienza nota, ed e' proprio da
        li' che nasce il vantaggio di avere uno strumento.

        Fidarsi solo del modello o solo del mercato sono due errori opposti.
        `fiducia_nel_mercato` in regole_lega.json decide dove stare fra i due:
        a 0 solo il modello, a 1 solo il mercato, 0.5 a meta'. La media si fa
        sui punti, non sui prezzi, per restare nella stessa unita' di misura.
        """
        b = getattr(self.reg, 'fiducia_mercato', 0.0)
        self.parere_mercato = {}
        if b <= 0:
            return
        for ruolo in RUOLI:
            pool = [x for x in disponibili if x.ruolo == ruolo]
            con_prezzo = [x for x in pool if (x.prezzo_riferimento or 0) > 0]
            if len(con_prezzo) < 8:
                continue
            # I prezzi storici si portano sulla scala dei punti del ruolo,
            # cosi' i due numeri sono confrontabili invece che accostati.
            somma_vor = sum(x.vor for x in con_prezzo)
            somma_rif = sum(x.prezzo_riferimento for x in con_prezzo)
            if somma_rif <= 0 or somma_vor <= 0:
                continue
            k = somma_vor / somma_rif
            for x in pool:
                rif = x.prezzo_riferimento or 0
                if rif <= 0:
                    continue           # senza storico resta il solo modello
                if self.pacchetto and ruolo == 'P' and not x.titolare_por:
                    # Una riserva non si compra: arriva col titolare a un
                    # credito. Che il mercato la pagasse cara quando era lei
                    # a giocare non cambia quanto vale adesso.
                    continue
                secondo_mercato = rif * k
                self.parere_mercato[x.id] = secondo_mercato
                x.punti = (1 - b) * x.punti + b * secondo_mercato
                x.vor = max(0.0, x.punti)

    # -------------------------------------------------------- prezzi attesi
    def _prezzi_attesi(self):
        """Quanto costera' ogni giocatore, dato come spende DAVVERO la stanza.

        Il prezzo di mercato calcolato sopra dice quanto un giocatore *vale*
        alla lega: e' una misura di merito, e distribuisce i crediti fra i
        ruoli in proporzione ai punti. Ma nessuna stanza si comporta cosi'.
        Sui prezzi realmente pagati la ripartizione e' P 9 / D 16 / C 28 / A 47,
        e in molte leghe sugli attaccanti si arriva al 60%.

        Ignorare questo scarto porta a un errore preciso e costoso: il motore
        vede gli attaccanti forti come cari e i difensori come convenienti,
        consiglia di caricare la difesa, e a fine asta ci si ritrova pieni di
        buoni affari da nove crediti e senza nessuno che segni. I crediti
        avanzati non valgono niente: quello che conta e' con che rosa esci.

        Qui i crediti si dividono prima **fra i ruoli**, secondo il
        comportamento atteso della stanza, e poi dentro ogni ruolo in
        proporzione al merito. E la previsione si corregge da sola: quello che
        la stanza ha gia' speso e' un fatto, e quel che resta va diviso su
        quello che resta da comprare.
        """
        reg, st = self.reg, self.stato
        speso, slot_res, peso_ruolo = {}, {}, {}
        for r in RUOLI:
            speso[r] = st.speso_ruolo(r) if hasattr(st, 'speso_ruolo') else 0
            slot_res[r] = max(0, st.slot_residui_ruolo(r))

        # Quanto resta per ogni ruolo: il preventivo meno quello gia' speso,
        # e comunque mai meno di un credito per slot ancora da assegnare.
        def _reparti(quota):
            """I crediti che restano per reparto, data una ripartizione.

            Si chiama due volte: con la previsione su come spende la
            stanza, che serve a dire quanto costera' un giocatore, e
            con il piano, che serve a decidere quanto offrire. Sono
            due domande diverse e vogliono due numeri diversi.
            """
            rimane = {}
            for r in RUOLI:
                # **Un reparto chiuso non trattiene crediti.** Quando l'ultimo slot
                # di un ruolo e' assegnato non c'e' piu' niente da comprare li'
                # dentro, e quello che la stanza aveva preventivato e non ha speso
                # non sparisce: lo spendera' sugli altri reparti. Lasciandolo nel
                # reparto chiuso finiva assegnato a nessuno, e i prezzi attesi di
                # tutto il resto dell'asta uscivano **piu' bassi del vero**. Nella
                # lega di Davide i portieri chiudono per primi, quindi succedeva
                # ogni volta: 194 crediti su 3344 &mdash; il 6% &mdash; non erano
                # in nessun prezzo.
                if slot_res[r] <= 0:
                    rimane[r] = 0.0
                    continue
                previsto = quota[r] * reg.crediti_totali
                rimane[r] = max(float(slot_res[r]),
                                previsto - speso[r] if reg.impara_mercato else previsto)
                # E un reparto non puo' trattenere piu' di quello che i giocatori
                # rimasti possono davvero costare. Il caso vero sono i portieri a
                # pacchetto: quando tutti i titolari sono stati assegnati restano
                # a listone solo le riserve, che arrivano in dote a un credito.
                # Il motore continuava a destinare al reparto duecentododici
                # crediti per diciotto riserve da un credito l'una, e quei
                # centonovantaquattro crediti &mdash; che la stanza spendera'
                # eccome, sugli altri reparti &mdash; non finivano in nessun
                # prezzo. In una lega dove i portieri chiudono per primi succedeva
                # a ogni asta, e da li' in poi ogni chiusura attesa era bassa.
                rimane[r] = min(rimane[r], self._tetto_reparto(r, slot_res[r]))
            somma = sum(rimane.values()) or 1.0
            scala = float(self.crediti_residui) / somma
            out = {}
            for r in RUOLI:
                # La normalizzazione non deve poter scendere sotto il minimo
                # tecnico: ogni slot costa almeno un credito.
                out[r] = max(float(slot_res[r]), rimane[r] * scala)
            return out

        # Quello che la stanza spendera' per reparto: e' con questo che si
        # risponde a "quanto costera'".
        self.budget_ruolo = _reparti(reg.quota_mercato)
        # E quello che il piano destina a ciascun reparto: e' con questo che
        # si decide fin dove spingersi.
        self.budget_piano = _reparti(reg.quota_budget)

        # Il secondo prezzo: quello con cui si **pianifica**, che non e' lo
        # stesso con cui si risponde a "quanto costera'". La ragione sta in
        # `prezzo_piano` qui sotto.
        vor_ruolo = dict((r, sum(x.vor for x in self.candidati[r]))
                         for r in RUOLI)
        # I pesi si calcolano dopo il budget di reparto: mediando fra due
        # prezzi, servono i crediti su cui quei prezzi si formano.
        pool_libero = dict((r, max(0.0, self.budget_ruolo[r] - slot_res[r]))
                           for r in RUOLI)
        pool_piano = dict((r, max(0.0, self.budget_piano[r] - slot_res[r]))
                          for r in RUOLI)
        peso = self._pesi(dict((x.id, x.vor) for x in self.g.values()),
                          pool_libero, slot_res)
        for r in RUOLI:
            peso_ruolo[r] = sum(peso[x.id] for x in self.candidati[r])

        for x in self.g.values():
            r = x.ruolo
            pool_r = pool_libero[r]
            if peso_ruolo[r] > 0 and pool_r > 0:
                x.prezzo_atteso = 1.0 + peso[x.id] / peso_ruolo[r] * pool_r
            else:
                x.prezzo_atteso = 1.0
            pool_p = pool_piano[r]
            if vor_ruolo[r] > 0 and pool_p > 0:
                x.prezzo_piano = 1.0 + x.vor / vor_ruolo[r] * pool_p
            else:
                x.prezzo_piano = 1.0
            if self.pacchetto and r == 'P' and not x.titolare_por:
                x.prezzo_piano = 1.0
        return self

    # ------------------------------------------------------------- indicatori
    @property
    def inflazione(self):
        """Quanto la stanza sta pagando rispetto all'inizio.

        >1: si e' speso poco finora, i prezzi da qui in avanti salgono.
        <1: si e' speso troppo presto, da qui in avanti si compra a sconto.
        """
        if not self.riferimento:
            return 1.0
        return self._densita / self.riferimento

    def disponibili(self, ruolo=None, n=None):
        venduti = self.stato.venduti()
        out = [x for x in self.g.values()
               if x.id not in venduti and (ruolo is None or x.ruolo == ruolo)]
        # L'id scioglie i pareggi: due giocatori con lo stesso VOR devono
        # uscire sempre nello stesso ordine, altrimenti la lista mostrata
        # cambia da sola.
        out.sort(key=lambda x: (-x.vor, x.id))
        return out[:n] if n else out

    def quota_riempitivo(self, ruolo):
        """Quanto gioca il tappabuchi che troveresti comunque, in quel reparto.

        Serve come **metro di paragone** quando si chiede quante giornate in
        piu' copre un giocatore: il confronto giusto non e' con la casella
        vuota &mdash; a fine asta uno da un credito lo si trova sempre &mdash;
        ma con quello che prenderesti al suo posto senza spendere niente.

        Si guarda chi costa fino a due crediti e si prende il quarto migliore
        per presenze attese, non il primo: i migliori fra i riempitivi se li
        prende qualcun altro, e contare sul migliore in assoluto sarebbe un
        ottimismo che poi si paga a fine reparto.
        """
        import formazione
        quote = sorted(
            (formazione.quota(x) for x in self.disponibili(ruolo)
             if (x.prezzo_base or 1) <= 2), reverse=True)
        if not quote:
            return 0.0
        return quote[min(3, len(quote) - 1)]

    def scarta(self, giocatore_id):
        """Toglie un giocatore dal listone tenuto in memoria.

        E' stato chiamato e non l'ha voluto nessuno: non tocca ne' l'asta ne'
        i dati, serve alle simulazioni per chiudere un giro senza rimettere in
        lista chi e' gia' passato. Qui `self.g` e' l'unica copia e basterebbe
        `pop`; il metodo esiste perche' nella traduzione JavaScript il listone
        e' tenuto in due strutture parallele, e togliere da una sola faceva
        girare la simulazione all'infinito. Le due API devono chiamarsi allo
        stesso modo, se no la differenza torna alla prima persona che traduce
        una riga guardando l'altra.
        """
        return self.g.pop(giocatore_id, None)

    def cerca(self, testo):
        t = testo.strip().lower()
        venduti = self.stato.venduti()
        return [x for x in self.g.values()
                if t in x.nome.lower() and x.id not in venduti]

    # ---------------------------------------------------- avversari e chiusura
    def concorrenti(self, giocatore):
        """Chi puo' ancora contendere quel giocatore, e fino a quanto.

        Il vincolo e' duplice e va rispettato tutto: serve uno slot libero in
        quel ruolo, e servono crediti tenendo 1 per ogni slot che restera'.

        Dipende solo dal RUOLO, non dal singolo giocatore: la risposta si tiene
        da parte fino al prossimo acquisto. Senza, ogni caricamento del listone
        faceva un migliaio di interrogazioni al database per ricalcolare
        ottanta volte le stesse otto righe.
        """
        cache = self._concorrenti_per_ruolo
        if giocatore.ruolo in cache:
            return cache[giocatore.ruolo]
        out = []
        for p in self.stato.presidenti():
            if p['io']:
                continue
            if self.stato.slot_residui(p['id'], giocatore.ruolo) <= 0:
                continue
            liq = self.stato.liquidita(p['id'])
            if liq < 1:
                continue
            out.append({'id': p['id'], 'nome': p['nome'], 'liquidita': liq,
                        'crediti': p['crediti'],
                        'aggressivita': round(
                            getattr(self, 'aggressivita', {}).get(p['id'], 1.0), 2)})
        out.sort(key=lambda d: -d['liquidita'])
        cache[giocatore.ruolo] = out
        return out

    def consenso(self, giocatore):
        """Quanto la stanza e' disposta a pagarlo: media fra il mio modello e
        il prezzo storicamente pagato in asta.

        I due numeri sanno cose diverse. Il mio modello conosce xG, minuti e
        modificatore; il prezzo storico conosce la titolarita' attesa e l'umore
        del mercato, che il database non contiene. Chi rilancia in sala segue
        il secondo molto piu' del primo, quindi per stimare *quanto costera'*
        conta almeno quanto il modello. Per stimare *quanto vale* no: li' il
        modello resta solo.
        """
        mercato = giocatore.prezzo_atteso or giocatore.prezzo_mercato or 1.0
        rif = giocatore.prezzo_riferimento or 0.0
        if rif <= 0:
            return mercato
        # Il riferimento e' un prezzo medio di leghe passate: va riportato al
        # denaro che c'e' ancora in circolo adesso.
        scala = (float(self.pool_discrezionale) / self._pool_iniziale
                 if self._pool_iniziale else 1.0)
        return 0.5 * mercato + 0.5 * rif * scala

    def prezzo_chiusura(self, giocatore):
        """Stima di quanto costera' davvero: la seconda offerta piu' alta, piu' uno.

        In un'asta all'inglese vince il primo ma paga quanto il secondo. Il
        tetto di ciascun avversario e' il minimo fra la sua liquidita' e quanto
        il giocatore vale secondo il consenso di mercato.
        """
        c = self.concorrenti(giocatore)
        atteso = self.consenso(giocatore)
        # Il tetto non e' lo stesso per tutti: ognuno paga sopra o sotto il
        # consenso secondo quanto ha gia' dimostrato di pagare. Chi ha speso
        # trecento crediti per roba che ne valeva duecentotrenta li paghera'
        # anche sul prossimo, e ignorarlo vuol dire perdere ogni volta
        # l'obiettivo per due crediti.
        tetti = sorted((min(x['liquidita'], atteso * x.get('aggressivita', 1.0))
                        for x in c), reverse=True)
        if not tetti:
            return 1.0
        limite = atteso * AGGRESSIVITA_MAX
        if len(tetti) == 1:
            # Con un solo avversario in gara si chiude molto sotto: nessuno dei
            # due deve arrivare al proprio tetto.
            return max(1.0, min(tetti[0], atteso * 0.6))
        return max(1.0, min(limite, tetti[1] + 1))

    # -------------------------------------------------------------- riassunto
    def riassunto(self):
        r = ['Mercato: %d crediti residui, %d slot da riempire, pool discrezionale %d'
             % (self.crediti_residui, self.slot_residui, self.pool_discrezionale),
             'Inflazione stanza: %.2f  (%s)' % (
                 self.inflazione,
                 'prezzi in salita' if self.inflazione > 1.03
                 else ('si compra a sconto' if self.inflazione < 0.97 else 'in linea'))]
        r.append('Fantamedia del titolare marginale (livello di rimpiazzo):')
        for ruolo in RUOLI:
            r.append('  %s: fm %.2f   (%d slot ancora da assegnare in lega)'
                     % (ruolo, self.rimpiazzo_fm[ruolo],
                        self.stato.slot_residui_ruolo(ruolo)))
        return '\n'.join(r)
