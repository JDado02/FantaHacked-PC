# -*- coding: utf-8 -*-
"""La curva dei prezzi conviene al tavolo? Confronto appaiato, due stanze.

`manopole.py` ha dato un risultato scomodo: la curva dei prezzi &mdash; che
sbaglia molto meno sui prezzi realmente pagati &mdash; sembrava **costare** una
ventina di punti in asta. Prima di crederci ci sono due cose da fare.

**Appaiare.** Confrontare due mediane di trenta aste diverse misura soprattutto
la fortuna. Qui ogni seme si gioca due volte, una per posizione della manopola,
e si guarda la differenza asta per asta.

**Sospettare degli avversari.** Il rumore umano di `cinque_aste.py` e' centrato
**sopra** l'uno (da 1,05 sui portieri a 1,22 sugli attaccanti): sono avversari
che per costruzione pagano troppo. Contro una stanza cosi' la strategia
vincente e' tirare al ribasso, e qualunque modello che alzi i prezzi attesi
fara' peggio &mdash; non perche' sbagli, ma perche' assomiglia di piu' a loro.
Quindi la stessa prova si rifa' con avversari **non distorti**, centrati
sull'uno, che sbagliano in entrambi i versi. Se il vantaggio sparisce li',
era una proprieta' della stanza finta e non del motore.

Uso:
    python curva_appaiato.py 50
"""
import math, multiprocessing, os, statistics, sys, time

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

import cento_aste as cento
import cinque_aste as base

NOMI = cento.NOMI
IMPARZIALE = dict((r, (1.0, s)) for r, (m, s) in base.RUMORE.items())


def _prova(argomenti):
    seme, peso, stanza = argomenti
    import valutazione
    valutazione.PESO_CURVA = peso
    base.RUMORE = IMPARZIALE if stanza == 'imparziale' else _ORIGINALE
    try:
        e = cento.gioca(seme, 'mercato')
        altri = [p for n, p in e['punti'].items() if n != NOMI[0]]
        return (seme, peso, stanza, e['punti'][NOMI[0]], max(altri),
                e['avanzati'], e['rischio'], sum(e['slot'].values()))
    except Exception as exc:
        return (seme, peso, stanza, None, None, None, None, repr(exc))


_ORIGINALE = dict(base.RUMORE)


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    semi = [3000 + 13 * i for i in range(quante)]
    compiti = [(s, p, st) for st in ('come adesso', 'imparziale')
               for p in (0.0, 0.6) for s in semi]
    avvio = time.time()
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        righe = pool.map(_prova, compiti)
    print('%d aste in %.0f s\n' % (len(righe), time.time() - avvio))

    dati = {}
    for seme, peso, stanza, mio, primo, avanzo, risc, slot in righe:
        if mio is None:
            continue
        dati[(stanza, peso, seme)] = (mio, primo, avanzo, risc, slot)

    for stanza in ('come adesso', 'imparziale'):
        diff, vinte = [], {0.0: 0, 0.6: 0}
        avanzi = {0.0: [], 0.6: []}
        for s in semi:
            a = dati.get((stanza, 0.0, s))
            b = dati.get((stanza, 0.6, s))
            if not a or not b:
                continue
            diff.append(b[0] - a[0])          # curva meno senza curva
            for peso, v in ((0.0, a), (0.6, b)):
                if v[0] >= v[1]:
                    vinte[peso] += 1
                avanzi[peso].append(v[2])
        if not diff:
            continue
        media = statistics.mean(diff)
        sd = statistics.stdev(diff) if len(diff) > 1 else 0.0
        errore = sd / math.sqrt(len(diff)) if diff else 0.0
        print('--- avversari: %s  (%d coppie)' % (stanza, len(diff)))
        print('    con la curva meno senza:  %+.1f punti in media'
              '   (deviazione %.0f, errore %.1f)' % (media, sd, errore))
        print('    quante volte la curva fa meglio:  %d su %d'
              % (sum(1 for d in diff if d > 0), len(diff)))
        print('    scarto in errori standard:  %+.1f%s'
              % (media / errore if errore else 0.0,
                 '   << rumore' if errore and abs(media / errore) < 2 else ''))
        print('    vittorie   senza curva %d/%d   con curva %d/%d'
              % (vinte[0.0], len(diff), vinte[0.6], len(diff)))
        print('    crediti avanzati   senza %.1f   con %.1f\n'
              % (statistics.mean(avanzi[0.0]), statistics.mean(avanzi[0.6])))


if __name__ == '__main__':
    main()
