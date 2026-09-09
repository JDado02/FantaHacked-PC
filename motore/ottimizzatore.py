# -*- coding: utf-8 -*-
"""Rosa ottima e prezzo massimo personale.

Il prezzo di mercato dice quanto vale un giocatore *per la lega*. In asta serve
un'altra risposta: quanto vale **per la mia rosa**. Sono cose diverse per tre
motivi che il prezzo di mercato, per costruzione, non puo' conoscere.

  1. **I crediti sono un vincolo, non un metro.** Cento crediti spesi su un
     attaccante sono cento crediti che non ho piu' per gli altri ventiquattro
     slot. Il valore di un giocatore e' quanto migliora la rosa *completa* che
     riesco ancora a costruire.

  2. **Non schieri venticinque giocatori, ne schieri undici.** Il terzo portiere
     non gioca mai: vale un credito per quanto sia bravo. L'ottavo difensore
     entra solo quando ne mancano quattro davanti a lui. Il valore di un
     giocatore dipende da *quanti* ne ho gia' in quel ruolo e da quanto sono
     forti.

  3. **Il modificatore di difesa non e' additivo.** Il quarto difensore forte
     non alza la media di portiere + tre migliori difensori. Solo guardando la
     mia rosa si puo' dire di quanto vale davvero.

Da cui la definizione esatta del prezzo massimo:

    max_bid(g) = il prezzo P piu' alto per cui
                 OPT(rosa che include g, budget-P)  >=  OPT(rosa senza g, budget)

Sopra quel prezzo la rosa che riesco a completare comprandolo e' peggiore di
quella che avrei lasciandolo andare. E' il punto di indifferenza: il prezzo
oltre il quale si perde, non il prezzo da offrire.

OPT si calcola con uno zaino per ruolo (quanti giocatori, quanto costano,
quanto valgono al loro posto in rosa) e una convoluzione max-piu' fra i quattro
ruoli per dividere il budget. Con numpy sono poche decine di millisecondi:
abbastanza per stare dietro a una chiamata d'asta.
"""
import math, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RUOLI = ('P', 'D', 'C', 'A')
NEG = -1e18
GIORNATE_STAGIONE = 38

# Cos'e' un riempitivo: costa fino a due crediti e sopra il livello di
# rimpiazzo non aggiunge piu' di cinque punti in tutta la stagione, cioe'
# niente che si distingua dal rumore delle proiezioni.
COSTO_RIEMPITIVO = 2

# Se il piano debba usare un prezzo suo invece di quello mostrato. Si': il
# numero da mostrare e il numero con cui pianificare non sono lo stesso numero.
#
# Sembra una contraddizione, perche' `prezzo_atteso` con la curva e' il prezzo
# **piu' preciso** che il motore sappia fare (29% di errore contro 39%). Ma
# `max_bid` non e' una previsione: e' un punto di indifferenza calcolato
# contro il piano. Se il piano crede i sostituti piu' economici, il limite su
# ogni singolo giocatore scende e il motore lascia perdere piu' spesso &mdash;
# e **lasciar perdere e' il modo in cui si vince un'asta**. Un piano che
# prezza tutto al valore giusto e' un piano modesto: alza i limiti, e fa
# pagare di piu' per gli stessi punti.
#
# Misurato su centocinquanta aste appaiate, modificatore di difesa compreso
# nel punteggio: pianificare col prezzo a merito vale **diciassette punti di
# stagione in piu'** (2,9 errori standard) e tre crediti e mezzo avanzati in
# piu'. Lo scarto non cambia con avversari non distorti, quindi non e' una
# proprieta' della stanza finta.
#
# Il conto scomposto per reparto dice anche dove se ne andavano: col prezzo
# preciso nel piano il motore spendeva trentotto crediti in piu' in difesa per
# settantanove punti &mdash; quasi mezzo credito a punto, contro i sette
# centesimi che pagava prima &mdash; togliendoli a centrocampo e attacco.
#
# Costa una cosa: comprato il titolare di una coppia, il limite sul socio sale
# meno spesso. Nella misura d'esito pero' quella perdita non si vede (rischio
# di restare in dieci 1,1 giornate contro 1,2), quindi resta una proprieta'
# che varrebbe la pena rinforzare dal lato del bonus coppia, non del prezzo.
#
# Chi vuole rifare il conto: `simulazioni/tre_vie.py`.
PIANO_SEPARATO = True

# Quanto pesa, nel valore di un giocatore, il fatto che chiuda una coppia gia'
# meta' in rosa.
#
# Il due non e' una derivazione, e' un tappabuchi misurato. La formula in
# `_coppie_da_chiudere` conta solo i punti che il socio mette sulle giornate
# che il titolare salta, sopra il livello di rimpiazzo. Quello che non conta e'
# la ragione per cui si vogliono entrambi: **quelle giornate, senza di lui, non
# le copre un giocatore medio del ruolo &mdash; le copre chi capita, o
# nessuno.** E' lo stesso punto cieco di `ultimi_posti`: la funzione da
# massimizzare vede i punti e non vede le caselle vuote.
#
# Il numero e' scelto misurando: su venticinque coppie, comprato il titolare,
# il limite sul socio sale 3 volte a peso 1 e 8 volte a peso 2, e su trenta
# aste il punteggio e il rischio di restare in dieci non peggiorano (2307
# contro 2295 punti, 1,1 giornate in entrambi i casi). A peso 3 non migliora
# piu' niente. Il conto si rifa' con `simulazioni/bonus_coppia.py`.
PESO_COPPIA = 2.0
VALORE_RIEMPITIVO = 5.0

# Quanti giocatori per ruolo si schierano in media. Media dei moduli ammessi
# in Classic: 343, 352, 442, 433, 451, 532, 541. Fa 4 difensori, 4
# centrocampisti, 2 attaccanti, piu' il portiere.
TITOLARI = {'P': 1.0, 'D': 4.0, 'C': 4.0, 'A': 2.0}

try:
    import numpy as np
    HA_NUMPY = True
except ImportError:                                        # pragma: no cover
    np = None
    HA_NUMPY = False

POOL_MAX_SENZA_NUMPY = 45


# --------------------------------------------------------------- primitive
def _nuovo(n, valore=NEG):
    if HA_NUMPY:
        return np.full(n, valore, dtype=np.float64)
    return [valore] * n


