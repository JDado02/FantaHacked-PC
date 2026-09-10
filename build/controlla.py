# -*- coding: utf-8 -*-
"""Passa il pacchetto all'antivirus prima di pubblicarlo.

Serve perche' e' successo il contrario. Un eseguibile e poi un `index.html`
sono stati pubblicati, scaricati, e **rimossi dal computer di chi li aveva
scaricati**: Windows Defender li ha classificati `Wacatac` &mdash; una
diagnosi automatica, senza firma di un virus conosciuto, di quelle che
colpiscono mezza la comunita' Python.

Quello che si e' imparato misurando, e che vale la pena scrivere qui:

  - il giudizio si attacca al **singolo file**, non alla forma. Lo stesso
    `index.html`, identico byte per byte tranne i terminatori di riga, e'
    rilevato in CRLF e pulito in LF;
  - non c'e' una riga colpevole: tagliato a meta', nessuna delle due meta'
    fa scattare niente. E' un giudizio su tutto il file;
  - quindi non si puo' *progettare* un pacchetto che non venga mai segnalato.
    Si puo' pero' non pubblicarne uno che lo e' gia', e questo dipende da noi.

E' il minimo sindacale: dieci secondi prima di mettere online una cosa che
qualcuno scarichera'.

Uso:
    python build/controlla.py                       controlla lo zip e la cartella
    python build/controlla.py percorso [percorso..]  controlla quello che gli dici
"""
import os
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(QUI)
PIATTAFORMA = r'C:\ProgramData\Microsoft\Windows Defender\Platform'


def strumento():
    """MpCmdRun.exe, che su Windows c'e' sempre ma non sempre nello stesso posto."""
    if os.path.isdir(PIATTAFORMA):
        for cartella in sorted(os.listdir(PIATTAFORMA), reverse=True):
            p = os.path.join(PIATTAFORMA, cartella, 'MpCmdRun.exe')
            if os.path.exists(p):
                return p
    vecchio = r'C:\Program Files\Windows Defender\MpCmdRun.exe'
    return vecchio if os.path.exists(vecchio) else None


def controlla(percorso, mp):
    """Vero se pulito. `-DisableRemediation`: deve dirlo, non toglierlo di mezzo."""
    out = subprocess.run(
        [mp, '-Scan', '-ScanType', '3', '-File', os.path.abspath(percorso),
         '-DisableRemediation'],
        capture_output=True, text=True, errors='replace')
    testo = (out.stdout or '') + (out.stderr or '')
    if 'found no threats' in testo:
        return True, ''
    righe = [r.strip() for r in testo.splitlines() if 'Threat' in r or 'file' in r]
    return False, '\n      '.join(righe[:6]) or testo.strip()[:300]


def main(percorsi):
    mp = strumento()
    if not mp:
        print('MpCmdRun non trovato: salto il controllo (non sei su Windows?)')
        return 0
    if not percorsi:
        percorsi = [os.path.join(BASE, 'FantaHacked-Windows.zip'),
                    os.path.join(BASE, 'build', 'dist', 'FantaHacked')]
    percorsi = [p for p in percorsi if os.path.exists(p)]
    if not percorsi:
        print('Niente da controllare: costruisci prima il pacchetto.')
        return 1

    brutti = 0
    for p in percorsi:
        pulito, dettaglio = controlla(p, mp)
        print('  %-8s %s' % ('pulito' if pulito else 'SEGNALATO',
                             os.path.relpath(p, BASE)))
        if not pulito:
            brutti += 1
            print('      ' + dettaglio)

    if brutti:
        print('\nNON PUBBLICARE. Un file segnalato viene rimosso dal computer di')
        print('chi lo scarica, e la fiducia si perde una volta sola.')
        print('Cosa fare, in ordine:')
        print('  1. ricostruisci: il giudizio si attacca al singolo file, e un')
        print('     pacchetto rifatto spesso passa. Poi ricontrolla.')
        print('  2. se insiste, segnalalo come falso positivo su')
        print('     https://www.microsoft.com/en-us/wdsi/filesubmission')
        print('     (Software developer -> Incorrectly detected). Rispondono in')
        print('     un paio di giorni, e la correzione vale per tutti.')
        return 1
    print('\nTutto pulito: si puo\' pubblicare.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
