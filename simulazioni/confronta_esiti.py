# -*- coding: utf-8 -*-
"""Le stesse cento aste, con due versioni dei dati: quali sono cambiate.

Il riassunto di `cento_aste.py` dice quante se ne vincono. Non dice **quali**,
e quando il numero si muove &mdash; 98 diventa 92 &mdash; la domanda vera e' se
il motore ha smesso di funzionare o se sono cambiate le carte in tavola.

Le due cose si distinguono guardando le aste una per una, a parita' di seme:
lo stesso ordine di chiamata, gli stessi avversari, gli stessi rilanci. Se il
motore fa gli stessi acquisti e cambia solo il punteggio, il dato nuovo ha
spostato il **metro**, non la decisione. Se cambia proprio quello che compra,
allora la decisione e' diversa, e conviene sapere su chi.

Uso:

    # prima del cambiamento
    python simulazioni/cento_aste.py 100
    copy simulazioni\\cento_aste_mercato.json  prima.json

    # ... si aggiornano i dati, si rifa' la pipeline ...
    python simulazioni/cento_aste.py 100

    python simulazioni/confronta_esiti.py prima.json simulazioni/cento_aste_mercato.json
"""
import io, json, statistics, sys

IO = 'Davide'


def posto(esito):
    p = esito['punti']
    return 1 + sum(1 for n, v in p.items() if n != IO and v > p[IO])


def margine(esito):
    p = esito['punti']
    return p[IO] - max(v for n, v in p.items() if n != IO)


def carica(percorso):
    with io.open(percorso, encoding='utf-8') as f:
        return dict((e['seme'], e) for e in json.load(f)['esiti'])


def main(prima, dopo):
    A, B = carica(prima), carica(dopo)
    semi = sorted(set(A) & set(B))
    if not semi:
        print('Nessun seme in comune: sono due serie diverse.')
        return 1

    va = sum(1 for s in semi if posto(A[s]) == 1)
    vb = sum(1 for s in semi if posto(B[s]) == 1)
    print('%d aste con lo stesso seme' % len(semi))
    print('  vinte   prima %d   dopo %d   (%+d)' % (va, vb, vb - va))
    print('  punti mediani   prima %.0f   dopo %.0f' % (
        statistics.median([A[s]['punti'][IO] for s in semi]),
        statistics.median([B[s]['punti'][IO] for s in semi])))
    print('  margine mediano prima %+.0f  dopo %+.0f' % (
        statistics.median([margine(A[s]) for s in semi]),
        statistics.median([margine(B[s]) for s in semi])))

    # Le aste che hanno cambiato esito, e di quanto: il punteggio del motore e
    # quello del migliore degli altri, prima e dopo. Serve a vedere se a
    # muoversi e' stato lui o la squadra che gli stava dietro.
    cambiate = [(s, posto(A[s]), posto(B[s])) for s in semi
                if (posto(A[s]) == 1) != (posto(B[s]) == 1)]
    if cambiate:
        print('\n%-8s %-14s %-19s %s' % ('seme', 'posto', 'punti del motore',
                                         'il migliore degli altri'))
        for s, pa, pb in cambiate:
            mia, mib = A[s]['punti'][IO], B[s]['punti'][IO]
            ala = max(v for n, v in A[s]['punti'].items() if n != IO)
            alb = max(v for n, v in B[s]['punti'].items() if n != IO)
            print('%-8d %d -> %-10d %6.0f -> %6.0f %+5.0f  %6.0f -> %6.0f %+5.0f'
                  % (s, pa, pb, mia, mib, mib - mia, ala, alb, alb - ala))

    # Chi ha cambiato punteggio, in media, fra tutte e otto le squadre: se si
    # muovono tutte allo stesso modo e' il metro; se si muove solo qualcuno
    # sono le rose.
    print('\nscarto medio di punteggio per squadra:')
    nomi = sorted(A[semi[0]]['punti'])
    for n in nomi:
        d = [B[s]['punti'][n] - A[s]['punti'][n] for s in semi]
        print('  %-10s %+7.1f   (da %+.0f a %+.0f)' % (
            n, sum(d) / len(d), min(d), max(d)))
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
