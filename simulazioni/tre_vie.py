# -*- coding: utf-8 -*-
"""Tre modi di prezzare, sulle stesse aste. Confronto appaiato.

  1. **come prima**    &mdash; niente curva: si mostra e si pianifica col merito.
  2. **curva ovunque** &mdash; la curva dei prezzi sia mostrata sia pianificata.
  3. **curva divisa**  &mdash; la curva si mostra, il piano resta al merito.

La terza e' l'ipotesi: il numero da mostrare e il numero con cui pianificare
non sono lo stesso numero. `max_bid` e' un punto di indifferenza calcolato
contro il piano, quindi un piano ottimista sui sostituti abbassa i limiti e fa
lasciar perdere piu' spesso &mdash; ed e' lasciando perdere che si vince
un'asta.

Uso:
    python tre_vie.py 60
"""
import math, multiprocessing, os, statistics, sys, time

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

import cento_aste as cento

NOMI = cento.NOMI
VIE = ('come prima', 'curva ovunque', 'curva divisa')


def _prova(argomenti):
    seme, via = argomenti
    import valutazione, ottimizzatore
    valutazione.PESO_CURVA = 0.0 if via == 'come prima' else 0.6
    # "curva ovunque" = il piano usa lo stesso prezzo che si mostra.
    ottimizzatore.PIANO_SEPARATO = (via == 'curva divisa')
    try:
        e = cento.gioca(seme, 'mercato')
        altri = [p for n, p in e['punti'].items() if n != NOMI[0]]
        return (via, seme, e['punti'][NOMI[0]], max(altri), e['avanzati'],
                e['rischio'], sum(e['slot'].values()))
    except Exception as exc:
        return (via, seme, None, None, None, None, repr(exc))


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    semi = [5000 + 11 * i for i in range(quante)]
    compiti = [(s, v) for v in VIE for s in semi]
    avvio = time.time()
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        righe = pool.map(_prova, compiti)
    print('%d aste in %.0f s\n' % (len(righe), time.time() - avvio))

    d = {}
    for via, seme, mio, primo, avanzo, risc, slot in righe:
        if mio is not None:
            d[(via, seme)] = (mio, primo, avanzo, risc, slot)

    print('%-16s %8s %10s %12s %10s %9s'
          % ('via', 'vinte', 'punti', 'contro (1)', 'in dieci', 'avanzati'))
    riferimento = None
    for via in VIE:
        coppie = [(s, d[(via, s)]) for s in semi if (via, s) in d]
        if not coppie:
            continue
        punti = [v[0] for _, v in coppie]
        vinte = sum(1 for _, v in coppie if v[0] >= v[1])
        riga = ('%-16s %5d/%-3d %10.0f' % (via, vinte, len(coppie),
                                           statistics.median(punti)))
        if riferimento is None:
            riferimento = dict((s, v[0]) for s, v in coppie)
            riga += '%12s' % '-'
        else:
            diff = [v[0] - riferimento[s] for s, v in coppie if s in riferimento]
            media = statistics.mean(diff)
            err = (statistics.stdev(diff) / math.sqrt(len(diff))
                   if len(diff) > 1 else 0.0)
            riga += '%9.0f%s' % (media, ' (%.1f)' % (media / err) if err else '')
        riga += '%10.1f %9.1f' % (
            38 * statistics.median([v[3] for _, v in coppie]),
            statistics.mean([v[2] for _, v in coppie]))
        print(riga)
    print('\n(fra parentesi lo scarto in errori standard: sotto 2 e\' rumore)')
    incomplete = [(via, s) for via in VIE for s in semi
                  if (via, s) in d and d[(via, s)][4] < 25]
    print('rose incomplete: %d su %d' % (len(incomplete), len(d)))


if __name__ == '__main__':
    main()
