# -*- coding: utf-8 -*-
"""La mia squadra, com'e' adesso: undici titolare, coperture, rischi.

Il resto del motore risponde a domande su un giocatore alla volta. Questo
modulo risponde all'unica domanda che conta davvero a fine asta: **che squadra
sto costruendo?**

Non e' un riassunto grafico degli acquisti. E' un conto vero:

  - qual e' il miglior undici che riesco a schierare, e con che modulo;
  - quanti punti a giornata vale, modificatore di difesa compreso;
  - quali caselle sono coperte da un titolare sicuro e quali da una scommessa;
  - quanti rigoristi ho, che nel fantacalcio e' mezza differenza fra due rose
    altrimenti identiche;
  - quanto sono esposto su una sola squadra di serie A.

Tutto ricalcolato a ogni acquisto, mio o altrui: quando un avversario porta via
un difensore, cambia chi resta sul mercato e quindi cambia cosa mi manca.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RUOLI = ('P', 'D', 'C', 'A')

# I moduli ammessi in Classic. L'undici migliore si sceglie fra questi: non ha
# senso valutare una rosa con un modulo che non si puo' schierare.
MODULI = [
    ('343', {'P': 1, 'D': 3, 'C': 4, 'A': 3}),
    ('352', {'P': 1, 'D': 3, 'C': 5, 'A': 2}),
    ('442', {'P': 1, 'D': 4, 'C': 4, 'A': 2}),
    ('433', {'P': 1, 'D': 4, 'C': 3, 'A': 3}),
    ('451', {'P': 1, 'D': 4, 'C': 5, 'A': 1}),
    ('532', {'P': 1, 'D': 5, 'C': 3, 'A': 2}),
    ('541', {'P': 1, 'D': 5, 'C': 4, 'A': 1}),
]

# Sotto questa quota di presenze una casella dell'undici non e' coperta: quel
# posto, qualche giornata, andra' riempito dalla panchina.
QUOTA_COPERTA = 0.72

# Da qui in su vale la pena avvisare che si rischia di restare in dieci. Tre
# giornate su trentotto: sotto, e' il rumore di fondo che ha qualunque rosa
# fatta bene, e un avviso che compare sempre non lo legge nessuno.
SOGLIA_RISCHIO = 0.08


GIORNATE = 38.0


def _fm(x):
    return x.fm or 0.0


def _distribuzione(quote):
    """P(esattamente k disponibili), da probabilita' indipendenti.

    E' la Poisson-binomiale, costruita a mano un giocatore alla volta: con
    otto giocatori per reparto sono sessanta moltiplicazioni, e il risultato e'
    esatto invece che simulato. Un numero che compare a schermo a ogni acquisto
    non deve tremare per via del seme del generatore.
    """
    d = [1.0]
    for p in quote:
        p = min(1.0, max(0.0, p))
        nuovo = [0.0] * (len(d) + 1)
        for k, v in enumerate(d):
            nuovo[k] += v * (1.0 - p)
            nuovo[k + 1] += v * p
        d = nuovo
    return d


def _formazione(dist):
    """(probabilita' di schierare undici, caselle vuote attese a giornata)."""
    p_portiere = 1.0 - dist['P'][0]
    completa = 0.0
    buchi = dist['P'][0] * 1.0        # senza portiere, quella casella e' vuota
    for d, pd in enumerate(dist['D']):
        if pd <= 0:
            continue
        for c, pc in enumerate(dist['C']):
            if pc <= 0:
                continue
            for a, pa in enumerate(dist['A']):
                if pa <= 0:
                    continue
                peso = pd * pc * pa
                manca = min(max(0, m['D'] - d) + max(0, m['C'] - c)
                            + max(0, m['A'] - a) for _, m in MODULI)
                if manca == 0:
                    completa += peso
                buchi += peso * manca
    return p_portiere * completa, buchi


class Equilibrio(object):
    """Fotografia della mia rosa, ricalcolata sullo stato corrente."""

    def __init__(self, valutatore, ottimizzatore):
        self.v = valutatore
        self.o = ottimizzatore
        self.reg = valutatore.reg
        self.stato = valutatore.stato

    # ------------------------------------------------------------- la rosa
    def rosa(self):
        io = self.stato.io()['id']
        out = dict((r, []) for r in RUOLI)
        for a in self.stato.acquisti():
            if a['presidente_id'] != io:
                continue
            x = self.v.g.get(a['giocatore_id'])
            if x is not None:
                out[x.ruolo].append(x)
        for r in RUOLI:
            out[r].sort(key=lambda x: -_fm(x))
        return out

    # ------------------------------------------------------- undici titolare
    def undici(self, rosa=None):
        """Il miglior undici schierabile, e con che modulo.

        Se un reparto non e' ancora completo le caselle scoperte restano
        vuote: mostrare una rosa finta a meta' asta non aiuterebbe nessuno.
        """
        rosa = rosa if rosa is not None else self.rosa()
        migliore = None
        for nome, forma in MODULI:
            scelti, valore, mancanti = {}, 0.0, 0
            for r in RUOLI:
                presi = rosa[r][:forma[r]]
                scelti[r] = presi
                valore += sum(_fm(x) for x in presi)
                mancanti += forma[r] - len(presi)
            # Le caselle vuote valgono la media di un riempitivo: senza questo
            # il confronto fra moduli premierebbe sempre quello che chiede meno
            # giocatori nei reparti che non ho ancora comprato.
            valore += mancanti * 5.5
            punteggio = valore
            if migliore is None or punteggio > migliore[0]:
                migliore = (punteggio, nome, forma, scelti, mancanti)
        _, nome, forma, scelti, mancanti = migliore
        elenco = []
        for r in RUOLI:
            for x in scelti[r]:
                elenco.append(self.voce(x))
            for _ in range(forma[r] - len(scelti[r])):
                elenco.append({'ruolo': r, 'vuoto': True})
        somma = sum(_fm(x) for r in RUOLI for x in scelti[r])
        return {'modulo': nome, 'forma': forma, 'giocatori': elenco,
                'caselle_vuote': mancanti,
                'fantamedia': round(somma, 1),
                'bonus_difesa': round(self._bonus_difesa(scelti), 2),
                'punti_giornata': round(somma + self._bonus_difesa(scelti), 1)}

    def _bonus_difesa(self, scelti):
        if not self.o.mod.attivo:
            return 0.0
        mv = [x.mv for x in scelti.get('P', [])][:self.reg.mod_dif_n_por]
        mv += [x.mv for x in scelti.get('D', [])][:self.reg.mod_dif_n_dif]
        quanti = self.reg.mod_dif_n_por + self.reg.mod_dif_n_dif
        if len(mv) < quanti:
            # Nucleo incompleto: si completa col livello di chi e' ancora sul
            # mercato, altrimenti il bonus sembrerebbe zero fino all'ultimo
            # acquisto e poi salterebbe di colpo.
            mv = mv + [self.o._pad['D']] * (quanti - len(mv))
        return self.reg.bonus_modificatore(sum(mv) / float(len(mv)))

    # -------------------------------------------------------------- voci
    def voce(self, x):
        return {
            'id': x.id, 'nome': x.nome, 'squadra': x.squadra, 'ruolo': x.ruolo,
            'fm': round(_fm(x), 2), 'mv': round(x.mv or 0, 2),
            'presenze': int(round(x.presenze or 0)),
            'titolarita': round(x.titolarita or 0, 2),
            'grado': x.grado or 'ignoto',
            'certezza': round(x.certezza or 0, 2),
            'sicuro': bool(x.sicuro),
            'rigorista': int(x.rigorista or 0),
        }

    # ------------------------------------------- rischio di restare in dieci
    #
    # E' la domanda che nessun'altra parte del motore fa. L'ottimizzatore
    # massimizza i punti dell'undici, e per farlo pesa ogni giocatore per le
    # giornate in cui scende davvero in campo: uno che non gioca mai vale
    # **zero** in quella funzione. Ma una casella vuota in formazione non e' un
    # giocatore che fa zero punti, e' una giornata giocata in dieci, e la
    # funzione da massimizzare non lo sa.
    #
    # Finche' i conti tornano non e' un problema. Il guaio arriva riempiendo la
    # panchina di fantamedie alte prodotte da cinque presenze: in rosa ci sono,
    # in campo no. Misurato su una rosa cosi', il rischio passa dal 2% al 58%
    # delle giornate. Qui il numero si vede mentre si compra, non a dicembre.
    def rischio_undici(self, rosa=None):
        """Quante giornate su 38 rischi di non riuscire a schierare undici.

        Il conto e' esatto, non simulato: con al massimo otto giocatori per
        reparto la distribuzione di quanti ne saranno disponibili si calcola
        per intero, e si somma su tutte le combinazioni che un modulo ammesso
        riesce a coprire.

        Gli slot ancora da comprare contano come un giocatore normale di quel
        reparto, altrimenti a inizio asta il rischio sarebbe del cento per
        cento: vero, e inutile. La domanda a cui risponde e' **se completi la
        rosa cosi' come stai andando**, non "se l'asta finisse adesso".

        Due assunzioni, e vanno dette perche' tirano in direzioni opposte. Le
        assenze si estraggono indipendenti, mentre nella realta' sono correlate
        (turni infrasettimanali, soste per le nazionali): il rischio vero e' un
        po' piu' alto di questo. Ma i portieri della stessa squadra di serie A
        no: quelli si dividono una maglia sola, e in porta ci va sempre
        qualcuno.
        """
        if rosa is None:
            rosa = self.rosa()
        prob = self._disponibilita(rosa)
        dist = dict((r, _distribuzione(prob[r])) for r in RUOLI)
        completa, buchi = _formazione(dist)
        return {
            'quota': round(1.0 - completa, 4),
            'giornate': round((1.0 - completa) * GIORNATE, 1),
            'caselle_vuote': round(buchi, 3),
            'reparto_stretto': self._collo_di_bottiglia(dist, completa),
            'disponibili': dict((r, round(sum(prob[r]), 1)) for r in RUOLI),
            'da_comprare': dict((r, max(0, self.reg.slot[r] - len(rosa[r])))
                                for r in RUOLI),
        }

    def _disponibilita(self, rosa):
        """Con che probabilita' ognuno prende voto in una giornata qualunque.

        I portieri della stessa squadra si fondono in una probabilita' sola.
        Trattarli come due monete separate direbbe che il sette per cento delle
        giornate si resta senza portiere, il che e' assurdo per chi possiede un
        pacchetto intero: la seconda moneta esce testa **proprio** quando la
        prima esce croce.
        """
        prob = {}
        for r in RUOLI:
            quote, per_squadra = [], {}
            for x in rosa[r]:
                q = min(1.0, max(0.0, (x.presenze or 0.0) / GIORNATE))
                if r == 'P':
                    per_squadra.setdefault(x.squadra, []).append(q)
                else:
                    quote.append(q)
            for _, insieme in sorted(per_squadra.items()):
                insieme.sort(reverse=True)
                if len(insieme) >= 2:
                    # Una maglia sola: se non gioca il primo gioca il secondo.
                    # Il margine copre le giornate in cui sono fermi entrambi.
                    quote.append(min(0.99, insieme[0] + 0.9 * sum(insieme[1:])))
                else:
                    quote.append(insieme[0])
            # Gli slot ancora da riempire contano come un giocatore medio di
            # quel reparto: la disponibilita' e' quella che l'ottimizzatore
            # misura sul mercato, non una costante scritta a mano.
            mancano = max(0, self.reg.slot[r] - len(rosa[r]))
            if r == 'P':
                # I portieri arrivano a pacchetto: gli slot scoperti sono le
                # riserve del titolare che comprero', non altre maglie.
                mancano = 0 if quote else 1
            tipica = getattr(self.o, 'disponibilita', {}).get(r, 0.75)
            quote.extend([tipica] * mancano)
            prob[r] = quote
        return prob

    def _collo_di_bottiglia(self, dist, completa):
        """Il reparto che, con un giocatore in piu', toglierebbe piu' rischio.

        Non si indovina: si rifa' il conto quattro volte, una per reparto,
        aggiungendo un giocatore sempre disponibile, e si guarda dove il
        rischio scende di piu'.
        """
        migliore, guadagno = None, 0.0
        for r in RUOLI:
            piu_uno = dict(dist)
            piu_uno[r] = [0.0] + list(dist[r])     # uno in piu', sempre presente
            nuova, _ = _formazione(piu_uno)
            if nuova - completa > guadagno:
                migliore, guadagno = r, nuova - completa
        if migliore is not None and guadagno >= 0.002:
            return {'ruolo': migliore, 'guadagno': round(guadagno, 4)}

        # Nessun reparto, da solo, sposta il risultato. Non vuol dire che vada
        # tutto bene: vuol dire che ne mancano piu' d'uno, e sono proprio i
        # casi in cui serve sapere da dove cominciare. Si indica allora il
        # reparto che resta piu' lontano dal minimo che un modulo gli chiede.
        peggiore, distanza = None, 0.0
        for r in ('P', 'D', 'C', 'A'):
            if r == 'P':
                manca = dist['P'][0]
            else:
                minimo = min(m[r] for _, m in MODULI)
                manca = sum(p * max(0, minimo - k)
                            for k, p in enumerate(dist[r]))
            if manca > distanza:
                peggiore, distanza = r, manca
        if peggiore is None or distanza <= 0.01:
            return None
        return {'ruolo': peggiore, 'guadagno': 0.0,
                'caselle_mancanti': round(distanza, 2)}

    # --------------------------------------------------------- il quadro
    def quadro(self):
        rosa = self.rosa()
        undici = self.undici(rosa)
        forma = undici['forma']
        copertura, avvisi = {}, []

        for r in RUOLI:
            presi = rosa[r]
            sicuri = [x for x in presi if x.sicuro]
            servono = forma[r]
            copertura[r] = {
                'in_rosa': len(presi),
                'slot': self.reg.slot[r],
                'nell_undici': servono,
                'titolari_sicuri': len(sicuri),
                'da_verificare': len([x for x in presi if not x.sicuro]),
                'scoperte': max(0, servono - len(sicuri)),
            }

        rigoristi = [self.voce(x) for r in RUOLI for x in rosa[r]
                     if (x.rigorista or 0) == 1]
        # Quanti giocatori ho della stessa squadra di serie A. Averne tanti
        # raddoppia i colpi quando quella squadra gira e li raddoppia anche
        # quando si inceppa: e' varianza, non valore.
        per_squadra = {}
        for r in RUOLI:
            for x in rosa[r]:
                per_squadra[x.squadra] = per_squadra.get(x.squadra, 0) + 1
        concentrazione = sorted(per_squadra.items(), key=lambda t: -t[1])

        totali = sum(len(rosa[r]) for r in RUOLI)
        sicuri_totali = sum(1 for r in RUOLI for x in rosa[r] if x.sicuro)

        # --- avvisi -------------------------------------------------------
        # Solo quando c'e' ancora modo di rimediare **e** il tempo comincia a
        # stringere. A inizio asta ogni casella e' scoperta: dirlo sarebbe
        # vero e inutile, e un avviso che compare sempre non lo legge nessuno.
        for r in RUOLI:
            c = copertura[r]
            manca_ancora = self.reg.slot[r] - c['in_rosa']
            if c['scoperte'] > 0 and 0 < manca_ancora <= c['scoperte'] + 1:
                avvisi.append({
                    'tipo': 'copertura', 'ruolo': r,
                    'testo': ('Nell\'undici %s hai %d caselle che oggi non sono '
                              'coperte da un titolare sicuro, e ti restano solo '
                              '%d acquisti in quel reparto.'
                              % (_nome_ruolo(r), c['scoperte'], manca_ancora))})
        meta_reparti_avanzati = (len(rosa['A']) + len(rosa['C'])
                                 >= (self.reg.slot['A'] + self.reg.slot['C']) / 2.0)
        if not rigoristi and meta_reparti_avanzati and (
                self.reg.slot['A'] + self.reg.slot['C']
                - len(rosa['A']) - len(rosa['C'])) > 0:
            avvisi.append({
                'tipo': 'rigoristi',
                'testo': ("Non hai nessun rigorista designato. Sono cinque o sei "
                          "gol garantiti a stagione: valgono piu' di una "
                          "fantamedia leggermente piu' alta.")})
        if concentrazione and concentrazione[0][1] >= 5:
            avvisi.append({
                'tipo': 'concentrazione',
                'testo': ('Hai %d giocatori del %s. Se quella squadra si inceppa '
                          'si inceppa mezza rosa: da qui in avanti guarda '
                          'altrove.'
                          % (concentrazione[0][1], concentrazione[0][0]))})

        # Il rischio di restare in dieci: e' l'unico numero del quadro che
        # non parla di quanto la rosa rende, ma di quante volte riesci a
        # metterla in campo.
        rischio = self.rischio_undici(rosa)
        if rischio['quota'] >= SOGLIA_RISCHIO:
            stretto = rischio.get('reparto_stretto') or {}
            dove = ((" Il reparto che ti tiene fermo e' quello %s."
                     % _nome_ruolo(stretto['ruolo']))
                    if stretto.get('ruolo') else '')
            avvisi.append({
                'tipo': 'rischio', 'ruolo': stretto.get('ruolo'),
                'testo': ('Con questa rosa rischi di non riuscire a schierare '
                          'undici in circa %s giornate su 38: in rosa quei '
                          'giocatori ci sono, in campo no.%s'
                          % (_giornate(rischio['giornate']), dove))})

        return {
            'undici': undici,
            'copertura': copertura,
            'rischio': rischio,
            'rigoristi': rigoristi,
            'concentrazione': [{'squadra': s, 'quanti': n}
                               for s, n in concentrazione[:4]],
            'in_rosa': totali,
            'titolari_sicuri': sicuri_totali,
            'avvisi': avvisi,
        }


def _giornate(n):
    """"due" invece di "2.0", che a schermo si legge meglio."""
    if n < 1.5:
        return 'una'
    return '%d' % round(n)


def _nome_ruolo(r):
    return {'P': 'in porta', 'D': 'in difesa', 'C': 'a centrocampo',
            'A': 'in attacco'}[r]
