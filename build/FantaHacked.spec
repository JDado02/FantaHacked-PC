# -*- mode: python ; coding: utf-8 -*-
#
# Va lanciato **dalla cartella del progetto**, non da qui: `pathex` e i
# percorsi sotto sono relativi, e da un'altra cartella escono nove megabyte di
# eseguibile che non parte.
#
#     python -m PyInstaller --clean --distpath . --workpath build/lavoro build/FantaHacked.spec
#
# In `datas` ci sono le cose che il programma **legge e basta**: l'interfaccia,
# gli schemi dei due database, il regolamento predefinito. Viaggiano dentro
# l'eseguibile perche' appartengono al programma, non all'utente, e senza di
# loro `FantaHacked.exe` da solo non parte: spostato in una cartella vuota si
# apriva su una pagina bianca. Chi ne mette una copia accanto all'exe vince
# comunque - vedi `percorsi.risorsa()` - e cosi' si lavora sull'interfaccia
# senza ricostruire niente, e ognuno puo' correggersi il proprio
# `regole_lega.json`.
#
# I due database invece **non** stanno qui dentro: uno si scarica, l'altro e'
# l'asta di chi sta giocando.

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
    a.binaries,
    a.datas,
    [],
    name='FantaHacked',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['../app/fantahacked.ico'],
)
