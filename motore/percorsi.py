# -*- coding: utf-8 -*-
"""Dove stanno i file, sia da sorgente sia da eseguibile.

Quando il programma gira come .exe, `__file__` punta dentro il pacchetto
temporaneo che PyInstaller scompatta, non alla cartella dell'utente. I dati
pero' devono restare fuori e restare modificabili: `regole_lega.json` va
cambiato ogni anno, e il database dei giocatori va aggiornato.

Percio' la radice e' la cartella che contiene l'eseguibile quando e'
congelato, e la cartella del progetto quando si lavora da sorgente.
"""
import os, sys


def radice():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def dentro(*parti):
    return os.path.join(radice(), *parti)


# Cartelle usate da tutto il resto.
MOTORE   = dentro('motore')
DATABASE = dentro('database')
WEB      = dentro('app', 'web')

# Il database dell'asta. La variabile d'ambiente esiste per una ragione sola,
# ed e' una ragione seria: **il collaudo apre e chiude decine di aste**, e
# ognuna comincia cancellando quella precedente. Puntato al database vero,
# lanciare le prove mentre si ha un'asta in corso la distrugge senza chiedere
# niente a nessuno. E' successo. Adesso le prove girano su una copia usa e
# getta, e il file vero non lo tocca nessuno.
DB_FILE  = (os.environ.get('FANTAHACKED_DB')
            or os.path.join(MOTORE, 'asta.db'))

# I dati dei giocatori, che sono un'altra cosa. Stanno in un file separato per
# una ragione pratica: quello si **riscarica**, questo no. Il listone, le
# statistiche e le proiezioni sono uguali per tutti e si aggiornano ogni volta
# che rileggo le fonti; l'asta e' tua, e' di quella sera, e se si perde non la
# rimette insieme nessuno.
#
# Tenendoli in un file solo, aggiornare i dati voleva dire riscrivere il file
# che contiene anche gli acquisti. Adesso il file dei dati si puo' sostituire
# in blocco quando si vuole, anche a meta' stagione, senza sfiorare l'asta.
DATI_FILE = (os.environ.get('FANTAHACKED_DATI')
             or os.path.join(DATABASE, 'dati.db'))

# Il file di prima, quando i due erano uno solo. Serve solo a riconoscerlo e
# spezzarlo in due al primo avvio: chi aveva un'asta in corso non la perde.
VECCHIO_DB = os.path.join(MOTORE, 'fanta.db')