def _accumula_max(v):
    """Rende la riga non decrescente: f[c] diventa 'spendendo al piu' c'."""
    if HA_NUMPY:
        return np.maximum.accumulate(v)
    out, corrente = [], NEG
    for x in v:
        corrente = x if x > corrente else corrente
        out.append(corrente)
    return out


def _fondi(a, b, B):
    """Convoluzione max-piu': out[c] = max su c1+c2<=c di a[c1] + b[c2].

    E' il passo che divide il budget fra due gruppi di ruoli.
    """
    out = _nuovo(B + 1)
    if HA_NUMPY:
        for c in range(B + 1):
            x = a[c]
            if x <= NEG / 2:
                continue
            coda = out[c:]
            np.maximum(coda, b[:B + 1 - c] + x, out=coda)
        return out
    for c in range(B + 1):
        x = a[c]
        if x <= NEG / 2:
            continue
        for d in range(B + 1 - c):
            v = x + b[d]
            if v > out[c + d]:
                out[c + d] = v
    return out


def _fondi_misto(a, b, lung):
    """Convoluzione max-piu' fra due tabelle di lunghezza diversa.

    Serve per il max_bid: il prezzo del giocatore da valutare esce dai crediti
    riservati al suo reparto, e i due gruppi non vivono percio' sullo stesso
    intervallo. Calcolarla una volta sola, invece che una per ogni prezzo
    candidato, e' cio' che tiene la risposta sotto i cinquanta millisecondi.
    """
    out = _nuovo(lung + 1)
    nb = len(b)
    for c in range(min(len(a), lung + 1)):
        x = a[c]
        if x <= NEG / 2:
            continue
        quanti = min(nb, lung + 1 - c)
        if quanti <= 0:
            continue
        if HA_NUMPY:
            coda = out[c:c + quanti]
            np.maximum(coda, b[:quanti] + x, out=coda)
        else:
            for d in range(quanti):
                v = x + b[d]
                if v > out[c + d]:
                    out[c + d] = v
    return out


def _fondi_con_traccia(a, b, B):
    """Come _fondi, ma dice anche quanto budget e' andato al primo gruppo."""
    out = _nuovo(B + 1)
    if HA_NUMPY:
        quota = np.zeros(B + 1, dtype=np.int32)
        for c in range(B + 1):
            x = a[c]
            if x <= NEG / 2:
                continue
            cand = b[:B + 1 - c] + x
            coda = out[c:]
            migliori = cand > coda
            coda[migliori] = cand[migliori]
            quota[c:][migliori] = c
        return out, quota
    quota = [0] * (B + 1)
    for c in range(B + 1):
        x = a[c]
        if x <= NEG / 2:
            continue
        for d in range(B + 1 - c):
            v = x + b[d]
            if v > out[c + d]:
                out[c + d] = v
                quota[c + d] = c
    return out, quota


