# -*- coding: utf-8 -*-
"""Quanto si paga, rispetto al proprio limite.

La domanda pratica di chi sta per fare l'asta: il numero grande sulla scheda
- "non oltre 49" - e' un obiettivo o un confine? Il motore risponde con i
fatti: giocando cento aste da solo, quanto ha pagato in media rispetto a
quello che era disposto a pagare.

E' la differenza fra due strategie che sembrano uguali e non lo sono:
rilanciare *fino al* limite, oppure *lasciare che siano gli altri a spingere*
e fermarsi quando superano il limite. Nella seconda i crediti risparmiati sono
punti comprati altrove.
"""
import multiprocessing, os, statistics, sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

import cento_aste as cento


def _asta(seme):
    e = cento.gioca(seme, 'mercato')
    return e['limiti'], e['punti'][cento.NOMI[0]]


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    semi = [60000 + 31 * i for i in range(quante)]
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        esiti = pool.map(_asta, semi)

    tutti = [t for limiti, _ in esiti for t in limiti]
    risparmi, quote, al_limite, sopra = [], [], 0, 0
    per_ruolo = {}
    for limite, prezzo, ancora, ruolo in tutti:
        if limite < 1:
            continue
        risparmi.append(limite - prezzo)
        quote.append(prezzo / float(limite))
        if prezzo >= limite:
            al_limite += 1
        if prezzo > limite:
            sopra += 1
        per_ruolo.setdefault(ruolo, []).append(prezzo / float(limite))

    print('%d acquisti su %d aste\n' % (len(tutti), quante))
    print('  pagato in media il %.0f%% del proprio limite'
          % (100 * statistics.mean(quote)))
    print('  risparmio mediano                 %d crediti a giocatore'
          % statistics.median(risparmi))
    print('  risparmio totale per asta         %d crediti'
          % (sum(risparmi) / quante))
    print('  comprati esattamente al limite    %d su %d (%.0f%%)'
          % (al_limite, len(tutti), 100.0 * al_limite / max(1, len(tutti))))
    print('  comprati sopra il limite          %d' % sopra)
    print('\n  quota del limite pagata, per reparto:')
    for r in ('P', 'D', 'C', 'A'):
        v = per_ruolo.get(r) or []
        if v:
            print('    %s  %.0f%%   (%d acquisti)'
                  % (r, 100 * statistics.mean(v), len(v)))


if __name__ == '__main__':
    main()
