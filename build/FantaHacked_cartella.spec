# -*- mode: python ; coding: utf-8 -*-
#
# La versione **a cartella**, ed e' quella che si distribuisce.
#
#     python -m PyInstaller --clean --distpath build/dist --workpath build/lavoro build/FantaHacked_cartella.spec
#
# Perche' non il file unico. Un eseguibile "onefile" di PyInstaller e' un
# programmino che a ogni avvio si scompatta da solo in una cartella temporanea
# e poi esegue quello che ha appena scritto: e' esattamente la descrizione di
# un dropper, e gli antivirus lo trattano come tale. Windows Defender su
# questo programma ha tirato fuori `Trojan:Win32/Wacatac.B!ml` &mdash; una
# diagnosi automatica, senza firma, di quelle che colpiscono mezza la
# comunita' Python. Ricompilare lo fa sparire, ma solo finche' quel file non
# viene di nuovo giudicato: non e' una soluzione, e' un rinvio.
#
# La versione a cartella non si scompatta niente: c'e' un avvio da cinque
# megabyte e accanto le librerie, come qualunque programma Windows normale.
# Sullo stesso computer e con le stesse definizioni passa pulita.
#
# In piu' parte prima, perche' non deve scompattare mezzo Python a ogni doppio
# clic.
#
# Il file unico si costruisce ancora con `FantaHacked.spec`: comodo da tenere
# su una chiavetta, ma non e' quello che si mette online.

a = Analysis(
    ['../app/server.py'],
    pathex=['motore'],
    binaries=[],
    datas=[
        ('../app/web', 'app/web'),
        ('../motore/schema_asta.sql', 'motore'),
        ('../motore/schema_dati.sql', 'motore'),
        ('../database/regole_lega.json', 'database'),
    ],
    hiddenimports=['percorsi', 'db', 'regole', 'proiezioni', 'titolarita', 'asta', 'valutazione', 'modificatore', 'ottimizzatore', 'strategia', 'equilibrio', 'aggiornamento'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FantaHacked',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../app/fantahacked.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='FantaHacked',
)