# ------------------------------------------------------ profondita' di rosa
def _binom_cdf(k, n, p):
    """P(Binomiale(n, p) <= k), calcolata in modo incrementale."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    q = 1.0 - p
    if q <= 0:
        return 0.0
    termine = q ** n
    somma = termine
    for i in range(k):
        termine *= (n - i) / float(i + 1) * (p / q)
        somma += termine
    return min(1.0, somma)


def pesi_profondita(slot, n_titolari, disponibilita):
    """Quante giornate scende in campo il k-esimo giocatore di un reparto.

    Il k-esimo gioca quando meno di `n_titolari` fra i k-1 piu' forti sono
    disponibili. Con disponibilita' individuale `a` indipendente, e' la
    binomiale cumulata. Il risultato e' la curva che dice quanto vale la
    panchina: alta e piatta dove servono molti titolari, che crolla subito
    dove ne serve uno solo.

        portieri  (1 titolare)  ->  1.00  0.25  0.06
        difensori (4 titolari)  ->  1.00  1.00  1.00  1.00  0.63  0.35 ...

    `n_titolari` puo' essere frazionario: si interpola fra i due interi.
    """
    basso = int(math.floor(n_titolari))
    alto = int(math.ceil(n_titolari))
    frazione = n_titolari - basso
    out = []
    for k in range(1, slot + 1):
        p_basso = _binom_cdf(basso - 1, k - 1, disponibilita)
        p_alto = (p_basso if alto == basso
                  else _binom_cdf(alto - 1, k - 1, disponibilita))
        out.append((1.0 - frazione) * p_basso + frazione * p_alto)
    return out


# ------------------------------------------------------------------ zaino
class Zaino(object):
    """f[k][c] = miglior valore prendendo esattamente k giocatori spendendo <= c.

    I giocatori vanno passati in ordine di valore decrescente. Cosi' quello che
    fa passare la soluzione da k-1 a k giocatori e' esattamente il k-esimo piu'
    forte del gruppo, e si puo' pesarlo per la profondita' di rosa: e' il modo
    in cui il rendimento decrescente della panchina entra nella
    programmazione dinamica senza romperla.
    """

    def __init__(self, pool, k_max, budget, peso, offset=0, obbligatorio=None,
                 traccia=False):
        self.k_max = max(0, k_max)
        self.B = budget
        self.pool = pool
        self.f = [_nuovo(budget + 1) for _ in range(self.k_max + 1)]
        self.f[0] = _nuovo(budget + 1, 0.0)
        self.preso = [] if traccia else None

        def w(k):
            i = k - 1 + offset
            return peso[i] if 0 <= i < len(peso) else 0.0

        for indice, voce in enumerate(pool):
            costo, valore, ident, mod = voce[0], voce[1], voce[2], voce[3]
            forzato = (obbligatorio is not None and ident == obbligatorio)
            righe = []
            if costo > budget and not forzato:
                if traccia:
                    self.preso.append(righe)
                continue
            for k in range(self.k_max, 0, -1):
                prec, cur = self.f[k - 1], self.f[k]
                # Valore al posto k: rendimento pesato per le giornate in cui
                # scende davvero in campo, piu' il modificatore se rientra nel
                # nucleo difensivo.
                punti_mod, posti_mod = mod
                v = valore * w(k) + (punti_mod if (k + offset) <= posti_mod else 0.0)
                if costo > budget:
                    continue
                if HA_NUMPY:
                    cand = prec[:budget + 1 - costo] + v
                    coda = cur[costo:]
                    if forzato:
                        # Obbligatorio: la soluzione a k giocatori DEVE contenerlo.
                        nuovo = _nuovo(budget + 1)
                        nuovo[costo:] = cand
                        self.f[k] = nuovo
                        if traccia:
                            righe.append((k, set(range(costo, budget + 1))))
                        continue
                    if traccia:
                        righe.append((k, set((np.flatnonzero(cand > coda) + costo).tolist())))
                    np.maximum(coda, cand, out=coda)
                else:
                    if forzato:
                        nuovo = _nuovo(budget + 1)
                        for c in range(costo, budget + 1):
                            nuovo[c] = prec[c - costo] + v
                        self.f[k] = nuovo
                        if traccia:
                            righe.append((k, set(range(costo, budget + 1))))
                        continue
                    migliorati = set()
                    for c in range(budget, costo - 1, -1):
                        nv = prec[c - costo] + v
                        if nv > cur[c]:
                            cur[c] = nv
                            migliorati.add(c)
                    if traccia:
                        righe.append((k, migliorati))
            if traccia:
                self.preso.append(righe)
        for k in range(self.k_max + 1):
            self.f[k] = _accumula_max(self.f[k])

    def riga(self, k):
        if k < 0:
            return _nuovo(self.B + 1)
        return self.f[min(k, self.k_max)]


# --------------------------------------------------------------- pool utile
def _pota(pool, k_max):
    """Toglie i giocatori dominati: costo non inferiore e valore non superiore.

    Non cambia il risultato, ed e' quello che permette di rispondere entro
    qualche decina di millisecondi. Restano sempre almeno k_max riempitivi
    economici, altrimenti la rosa non si chiude.
    """
    per_costo = sorted(pool, key=lambda t: (t[0], -t[1]))
    tenuti, migliore = [], NEG
    for voce in per_costo:
        if voce[1] > migliore:
            migliore = voce[1]
            tenuti.append(voce)
    visti = set(v[2] for v in tenuti)
    for voce in per_costo[:k_max]:
        if voce[2] not in visti:
            tenuti.append(voce)
            visti.add(voce[2])
    if not HA_NUMPY and len(tenuti) > POOL_MAX_SENZA_NUMPY:
        alti = sorted(tenuti, key=lambda t: -t[1])[:POOL_MAX_SENZA_NUMPY - k_max]
        bassi = sorted(tenuti, key=lambda t: t[0])[:k_max]
        tenuti = list({v[2]: v for v in alti + bassi}.values())
    return sorted(tenuti, key=lambda t: -t[1])


# ----------------------------------------------------------- ottimizzatore
class Ottimizzatore(object):
    """OPT e max_bid sullo stato corrente dell'asta.

    Va richiamato `aggiorna()` dopo ogni acquisto: tabelle, pesi e nucleo
    difensivo dipendono da chi e' ancora libero e da cosa ho gia' in rosa.
    """

    def __init__(self, valutatore):
        self.v = valutatore
        self.reg = valutatore.reg
        self.stato = valutatore.stato
        self.mod = valutatore.mod
        self.aggiorna()

    # ------------------------------------------------------------ preparazione
    def aggiorna(self):
        v, stato = self.v, self.stato
        self.io = stato.io()['id']
        self.budget = max(0, stato.crediti(self.io))
        self.serve = dict((r, max(0, stato.slot_residui(self.io, r))) for r in RUOLI)
        self.slot_residui = sum(self.serve.values())

        venduti = stato.venduti()
        self.liberi = dict((r, []) for r in RUOLI)
        for x in v.g.values():
            if x.id not in venduti:
                self.liberi[x.ruolo].append(x)

        # Disponibilita' media di chi finira' in una rosa: la misura il
        # database, non e' una costante scritta a mano.
        self.disponibilita = {}
        self.pesi = {}
        for r in RUOLI:
            # Misurata su chi fara' il TITOLARE, non su chiunque finira' in una
            # rosa: fra i secondi portieri ci sono medie alte con tre presenze,
            # e includerli farebbe sembrare la panchina piu' utile di quanto e'.
            quanti = max(1, int(round(TITOLARI[r] * self.reg.partecipanti)))
            pool = sorted(self.liberi[r], key=lambda x: -(x.presenze * x.fm))[:quanti]
            pres = [x.presenze for x in pool if x.presenze]
            a = (sum(pres) / len(pres) / 38.0) if pres else 0.7
            self.disponibilita[r] = min(0.95, max(0.35, a))
            self.pesi[r] = pesi_profondita(self.reg.slot[r], TITOLARI[r],
                                           self.disponibilita[r])

        # Coi portieri a pacchetto il reparto e' una scelta sola: prendi il
        # titolare di una squadra e ti arrivano anche le sue due riserve.
        self.pacchetto_por = bool(getattr(v, 'pacchetto', False))
        if self.pacchetto_por:
            self.liberi['P'] = [x for x in self.liberi['P'] if x.titolare_por]
            self.serve['P'] = int(math.ceil(
                self.serve['P'] / float(max(1, self.reg.slot['P']))))
            self.pesi['P'] = [1.0] * max(1, self.serve['P'] + 1)

        self.mia_rosa = self._mia_rosa()
        self.coppia_bonus = self._coppie_da_chiudere()
        self._pad = dict((r, self._livello_nucleo(r)) for r in ('P', 'D'))
        self.media_difesa = self._media_difesa()

        # Valore base: punti sopra il rimpiazzo, SENZA il contributo generico al
        # modificatore di listone. Quello lo rimettiamo su misura della mia rosa.
        self.valore = {}
        self.costo = {}
        self.mod_punti = {}
        for r in RUOLI:
            for x in self.liberi[r]:
                self.valore[x.id] = (max(0.0, x.presenze * (x.fm - v.rimpiazzo_fm[r]))
                                     + self.coppia_bonus.get(x.id, 0.0))
                # Il costo NON e' quanto vale: e' quanto costera'.
                # Pianificare sui valori teorici invece che sui prezzi veri
                # porta a riempirsi di difensori "convenienti" e ad arrivare
                # agli attaccanti senza piu' crediti, che e' il modo classico
                # di perdere un'asta facendo solo buoni affari.
                #
                # E non e' `prezzo_atteso`, che pure e' il prezzo piu' preciso
                # che il motore sappia fare: il perche' sta tutto su
                # `PIANO_SEPARATO`, in cima al file.
                pianificato = (getattr(x, 'prezzo_piano', None)
                               if PIANO_SEPARATO else None)
                self.costo[x.id] = max(1, int(round(
                    pianificato or x.prezzo_atteso or x.prezzo_mercato or 1.0)))
                if r == 'P' and getattr(v, 'pacchetto', False) and x.titolare_por:
                    self.costo[x.id] += len(x.riserve_por or ())
                self.mod_punti[x.id] = self.contributo_difesa(x)
        for r in RUOLI:
            self.liberi[r].sort(key=lambda x: -self.valore[x.id])

        self._riserve()
        self._tabelle = {}
        self._resto = {}
        self._opt_base = None
        self._curva = None
        self._tasso = None
        self._tasso_ruolo = {}
        self._piano = None
        self._ottimo = None

    # ------------------------------------------------------------- riserve
    def _riserve(self):
        """Crediti accantonati per reparto, che il resto della rosa non tocca.

        Senza un vincolo del genere l'ottimizzatore fa una cosa difendibile in
        punti ma fragile nella realta': compra sei attaccanti da un credito,
        perche' in un mercato che paga gli attaccanti il doppio di quanto
        rendono e' matematicamente la scelta giusta. Il guaio e' che ci si
        gioca tutto sul fatto che le proiezioni siano giuste su quattro
        giocatori invece che su uno, e se sbagliano non resta nessun attacco.

        La percentuale sta in regole_lega.json: e' una scelta di rischio, e
        come tale spetta a chi fa l'asta, non al programma.
        """
        quote = getattr(self.reg, 'riserva_ruolo', None) or {}
        self.riserva = dict((r, 0) for r in RUOLI)
        if not any(quote.values()):
            self.surplus = self.budget
            return
        speso = {}
        for a in self.stato.acquisti():
            if a['presidente_id'] == self.io:
                speso[a['ruolo']] = speso.get(a['ruolo'], 0) + a['prezzo']
        grezza = {}
        for r in RUOLI:
            if self.serve[r] <= 0:
                grezza[r] = 0.0
                continue
            # Quello che ho gia' speso nel reparto conta come riserva
            # gia' onorata: non va accantonato due volte.
            grezza[r] = max(0.0, quote.get(r, 0.0) * self.reg.crediti
                            - speso.get(r, 0))
        # Non si puo' accantonare piu' di quanto si abbia, e va comunque
        # lasciato un credito per ogni slot degli altri reparti.
        for r in RUOLI:
            altri_slot = sum(self.serve[s] for s in RUOLI if s != r)
            grezza[r] = min(grezza[r], max(0, self.budget - altri_slot))
        somma = sum(grezza.values())
        if somma > self.budget:
            k = float(self.budget) / somma
            for r in RUOLI:
                grezza[r] *= k
        for r in RUOLI:
            self.riserva[r] = int(grezza[r])
        self.surplus = max(0, self.budget - sum(self.riserva.values()))

    def _mia_rosa(self):
        rosa = dict((r, []) for r in RUOLI)
        for a in self.stato.acquisti():
            if a['presidente_id'] != self.io:
                continue
            x = self.v.g.get(a['giocatore_id'])
            if x is not None:
                rosa[x.ruolo].append(x)
        for r in RUOLI:
            rosa[r].sort(key=lambda x: -(x.presenze * (x.fm - self.v.rimpiazzo_fm[r])))
        return rosa

    # ------------------------------------------------ coppie complementari
    def _coppie_da_chiudere(self):
        """Quanto vale, in piu', chi completa una coppia gia' in rosa mia.

        Non e' un premio ai vice in generale: e' il valore di **chiudere**
        una coppia che ho gia' meta'. Se possiedo il titolare e sul mercato
        c'e' ancora il suo vice (o il suo avversario in un ballottaggio), quel
        giocatore non vale solo la fantamedia sulle poche presenze che gli si
        prevedono da solo. Vale anche a coprire le giornate che il titolare
        salta, con qualcuno che quella maglia la conosce davvero — non con il
        primo del listone che capita quando manca un titolare.

        Il tetto della copertura e' il minimo fra le giornate che il titolare
        lascia scoperte e le presenze attese del vice: non si puo' contare due
        volte le stesse giornate, ne' promettere al vice piu' partite di
        quante gliene diano le sue stesse proiezioni.
        """
        v = self.v
        miei = set(x.id for r in RUOLI for x in self.mia_rosa[r])
        bonus = {}
        for r in RUOLI:
            for x in self.liberi[r]:
                extra = 0.0
                for c in v.compagni_di_maglia(x.id):
                    if c['altro'] not in miei:
                        continue
                    titolare = v.g.get(c['altro'])
                    if titolare is None:
                        continue
                    scoperte = max(0.0, float(GIORNATE_STAGIONE)
                                   - (titolare.presenze or 0.0))
                    if scoperte <= 0:
                        continue
                    tetto = min(scoperte, x.presenze or 0.0)
                    sopra_rimpiazzo = max(0.0, (x.fm or 0.0) - v.rimpiazzo_fm[r])
                    extra += tetto * sopra_rimpiazzo
                if extra > 0:
                    bonus[x.id] = extra * PESO_COPPIA
        return bonus

    # ------------------------------------------------- modificatore di difesa
    def _livello_nucleo(self, ruolo):
        """Media voto del tipico componente di difesa ancora sul mercato.

        E' il tappo con cui si riempiono gli slot del nucleo difensivo che non
        ho ancora comprato: non posso dare per scontato di prendere un fenomeno,
        ne' devo assumere il peggiore disponibile. Il riferimento e' chi, ai
        prezzi correnti, occupa l'ultimo posto utile del nucleo in tutta la lega.
        """
        n = (self.reg.mod_dif_n_por if ruolo == 'P' else self.reg.mod_dif_n_dif)
        pool = sorted(self.liberi[ruolo], key=lambda x: -x.mv)
        if not pool:
            return 6.0
        squadre = sum(1 for p in self.stato.presidenti()
                      if self.stato.slot_residui(p['id'], ruolo) > 0)
        rango = max(1, n * max(1, squadre))
        i = min(rango, len(pool)) - 1
        finestra = pool[max(0, i - 1):i + 2]
        return sum(x.mv for x in finestra) / float(len(finestra))

    def _nucleo(self, aggiunto=None):
        out = []
        for ruolo, quanti in (('P', self.reg.mod_dif_n_por),
                              ('D', self.reg.mod_dif_n_dif)):
            if quanti <= 0:
                continue
            mv = [x.mv for x in self.mia_rosa[ruolo]]
            if aggiunto is not None and aggiunto.ruolo == ruolo:
                mv.append(aggiunto.mv)
            mv.sort(reverse=True)
            mv = mv[:quanti]
            while len(mv) < quanti:      # slot del nucleo non ancora coperti
                mv.append(self._pad[ruolo])
            out.extend(mv)
        return out

    def _media_difesa(self, aggiunto=None):
        nucleo = self._nucleo(aggiunto)
        return sum(nucleo) / float(len(nucleo)) if nucleo else 0.0

    def contributo_difesa(self, giocatore):
        """Punti stagione che quel giocatore aggiunge al MIO modificatore.

        Zero per centrocampisti e attaccanti; zero anche per il quarto
        difensore forte quando i primi tre sono gia' meglio di lui. E' il punto
        in cui il calcolo smette di essere di listone e diventa personale.
        """
        if not self.mod.attivo or giocatore.ruolo not in ('P', 'D'):
            return 0.0
        if giocatore.ruolo == 'P' and self.reg.mod_dif_n_por <= 0:
            return 0.0
        return self.mod.guadagno(self.media_difesa, self._media_difesa(giocatore))

    def _posti_nucleo(self, ruolo):
        if not self.mod.attivo:
            return 0
        return (self.reg.mod_dif_n_por if ruolo == 'P'
                else self.reg.mod_dif_n_dif if ruolo == 'D' else 0)

    # ------------------------------------------------------------- tabelle
    def _pool(self, ruolo, escludi=None):
        posti = self._posti_nucleo(ruolo)
        out = []
        for x in self.liberi[ruolo]:
            if escludi is not None and x.id == escludi:
                continue
            out.append((self.costo[x.id], self.valore[x.id], x.id,
                        (self.mod_punti[x.id], posti)))
        return _pota(out, max(1, self.serve[ruolo]))

    def _offset(self, ruolo):
        """Quanti giocatori ho gia' in quel ruolo: i nuovi partono dopo di loro."""
        return len(self.mia_rosa[ruolo])

    def _tabella(self, ruolo, escludi=None, obbligatorio=None, traccia=False):
        chiave = (ruolo, escludi, obbligatorio, traccia)
        if chiave in self._tabelle:
            return self._tabelle[chiave]
        pool = self._pool(ruolo, escludi)
        if obbligatorio is not None:
            # Il giocatore entra a costo zero: il suo prezzo e' la variabile
            # che stiamo cercando, e viene tolto dal budget a parte.
            g = self.v.g[obbligatorio]
            voce = (0, self.valore.get(g.id, 0.0), g.id,
                    (self.mod_punti.get(g.id, 0.0), self._posti_nucleo(ruolo)))
            pool = sorted(pool + [voce], key=lambda t: -t[1])
        z = Zaino(pool, max(1, self.serve[ruolo]), self.budget, self.pesi[ruolo],
                  offset=self._offset(ruolo), obbligatorio=obbligatorio,
                  traccia=traccia)
        self._tabelle[chiave] = z
        return z

    def _sposta(self, riga, offset):
        """Porta una riga nello spazio del budget libero.

        Ogni reparto ha gia' i suoi crediti accantonati: quello che si
        distribuisce e' solo il surplus. `out[y]` e' il miglior valore del
        reparto spendendo al piu' `offset + y`, dove `offset` sono i suoi
        crediti riservati (meno l'eventuale prezzo gia' pagato per un
        giocatore forzato in rosa).
        """
        n = self.surplus + 1
        out = _nuovo(n)
        for y in range(n):
            c = offset + y
            if 0 <= c <= self.budget:
                out[y] = riga[c]
            elif c > self.budget:
                out[y] = riga[self.budget]
        return out

    def _riga(self, ruolo, k, escludi=None, obbligatorio=None, sconto=0):
        return self._sposta(
            self._tabella(ruolo, escludi, obbligatorio).riga(k),
            self.riserva[ruolo] - sconto)

    def _resto_ruoli(self, ruolo):
        """Miglior valore dai TRE ruoli diversi da questo, per ogni budget."""
        if ruolo in self._resto:
            return self._resto[ruolo]
        altri = [r for r in RUOLI if r != ruolo]
        acc = self._riga(altri[0], self.serve[altri[0]])
        for r in altri[1:]:
            acc = _fondi(acc, self._riga(r, self.serve[r]), self.surplus)
        self._resto[ruolo] = acc
        return acc

    # ------------------------------------------------------------------- OPT
    def opt(self):
        """Valore della miglior rosa che posso ancora completare."""
        if self._opt_base is None:
            if self.slot_residui == 0:
                self._opt_base = 0.0
                self._curva = None
            else:
                acc = self._riga(RUOLI[0], self.serve[RUOLI[0]])
                for r in RUOLI[1:]:
                    acc = _fondi(acc, self._riga(r, self.serve[r]), self.surplus)
                self._curva = acc
                self._opt_base = float(acc[self.surplus])
        return self._opt_base

    # ------------------------------------------ quanto vale un credito, adesso
    def tasso_cambio(self):
        """Punti di stagione che rende un credito speso dove rende di piu'.

        E' il prezzo interno dei crediti: la pendenza della curva dell'ottimo
        nel punto in cui mi trovo. Serve a rispondere alla domanda che il
        prezzo massimo, da solo, non sa affrontare: *quel giocatore, a quella
        cifra, vale piu' o meno di quello che quei crediti comprerebbero
        altrove?* Il prezzo massimo confronta il giocatore con un rivale
        preciso e finisce per eleggere un vincitore unico; questo lo confronta
        con il mercato, e mette in fila tutti.

        Si misura su una fetta vera di budget, non sull'ultimo credito: la
        curva e' a gradini, e la pendenza fra due gradini vicini dice solo
        dov'e' il gradino.
        """
        if self._tasso is not None:
            return self._tasso
        self.opt()
        curva = self._curva
        if curva is None or self.surplus <= 0:
            self._tasso = 0.0
            return self._tasso
        fetta = max(5, self.surplus // 5)
        giu = max(0, self.surplus - fetta)
        alto = float(curva[self.surplus])
        basso = float(curva[giu])
        if basso <= NEG / 2 or alto <= NEG / 2 or self.surplus == giu:
            self._tasso = 0.0
        else:
            self._tasso = max(0.0, (alto - basso) / float(self.surplus - giu))
        return self._tasso

    def resa(self, giocatore):
        """Punti di stagione che quel giocatore aggiunge, nel primo slot libero.

        Non e' `valore`: il quinto difensore gioca meno del primo, e il
        modificatore lo alza solo se rientra nel nucleo. Sono le stesse due
        correzioni che fa lo zaino, applicate al posto che quel giocatore
        occuperebbe se lo comprassi adesso.
        """
        x = giocatore
        if x.id not in self.valore:
            return 0.0
        r = x.ruolo
        gia = len(self.mia_rosa[r])
        pesi = self.pesi.get(r) or [1.0]
        peso = pesi[gia] if gia < len(pesi) else 0.0
        punti = self.valore[x.id] * peso
        if (gia + 1) <= self._posti_nucleo(r):
            punti += self.mod_punti.get(x.id, 0.0)
        return punti

    def tasso_ruolo(self, ruolo):
        """Punti per credito che si stanno pagando **in quel reparto**.

        Il tasso generale non basta a mettere in fila un reparto, e il caso
        limite lo dice meglio di qualsiasi spiegazione: in questa lega gli
        attaccanti si portano via il sessanta per cento del budget, e misurati
        col metro comune risultano **tutti** in perdita, dal primo all'ultimo.
        Vero, e inutile: sei attaccanti vanno comprati lo stesso, e la domanda
        vera non e' "conviene comprare attaccanti" ma "di questi, quali rendono
        piu' di quanto costano *rispetto agli altri attaccanti*".

        Il tasso del reparto e' quello: quanti punti per credito rende la spesa
        che la lega fara' davvero li' dentro. Si stima sui giocatori che
        verranno effettivamente venduti &mdash; tanti quanti sono gli slot che
        restano scoperti in tutte le rose &mdash; presi dai piu' utili in giu'.
        Si aggiorna da solo: se la stanza svena il mercato degli attaccanti, il
        tasso sale e i "buoni affari" apparenti spariscono.
        """
        if ruolo in self._tasso_ruolo:
            return self._tasso_ruolo[ruolo]
        slot = sum(self.stato.slot_residui(p['id'], ruolo)
                   for p in self.stato.presidenti())
        if ruolo == 'P' and self.pacchetto_por:
            # Un pacchetto chiude tre slot: le scelte sono un terzo.
            slot = int(math.ceil(slot / float(max(1, self.reg.slot['P']))))
        pool = sorted(self.liberi[ruolo], key=lambda x: -self.resa(x))
        pool = pool[:max(1, slot)]
        resa = sum(max(0.0, self.resa(x)) for x in pool)
        spesa = sum(max(1, self.costo[x.id]) for x in pool)
        self._tasso_ruolo[ruolo] = (resa / spesa) if spesa > 0 else 0.0
        return self._tasso_ruolo[ruolo]

    def convenienza(self, giocatore, prezzo):
        """Quanto ci guadagno a prenderlo a quel prezzo, invece che i crediti.

        Positivo: rende piu' della media di quello che quei crediti
        comprerebbero **nel suo reparto**. Negativo: nello stesso reparto, a
        quella cifra, si prende di meglio.

        A differenza del prezzo massimo, **non dipende da chi altro c'e' nel
        reparto**: e' per questo che si puo' usare per fare una classifica.
        Due portieri che si equivalgono restano vicini in classifica invece di
        diventare uno "occasione" e l'altro "lascia" per due punti su duecento.
        """
        return (self.resa(giocatore)
                - max(0, prezzo) * self.tasso_ruolo(giocatore.ruolo))

    # -------------------------------------------------------------- max_bid
    def max_bid(self, giocatore, prezzo=None):
        """Prezzo oltre il quale comprarlo peggiora la rosa finale.

        Restituisce (limite, dettaglio). Limite 0 vuol dire: lascialo andare.

        `prezzo` e' facoltativo: se lo si passa, il dettaglio dice anche quanto
        migliorerebbe la rosa comprandolo **a quel prezzo li'**. E' la misura
        che serve per mettere in fila i consigli, perche' il guadagno a un
        credito lo vincerebbero sempre i giocatori piu' cari, che pero' a un
        credito non li prende nessuno.
        """
        g = giocatore
        d = {'motivo': '', 'guadagno': 0.0, 'guadagno_al_prezzo': 0.0,
             'opt_senza': 0.0, 'opt_con': 0.0,
             'contributo_modificatore': self.mod_punti.get(g.id, 0.0)}
        # **Fuori dalla lista di serie A: non si compra, punto.** Prima di
        # ogni altro conto, perche' ogni altro conto lo tratterebbe come un
        # giocatore molto scarso - e un giocatore molto scarso, a fine asta,
        # la regola degli ultimi posti lo propone lo stesso: meglio lui che
        # una casella vuota. Ma uno che non puo' scendere in campo **e'** una
        # casella vuota, e per giunta occupa uno slot che potrebbe tenere
        # qualcuno che ogni tanto gioca.
        if getattr(g, 'fuori_lista', False):
            d['motivo'] = ("non e' iscritto alla lista di serie A:"
                           " non puo' giocare nemmeno una partita")
            d['fuori_lista'] = True
            return 0, d
        if self.serve.get(g.ruolo, 0) <= 0:
            d['motivo'] = 'reparto %s gia\' completo' % g.ruolo
            return 0, d
        if g.id in self.stato.venduti():
            d['motivo'] = 'gia\' assegnato'
            return 0, d
        liq = self.stato.liquidita(self.io)
        if liq < 1:
            d['motivo'] = 'crediti finiti: devi tenerne 1 per ogni slot scoperto'
            return 0, d

        B = self.budget
        resto = self._resto_ruoli(g.ruolo)
        n = self.serve[g.ruolo]

        # Senza di lui: se non lo prendo io lo prende un avversario, quindi
        # esce comunque dal pool. Se pero' non faceva parte della rosa ottima,
        # toglierlo non cambia niente: e' la scorciatoia che rende sostenibile
        # calcolare il max_bid su decine di giocatori a ogni chiamata.
        if g.id in self.insieme_ottimo():
            senza = _fondi(resto, self._riga(g.ruolo, n, escludi=g.id), self.surplus)
            opt_senza = float(senza[self.surplus])
        else:
            opt_senza = self.opt()
        d['opt_senza'] = opt_senza

        # Con lui: entra in rosa a costo zero nella tabella, e il prezzo si
        # scala dai crediti del suo reparto. Finche' il prezzo rientra nella
        # riserva del reparto non tocca il budget libero: e' esattamente cio'
        # che la riserva serve a garantire.
        # Comprandolo a P, al suo reparto restano `riserva + surplus - P`
        # crediti da dividere col resto della rosa. Una convoluzione sola
        # copre tutti i prezzi: basta leggerla nel punto giusto.
        tab_con = self._tabella(g.ruolo, obbligatorio=g.id).riga(n)
        lung = self.surplus + self.riserva[g.ruolo]
        z = _fondi_misto(tab_con, resto, lung)

        def opt_con(prezzo):
            t = lung - prezzo
            return float(z[t]) if 0 <= t <= lung else NEG

        limite = 0
        for P in range(min(int(liq), B), 0, -1):
            v = opt_con(P)
            if v <= NEG / 2:
                continue
            if v >= opt_senza - 1e-9:
                limite = P
                d['opt_con'] = v
                break
        if limite <= 0 and self.ultimi_posti(g.ruolo):
            # Meglio lui che una casella vuota: vedi `ultimi_posti`.
            limite = 1
            d['ultimo_posto'] = True
            d['motivo'] = ('lo slot va riempito comunque: a un credito vale'
                           " piu' di una giornata giocata in dieci")
        elif limite <= 0:
            d['motivo'] = ('anche a 1 credito toglie piu\' di quanto aggiunge: '
                           'quello slot rende di piu\' su un altro giocatore')
        g1 = opt_con(1)
        d['guadagno'] = (g1 - opt_senza) if g1 > NEG / 2 else 0.0
        if prezzo is not None:
            p = max(1, min(int(prezzo), int(liq), B))
            gp = opt_con(p)
            d['guadagno_al_prezzo'] = (gp - opt_senza) if gp > NEG / 2 else 0.0
            d['prezzo_valutato'] = p
        return limite, d

    def ultimi_posti(self, ruolo):
        """Vero quando quello slot va riempito e basta, senza piu' scegliere.

        L'ottimizzatore massimizza i punti dell'undici, e in quella funzione un
        giocatore che non gioca mai vale **zero**. Una casella vuota in
        formazione pero' non vale zero: vale una giornata in dieci, che e'
        molto meno di zero. Finche' restano crediti la differenza non si vede,
        perche' c'e' sempre un impiego migliore per quello slot. Alla fine non
        c'e' piu', e allora il conto si rovescia.

        Misurato su cento aste: **tre volte su cento** il motore chiudeva
        rispondendo &laquo;lascialo&raquo; a ventinove attaccanti di fila con
        quattro slot ancora vuoti in rosa. Non era prudenza, era il piano di
        spesa diventato impossibile: coi riempitivi preventivati a due crediti
        e uno solo in cassa per slot, `opt` non trovava piu' nessuna rosa
        completa e restituiva NEG per chiunque. Il messaggio diceva "quello
        slot rende di piu' su un altro giocatore", e non c'era nessun altro
        giocatore.

        Due condizioni, o l'una o l'altra:

        1. **I crediti non bastano piu' nemmeno per i riempitivi preventivati.**
           Da quel momento ogni slot che resta e' un acquisto da un credito, e
           non c'e' piu' niente da proteggere.
        2. **Il listone del ruolo si sta svuotando**: restano meno giocatori di
           quanti slot la lega deve ancora assegnare. Chi passa la mano adesso
           rischia di non trovarne un altro.
        """
        if self.serve.get(ruolo, 0) <= 0:
            return False
        slot_totali = sum(self.serve.values())
        if slot_totali > 0 and self.budget < COSTO_RIEMPITIVO * slot_totali:
            return True
        try:
            liberi = len(self.v.disponibili(ruolo))
            return liberi <= self.stato.slot_residui_ruolo(ruolo)
        except Exception:
            return False

    def insieme_ottimo(self):
        """Chi compone la rosa ottima adesso: serve per la scorciatoia sopra."""
        if self._ottimo is None:
            fuori = set()
            for r, d in self.piano().get('per_ruolo', {}).items():
                for t in d.get('obiettivi', []):
                    fuori.add(t['id'])
            self._ottimo = fuori
        return self._ottimo

    # ------------------------------------------------------- piano di spesa
    def piano(self):
        """Come conviene distribuire i crediti che restano, e su chi.

        E' la risposta a "posso permettermelo?": la rosa che il motore
        completerebbe adesso, ruolo per ruolo, ai prezzi correnti.
        """
        if self._piano is not None:
            return self._piano
        if self.slot_residui == 0 or self.budget <= 0:
            self._piano = {'per_ruolo': {}, 'crediti': self.budget, 'valore': 0.0}
            return self._piano
        B = self.budget
        righe = [(r, self._riga(r, self.serve[r])) for r in RUOLI]
        acc = righe[0][1]
        quote = []
        for r, riga in righe[1:]:
            acc, q = _fondi_con_traccia(acc, riga, self.surplus)
            quote.append(q)
        residuo = self.surplus
        spesa = {}
        for i in range(len(quote) - 1, -1, -1):
            sinistra = int(quote[i][residuo])
            spesa[righe[i + 1][0]] = residuo - sinistra
            residuo = sinistra
        spesa[righe[0][0]] = residuo
        # Ai crediti liberi si riaggiungono quelli accantonati per reparto.
        for r in RUOLI:
            spesa[r] = spesa.get(r, 0) + self.riserva[r]

        per_ruolo = {}
        for r in RUOLI:
            per_ruolo[r] = {
                'slot': self.serve[r],
                'crediti': spesa.get(r, 0),
                'obiettivi': self._obiettivi(r, self.serve[r], spesa.get(r, 0)),
            }
        spesa_prevista = sum(t['costo'] for r in RUOLI
                             for t in per_ruolo[r]['obiettivi'])
        self._piano = {'per_ruolo': per_ruolo, 'crediti': B,
                       'valore': self.opt(),
                       'spesa_prevista': int(spesa_prevista),
                       'avanzo': int(max(0, B - spesa_prevista))}
        return self._piano

    def _obiettivi(self, ruolo, n, budget):
        """I giocatori che il motore prenderebbe con quel budget in quel ruolo."""
        if n <= 0 or budget <= 0:
            return []
        pool = self._pool(ruolo)
        z = self._tabella(ruolo, traccia=True)
        scelti = self._migliora_riempitivi(ruolo, self._traccia(z, pool, n, budget))
        out = []
        for ident in scelti:
            x = self.v.g.get(ident)
            if x is not None:
                out.append({'id': x.id, 'nome': x.nome, 'squadra': x.squadra,
                            'costo': self.costo[x.id], 'mv': round(x.mv, 2)})
        out.sort(key=lambda d: -d['costo'])
        return out

    def _migliora_riempitivi(self, ruolo, scelti):
        """Fra due riempitivi da un credito, propone quello che almeno gioca.

        Sugli ultimi slot di un reparto il peso di profondita' e' quasi zero:
        l'ottavo centrocampista entra cosi' di rado che, per la funzione da
        massimizzare, prenderne uno da centottanta punti o uno da due e' quasi
        la stessa cosa. Quasi: e la programmazione dinamica, davanti a un
        pareggio, sceglie il primo che le capita.

        Il risultato era un piano che a un credito proponeva gente con zero
        presenze attese mentre a un credito c'erano titolari veri. Nessun danno
        al calcolo &mdash; il valore ottimo non cambia &mdash; ma un piano che
        consiglia un giocatore che non gioca, potendone consigliare uno che
        gioca allo stesso prezzo, non merita di essere creduto sul resto.

        Lo scambio avviene solo a parita' di costo, quindi il budget non si
        muove e l'ottimo non puo' peggiorare.
        """
        def chiave(ident):
            # Sotto la linea di rimpiazzo il valore e' zero per tutti, e sono
            # tutti pari. A parita' conta chi **scende in campo**: un ottavo
            # difensore che gioca ventisette partite, quando ti tocca
            # schierarlo, il voto lo prende; uno che ne gioca due ti lascia con
            # la casella vuota e una sostituzione bruciata.
            #
            # Il criterio e' **solo** questo, e il valore sopra il rimpiazzo si
            # ignora del tutto: a questo livello vale zero virgola qualcosa per
            # tutti, e ordinare per quel numero fa vincere lo scarto di un
            # decimo a chi gioca sei partite contro chi ne gioca trenta. Non e'
            # una preferenza, e' rumore che scavalca un segnale duecento volte
            # piu' grande.
            x = self.v.g.get(ident)
            return (x.presenze or 0.0) * (x.fm or 0.0) if x else 0.0

        scelti = list(scelti)
        presi = set(scelti)
        for i, ident in enumerate(scelti):
            costo = self.costo.get(ident)
            # Riempitivo: costa una miseria e sopra il rimpiazzo non aggiunge
            # nulla che si distingua dal rumore. Non basta guardare il valore:
            # chi gioca due partite con la media appena sopra la linea ha un
            # valore tecnicamente positivo, e sarebbe sfuggito al controllo pur
            # essendo esattamente il caso da correggere.
            if costo is None or costo > COSTO_RIEMPITIVO:
                continue
            if self.valore.get(ident, 0.0) >= VALORE_RIEMPITIVO:
                continue
            migliore, suo = None, chiave(ident)
            for y in self.liberi[ruolo]:
                if y.id in presi or self.costo.get(y.id) != costo:
                    continue
                k = chiave(y.id)
                if k > suo:
                    migliore, suo = y.id, k
            if migliore is not None:
                presi.discard(ident)
                presi.add(migliore)
                scelti[i] = migliore
        return scelti

    @staticmethod
    def _traccia(z, pool, k, budget):
        """Ricostruisce quali giocatori compongono l'ottimo (k, budget)."""
        scelti, c = [], budget
        for i in range(len(pool) - 1, -1, -1):
            if k <= 0:
                break
            righe = z.preso[i] if z.preso and i < len(z.preso) else None
            if not righe:
                continue
            costo = pool[i][0]
            for kk, colonne in righe:
                if kk != k or not colonne:
                    continue
                if c in colonne:
                    scelti.append(pool[i][2])
                    c -= costo
                    k -= 1
                break
        return scelti


# --------------------------------------------------------------------- prova
if __name__ == '__main__':
    import time
    import db as dbmod, regole as regmod, proiezioni as prmod
    from asta import StatoAsta
    from valutazione import Valutatore

    con = dbmod.connetti()
    reg = regmod.carica()
    if con.execute('SELECT COUNT(*) FROM proiezioni').fetchone()[0] == 0:
        prmod.esegui(con, reg)
    stato = StatoAsta(con, reg).inizializza(
        ['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo'], mio_nome='Davide')
    v = Valutatore(con, reg, stato)

    t = time.time()
    o = Ottimizzatore(v)
    print('numpy: %s   preparazione %.0f ms' % (HA_NUMPY, 1000 * (time.time() - t)))
    print('\nProfondita\' di rosa (giornate in campo del k-esimo del reparto):')
    for r in RUOLI:
        print('  %s  disponibilita %.2f  ->  %s' % (
            r, o.disponibilita[r], '  '.join('%.2f' % p for p in o.pesi[r])))
    t = time.time()
    print('\nOPT rosa completabile: %.0f punti   (%.0f ms)'
          % (o.opt(), 1000 * (time.time() - t)))
    print('media difesa di partenza: %.2f   (tappo P %.2f  D %.2f)'
          % (o.media_difesa, o._pad['P'], o._pad['D']))

    print('\n%-20s %-3s %8s %8s %9s %7s' % ('giocatore', 'r', 'mercato',
                                            'max_bid', 'mod.dif', 'ms'))
    for ruolo in RUOLI:
        for x in v.disponibili(ruolo, 3):
            t = time.time()
            limite, d = o.max_bid(x)
            print('%-20s %-3s %8.0f %8d %9.0f %7.0f'
                  % (x.nome[:20], x.ruolo, x.prezzo_mercato, limite,
                     d['contributo_modificatore'], 1000 * (time.time() - t)))

    print('\nPiano di spesa a inizio asta:')
    p = o.piano()
    for r in RUOLI:
        d = p['per_ruolo'][r]
        print('  %s: %2d slot, %3d crediti -> %s'
              % (r, d['slot'], d['crediti'],
                 ', '.join('%s %d' % (t['nome'], t['costo'])
                           for t in d['obiettivi'][:6])))
    con.close()
