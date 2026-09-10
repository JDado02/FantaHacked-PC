# -*- coding: utf-8 -*-
"""Passa il pacchetto all'antivirus prima di pubblicarlo, come lo vedra' lui.

Serve perche' e' successo il contrario, tre volte. Un eseguibile, poi un
`index.html`, poi `index.html` e `app.js` insieme sono stati pubblicati,
scaricati, e **rimossi dal computer di chi li aveva scaricati**: Windows
Defender li ha classificati `Wacatac` &mdash; una diagnosi automatica, senza
firma di un virus conosciuto, di quelle che colpiscono mezza la comunita'
Python.

Quello che si e' imparato misurando, e che vale la pena scrivere qui:

  - **una scansione locale non e' uno scaricamento.** Windows mette sui file
    scaricati un flusso `Zone.Identifier`, e su quelli Defender applica
    un'analisi piu' severa, con la parte in cloud. Senza quel marchio i file
    segnalati risultavano puliti: e' il motivo per cui i primi due controlli
    hanno dato via libera a pacchetti che poi sono stati rimossi;
  - il giudizio si attacca al **singolo file**, non alla forma. Lo stesso
    `index.html`, identico byte per byte tranne i terminatori di riga, e'
    segnalato in CRLF e pulito in LF;
  - non c'e' una riga colpevole: tagliato a meta', nessuna delle due meta' fa
    scattare niente. E' un giudizio su tutto il file insieme;
  - quindi non si puo' *progettare* un pacchetto che non venga mai segnalato.
    Si puo' pero' non pubblicarne uno che lo e' gia', e questo dipende da noi.

Uso:
    python build/controlla.py                        lo zip e la cartella
    python build/controlla.py percorso [percorso..]   quello che gli dici
"""
import io
import os
import subprocess
import sys

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(QUI)
PIATTAFORMA = r'C:\ProgramData\Microsoft\Windows Defender\Platform'

# Il marchio che Windows mette sui file scaricati.
MARCHIO = ('[ZoneTransfer]\r\n'
           'ZoneId=3\r\n'
           'HostUrl=https://raw.githubusercontent.com/\r\n')

# Le nostre cose dentro il pacchetto. Le librerie di Python le ha gia'
# scansionate chiunque le abbia installate: quello che vale la pena guardare,
# e che nessun altro ha mai guardato, e' l'interfaccia e i file di qui.
NOSTRI = ('_internal/app', '_internal/database', '_internal/motore')


def strumento():
    """MpCmdRun.exe, che su Windows c'e' sempre ma non sempre nello stesso posto."""
    if os.path.isdir(PIATTAFORMA):
        for cartella in sorted(os.listdir(PIATTAFORMA), reverse=True):
            p = os.path.join(PIATTAFORMA, cartella, 'MpCmdRun.exe')
            if os.path.exists(p):
                return p
    vecchio = r'C:\Program Files\Windows Defender\MpCmdRun.exe'
    return vecchio if os.path.exists(vecchio) else None


def marchia_come_scaricato(percorso):
    """Fa credere a Windows che il file arrivi da internet.

    E' la correzione piu' importante di questo file, imparata sbagliando due
    volte: senza il marchio, i file che venivano segnalati sul computer di chi
    li scaricava risultavano puliti qui. Verificato anche al contrario &mdash;
    col marchio, i file della versione precedente vengono segnalati anche qui.
    """
    try:
        with io.open(percorso + ':Zone.Identifier', 'w', encoding='utf-8',
                     newline='') as f:
            f.write(MARCHIO)
        return True
    except OSError:
        return False          # non NTFS, oppure gia' bloccato da Defender


def controlla(percorso, mp):
    """Vero se pulito. `-DisableRemediation`: deve dirlo, non toglierlo di mezzo."""
    marchia_come_scaricato(percorso)
    out = subprocess.run(
        [mp, '-Scan', '-ScanType', '3', '-File', os.path.abspath(percorso),
         '-DisableRemediation'],
        capture_output=True, text=True, errors='replace')
    testo = (out.stdout or '') + (out.stderr or '')
    if 'found no threats' in testo:
        return True, ''
    righe = [r.strip() for r in testo.splitlines() if 'Threat' in r]
    return False, '  '.join(righe[:3]) or testo.strip()[:200]


def da_controllare(percorso):
    """Il pacchetto **aperto**, file per file.

    Scansionare lo zip non basta e la prima volta ha ingannato: lo zip
    risultava pulito mentre l'`index.html` che aveva dentro veniva segnalato
    allo scaricamento. Un controllo che guarda solo il contenitore non e' un
    controllo, e' una rassicurazione.
    """
    if os.path.isfile(percorso):
        return [percorso]
    fuori = []
    avvio = os.path.join(percorso, 'FantaHacked.exe')
    if os.path.exists(avvio):
        fuori.append(avvio)
    for pezzo in NOSTRI:
        radice = os.path.join(percorso, *pezzo.split('/'))
        for cartella, _sotto, nomi in os.walk(radice):
            for n in sorted(nomi):
                fuori.append(os.path.join(cartella, n))
    return fuori


def main(percorsi):
    mp = strumento()
    if not mp:
        print('MpCmdRun non trovato: salto il controllo (non sei su Windows?)')
        return 0
    if not percorsi:
        percorsi = [os.path.join(BASE, 'FantaHacked-Windows.zip'),
                    os.path.join(BASE, 'build', 'dist', 'FantaHacked')]
    aperti = []
    for p in percorsi:
        if os.path.exists(p):
            aperti.extend(da_controllare(p))
    if not aperti:
        print('Niente da controllare: costruisci prima il pacchetto.')
        return 1

    print('%d file, marchiati come scaricati da internet:' % len(aperti))
    brutti = 0
    for p in aperti:
        pulito, dettaglio = controlla(p, mp)
        try:
            nome = os.path.relpath(p, BASE)
        except ValueError:
            nome = p
        print('  %-10s %s' % ('pulito' if pulito else 'SEGNALATO', nome))
        if not pulito:
            brutti += 1
            print('      ' + dettaglio)

    if brutti:
        print('\nNON PUBBLICARE: %d file su %d.' % (brutti, len(aperti)))
        print('Un file segnalato viene rimosso dal computer di chi lo scarica,')
        print('e la fiducia si perde una volta sola. Cosa fare, in ordine:')
        print('  1. ricostruisci il pacchetto: il giudizio si attacca al')
        print('     singolo file, e uno rifatto spesso passa. Poi ricontrolla.')
        print('  2. se insiste, segnalalo come falso positivo su')
        print('     https://www.microsoft.com/en-us/wdsi/filesubmission')
        print('     (Software developer -> Incorrectly detected): rispondono in')
        print('     un paio di giorni, e la correzione vale per tutti.')
        return 1
    print("\nTutti puliti: si puo' pubblicare.")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
