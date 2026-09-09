# -*- coding: utf-8 -*-
"""Analisi di un'asta gia' giocata, letta da un CSV di rose.

Il file di partenza e' quello che esporta la piattaforma: una riga per
giocatore con squadra fantacalcio, prezzo pagato e id ufficiale. Qui si
risponde alle domande che ci si fa il giorno dopo:

  - chi ha fatto la rosa piu' forte, e di quanto;
  - chi ha pagato bene e chi ha pagato male, rispetto a quanto valeva;
  - chi rischia di restare in dieci;
  - dove sono finiti i crediti, reparto per reparto.

I punti sono quelli del **nostro** modello di proiezioni, modificatore di
difesa compreso. E' il metro di questo programma, non una verita': la
stagione dira' chi aveva ragione.

Uso:  python analizza_asta.py "C:/percorso/rose.csv"
"""
import collections, csv, io, os, random, statistics, sys, unicodedata

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

import percorsi, db as dbmod, regole as regmod
from asta import StatoAsta
from valutazione import Valutatore
from modificatore import Modificatore
import copertura

RUOLI = ('P', 'D', 'C', 'A')
NOME_RUOLO = {'P': 'portieri', 'D': 'difensori',
              'C': 'centrocampisti', 'A': 'attaccanti'}


def _norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return ''.join(ch for ch in s.lower() if ch.isalnum())


def carica(percorso, v):
    """Le rose del file, con accanto quello che il motore sa di ogni giocatore."""
    per_nome = collections.defaultdict(list)
    for x in v.g.values():
        per_nome[_norm(x.nome)].append(x)

    rose = collections.defaultdict(lambda: dict((r, []) for r in RUOLI))
    persi = []
    for r in csv.DictReader(io.open(percorso, encoding='utf-8')):
        x = v.g.get(int(r['Fantacalcio_Id']))
        if x is None:
            cand = per_nome.get(_norm(r['Nome']))
            x = cand[0] if cand and len(cand) == 1 else None
        if x is None:
            persi.append(r['Nome'])
            continue
        rose[r['Squadra']][x.ruolo].append({
            'nome': x.nome, 'squadra': x.squadra, 'prezzo': int(r['Prezzo']),
            'presenze': int(round(x.presenze or 0)), 'mv': x.mv or 0.0,
            'punti': round((x.presenze or 0) * (x.fm or 0)),
            'base': x.prezzo_base or 1.0,
        })
    return rose, persi


QUANTI = {'P': 1, 'D': 4, 'C': 4, 'A': 2}
GIORNATE = 38


def di_giornata(rosa, reg, tiri=4000, seme=5):
    """Punti di stagione schierando ogni domenica chi e' disponibile.

    `undici()` qui sotto somma i punti di stagione dei migliori undici, e
    suppone che siano sempre quelli a giocare: quando uno salta una partita
    quella casella fa zero. E' comodo e sottovaluta due cose insieme &mdash;
    la panchina, che nella realta' entra, e chi rende tanto ma gioca poco.

    Kean e' il caso da manuale: fantamedia 7,61 su 25 partite, contro un
    compagno di reparto da 7,00 su 28. Sul totale di stagione il secondo sta
    davanti; ma nelle venticinque domeniche in cui Kean c'e' schieri **lui**,
    e nelle altre tredici schieri l'altro. Contarlo come riserva e' un errore
    del metro, non un giudizio sul giocatore.

    Qui ogni giornata si estrae chi c'e' e si schiera il meglio disponibile.
    L'ipotesi e' che le assenze siano indipendenti: e' una semplificazione
    (un'influenza in spogliatoio ne ferma tre insieme), e tende quindi a
    essere un filo ottimista sulle rose profonde.
    """
    rnd = random.Random(seme)
    per_ruolo = {}
    for r in RUOLI:
        per_ruolo[r] = [(d['punti'] / max(1.0, d['presenze']) if d['presenze'] else 0.0,
                         min(1.0, d['presenze'] / float(GIORNATE)))
                        for d in rosa[r]]
    tot = 0.0
    for _ in range(tiri):
        for r in RUOLI:
            disp = sorted((fm for fm, p in per_ruolo[r] if rnd.random() < p),
                          reverse=True)
            tot += sum(disp[:QUANTI[r]])
    tot = tot / tiri * GIORNATE
    return tot + _modificatore(rosa, reg)


def _modificatore(rosa, reg):
    """I punti che porta il modificatore di difesa, se la lega lo usa."""
    mod = Modificatore(reg)
    if not mod.attivo:
        return 0.0
    por = sorted(rosa['P'], key=lambda d: -d['mv'])[:reg.mod_dif_n_por]
    dif = sorted(rosa['D'], key=lambda d: -d['mv'])[:reg.mod_dif_n_dif]
    scelti = por + dif
    if len(scelti) != reg.mod_dif_n_por + reg.mod_dif_n_dif:
        return 0.0
    return mod.punti_stagione(sum(d['mv'] for d in scelti) / len(scelti))


