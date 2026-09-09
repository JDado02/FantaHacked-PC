# -*- coding: utf-8 -*-
"""Le due domande dell'asta live.

  1. **Esce un giocatore: fino a quanto mi conviene spingermi?**
     `scheda()` mette insieme prezzo di mercato, prezzo massimo personale,
     chiusura attesa e chi puo' ancora rilanciare, e ne tira fuori un verdetto.

  2. **Tocca a me chiamare: chi chiamo?**
     `consiglio()` ordina i giocatori del ruolo in corso secondo due strategie
     che convivono nella stessa asta.

Le due strategie:

  **Prendere.** Chiamo un giocatore che vale per me piu' di quanto costera'.
  Il margine e' `max_bid - chiusura_attesa`: quanto resta in tasca rispetto a
  quello che quel giocatore vale nella mia rosa.

  **Svuotare.** Chiamo un giocatore che NON voglio ma che gli altri pagheranno
  caro. Ogni credito che bruciano su di lui e' un credito che non avranno
  quando chiamero' i miei obiettivi. Ha senso solo finche' gli avversari sono
  ricchi: a fine asta chiamare un big serve solo a regalarlo.

Quale delle due prevalga non e' una preferenza: dipende da quanto la stanza ha
ancora in mano rispetto a me. Se sono io il piu' ricco, ogni asta al rialzo mi
favorisce e conviene prendere; se sono il piu' povero, conviene far spendere
gli altri prima di scoprirmi.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RUOLI = ('P', 'D', 'C', 'A')
GIORNATE = 38

# Un giocatore vale la chiamata "per prenderlo" se il margine supera questa
# quota del prezzo di chiusura. Sotto, e' un'asta a somma zero.
MARGINE_MINIMO = 0.08

# Sotto questa certezza un titolare e' un'ipotesi, non un fatto: e' la soglia
# che separa l'alternativa affidabile dalla scommessa.
CERTEZZA_RIPIEGO = 0.45

# Quanti giocatori del reparto si valutano davvero prima di mettere in fila i
# consigli. Il prezzo massimo costa qualche millisecondo a testa, e valutare
# tutti e centonovanta i difensori vorrebbe dire mezzo secondo a ogni acquisto.
# Novanta, presi per valore sopra il rimpiazzo, coprono chiunque possa essere
# un'occasione: sotto quella soglia ci sono solo riempitivi da un credito, che
# infatti compaiono comunque fra le alternative.
QUANTI_VALUTATI = 90

# Le tre fasce si tagliano sulla **convenienza**: quanti punti di stagione
# rende in piu' (o in meno) di quello che quei crediti comprano nel suo stesso
# reparto. Fra le due soglie c'e' la fascia di mezzo, che e' la piu' popolata:
# il giocatore che non e' ne' un affare ne' una trappola, costa quello che
# vale, e serve quando gli obiettivi sono volati via.
SOGLIA_OCCASIONE = 1.0
SOGLIA_TRAPPOLA = 3.0

# Sotto questa cifra un giocatore non e' una trappola, e' un riempitivo: non ha
# senso metterlo fra quelli da evitare, perche' nessuno ci si rovina sopra.
PREZZO_TRAPPOLA = 5

# Sotto questa cifra non vale la pena far spendere nessuno: otto crediti bruciati
# a un avversario non cambiano la sua asta.
PREZZO_SVUOTO = 8

# Quanti avversari devono poter superare il tetto perche' spingere sia sicuro.
# Con uno solo, se quello passa la mano il giocatore e' tuo &mdash; e uno che
# passa la mano capita tutte le sere.
CONTENDENTI_MINIMI = 2

# I verdetti che non dicono di lasciar perdere. Non e' lo stesso insieme che
# decide chi entra nella fascia alta &mdash; quello e' piu' stretto e sta
# dentro `consiglio()` &mdash; ma quello che dice se un nome puo' comparire
# sotto "top acquisti" senza che la scheda lo smentisca.
VERDETTI_BUONI = ('OCCASIONE', 'PRENDILO', 'AL PREZZO GIUSTO',
                  'DA UN CREDITO', 'RIPIEGO')


def _arrotonda(x):
    return int(round(x))


def _nome_ruolo(ruolo):
    return {'P': 'portieri', 'D': 'difensori',
            'C': 'centrocampisti', 'A': 'attaccanti'}[ruolo]


def _nome_singolare(ruolo):
    """Il singolare di un ruolo, scritto e non calcolato.

    In tre punti si toglieva l'ultima lettera al plurale, e a schermo usciva
    "un portier", "un difensor", "un centrocampist". In italiano i plurali in
    -i tornano al singolare in modi diversi a seconda della parola, e sono
    quattro parole: si scrivono e basta.
    """
    return {'P': 'portiere', 'D': 'difensore',
            'C': 'centrocampista', 'A': 'attaccante'}[ruolo]


def _dei(n):
    """L'articolo giusto davanti al numero: otto e undici vogliono `degli`."""
    return 'degli' if n in (8, 11) else 'dei'


