# -*- coding: utf-8 -*-
"""Lo zip che si scarica da GitHub.

Prende `build/dist/FantaHacked/` (la versione a cartella) e ne fa
`FantaHacked-Windows.zip` alla radice del progetto, che e' il file linkato in
cima al README.

Le date dentro lo zip sono azzerate apposta. Senza, due zip fatti da cartelle
identiche in due momenti diversi hanno contenuti diversi, e git se ne accorge:
il repository crescerebbe di venti megabyte ogni volta che si lancia lo script
"per sicurezza". Cosi' invece "niente da fare" vuol dire davvero niente.

Uso:
    python -m PyInstaller --clean --distpath build/dist --workpath build/lavoro build/FantaHacked_cartella.spec
    python build/impacchetta.py
"""
import os
import sys
import zipfile

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(QUI)
SORGENTE = os.path.join(BASE, 'build', 'dist', 'FantaHacked')
USCITA = os.path.join(BASE, 'FantaHacked-Windows.zip')

# 1980: la data piu' vecchia che il formato zip sappia scrivere.
QUANDO = (1980, 1, 1, 0, 0, 0)


def impacchetta(sorgente=SORGENTE, uscita=USCITA):
    if not os.path.isdir(sorgente):
        print('Manca %s: costruisci prima la versione a cartella.' % sorgente)
        return 1
    file = []
    for radice, _cartelle, nomi in os.walk(sorgente):
        for n in sorted(nomi):
            pieno = os.path.join(radice, n)
            dentro = os.path.relpath(pieno, os.path.dirname(sorgente))
            file.append((pieno, dentro.replace(os.sep, '/')))
    file.sort(key=lambda t: t[1])

    with zipfile.ZipFile(uscita, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for pieno, dentro in file:
            info = zipfile.ZipInfo(dentro, date_time=QUANDO)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(pieno, 'rb') as f:
                z.writestr(info, f.read())

    grezzo = sum(os.path.getsize(p) for p, _ in file)
    print('%s' % uscita)
    print('  %d file, %.1f MB -> %.1f MB'
          % (len(file), grezzo / 1e6, os.path.getsize(uscita) / 1e6))
    return 0


if __name__ == '__main__':
    sys.exit(impacchetta())