def undici(rosa, reg):
    """Punti di stagione dell'undici migliore, modificatore compreso."""
    quanti = QUANTI
    tot = 0.0
    for r in RUOLI:
        migliori = sorted(rosa[r], key=lambda d: -d['punti'])[:quanti[r]]
        tot += sum(d['punti'] for d in migliori)
    mod = Modificatore(reg)
    if mod.attivo:
        por = sorted(rosa['P'], key=lambda d: -d['mv'])[:reg.mod_dif_n_por]
        dif = sorted(rosa['D'], key=lambda d: -d['mv'])[:reg.mod_dif_n_dif]
        scelti = por + dif
        if len(scelti) == reg.mod_dif_n_por + reg.mod_dif_n_dif:
            media = sum(d['mv'] for d in scelti) / len(scelti)
            tot += mod.punti_stagione(media)
    return tot


def main():
    percorso = sys.argv[1] if len(sys.argv) > 1 else None
    if not percorso:
        print('Uso: python analizza_asta.py <file rose.csv>')
        return 1
    con = dbmod.connetti()
    reg = regmod.carica()
    st = StatoAsta(con, reg)
    if not st.esiste():
        st.inizializza(['A', 'B', 'C', 'D', 'E', 'F', 'G'], mio_nome='Io')
    v = Valutatore(con, reg, st)
    rose, persi = carica(percorso, v)
    if persi:
        print('Non trovati a listone: %s\n' % ', '.join(persi))

    dati = []
    for squadra, rosa in rose.items():
        pt = undici(rosa, reg)
        pt_g = di_giornata(rosa, reg)
        spesa = dict((r, sum(d['prezzo'] for d in rosa[r])) for r in RUOLI)
        rischio = copertura.rischio(rosa, giornate=8000, seme=7)[0]
        valore = sum(d['base'] for r in RUOLI for d in rosa[r])
        pagato = sum(spesa.values())
        dati.append({'squadra': squadra, 'punti': pt, 'spesa': spesa,
                     'pagato': pagato, 'valore': valore, 'rischio': rischio,
                     'giornata': pt_g,
                     'rosa': rosa})
    dati.sort(key=lambda d: -d['punti'])

    print('=' * 74)
    print('CLASSIFICA SECONDO IL MOTORE  (punti di stagione dell\'undici tipo)')
    print('=' * 74)
    print('%-3s %-24s %8s %9s %9s %10s %10s'
          % ('', 'squadra', 'punti', 'di giorn.', 'spesi', 'in dieci', 'affare'))
    primo = dati[0]['punti']
    for i, d in enumerate(dati, start=1):
        affare = d['valore'] - d['pagato']
        print('%-3d %-24s %8.0f %9.0f %9d %7.1f/38 %+10.0f'
              % (i, d['squadra'], d['punti'], d['giornata'], d['pagato'],
                 38 * d['rischio'], affare))
        if i == 1:
            continue
    print('\nscarto fra primo e ultimo: %.0f punti (%.1f%%)'
          % (primo - dati[-1]['punti'],
             100 * (primo - dati[-1]['punti']) / primo))

    per_giornata = sorted(dati, key=lambda d: -d['giornata'])
    if [d['squadra'] for d in per_giornata] != [d['squadra'] for d in dati]:
        print()
        print("Schierando ogni domenica chi e' disponibile l'ordine cambia:")
        for i, d in enumerate(per_giornata, start=1):
            print('  %d  %-24s %6.0f' % (i, d['squadra'], d['giornata']))
    print('\n' + '=' * 74)
    print('DOVE SONO FINITI I CREDITI')
    print('=' * 74)
    print('%-24s %7s %7s %7s %7s' % ('squadra', 'P', 'D', 'C', 'A'))
    for d in dati:
        print('%-24s %6.0f%% %6.0f%% %6.0f%% %6.0f%%'
              % (d['squadra'],
                 *[100.0 * d['spesa'][r] / max(1, d['pagato']) for r in RUOLI]))
    medie = dict((r, statistics.mean([100.0 * d['spesa'][r] / max(1, d['pagato'])
                                      for d in dati])) for r in RUOLI)
    print('%-24s %6.0f%% %6.0f%% %6.0f%% %6.0f%%'
          % ('media della stanza', *[medie[r] for r in RUOLI]))

    print('\n' + '=' * 74)
    print('I COLPI E GLI ERRORI  (prezzo pagato contro quanto valeva)')
    print('=' * 74)
    tutti = [(d['squadra'], g) for d in dati for r in RUOLI for g in d['rosa'][r]]
    scarti = sorted(tutti, key=lambda t: t[1]['base'] - t[1]['prezzo'])
    print('\nPagati piu\' di quanto valessero:')
    for sq, g in scarti[:10]:
        print('  %-22s %-20s %4d crediti, ne valeva %3.0f   (%+.0f)'
              % (sq, g['nome'], g['prezzo'], g['base'], g['base'] - g['prezzo']))
    print('\nPresi sotto il loro valore:')
    for sq, g in scarti[-10:][::-1]:
        print('  %-22s %-20s %4d crediti, ne valeva %3.0f   (%+.0f)'
              % (sq, g['nome'], g['prezzo'], g['base'], g['base'] - g['prezzo']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