class Consigliere(object):
    """Traduce motore e ottimizzatore in decisioni. Non tocca il database."""

    def __init__(self, valutatore, ottimizzatore):
        self.v = valutatore
        self.o = ottimizzatore
        self.stato = valutatore.stato
        self.reg = valutatore.reg

    def aggiorna(self):
        self.v.aggiorna()
        self.o.aggiorna()

    # ------------------------------------------------------------- contesto
    def fase(self):
        """Il ruolo che si sta chiamando: si va per reparti, dai portieri.

        Finche' non tutti hanno i 3 portieri si chiamano portieri.
        """
        for r in RUOLI:
            if self.stato.slot_residui_ruolo(r) > 0:
                return r
        return None

    def pressione(self):
        """Quanto sono ricco rispetto agli avversari, a parita' di slot.

        > 1: ho piu' potere d'acquisto della media, posso permettermi di
        prendere. < 1: sono indietro, mi conviene far spendere loro.
        """
        io = self.o.io
        miei_slot = max(1, self.stato.slot_residui(io))
        mio = self.stato.crediti(io) / float(miei_slot)
        altri = []
        for p in self.stato.presidenti():
            if p['io']:
                continue
            s = self.stato.slot_residui(p['id'])
            if s > 0:
                altri.append(p['crediti'] / float(s))
        if not altri:
            return 1.0
        media = sum(altri) / len(altri)
        return mio / media if media else 1.0

    # ------------------------------------------------- il verdetto, una volta
    #
    # Tutto quello che l'interfaccia mostra su un giocatore passa di qui:
    # la scheda che si apre quando viene chiamato e le liste dei consigli.
    # Calcolarlo in due posti diversi vuol dire, prima o poi, mostrare un
    # giocatore sotto il titolo "da prendere" e poi dirgli "lascia" quando
    # lo si apre. E' successo, ed e' il motivo per cui adesso la funzione
    # e' una sola.
    def decisione(self, giocatore):
        v, o, stato = self.v, self.o, self.stato
        x = giocatore
        # Prima quanto costera', poi quanto vale: cosi' il motore puo' dire
        # anche di quanto migliorerebbe la rosa pagandolo quel che costa, che
        # e' l'unica misura di utilita' con cui abbia senso ordinare i consigli.
        chiusura = _arrotonda(v.prezzo_chiusura(x))
        limite, dett = o.max_bid(x, prezzo=chiusura)
        concorrenti = v.concorrenti(x)
        serve = o.serve.get(x.ruolo, 0)

        # Il prezzo da offrire non e' il limite: al limite non guadagno niente.
        # E' quanto basta per portarlo via.
        consigliato = min(limite, max(1, chiusura)) if limite else 0
        conv = o.convenienza(x, chiusura)
        verdetto, colore, frase = self._verdetto(
            x, limite, chiusura, consigliato, serve, dett, concorrenti, conv)
        if verdetto == 'DA UN CREDITO':
            # Il limite resta zero nel calcolo, ma allo schermo dev'essere 1:
            # lo slot va riempito, e a un credito questo vale quanto un altro.
            limite = consigliato = 1
        return {
            'id': x.id, 'nome': x.nome, 'squadra': x.squadra, 'ruolo': x.ruolo,
            'max_bid': limite, 'consigliato': consigliato, 'chiusura': chiusura,
            'margine': limite - chiusura,
            'verdetto': verdetto, 'colore': colore, 'frase': frase,
            'serve_nel_ruolo': serve,
            'concorrenti': concorrenti,
            'contributo_modificatore': _arrotonda(dett['contributo_modificatore']),
            'guadagno': _arrotonda(dett['guadagno']),
            'utilita': _arrotonda(dett.get('guadagno_al_prezzo', 0.0)),
            # Quanto rende, e quanto rende **in piu' di quello che costa**.
            # Il primo numero mette in fila i consigli, il secondo decide in
            # quale delle tre fasce finisce: sono due domande diverse e vanno
            # tenute separate, altrimenti il portiere da sei crediti scavalca
            # quello da quaranta solo perche' costa poco.
            'resa': round(o.resa(x), 1),
            'convenienza': round(conv, 1),
            'motivo': dett['motivo'],
            'mercato': _arrotonda(x.prezzo_mercato or 1),
            'costo_atteso': _arrotonda(x.prezzo_atteso or x.prezzo_mercato or 1),
            'fantamedia': round(x.fm, 2),
            'presenze': _arrotonda(x.presenze),
            'gerarchia': self.gerarchia(x),
            'chiude_coppia': self._chiude_coppia(x),
        }

    # ------------------------------------------------------- chi gioca davvero
    @staticmethod
    def gerarchia(x):
        """Il posto in gerarchia, pronto da mostrare.

        E' l'informazione che manca a chi guarda solo la fantamedia, ed e'
        quella che separa un'alternativa vera da una trappola: sei e novanta
        di media su otto partite non valgono niente.
        """
        quota = x.titolarita
        if quota is None:
            return {'grado': 'ignoto', 'etichetta': 'Da verificare',
                    'quota': None, 'certezza': 0.0, 'sicuro': False,
                    'posto': None, 'in_reparto': None, 'nuovo': bool(x.nuovo),
                    'rigorista': int(x.rigorista or 0),
                    'testo': 'Non ho abbastanza dati per dire quanto giochera\'.'}
        partite = int(round(quota * 38))
        if x.grado == 'titolare':
            posto = x.posto_reparto or 1
            quanti = x.in_reparto or 1
            reparto = '%s %d %s' % (_dei(quanti), quanti, _nome_ruolo(x.ruolo))
            dove = ('il piu\' impiegato %s a listone della sua squadra' % reparto
                    if posto == 1 else
                    'il %d%s per impiego %s della sua squadra'
                    % (posto, '°', reparto))
            testo = 'Titolare: %d presenze attese, %s.' % (partite, dove)
        elif x.grado == 'ballottaggio':
            testo = ('In ballottaggio: le presenze attese sono %d su 38, non e\' '
                     'un posto garantito.' % partite)
        elif x.grado == 'rotazione':
            testo = ('Gioca a rotazione: circa %d partite. La fantamedia vale '
                     'quello che vale su cosi\' poche presenze.' % partite)
        else:
            testo = ('Riserva: %d presenze attese. Qualunque sia la sua '
                     'fantamedia, in campo lo vedi poco.' % partite)
        if x.nuovo:
            testo += ' E\' arrivato quest\'anno: lo storico dice poco.'
        return {'grado': x.grado, 'etichetta': x.etichetta_grado,
                'quota': round(quota, 2), 'certezza': round(x.certezza or 0, 2),
                'sicuro': bool(x.sicuro), 'posto': x.posto_reparto,
                'in_reparto': x.in_reparto, 'nuovo': bool(x.nuovo),
                'rigorista': int(x.rigorista or 0), 'testo': testo}

    # ---------------------------------------------------------- scheda live
    def scheda(self, giocatore):
        """Tutto quello che serve sapere su un giocatore appena chiamato."""
        v, o, stato = self.v, self.o, self.stato
        x = giocatore
        io = stato.io()
        d = self.decisione(x)
        limite = d['max_bid']
        consigliato = d['consigliato']
        chiusura = d['chiusura']
        concorrenti = d['concorrenti']
        mercato = d['mercato']
        serve = d['serve_nel_ruolo']
        verdetto, colore, frase = d['verdetto'], d['colore'], d['frase']
        liquidita = stato.liquidita(io['id'])

        # Le alternative servono a una cosa sola: sapere su chi ripiegare se
        # questo va via caro. Percio' vengono prima i titolari sicuri. Proporre
        # una riserva con la media alta al posto di un big e' il modo piu'
        # rapido di rovinare una rosa, ed e' esattamente quello che succede
        # ordinando per punti e basta.
        candidati = [y for y in v.disponibili(x.ruolo, 20) if y.id != x.id]
        candidati.sort(key=lambda y: (0 if y.sicuro else 1, -(y.vor or 0)))
        alternative = []
        for y in candidati[:3]:
            lim_y, _ = o.max_bid(y)
            alternative.append({
                'id': y.id, 'nome': y.nome, 'squadra': y.squadra,
                'mercato': _arrotonda(y.prezzo_mercato or 1),
                'chiusura': _arrotonda(v.prezzo_chiusura(y)),
                'max_bid': lim_y,
                'gerarchia': self.gerarchia(y),
                'quota_punti': (round(100.0 * y.punti / x.punti)
                                if x.punti and x.punti > 0 else None),
            })

        return {
            'id': x.id, 'nome': x.nome, 'squadra': x.squadra, 'ruolo': x.ruolo,
            'qi': x.qi, 'mv': round(x.mv, 2), 'fantamedia': round(x.fm, 2),
            'presenze': _arrotonda(x.presenze), 'punti': _arrotonda(x.punti),
            'metodo': x.metodo, 'affidabilita': round(x.affidabilita, 2),
            'mercato': mercato,
            'costo_atteso': d['costo_atteso'],
            'gerarchia': d['gerarchia'],
            'utilita': d['utilita'],
            'chiude_coppia': d['chiude_coppia'],
            'riferimento': _arrotonda(x.prezzo_riferimento or 0),
            'max_bid': limite,
            'consigliato': consigliato,
            'chiusura': chiusura,
            'margine': limite - chiusura if limite else None,
            'liquidita': liquidita,
            'serve_nel_ruolo': serve,
            'contributo_modificatore': d['contributo_modificatore'],
            'divergenza': self._divergenza(x),
            'stessa_squadra': self._stessa_squadra(x),
            'pacchetto': self._pacchetto(x),
            'compagni_di_maglia': self._compagni(x),
            'riserva_ruolo': self.o.riserva.get(x.ruolo, 0),
            'guadagno': d['guadagno'],
            'motivo': d['motivo'],
            'verdetto': verdetto, 'colore': colore, 'frase': frase,
            'concorrenti': concorrenti,
            'alternative': alternative,
        }

    def _chiude_coppia(self, x):
        """Se comprarlo chiude una maglia che ho gia' meta' in rosa, dillo.

        E' la parte del prezzo massimo che non si vede guardando solo lui: il
        limite e' piu' alto perche' possiedo gia' il suo socio, e senza questa
        frase sembrerebbe un errore invece che il motivo per cui vale la pena
        spingersi oltre quello che varrebbe da solo.
        """
        bonus = self.o.coppia_bonus.get(x.id, 0.0)
        if bonus <= 0:
            return None
        miei = set(y.id for r in RUOLI for y in self.o.mia_rosa[r])
        for c in self.v.compagni_di_maglia(x.id):
            if c['altro'] in miei:
                altro = self.v.g.get(c['altro'])
                if altro is not None:
                    return {'con': altro.nome,
                            'copertura': round(c['copertura'], 2),
                            'copertura_buchi': round(c['copertura_buchi'], 2),
                            'buchi': round(c['buchi'], 1),
                            'punti_extra': _arrotonda(bonus)}
        return None

    def _stessa_squadra(self, x):
        """Quanti ne ho gia' della sua stessa squadra di serie A.

        Non e' un difetto in se': e' varianza. Quattro giocatori della stessa
        squadra fanno una giornata memorabile quando quella squadra gira e una
        disastrosa quando si inceppa, e le due cose si compensano solo sulla
        stagione. Va detto prima di comprare il quinto, non dopo.
        """
        io = self.stato.io()['id']
        n = 0
        for a in self.stato.acquisti():
            if a['presidente_id'] == io and a['squadra'] == x.squadra:
                n += 1
        return n

    def _compagni(self, x):
        """Chi si divide la maglia con lui: comprarli insieme copre la stagione.

        E' l'informazione che nessun listone scrive da solo: quando uno dei
        due non gioca, gioca l'altro. Il secondo costa una frazione del primo
        perche' il mercato paga chi e' sicuro, non chi e' complementare — ed
        e' esattamente il divario in cui si trova l'affare.
        """
        proprietario = {}
        for a in self.stato.acquisti():
            proprietario[a['giocatore_id']] = a['presidente_id']
        io_id = self.stato.io()['id']
        nomi = dict((p['id'], p['nome']) for p in self.stato.presidenti())

        out = []
        for c in self.v.compagni_di_maglia(x.id):
            y = self.v.g.get(c['altro'])
            if y is None:
                continue
            presidente = proprietario.get(y.id)
            stato_y = ('mio' if presidente == io_id
                      else 'avversario' if presidente is not None else 'libero')
            voce = {
                'id': y.id, 'nome': y.nome, 'squadra': y.squadra,
                'tipo': c['tipo'], 'copertura': round(c['copertura'], 2),
                'copertura_buchi': round(c['copertura_buchi'], 2),
                'buchi': round(c['buchi'], 1),
                'buchi_coperti': round(c['buchi_coperti'], 1),
                'giornate_coperte': round(c['giornate_coperte'], 1),
                'presenze': _arrotonda(y.presenze), 'fantamedia': round(y.fm, 2),
                'nota': c['nota'] or None, 'stato': stato_y,
            }
            if stato_y == 'libero':
                voce['mercato'] = _arrotonda(y.prezzo_atteso or y.prezzo_mercato or 1)
                voce['max_bid'] = self.o.max_bid(y)[0]
            elif stato_y == 'avversario':
                voce['presidente'] = nomi.get(presidente, '?')
            out.append(voce)
        out.sort(key=lambda d: -d['copertura_buchi'])
        return out

    def _pacchetto(self, x):
        """Le riserve che arrivano insieme al portiere titolare.

        Chiudono il reparto in un colpo solo: e' l'informazione che cambia il
        senso della cifra a schermo, perche' quel prezzo non compra un
        giocatore ma tutti e tre gli slot da portiere.
        """
        venduti = self.stato.venduti()
        out = []
        for rid in self.v.riserve_di(x.id):
            if rid in venduti:
                continue
            y = self.v.g.get(rid)
            if y is not None:
                out.append({'id': y.id, 'nome': y.nome, 'squadra': y.squadra,
                            'mv': round(y.mv, 2)})
        return out

    def _divergenza(self, x):
        """Avvisa quando il modello e il mercato reale non si somigliano.

        Il prezzo storico d'asta sa cose che il database non contiene: chi ha
        perso il posto da titolare, chi e' appena rientrato da un infortunio
        lungo. Quando i due numeri divergono molto, e' il modello a dover
        essere guardato con sospetto, non il mercato.
        """
        rif = x.prezzo_riferimento or 0.0
        mio = x.prezzo_mercato or 1.0
        if rif < 3 and mio < 15:
            return None
        scala = (float(self.v.pool_discrezionale) / self.v._pool_iniziale
                 if getattr(self.v, '_pool_iniziale', 0) else 1.0)
        atteso = rif * scala
        if atteso <= 0:
            return {'verso': 'ignoto',
                    'testo': "Nessun prezzo d'asta storico per questo giocatore."}
        rapporto = mio / max(1.0, atteso)
        if rapporto >= 2.0:
            return {'verso': 'sopra', 'rapporto': round(rapporto, 1),
                    'testo': ("Il mio modello lo valuta %.1f volte quello che si "
                              "e' pagato in asta negli anni scorsi (%d crediti). "
                              "Se sai che ha perso il posto, fidati del mercato."
                              % (rapporto, _arrotonda(atteso)))}
        if rapporto <= 0.5:
            return {'verso': 'sotto', 'rapporto': round(rapporto, 1),
                    'testo': ("In asta si e' sempre pagato molto di piu' (%d "
                              "crediti): la stanza potrebbe spingersi oltre il "
                              "tuo limite." % _arrotonda(atteso))}
        return None

    def _meglio_di(self, x):
        """Chi occuperebbe quello slot al posto suo, secondo il piano di spesa.

        Quando il prezzo massimo scende a zero non e' perche' il giocatore sia
        scarso: e' perche' quello slot, con quei crediti, rende di piu' su
        qualcun altro. Dirlo per nome cambia una bocciatura in un'indicazione.
        """
        try:
            obiettivi = self.o.piano()['per_ruolo'].get(x.ruolo, {}).get('obiettivi', [])
        except Exception:
            return ''
        nomi = ['%s (~%d)' % (t['nome'], t['costo'])
                for t in obiettivi if t['id'] != x.id][:2]
        if not nomi:
            return ''
        return ' o '.join(nomi) if len(nomi) == 2 else nomi[0]

    def _verdetto(self, x, limite, chiusura, consigliato, serve, dett,
                  concorrenti, convenienza=0.0):
        """Una riga sola, quella che si legge in tre secondi mentre rilanciano.

        Il verdetto e' uno solo per tutto il programma: quello che si legge
        nella lista dei consigli e quello che si legge aprendo la scheda sono
        la stessa frase, calcolata qui una volta.

        `RIPIEGO` esiste per una ragione precisa. Il prezzo massimo confronta il
        giocatore con il piano del motore, e in un reparto da uno slot solo il
        piano ha un vincitore unico: chiunque altro finisce a "lascia", anche
        un portiere che al prezzo suo e' un ottimo acquisto. Dirgli "lascia"
        sarebbe falso &mdash; e' quello che si compra se il primo vola via
        &mdash; e dirgli "prendilo" pure. `RIPIEGO` e' il verdetto giusto per
        quel caso, e senza di esso la lista e la scheda smettono di dire la
        stessa cosa.
        """
        # Prima di tutto il resto: se non e\' iscritto alla lista di serie A
        # non c\'e\' niente da valutare. Senza questo ramo il verdetto usciva
        # RIPIEGO - *e\' chi prendere se i tuoi obiettivi volano via* - su uno
        # che non puo\' giocare nemmeno una partita.
        if getattr(x, 'fuori_lista', False):
            return ('FUORI LISTA', 'stop',
                    "Non e' iscritto alla lista di serie A: non puo' "
                    "scendere in campo. In rosa varrebbe come una casella "
                    "vuota.")
        if serve <= 0:
            return ('NON SERVE', 'stop',
                    'Reparto %s completo: non hai piu\' slot.' % x.ruolo)
        # Non e' il primo della lista, ma nemmeno una trappola: e' esattamente
        # il giocatore su cui ripiegare, e chiamarlo "lascia" sarebbe falso
        # quanto chiamarlo "prendilo". Sono i due terzi del reparto: il motore
        # ha una prima scelta per quello slot, ma se quella vola via questi
        # restano acquisti sensati e vanno detti tali.
        if ((limite <= 0 or limite < chiusura)
                and convenienza > -SOGLIA_TRAPPOLA and chiusura >= 1
                and not dett['motivo'].startswith(('gia\'', 'crediti finiti'))):
            coda = ('rende piu\' della media dei %s' % _nome_ruolo(x.ruolo)
                    if convenienza >= SOGLIA_OCCASIONE
                    else 'costa quello che vale')
            return ('RIPIEGO', 'attenzione',
                    'Non e\' la prima scelta del motore per questo slot, ma a '
                    '%d crediti %s: e\' chi prendere se i tuoi obiettivi volano '
                    'via.' % (chiusura, coda))
        if limite <= 0:
            if dett['motivo'].startswith('gia\''):
                return ('GIA\' VENDUTO', 'stop',
                        'Questo giocatore e\' gia\' stato assegnato.')
            if dett['motivo'].startswith('crediti finiti'):
                return ('NON PUOI', 'stop',
                        'Devi tenere 1 credito per ognuno dei %d slot scoperti.'
                        % self.stato.slot_residui(self.o.io))
            # A fondo listone il limite scende a zero anche quando la perdita
            # e' irrisoria: tutti costano un credito e si equivalgono. Dire
            # "lascia" li' sarebbe un falso allarme, lo slot va comunque riempito.
            if abs(dett.get('guadagno', 0.0)) < 4 and chiusura <= 2:
                return ('DA UN CREDITO', 'attenzione',
                        'Vale quanto i tanti altri da un credito. Prendilo pure '
                        'per riempire lo slot, ma non salirci.')
            # "C'e' di meglio" da solo non aiuta: va detto chi.
            meglio = self._meglio_di(x)
            if meglio:
                return ('LASCIA', 'stop',
                        'Con quegli stessi crediti il motore preferisce %s.' % meglio)
            return ('LASCIA', 'stop',
                    'Con gli stessi crediti c\'e\' di meglio in questo ruolo.')
        if limite < chiusura:
            return ('LASCIA', 'stop',
                    'Chiudera\' sui %d e per la tua rosa ne vale al massimo %d.'
                    % (chiusura, limite))
        margine = limite - chiusura
        if not concorrenti:
            return ('PRENDILO', 'ottimo',
                    'Nessun avversario puo\' rilanciare: e\' tuo a un credito.')
        if margine >= max(3, MARGINE_MINIMO * max(1, chiusura)):
            return ('OCCASIONE', 'ottimo',
                    'Vale %d per la tua rosa e dovrebbe chiudere sui %d: '
                    'hai %d crediti di margine.' % (limite, chiusura, margine))
        return ('AL PREZZO GIUSTO', 'attenzione',
                'Prendilo solo entro %d: sopra stai pagando piu\' di quanto '
                'renda alla tua rosa.' % limite)

    # ------------------------------------------------------ chi chiamare
    def consiglio(self, quanti=12):
        """Chi conviene chiamare adesso, e perche'.

        **Una classifica sola, e mai un vincitore unico.** La versione
        precedente mostrava solo chi passava il vaglio del prezzo massimo, e
        con i portieri a pacchetto quel vaglio lo passa una persona sola: lo
        slot da portiere e' uno, il motore elegge il migliore, e chiunque altro
        risulta "peggio del piano" perche' occuperebbe il posto dell'eletto.
        A schermo restava un nome solo &mdash; e siccome i primi cinque
        portieri distano fra loro due o tre punti su duecento, bastava un
        acquisto altrui a far cambiare quel nome. Sembrava un capriccio del
        programma; era una volata decisa per un centimetro, raccontata come se
        ci fosse un solo corridore.

        Adesso il reparto si mostra intero, in fila per **utilita'**: quanti
        punti di stagione guadagna la rosa comprandolo al prezzo a cui andra'
        via. E' un numero confrontabile fra tutti, positivo o negativo, e
        vederlo accanto a ogni nome e' quello che permette di accorgersi che il
        secondo vale due punti meno del primo e ne costa quindici in meno.

        Tre fasce, piu' due liste che rispondono ad altre domande:

          **top**          l'acquisto migliora la rosa: sono le occasioni
          **evitare**      costa molto e rende meno di quello che avresti
          **alternative**  ne' affare ne' trappola: il piano B alla portata
          **svuotare**     non lo voglio, ma far pagare lui e' far pagare loro
          **coppie**       chi completa una maglia che ho gia' meta' in rosa
        """
        ruolo = self.fase()
        if ruolo is None:
            return {'fase': None, 'top': [], 'evitare': [], 'alternative': [],
                    'svuotare': [], 'coppie': self._coppie_aperte(),
                    'prendere': [], 'ripiego': [], 'pressione': 1.0,
                    'indicazione': 'Asta finita.'}

        v, o, stato = self.v, self.o, self.stato
        io = stato.io()['id']
        serve = o.serve.get(ruolo, 0)
        pressione = self.pressione()
        liquidita = stato.liquidita(io)

        # Il verdetto e' quello che uscira' aprendo la scheda: le liste non
        # decidono niente per conto loro, si limitano a raggruppare. Cosi' un
        # giocatore non puo' finire sotto "da prendere" e poi dire "lascia".
        # Solo i verdetti che dicono "compralo adesso". `RIPIEGO` non entra:
        # e' il verdetto della fascia di mezzo, e se lo si contasse qui
        # finirebbero tutti fra i consigliati e le tre fasce tornerebbero una.
        VALE = ('OCCASIONE', 'PRENDILO', 'AL PREZZO GIUSTO')
        top, evitare, neutri, svuotare = [], [], [], []
        # Quanti avversari possono ancora contendere un giocatore di questo
        # reparto. A zero cambia il senso di meta' delle risposte: non c'e'
        # piu' niente da far pagare a nessuno e niente puo' essere una
        # trappola, perche' qualunque nome lo paghi un credito.
        conc_max = 0
        for x in v.disponibili(ruolo, QUANTI_VALUTATI):
            d = self.decisione(x)
            conc = d.pop('concorrenti')
            d['concorrenti'] = len(conc)
            conc_max = max(conc_max, len(conc))
            d['divergenza'] = self._divergenza(x)
            d['perche'] = d['frase']
            margine = d['margine']
            utilita = d['utilita']
            # In fila per **utilita'**, non per convenienza: quanto migliora la
            # rosa comprandolo al prezzo a cui andra' via. Ordinare per margine
            # metterebbe in cima l'affare da tre crediti e in fondo il
            # giocatore che cambia la squadra, che e' esattamente il rovescio
            # di quello che serve sapere quando tocca chiamare.
            d['punteggio'] = utilita + 0.25 * max(0, margine)

            conv = d['convenienza']
            if (d['verdetto'] in VALE
                    or (conv >= SOGLIA_OCCASIONE and d['resa'] > 0)):
                soglia = max(1, MARGINE_MINIMO * max(1, d['chiusura']))
                d['categoria'] = 'occasione' if margine >= soglia else 'giusto'
                top.append(dict(d))
            elif conv <= -SOGLIA_TRAPPOLA and d['chiusura'] >= PREZZO_TRAPPOLA:
                d['categoria'] = 'evitare'
                d['perche'] = self._perche_evitare(x, d)
                evitare.append(dict(d))
            else:
                # Non e' un affare, ma nemmeno un errore: costa quello che
                # vale. E' il giocatore che si prende quando gli obiettivi sono
                # volati via e lo slot va comunque riempito.
                d['categoria'] = 'alternativa'
                neutri.append(dict(d))

            # Non lo voglio a quel prezzo. Se pero' costa caro e ci sono
            # avversari che se lo contenderanno, chiamarlo brucia i loro
            # crediti prima che tocchi ai miei obiettivi.
            if d['categoria'] not in ('occasione', 'giusto'):
                e = self._svuota(x, d, conc, liquidita)
                if e is not None:
                    svuotare.append(e)

        # Dentro la fascia l'ordine e' per **utilita'**, cioe' per quanto
        # sposta la rosa, non per convenienza: la convenienza dice se merita di
        # stare in quella fascia, ma se devo scegliere un portiere solo voglio
        # in cima quello che mi fa fare piu' punti, non quello che costa meno.
        top.sort(key=lambda d: (-d['punteggio'], -d['convenienza'], d['id']))
        svuotare.sort(key=lambda d: (-d['punteggio'], d['id']))
        # Da evitare in ordine di pericolo, non di bruttezza: la trappola vera
        # e' quella su cui la stanza spendera' davvero. Chi perde venti punti
        # ma chiude a due crediti non ha mai rovinato un'asta a nessuno.
        evitare.sort(key=lambda d: (d['convenienza'] - 0.15 * d['chiusura'],
                                    d['id']))

        # Chi sta fra i consigliati non puo' anche essere uno da far pagare
        # agli altri: sono due indicazioni opposte sullo stesso nome, e a
        # schermo diventerebbero un invito a chiamarlo per poi non prenderlo.
        in_top = set(d['id'] for d in top[:quanti])
        svuotare = [d for d in svuotare if d['id'] not in in_top]

        # Il primo della fascia e' il metro di paragone di tutti gli altri:
        # dire "e' il secondo, rende tre punti meno del primo ma ne costa
        # quindici in meno" e' l'unica frase che rende utile una classifica.
        # Senza, ogni riga dalla seconda in giu' ripete "il motore preferisce
        # Vicario", che e' vero e non serve a niente.
        for posto, d in enumerate(top[:quanti], start=1):
            d['posto_fascia'] = posto
            if posto > 1:
                d['perche'] = self._confronto(d, top[0])

        # Fra i "gia' visti" vanno anche quelli da evitare: `_alternative`
        # ripesca dal fondo del listone quando le alternative vere sono poche,
        # e da li' rientrava chi era gia' stato classificato trappola.
        in_alto = in_top | set(d['id'] for d in evitare)
        alternative = self._alternative(ruolo, serve, neutri, in_alto)
        # Stessa ragione della riga sopra su `in_top`, e mancava: un giocatore
        # che sta fra le alternative e' uno che **potresti prendere**, e
        # spingerne il prezzo per far spendere gli altri e' l'indicazione
        # opposta. Sullo schermo comparivano tutte e due, sullo stesso nome.
        in_alt = set(d['id'] for d in alternative)
        svuotare = [d for d in svuotare if d['id'] not in in_alt]
        _, scarsita = self._ripiego(ruolo, serve)

        # **Una lista vuota non e' una risposta.** Puo' succedere, ed e'
        # perfino corretto nel merito: se il piano destina cinque crediti agli
        # ultimi due difensori perche' il resto rende di piu' in attacco,
        # nessun difensore supera la soglia dell'occasione. Ma chi sta facendo
        # l'asta quei due slot deve riempirli lo stesso, e trovarsi la sezione
        # dei consigli vuota vuol dire non sapere chi chiamare &mdash; che e'
        # esattamente il momento in cui si compra a caso.
        #
        # Percio' quando la fascia alta resta vuota si promuovono i primi della
        # fascia di mezzo, dicendo chiaro perche' sono li': non sono affari,
        # sono i migliori dentro i crediti che il piano assegna a quel reparto.
        obbligati = 0
        if not top and serve > 0 and alternative:
            quanti_min = min(len(alternative), max(3, serve))
            budget = self._budget_ruolo(ruolo)
            for d in alternative[:quanti_min]:
                if d.get('verdetto') not in VERDETTI_BUONI:
                    # Meglio una lista corta che una lista che si contraddice.
                    continue
                e = dict(d)
                e['categoria'] = 'obbligato'
                e['perche'] = (
                    "Nessuno in questo reparto e' un affare ai prezzi di "
                    "adesso, ma %d slot vanno riempiti e il piano ci destina "
                    "%d crediti: fra quelli alla portata, questo e' il "
                    "migliore che gioca. %s, %d presenze attese."
                    % (serve, budget,
                       (d.get('gerarchia') or {}).get('etichetta') or 'Da verificare',
                       d['presenze']))
                top.append(e)
            # Si tolgono dalle alternative **quelli promossi davvero**, non i
            # primi `quanti_min`: da quando la promozione salta chi ha un
            # verdetto che dice di lasciare, i due insiemi non coincidono piu'
            # e lo stesso nome finiva in tutt'e due le sezioni.
            promossi = set(d['id'] for d in top)
            obbligati = len(promossi)
            alternative = [d for d in alternative if d['id'] not in promossi]

        # Chi chiude una coppia sta in un riquadro suo, in cima a tutto, e
        # non dentro le tre fasce: e' un'informazione che vale a prescindere da
        # quanto quel giocatore renda da solo &mdash; anzi, di solito rende
        # poco proprio perche' e' il secondo &mdash; e infilarla in mezzo a una
        # classifica ordinata per resa sarebbe il modo migliore di non vederla
        # mai. Quel riquadro e' il posto fisso, e ci resta finche' la coppia
        # non e' chiusa o il socio non se lo prende qualcun altro.
        coppie = self._coppie_aperte()
        in_coppia = set(c['id'] for c in coppie)
        top = [d for d in top if d['id'] not in in_coppia]
        evitare = [d for d in evitare if d['id'] not in in_coppia]
        alternative = [d for d in alternative if d['id'] not in in_coppia]
        svuotare = [d for d in svuotare if d['id'] not in in_coppia]

        # **Ultimo controllo, sulle liste come escono davvero.** Sopra ci sono
        # gia' tre deduplicazioni, ognuna al punto giusto del ragionamento, e
        # ognuna guarda le liste com'erano in quel momento: chi entra dopo, o
        # per una strada che quel punto non copre, passa. Le vie sono tante
        # abbastanza che inseguirle una per una e' come tapparle una per volta
        # e sperare. Qui invece si guarda il risultato, che e' l'unica cosa che
        # l'utente vede: un nome fra i consigliati non puo' comparire anche
        # fra le alternative o fra quelli da far pagare agli altri.
        # **Quanti nomi mostrare dipende da quanti te ne possono soffiare.**
        # Finche' c'e' qualcuno che puo' rilanciare serve profondita': i tuoi
        # primi obiettivi possono volare via, e la lista deve arrivare fino a
        # chi prenderesti allora. Quando invece non e' rimasto nessuno che
        # possa contenderteli, la profondita' non serve a niente: dodici righe
        # che dicono la stessa cosa &mdash; "rende 3 punti meno del primo e
        # costa uguale" &mdash; per un posto solo sono rumore, e spingono
        # fuori schermo tutto il resto. E' quello che succedeva comprati sette
        # pacchetti di portieri su otto.
        if conc_max < CONTENDENTI_MINIMI:
            quanti = max(3, min(quanti, 3 * max(1, serve)))
        fuori = top[:quanti]
        gia = set(d['id'] for d in fuori)
        alt = [d for d in alternative if d['id'] not in gia][:quanti]
        gia |= set(d['id'] for d in alt)
        svu = [d for d in svuotare if d['id'] not in gia][:max(4, quanti // 2)]

        return {
            'fase': ruolo,
            'serve': serve,
            'pressione': round(pressione, 2),
            'indicazione': self._indicazione(ruolo, serve, pressione,
                                             top, svu, obbligati,
                                             self._budget_ruolo(ruolo)),
            'top': fuori,
            'evitare': evitare[:quanti],
            'alternative': alt,
            'svuotare': svu,
            # Perche' una sezione e' vuota. Vuota senza spiegazione sembra che
            # il programma abbia smesso di rispondere; quasi sempre invece la
            # risposta e' "non c'e' niente da dire", e sapere **perche'** vale
            # quanto la lista.
            'vuoti': self._perche_vuoto(ruolo, top, evitare, alt, svu, conc_max),
            'coppie': coppie,
            'valutati': min(QUANTI_VALUTATI, len(v.disponibili(ruolo))),
            'liberi_nel_ruolo': len(v.disponibili(ruolo)),
            'scarsita': scarsita,
            'budget_ruolo': self._budget_ruolo(ruolo),
            # I nomi vecchi restano finche' non e' aggiornato tutto il resto.
            'prendere': top[:quanti],
            'ripiego': alternative[:quanti],
        }

    # ----------------------------------------------------------- le fasce
    def _perche_vuoto(self, ruolo, top, evitare, alternative, svuotare,
                      contendenti):
        """Perche' una sezione non ha niente da dire.

        Una lista vuota senza spiegazione si legge come un guasto: sembra che
        il programma abbia smesso di rispondere proprio quando serviva. Quasi
        sempre invece la risposta e' "non c'e' niente da segnalare", e allora
        la cosa utile e' dire **perche'** non c'e'.

        Il caso che l'ha resa necessaria: comprati sette pacchetti di portieri
        su otto, "da evitare" si svuota. Non e' un difetto &mdash; senza piu'
        avversari che possano rilanciare, nessun portiere puo' essere una
        trappola, perche' qualunque portiere costa un credito. Ma a schermo
        restava "Niente da segnalare in questo reparto", che non lo dice.
        """
        nome = _nome_ruolo(ruolo)
        uno = _nome_singolare(ruolo)
        soli = contendenti <= 0
        out = {}
        if not evitare:
            out['evitare'] = (
                'Nessuna trappola: non e\' rimasto nessun avversario che possa '
                'rilanciare su un %s, quindi qualunque nome di questa lista lo '
                'paghi un credito.' % uno
                if soli else
                'Nessuna trappola: ai prezzi di adesso i %s che restano costano '
                'tutti meno di quanto rendono, o costano cosi\' poco che '
                'sbagliare non fa danno.' % nome)
        if not alternative:
            out['alternative'] = (
                'Non servono: sopra ci sono gia\' tutti i %s che vale la pena '
                'considerare.' % nome
                if top else
                'Nessun %s rientra nella spesa media per slot che ti resta in '
                'questo reparto.' % uno)
        if not svuotare:
            out['svuotare'] = (
                'Nessuno da far pagare: gli avversari non hanno piu\' slot da '
                '%s liberi, quindi non c\'e\' nessuno a cui bruciare crediti.'
                % nome
                if soli else
                'Nessuno da far pagare: per farlo servono almeno due avversari '
                'che possano superare il tetto di sicurezza, e adesso non ci '
                'sono.')
        return out

    def _alternative(self, ruolo, serve, neutri, gia_visti):
        """Il piano B: chi posso prendere **tutti**, non uno solo svenandomi.

        E' la domanda che ci si fa a meta' asta: se questi quattro difensori
        volano oltre il mio limite, mi ritrovo ad andare sul listone a prendere
        gente a caso? La risposta deve essere pronta prima che serva.

        Vengono prima i titolari veri. Un ripiego serve quando bisogna riempire
        uno slot in fretta; se in quel momento il programma propone una
        fantamedia alta prodotta da otto presenze, il danno lo fa lui, non
        l'asta.
        """
        if serve <= 0:
            return []
        budget = max(self._budget_ruolo(ruolo), serve)
        per_slot = budget / float(max(1, serve))
        # Fino a una volta e mezzo la spesa media per slot: sopra, prendendolo,
        # si sbilancia il reparto e gli altri slot restano scoperti.
        tetto = max(2.0, per_slot * 1.5)

        def gioca(d):
            g = d.get('gerarchia') or {}
            return (g.get('grado') == 'titolare'
                    and (g.get('certezza') or 0) >= CERTEZZA_RIPIEGO)

        out = [d for d in neutri
               if d['id'] not in gia_visti and d['chiusura'] <= tetto
               and d['resa'] > 0]
        out.sort(key=lambda d: (0 if gioca(d) else 1, -d['punteggio'], d['id']))
        for d in out:
            g = d.get('gerarchia') or {}
            d['perche'] = ('%s, %d presenze attese e %.2f di fantamedia: a %d '
                           'crediti costa quello che vale.'
                           % (g.get('etichetta') or 'Da verificare',
                              d['presenze'], d['fantamedia'],
                              max(1, d['chiusura'])))

        # Il fondo del listone non passa dalla valutazione completa: se le
        # alternative vere sono poche, si pesca li' con la vecchia regola.
        if len(out) < 6:
            visti = set(gia_visti) | set(d['id'] for d in out)
            extra, _ = self._ripiego(ruolo, serve, visti)
            for d in extra:
                d['categoria'] = 'alternativa'
                d['perche'] = d.get('frase', '')
                d.setdefault('punteggio', d.get('utilita', 0))
                out.append(d)
        return out

    @staticmethod
    def _confronto(d, primo):
        """Come sta questo rispetto al migliore della fascia, in una riga."""
        dp = round(d['resa'] - primo['resa'])
        dc = d['chiusura'] - primo['chiusura']
        chi = primo['nome']
        if dc < 0 and dp < 0:
            return ("Rende %d punti meno di %s, ma ne costa %d in meno: e' il "
                    "ripiego se %s vola oltre il tuo limite."
                    % (-dp, chi, -dc, chi))
        if dc < 0:
            return ("Costa %d crediti meno di %s e rende quanto lui: a parita' "
                    "di reparto e' l'affare piu' grosso della lista." % (-dc, chi))
        if dp < 0:
            return ("Rende %d punti meno di %s e costa %d crediti in piu': ha "
                    "senso solo se %s va via prima." % (-dp, chi, dc, chi))
        return ("Rende %d punti piu' di %s ma ne costa %d in piu'."
                % (dp, chi, dc))

    def _perche_evitare(self, x, d):
        """Perche' quel giocatore e' una trappola, in una riga."""
        g = d.get('gerarchia') or {}
        if g.get('grado') in ('riserva', 'rotazione'):
            return ('Chiudera\' sui %d crediti per %d presenze attese: la '
                    'fantamedia la fa quando gioca, e gioca poco.'
                    % (d['chiusura'], d['presenze']))
        if g.get('grado') == 'ballottaggio':
            return ('Chiudera\' sui %d crediti e il posto non e\' suo: sono '
                    '%d presenze attese su 38.' % (d['chiusura'], d['presenze']))
        meglio = self._meglio_di(x)
        if meglio:
            return ('A %d crediti rende %d punti meno di quello che quei '
                    'crediti comprano fra i %s: il motore prende %s.'
                    % (d['chiusura'], round(-d['convenienza']),
                       _nome_ruolo(x.ruolo), meglio))
        return ('A %d crediti rende %d punti di stagione meno di quello che '
                'quei crediti comprano fra i %s.'
                % (d['chiusura'], round(-d['convenienza']), _nome_ruolo(x.ruolo)))

    # ------------------------------------------- coppie gia' meta' in rosa
    def _coppie_aperte(self):
        """Le maglie di cui possiedo gia' meta': l'altra meta' va comprata.

        E' il momento in cui il vantaggio e' piu' grande, perche' il mercato
        paga chi e' sicuro e non chi e' complementare. Se ho comprato uno dei
        due che si giocano il posto, il secondo mi copre le giornate in cui il
        primo non gioca e costa una frazione &mdash; ma solo se me lo ricordo
        prima che se lo prenda qualcun altro. Per questo sta in cima, e non
        dentro una classifica dove potrebbe cadere decimo.
        """
        v, o = self.v, self.o
        miei = set(y.id for r in RUOLI for y in o.mia_rosa[r])
        if not miei:
            return []
        venduti = self.stato.venduti()
        out, visti = [], set()
        for mio_id in sorted(miei):
            mio = v.g.get(mio_id)
            if mio is None:
                continue
            for c in v.compagni_di_maglia(mio_id):
                altro = v.g.get(c['altro'])
                if altro is None or altro.id in visti or altro.id in venduti:
                    continue
                visti.add(altro.id)
                d = self.decisione(altro)
                d.pop('concorrenti', None)
                scoperte = c['buchi']
                coperte = c['buchi_coperti']
                quota = round(100 * c['copertura_buchi'])
                ruolo_suo = ('Si gioca il posto con' if c['tipo'] == 'ballottaggio'
                             else 'E\' il vice di')
                testo = ('%s %s, che hai gia\' in rosa. %s salta circa %d '
                         'giornate, e lui ne copre %d: e\' il %d%% dei suoi '
                         'buchi. Il mercato paga chi e\' sicuro, non chi e\' '
                         'complementare, ed e\' li\' che sta l\'affare.'
                         % (ruolo_suo, mio.nome, mio.nome, round(scoperte),
                            round(coperte), quota))
                out.append({
                    'id': altro.id, 'nome': altro.nome, 'squadra': altro.squadra,
                    'ruolo': altro.ruolo, 'tipo': c['tipo'],
                    'con': mio.nome, 'con_id': mio.id,
                    'copertura': round(c['copertura'], 2),
                    'copertura_buchi': round(c['copertura_buchi'], 2),
                    'buchi': round(scoperte, 1),
                    'giornate_coperte': round(coperte, 1),
                    'chiusura': d['chiusura'], 'max_bid': d['max_bid'],
                    'utilita': d['utilita'], 'verdetto': d['verdetto'],
                    'gerarchia': d['gerarchia'],
                    'slot_liberi': o.serve.get(altro.ruolo, 0),
                    'perche': testo,
                    'decisione': d,
                })
        # L'id chiude anche qui: due soci che coprono la stessa quota e
        # rendono uguale devono comparire sempre nello stesso ordine.
        out.sort(key=lambda d: (-d['copertura_buchi'], -d['utilita'], d['id']))
        return out

    # ------------------------------------------------------ il piano B
    def _budget_ruolo(self, ruolo):
        """Quanti crediti miei sono destinati a questo reparto, adesso."""
        try:
            d = self.o.piano()['per_ruolo'].get(ruolo) or {}
            return int(d.get('crediti', 0))
        except Exception:
            return 0

    def _ripiego(self, ruolo, serve, gia_visti=()):
        """Su chi ripiegare se gli obiettivi vanno via troppo cari.

        E' la domanda che ci si fa a meta' asta: se questi quattro difensori
        volano oltre il mio limite, mi ritrovo ad andare sul listone a prendere
        gente a caso? La risposta deve essere pronta prima che serva.

        Il ripiego non e' "i prossimi della lista": e' chi rientra nella spesa
        media per slot che mi resta in quel reparto. Sono i giocatori che posso
        prendere **tutti**, non uno solo svenandomi.
        """
        if serve <= 0:
            return [], None
        v, o, stato = self.v, self.o, self.stato
        liberi = v.disponibili(ruolo)
        budget = max(self._budget_ruolo(ruolo), serve)
        per_slot = budget / float(max(1, serve))
        # Fino a una volta e mezzo la spesa media: sopra, prendendolo, si
        # sbilancia il reparto e gli altri slot restano scoperti.
        tetto = max(2.0, per_slot * 1.5)

        # Ordinati per resa attesa, non per prezzo: il ripiego serve a sapere
        # chi vale di piu' fra quelli che restano alla portata, non a rifare
        # la stessa classifica di sopra.
        #
        # E soprattutto: **solo chi gioca**. Un ripiego serve quando gli
        # obiettivi sono volati via e bisogna riempire uno slot in fretta; se
        # in quel momento il programma propone una fantamedia alta prodotta da
        # otto presenze, il danno lo fa lui, non l'asta. Chi non e' titolare
        # con ragionevole certezza entra solo se non e' rimasto nessun altro.
        candidati = sorted(liberi, key=lambda y: (-(y.presenze * y.fm), y.id))
        sicuri, incerti = [], []
        for x in candidati:
            if x.id in gia_visti:
                continue
            if _arrotonda(v.prezzo_chiusura(x)) > tetto:
                continue
            if x.grado == 'titolare' and (x.certezza or 0) >= CERTEZZA_RIPIEGO:
                sicuri.append(x)
            else:
                incerti.append(x)
            if len(sicuri) >= 6:
                break
        out = []
        # Il fondo del listone non passa dalla classificazione in fasce, quindi
        # qui puo' arrivare anche una trappola: qualcuno che a quel prezzo
        # rende meno di quanto rendano gli stessi crediti nel suo reparto.
        # Succedeva, e da "alternative" quel nome finiva promosso fra i "top
        # acquisti" dalla regola che vieta la lista vuota, con la scheda che
        # continuava a dire LASCIA. Era il difetto da cui e' nato tutto questo
        # lavoro, rientrato dalla finestra.
        def trappola(x):
            return self.o.convenienza(x, _arrotonda(v.prezzo_chiusura(x)))                 <= -SOGLIA_TRAPPOLA
        sicuri = [x for x in sicuri if not trappola(x)]
        incerti = [x for x in incerti if not trappola(x)]
        for x in (sicuri + incerti)[:6]:
            d = self.decisione(x)
            d.pop('concorrenti', None)
            d['categoria'] = 'ripiego'
            out.append(d)

        # Quanti ne restano davvero utili, contro quanti me ne servono.
        sopra = sum(1 for x in liberi if x.fm > v.rimpiazzo_fm[ruolo])
        in_gara = sum(1 for p in stato.presidenti()
                      if stato.slot_residui(p['id'], ruolo) > 0)
        scarsita = None
        if sopra <= serve * 2:
            scarsita = ('Restano %d %s sopra il livello di rimpiazzo e te ne '
                        'servono %d: da qui in avanti conta prenderli, non '
                        'risparmiare.' % (sopra, self._nome_ruolo(ruolo), serve))
        elif in_gara <= 3:
            scarsita = ('Solo %d squadre hanno ancora slot liberi in questo '
                        'reparto: i prezzi scenderanno.' % in_gara)
        return out, scarsita

    _nome_ruolo = staticmethod(_nome_ruolo)

    # -------------------------------------------- far pagare, senza rimetterci
    def _svuota(self, x, d, conc, liquidita):
        """Fin dove si puo' spingere un giocatore che non voglio, in sicurezza.

        Chiamare un big che non interessa e' una mossa vera: ogni credito che
        gli altri bruciano su di lui e' un credito che non avranno quando
        chiamerai i tuoi. Ma e' anche il modo piu' rapido di ritrovarsi in rosa,
        a quaranta crediti, uno che non si voleva. Il pannello diceva "chiusura
        attesa 46" e si poteva leggere come *spingi fino a 46*: se in quel
        momento gli altri si fermano, quei 46 li paghi tu.

        Due condizioni, che sono la stessa idea vista da due lati:

          1. **Un tetto sotto quanto vale sul mercato.** Se nessuno rilancia e
             te lo aggiudichi, ti resta in rosa un giocatore pagato meno di
             quanto valga: non e' il piano, ma non e' una perdita.
          2. **Almeno due avversari ancora in gara** che possano superare quel
             tetto. Con uno solo, se passa la mano il giocatore e' tuo; con
             nessuno, stai solo comprando a caso.
        """
        if d['chiusura'] < PREZZO_SVUOTO:
            return None
        tetto = int(max(1, round((x.prezzo_base or 1.0) - 1)))
        # Chi puo' davvero passare il tetto: gli altri non fanno salire niente.
        capaci = [c for c in conc if c['liquidita'] > tetto]
        if len(capaci) < CONTENDENTI_MINIMI:
            return None
        minaccia = sum(1 for c in capaci if c['liquidita'] > liquidita)
        # Il tetto mostrato e' il piu' basso fra i due: sotto quanto vale
        # **e** non oltre dove il giocatore chiudera' comunque. Il secondo
        # taglio mancava, e a meta' asta &mdash; quando `prezzo_base` resta
        # fermo e la chiusura attesa scende &mdash; il pannello finiva per
        # invitare a spingere sopra il prezzo a cui quel giocatore sarebbe
        # andato via da solo. Spingere li' non fa spendere niente a nessuno:
        # fa solo correre il rischio di aggiudicarselo.
        tetto = min(tetto, int(d['chiusura']))
        e = dict(d)
        e['brucia'] = tetto
        e['tetto_sicuro'] = tetto
        e['contendenti'] = len(capaci)
        e['minacciosi'] = minaccia
        e['categoria'] = 'svuota'
        e['perche'] = self._perche_svuotare(x, e, capaci)
        e['punteggio'] = e['brucia'] * (1 + minaccia) / float(1 + len(capaci))
        return e

    def _perche_svuotare(self, x, voce, conc):
        chi = ('%d avversari piu\' liquidi di te' % voce['minacciosi']
               if voce['minacciosi'] >= 2 else '%d avversari' % len(conc))
        return ('Non lo vuoi, ma %s se lo contenderanno. Spingilo fino a %d e '
                'non oltre: sopra quella cifra, se si fermano, te lo ritrovi in '
                'rosa a un prezzo che non volevi pagare.'
                % (chi, voce['tetto_sicuro']))

    def _indicazione(self, ruolo, serve, pressione, prendere, svuotare,
                     obbligati=0, budget=0):
        nome = {'P': 'portieri', 'D': 'difensori',
                'C': 'centrocampisti', 'A': 'attaccanti'}[ruolo]
        # Quando la fascia alta e' vuota la cosa da dire non e' "non conviene
        # nessuno": e' **dove sono finiti i crediti**. Senza quella frase il
        # piano sembra un'omissione invece che una scelta.
        if obbligati and serve > 0:
            return ("Il piano destina solo %d crediti ai %d %s che ti mancano: "
                    "il resto rende di piu' negli altri reparti. Qui sotto ci "
                    "sono i migliori in quella fascia di prezzo, non degli "
                    "affari. Se ne vuoi uno piu' forte devi togliere crediti a "
                    "un altro reparto, e aprendolo il motore ti dice quanto ci "
                    "perdi." % (budget, serve,
                       nome if serve != 1 else _nome_singolare(ruolo)))
        if serve <= 0:
            return ('Hai gia' + '\' completato i %s: da qui in avanti chiama '
                    'solo per far spendere gli altri.' % nome)
        if pressione >= 1.15 and prendere:
            return ('Sei piu\' liquido della media (%.2f): chiama i tuoi '
                    'obiettivi finche\' gli altri non possono seguirti.' % pressione)
        if pressione <= 0.85:
            return ('Hai meno potere d\'acquisto della media (%.2f): fai '
                    'spendere loro prima di scoprirti.' % pressione)
        if not prendere:
            return ("Ai prezzi di adesso nessun %s conviene: costano tutti piu' "
                    "di quanto renderebbero alla tua rosa. Conviene chiamare per "
                    "far spendere gli altri e aspettare che i prezzi scendano."
                    % _nome_singolare(ruolo))
        if serve == 1:
            return ("Ti manca un %s. Sceglilo bene: e' l'ultimo slot."
                    % _nome_singolare(ruolo))
        return 'Mancano %d %s alla tua rosa.' % (serve, nome)
