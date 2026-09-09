# -*- coding: utf-8 -*-
"""Costruisce il pacchetto dei dati e lo prepara per la pubblicazione.

Il pacchetto e' quello che i programmi scaricano: **un file solo**, compresso,
con dentro listone, statistiche, gerarchie e proiezioni. Accanto ci va un
`manifest.json` di due kilobyte, che e' l'unica cosa che il programma legge a
ogni avvio per decidere se scaricare o no.

    python pubblica.py                 costruisce in ../pubblicazione/
    python pubblica.py --pubblica      e crea anche la release su GitHub

La seconda forma ha bisogno di `gh` (lo strumento a riga di comando di GitHub)
oppure di `git` con le credenziali gia' salvate. Se non c'e' ne' l'uno ne'
l'altro, i due file restano li' pronti e si caricano a mano dalla pagina delle
release: sono due, e ci vogliono venti secondi.

Perche' una release e non i file nel repository: un database da mezzo mega
messo sotto controllo di versione lascia una copia intera nella cronologia a
ogni aggiornamento, e in una stagione il repository diventa piu' grande dei
dati che contiene. Le release stanno fuori dalla cronologia.
"""
import argparse, gzip, hashlib, io, json, os, subprocess, sys, time

QUI = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.dirname(QUI)
BASE = os.path.dirname(DATABASE)
sys.path.insert(0, os.path.join(BASE, 'motore'))

import percorsi
import db as dbmod
import regole as regmod
import aggiornamento

USCITA = os.path.join(BASE, 'pubblicazione')
REPO = os.environ.get('FANTAHACKED_REPO') or 'JDado02/DBFantaHacked'


def costruisci(uscita=USCITA, con_proiezioni=True):
    """Rifa' il file dei dati dai CSV, ci mette dentro le proiezioni, comprime."""
    if not os.path.isdir(uscita):
        os.makedirs(uscita)
    db = os.path.join(uscita, 'dati.db')
    print('[1] Costruzione del file dei dati')
    n = dbmod.crea_dati(db, verboso=False)
    for k in sorted(n):
        print('    %-14s %5d righe' % (k, n[k]))

    firma_reg = aggiornamento.firma_regole()
    if con_proiezioni:
        print('\n[2] Proiezioni')
        # Le proiezioni dipendono dal regolamento, quindi il pacchetto porta
        # anche la firma di quello con cui sono state calcolate. Chi ha regole
        # diverse se le rifa' da solo al primo avvio: e' il motivo per cui la
        # firma viaggia insieme ai numeri invece di restare implicita.
        asta = os.path.join(uscita, '_asta_di_servizio.db')
        dbmod.crea_asta(asta)
        con = dbmod.connetti(asta, db)
        import proiezioni as proimod
        _, righe = proimod.esegui(con, regmod.carica())
        con.execute('INSERT OR REPLACE INTO dati.meta (chiave, valore) VALUES (?,?)',
                    ('regole_firma', firma_reg))
        con.commit()
        con.close()
        os.remove(asta)
        print('    %d giocatori proiettati (regolamento %s)' % (len(righe), firma_reg))

    print('\n[3] Compressione')
    grezzo = io.open(db, 'rb').read()
    # Senza `mtime=0` gzip infila l'ora dentro il file, e lo stesso database
    # compresso due volte da due file diversi. Il risultato pratico e' che
    # ripubblicare dati identici sembrerebbe comunque un cambiamento, e il
    # repository crescerebbe di 185 KB ogni volta che si lancia lo script per
    # sicurezza. Cosi' invece "niente da fare" vuol dire davvero niente.
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb', compresslevel=9, mtime=0) as g:
        g.write(grezzo)
    compresso = buffer.getvalue()
    gz = os.path.join(uscita, 'dati.db.gz')
    io.open(gz, 'wb').write(compresso)
    print('    %.0f KB -> %.0f KB compressi' % (len(grezzo)/1024.0, len(compresso)/1024.0))

    generato_il = _generato_il()
    manifest = {
        'generato_il': generato_il,
        'schema': dbmod.SCHEMA_DATI,
        'regole_firma': firma_reg,
        'file': 'dati.db.gz',
        'sha256': hashlib.sha256(compresso).hexdigest(),
        'dimensione': len(compresso),
        'dimensione_estratto': len(grezzo),
        'giocatori': n.get('giocatori', 0),
    }
    mp = os.path.join(uscita, 'manifest.json')
    io.open(mp, 'w', encoding='utf-8').write(
        json.dumps(manifest, ensure_ascii=False, indent=2) + chr(10))
    print('\n[4] Manifest')
    for k in ('generato_il', 'schema', 'giocatori', 'dimensione', 'sha256'):
        print('    %-14s %s' % (k, manifest[k]))
    os.remove(db)          # nel pacchetto va solo il compresso
    return manifest, uscita


