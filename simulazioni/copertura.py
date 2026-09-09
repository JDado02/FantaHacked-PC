# -*- coding: utf-8 -*-
"""Quante giornate rischi di restare in dieci.

Il motore massimizza i punti dell'undici titolare, e per farlo pesa ogni
giocatore per le giornate in cui scende davvero in campo. Ma un giocatore che
non gioca mai vale **zero** in quella funzione, non vale **meno di zero**: la
funzione da massimizzare non sa che una casella vuota in formazione non e' un
giocatore che fa zero punti, e' una giornata giocata in dieci.

Qui la domanda si misura invece di discuterla. Per ogni giornata si estrae chi
e' disponibile (ogni giocatore con probabilita' pari alle sue presenze attese
diviso trentotto), si guarda se esiste un modulo ammesso che si possa comporre
con quelli rimasti, e si contano le giornate in cui non esiste.

Il conto sta dalla parte della prudenza in un punto e dalla parte opposta in un
altro, e vale la pena dirlo. Dalla parte prudente: le assenze si estraggono
indipendenti, mentre nella realta' sono correlate (turno infrasettimanale,
sosta per le nazionali) e quindi il rischio vero e' un po' piu' alto di questo.
Dalla parte opposta: si assume di poter usare tutta la panchina, mentre il
regolamento concede cinque sostituzioni.
"""
import os, random, sys

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(QUI)
sys.path.insert(0, os.path.join(BASE, 'motore'))

GIORNATE = 38.0
RUOLI = ('P', 'D', 'C', 'A')

# I moduli ammessi in Classic: difensori, centrocampisti, attaccanti.
MODULI = ((3, 4, 3), (3, 5, 2), (4, 4, 2), (4, 3, 3),
          (4, 5, 1), (5, 3, 2), (5, 4, 1))

# Quante sostituzioni concede il regolamento: oltre quelle, chi non ha preso
# voto resta in formazione con la casella vuota.
SOSTITUZIONI = 5


def schierabile(disp, cambi=SOSTITUZIONI):
    """Riesco a comporre un undici con chi ha preso voto oggi?

    `disp` e' il numero di disponibili per ruolo. Serve almeno un portiere e un
    modulo ammesso che stia dentro i disponibili di ogni reparto.
    """
    if disp['P'] < 1:
        return False
    for d, c, a in MODULI:
        if disp['D'] >= d and disp['C'] >= c and disp['A'] >= a:
            return True
    return False


def buchi(disp):
    """Quante caselle restano vuote, col modulo che ne lascia meno."""
    if not disp['P']:
        mancanti_p = 1
    else:
        mancanti_p = 0
    peggio = 10
    for d, c, a in MODULI:
        manca = (max(0, d - disp['D']) + max(0, c - disp['C'])
                 + max(0, a - disp['A']))
        peggio = min(peggio, manca)
    return mancanti_p + peggio


def _probabilita(rosa):
    """Probabilita' che ognuno prenda voto in una giornata qualunque.

    Con una correzione che cambia il risultato piu' di ogni altra cosa: **due
    portieri della stessa squadra di serie A non sono indipendenti**. Sono i
    due che si dividono la stessa maglia, e in porta ci va sempre qualcuno.
    Trattarli come due monete separate diceva che il sette per cento delle
    giornate si resta senza portiere, il che e' assurdo per chiunque possieda
    un pacchetto intero: la seconda moneta esce testa **proprio** quando la
    prima esce croce.

    Percio' i portieri della stessa squadra si fondono in una probabilita'
    sola, quella che quella maglia prenda voto: alta e vicina a uno.
    """
    prob = {}
    for r in RUOLI:
        prob[r] = [min(1.0, max(0.0, (g['presenze'] or 0) / GIORNATE))
                   for g in rosa[r]]
    per_squadra = {}
    for g in rosa['P']:
        squadra = g.get('squadra')
        if squadra is None:
            continue
        per_squadra.setdefault(squadra, []).append(
            min(1.0, max(0.0, (g['presenze'] or 0) / GIORNATE)))
    if per_squadra and all(g.get('squadra') for g in rosa['P']):
        fuse = []
        for squadra, quote in per_squadra.items():
            if len(quote) >= 2:
                # La maglia e' una: se non gioca il primo gioca il secondo.
                # Si tiene un margine per squalifiche e infortuni contemporanei.
                fuse.append(min(0.99, max(quote) + 0.9 * sum(sorted(quote)[:-1])))
            else:
                fuse.append(quote[0])
        prob['P'] = fuse
    return prob


def rischio(rosa, giornate=20000, seme=1):
    """Probabilita' di non riuscire a schierare undici, e buchi medi."""
    rng = random.Random(seme)
    prob = _probabilita(rosa)
    incomplete = 0
    somma_buchi = 0
    for _ in range(giornate):
        disp = {}
        for r in RUOLI:
            disp[r] = sum(1 for p in prob[r] if rng.random() < p)
        if not schierabile(disp):
            incomplete += 1
            somma_buchi += buchi(disp)
    return (incomplete / float(giornate),
            somma_buchi / float(giornate))


def relazione(rosa, nome=''):
    q, b = rischio(rosa)
    righe = []
    righe.append('%-12s giornate a rischio %5.1f%%   caselle vuote per giornata %.2f'
                 % (nome, 100 * q, b))
    for r in RUOLI:
        attese = sum((g['presenze'] or 0) / GIORNATE for g in rosa[r])
        righe.append('   %s: %d giocatori, %.1f disponibili in media  (%s)'
                     % (r, len(rosa[r]), attese,
                        ', '.join('%d' % (g['presenze'] or 0) for g in rosa[r])))
    return '\n'.join(righe)
