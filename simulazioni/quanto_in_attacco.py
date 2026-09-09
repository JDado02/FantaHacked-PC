# -*- coding: utf-8 -*-
"""Conviene obbligare il motore a spendere di piu' in attacco?

Il motore, lasciato libero contro una stanza che paga i prezzi veri, mette in
attacco il 38% dei crediti, contro il 60% che `regole_lega.json` dichiara.
L'obiezione e' seria: **gli attaccanti sono quelli che possono fare piu' gol**,
e in effetti fra un attaccante forte e un riempitivo ballano 78 punti di
stagione, contro i 17 che ballano fra due difensori.

Solo che quei 78 punti costano 71 crediti e quei 17 ne costano 13. Al margine
fanno 1,09 punti per credito in attacco contro 1,35 in difesa: e' quello il
conto che decide, non il numero di gol.

Qui invece di ragionarci si alza il pavimento del reparto e si guarda cosa
succede alla rosa. Il pavimento (`riserva_minima_per_ruolo`) e' la percentuale
del budget che il motore deve comunque destinare a un reparto qualunque cosa
dicano i conti: alzarlo e' esattamente il modo di dirgli "spendi di piu' in
attacco".

Uso:
    python quanto_in_attacco.py 40
"""
import math, multiprocessing, os, statistics, sys, time

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

import cento_aste as cento

NOMI = cento.NOMI
PAVIMENTI = (0.30, 0.40, 0.50, 0.60)


def _pavimento(quota):
    def applica(reg):
        # Gli altri reparti si stringono in proporzione, cosi' la somma resta
        # sotto il cento per cento e il confronto misura lo spostamento verso
        # l'attacco e non un budget gonfiato.
        altri = sum(v for r, v in reg.riserva_ruolo.items() if r != 'A')
        spazio = max(0.0, 0.95 - quota)
        for r in reg.riserva_ruolo:
            if r != 'A' and altri > 0:
                reg.riserva_ruolo[r] = reg.riserva_ruolo[r] / altri * spazio
        reg.riserva_ruolo['A'] = quota
    return applica


def _asta(argomenti):
    seme, quota = argomenti
    e = cento.gioca(seme, 'mercato', patch_reg=_pavimento(quota))
    altri = [p for n, p in e['punti'].items() if n != NOMI[0]]
    return (quota, seme, e['punti'][NOMI[0]], max(altri),
            e['spesa']['A'], e['rischio'], sum(e['slot'].values()))


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    semi = [40000 + 29 * i for i in range(quante)]
    avvio = time.time()
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        righe = pool.map(_asta, [(s, q) for q in PAVIMENTI for s in semi])
    per = {}
    for quota, seme, mio, primo, spesa, risc, slot in righe:
        per.setdefault(quota, {})[seme] = (mio, primo, spesa, risc, slot)
    print('%d aste in %.0f s\n' % (len(righe), time.time() - avvio))
    print('%-22s %8s %9s %12s %10s'
          % ('pavimento in attacco', 'vinte', 'punti', 'contro il 30%',
             'speso in A'))
    base = None
    for quota in PAVIMENTI:
        d = per.get(quota) or {}
        punti = [v[0] for v in d.values()]
        vinte = sum(1 for v in d.values() if v[0] >= v[1])
        med = statistics.median(punti)
        if base is None:
            base = dict((s, v[0]) for s, v in d.items())
            scarto = '-'
        else:
            diff = [v[0] - base[s] for s, v in d.items() if s in base]
            media = statistics.mean(diff)
            err = (statistics.stdev(diff) / math.sqrt(len(diff))
                   if len(diff) > 1 else 0.0)
            scarto = '%+.0f%s' % (media, ' (%.1f)' % (media / err) if err else '')
        print('%-22s %5d/%-3d %9.0f %12s %9.0f%%'
              % ('%.0f%% del budget' % (100 * quota), vinte, len(d), med,
                 scarto, 100 * statistics.mean([v[2] for v in d.values()]) / 500))
    print('\n(fra parentesi lo scarto in errori standard: sotto 2 e\' rumore)')


if __name__ == '__main__':
    main()
