# -*- coding: utf-8 -*-
"""Le manopole del motore, girate una alla volta contro la stessa stanza.

Ogni riga di `regole_lega.json` che comincia con un numero e' una scelta, e
finora le scelte erano ragionate ma non misurate. Qui si girano una alla volta
sulle stesse aste &mdash; stessi semi, stessi caratteri, stesse chiamate &mdash;
cosi' la differenza che si vede e' la manopola e non la fortuna.

Gli avversari sono ancorati ai prezzi realmente pagati, come in
`cento_aste.py`: se si ancorassero al nostro modello, girare una manopola
sposterebbe anche loro e ogni confronto direbbe zero.

Uso:
    python manopole.py 30            trenta aste per ogni posizione
"""
import multiprocessing, os, statistics, sys, time

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

import cento_aste as cento

NOMI = cento.NOMI


# Ogni prova e' (etichetta, funzione che modifica il mondo prima dell'asta).
# La modifica si fa nel processo figlio, dopo l'import: e' l'unico posto dove
# valutazione e regole esistono gia' e nessuna asta e' ancora cominciata.
def _senza_pavimenti(reg):
    """Toglie le riserve minime per reparto."""
    reg.riserva_ruolo = dict((r, 0.0) for r in reg.riserva_ruolo)


def _prova(argomenti):
    seme, chiave = argomenti
    import valutazione, regole
    originale_curva = valutazione.PESO_CURVA
    patch_reg = None
    if chiave.startswith('curva='):
        valutazione.PESO_CURVA = float(chiave.split('=')[1])
    elif chiave.startswith('rilancio='):
        cento.MARGINE = float(chiave.split('=')[1])
    elif chiave == 'senza pavimenti':
        patch_reg = _senza_pavimenti
    elif chiave.startswith('mercato='):
        cento.FIDUCIA = float(chiave.split('=')[1])
    try:
        return chiave, cento.gioca(seme, 'mercato', patch_reg=patch_reg)
    finally:
        valutazione.PESO_CURVA = originale_curva
        cento.MARGINE = 0.0
        cento.FIDUCIA = None


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    semi = [1000 + 7 * i for i in range(quante)]
    prove = ['com\'e\' adesso',
             'rilancio=0.05', 'rilancio=0.10', 'rilancio=0.20',
             'curva=0.0', 'curva=0.4', 'curva=0.8',
             'senza pavimenti',
             'mercato=0.25', 'mercato=0.75']
    compiti = [(s, k) for k in prove for s in semi]
    avvio = time.time()
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        esiti = pool.map(_prova, compiti)
    per_prova = {}
    for chiave, e in esiti:
        if 'errore' in e:
            continue
        per_prova.setdefault(chiave, []).append(e)
    print('%d aste in %.0f s\n' % (len(esiti), time.time() - avvio))
    print('%-18s %7s %9s %9s %9s %9s' % ('manopola', 'vinte', 'punti',
                                         'scarto', 'in dieci', 'avanzati'))
    riferimento = None
    for chiave in prove:
        lista = per_prova.get(chiave) or []
        if not lista:
            continue
        io = NOMI[0]
        punti, scarti, piaz = [], [], []
        for e in lista:
            mio = e['punti'][io]
            altri = [p for n, p in e['punti'].items() if n != io]
            punti.append(mio)
            scarti.append(mio - max(altri))
            piaz.append(1 + sum(1 for p in altri if p > mio))
        med = statistics.median(punti)
        if riferimento is None:
            riferimento = med
        print('%-18s %4d/%-3d %9.0f %+9.0f %9.1f %9.1f'
              % (chiave, sum(1 for p in piaz if p == 1), len(lista), med,
                 med - riferimento, 38 * statistics.median(
                     [e['rischio'] for e in lista]),
                 statistics.mean([e['avanzati'] for e in lista])))


if __name__ == '__main__':
    main()
