# -*- coding: utf-8 -*-
"""Dove se ne vanno i punti che la curva costa, reparto per reparto.

`tre_vie.py` dice che pianificare con la curva dei prezzi costa una ventina di
punti di stagione e fa spendere tre crediti in piu'. Dice quanto, non dove.
Qui si guarda la stessa cosa scomposta: crediti e punti reparto per reparto, e
il rapporto fra i due, che e' quanto si sta pagando un punto li' dentro.
"""
import multiprocessing, os, statistics, sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

RUOLI = ('P', 'D', 'C', 'A')


def prova(argomenti):
    seme, peso = argomenti
    import valutazione
    valutazione.PESO_CURVA = peso
    import cento_aste as cento
    e = cento.gioca(seme, 'mercato')
    per_ruolo = dict(
        (r, (sum(g['prezzo'] for g in e['rosa'][r]),
             sum(g['punti'] for g in e['rosa'][r]))) for r in RUOLI)
    return peso, seme, per_ruolo, e['punti']['Davide'], e['avanzati']


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    semi = [7000 + 17 * i for i in range(quante)]
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        righe = pool.map(prova, [(s, w) for w in (0.0, 0.6) for s in semi])
    per = dict(((w, s), (d, pt, av)) for w, s, d, pt, av in righe)

    print('%-6s %25s %25s' % ('', 'senza curva nel piano', 'con la curva'))
    print('%-6s %11s %12s %11s %12s %16s'
          % ('ruolo', 'crediti', 'punti', 'crediti', 'punti', 'crediti/punto'))
    for r in RUOLI:
        a = [per[(0.0, s)][0][r] for s in semi if (0.0, s) in per]
        b = [per[(0.6, s)][0][r] for s in semi if (0.6, s) in per]
        ca, pa = statistics.mean(x[0] for x in a), statistics.mean(x[1] for x in a)
        cb, pb = statistics.mean(x[0] for x in b), statistics.mean(x[1] for x in b)
        print('%-6s %11.0f %12.0f %11.0f %12.0f   %6.3f -> %6.3f'
              % (r, ca, pa, cb, pb, ca / max(pa, 1), cb / max(pb, 1)))
    print()
    for w, eti in ((0.0, 'senza curva nel piano'), (0.6, 'con la curva')):
        pt = [per[(w, s)][1] for s in semi if (w, s) in per]
        av = [per[(w, s)][2] for s in semi if (w, s) in per]
        print('%-22s undici %.0f   crediti avanzati %.1f'
              % (eti, statistics.mean(pt), statistics.mean(av)))


if __name__ == '__main__':
    main()