def _generato_il():
    """La data che dichiara la pipeline dei dati."""
    try:
        with io.open(os.path.join(DATABASE, 'manifest.json'), encoding='utf-8') as f:
            d = json.load(f).get('generato_il')
        if d:
            return d
    except Exception:
        pass
    return time.strftime('%Y-%m-%d')


def pubblica(manifest, uscita=USCITA, repo=REPO):
    """Manda i due file nel repository. Serve solo `git` con le sue credenziali.

    Il repository viene clonato in una cartella temporanea a ogni giro invece
    di tenerne una copia in giro: non c'e' niente da conservare fra una
    pubblicazione e l'altra, e una copia dimenticata a meta' e' l'unico modo
    per pubblicare per sbaglio dati vecchi.
    """
    import shutil as sh
    import tempfile
    if not _c_e('git'):
        print('\n[5] Pubblicazione')
        print("    `git` non e' installato. I due file sono pronti in")
        print('    %s' % uscita)
        print('    Si caricano anche a mano da https://github.com/%s' % repo)
        return False
    print('\n[5] Pubblicazione su %s' % repo)
    lavoro = tempfile.mkdtemp(prefix='fantahacked_pub_')
    try:
        clone = os.path.join(lavoro, 'repo')
        r = subprocess.run(['git', 'clone', '--depth', '1',
                            'https://github.com/%s.git' % repo, clone],
                           capture_output=True, text=True,
                           env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
        if r.returncode != 0:
            print('    clone non riuscito: %s' % (r.stderr or '').strip()[:200])
            return False
        for f in ('dati.db.gz', 'manifest.json'):
            sh.copyfile(os.path.join(uscita, f), os.path.join(clone, f))
        _scrivi_leggimi(clone, manifest, repo)
        subprocess.run(['git', 'add', '-A'], cwd=clone, capture_output=True)
        messaggio = ('Dati del %s (%d giocatori, %.0f KB)'
                     % (manifest['generato_il'], manifest['giocatori'],
                        manifest['dimensione'] / 1024.0))
        r = subprocess.run(['git', 'commit', '-m', messaggio],
                           cwd=clone, capture_output=True, text=True)
        if r.returncode != 0 and 'nothing to commit' in (r.stdout + r.stderr):
            print('    i dati pubblicati sono gia\' questi: niente da fare')
            return True
        r = subprocess.run(['git', 'push'], cwd=clone, capture_output=True,
                           text=True, env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
        if r.returncode != 0:
            print('    push non riuscito: %s' % (r.stderr or '').strip()[:200])
            return False
        print('    fatto: https://github.com/%s' % repo)
        print('    (GitHub tiene i file in cache cinque minuti: un programma')
        print('     acceso adesso puo\' vedere ancora i dati di prima)')
        return True
    finally:
        sh.rmtree(lavoro, ignore_errors=True)


def _scrivi_leggimi(clone, manifest, repo):
    """Due righe per chi capita sul repository e si chiede cosa sia."""
    testo = (
        '# Dati di FantaHacked' + chr(10) * 2 +
        'I dati dei giocatori usati da FantaHacked, in un file solo.' + chr(10) * 2 +
        '| | |' + chr(10) + '|---|---|' + chr(10) +
        '| aggiornati al | **%s** |' % manifest['generato_il'] + chr(10) +
        '| giocatori | %d |' % manifest['giocatori'] + chr(10) +
        '| dimensione | %.0f KB compressi |' % (manifest['dimensione'] / 1024.0) + chr(10) +
        '| formato | SQLite, schema %s |' % manifest['schema'] + chr(10) * 2 +
        'Il programma legge `manifest.json` a ogni avvio - due kilobyte - e' + chr(10) +
        'scarica `dati.db.gz` solo se la data e cambiata. Se internet non c e,' + chr(10) +
        'parte con i dati che ha gia.' + chr(10) * 2 +
        'Dentro ci sono listone, statistiche, gerarchie di reparto e proiezioni.' + chr(10) +
        'Non c e niente dell asta: quella resta sul dispositivo di chi la gioca.' + chr(10) * 2 +
        'Si pubblica con `python database/pipeline/pubblica.py --pubblica`.' + chr(10))
    with io.open(os.path.join(clone, 'README.md'), 'w', encoding='utf-8') as f:
        f.write(testo)


def _c_e(programma):
    from shutil import which
    return which(programma) is not None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pubblica', action='store_true',
                    help='crea anche la release su GitHub')
    ap.add_argument('--uscita', default=USCITA)
    ap.add_argument('--repo', default=REPO)
    a = ap.parse_args()
    manifest, uscita = costruisci(a.uscita)
    if a.pubblica:
        pubblica(manifest, uscita, a.repo)
    else:
        print('\nPronti in %s' % uscita)
        print('Per pubblicarli:  python pubblica.py --pubblica')
    return 0


if __name__ == '__main__':
    sys.exit(main())
