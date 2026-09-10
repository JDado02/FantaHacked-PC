# -*- coding: utf-8 -*-
"""I due database SQLite, e come si aprono insieme.

I file sono due, e la ragione e' che le due cose che contengono non si
somigliano per niente:

  `database/dati.db`   listone, statistiche, gerarchie, proiezioni.
                       Sola lettura, uguale per tutti, **si riscarica**.

  `motore/asta.db`     chi ha comprato chi e a quanto.
                       Si scrive di continuo, e' di quella sera, e se si
                       perde non lo rimette insieme nessuno.

Finche' erano un file solo, aggiornare i dati voleva dire riscrivere il file
che contiene anche gli acquisti: o si rinunciava ad aggiornare a stagione
iniziata, o si rischiava di perdere un'asta in corso. Adesso il file dei dati
si puo' buttare e riscrivere quando si vuole.

Il programma li apre insieme (`ATTACH`), e le query non cambiano di una
virgola: SQLite risolve `giocatori` e `acquisti` da solo, ciascuno nel file in
cui sta. Due cose pero' non attraversano il confine, e sono trattate qui:

  - **le chiavi esterne**, che SQLite non fa rispettare fra due file: quella
    di `acquisti` verso `giocatori` e' stata tolta dallo schema, e il controllo
    lo fa `asta.registra`;
  - **le viste**, che vedono solo il file in cui sono definite: `v_disponibili`
    tocca entrambi e viene creata come vista temporanea a ogni connessione.

Uso:  python db.py            ricrea i due database da zero
"""
import contextlib, csv, os, sqlite3, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import percorsi

BASE      = percorsi.radice()
DATABASE  = percorsi.DATABASE
MOTORE    = percorsi.MOTORE
DB_PATH   = percorsi.DB_FILE
DATI_PATH = percorsi.DATI_FILE

# Versione dello schema dei dati. Sale quando cambia la forma delle tabelle,
# non quando cambiano i numeri dentro. Il programma rifiuta un file di dati
# **piu' nuovo** di quello che sa leggere invece di aprirlo e rompersi a meta'
# asta; uno piu' vecchio lo ripara aggiungendo le colonne che gli mancano.
SCHEMA_DATI = 1


class DatiTroppoNuovi(Exception):
    """Il file dei dati vuole una versione del programma piu' recente."""


def _cartella(percorso):
    """Si assicura che la cartella del file esista.

    Serve quando `FantaHacked.exe` viene messo in una cartella vuota: li'
    `motore/` non c'e', e SQLite non crea le cartelle per conto suo - dice
    soltanto "unable to open database file", che a chi ha appena fatto doppio
    clic non spiega niente.
    """
    cartella = os.path.dirname(os.path.abspath(percorso))
    if cartella and not os.path.isdir(cartella):
        os.makedirs(cartella)
    return percorso


def _v(x):
    """Cella CSV -> valore SQLite. La stringa vuota diventa NULL, non zero."""
    if x is None or x == '':
        return None
    return x


# ------------------------------------------------------------- apertura
def connetti(percorso=None, dati=None, **kw):
    """Apre l'asta e ci aggancia i dati. E' l'unico modo di aprire il database.

    Se e' rimasto in giro il vecchio `fanta.db` di quando i file erano uno
    solo, viene spezzato in due prima di tutto il resto: chi aveva un'asta in
    corso se la ritrova dov'era.
    """
    percorso = _cartella(percorso or DB_PATH)
    dati = dati or DATI_PATH
    _dividi_il_vecchio(percorso, dati)

    con = sqlite3.connect(percorso, **kw)
    con.row_factory = sqlite3.Row
    if not _ha_tabelle(con):
        with open(percorsi.risorsa('motore', 'schema_asta.sql'), encoding='utf-8') as f:
            con.executescript(f.read())
        con.commit()
    if os.path.exists(dati):
        con.execute('ATTACH DATABASE ? AS dati', (dati,))
        _controlla_versione(con)
    # Dopo l'aggancio, non prima: il vincolo su `presidenti` resta, quello
    # verso `giocatori` non c'e' piu' nello schema.
    con.execute('PRAGMA foreign_keys = ON')
    migra(con)
    _viste_temporanee(con)
    return con


def _ha_tabelle(con):
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone())


def _controlla_versione(con):
    try:
        r = con.execute("SELECT valore FROM dati.meta WHERE chiave='schema'").fetchone()
    except sqlite3.OperationalError:
        return          # file di dati di prima che la versione esistesse
    if r and int(r['valore']) > SCHEMA_DATI:
        raise DatiTroppoNuovi(
            'i dati sono in formato %s, questo programma legge fino al %d: '
            'aggiorna FantaHacked' % (r['valore'], SCHEMA_DATI))


def _viste_temporanee(con):
    """Le viste che attraversano i due file vivono solo per la connessione.

    Una vista vede unicamente il database in cui e' definita, quindi
    `v_disponibili` - che incrocia il listone con gli acquisti - non puo'
    stare ne' in un file ne' nell'altro. Come vista temporanea, invece, vede
    tutto quello che la connessione ha aperto.
    """
    if not con.execute("PRAGMA database_list").fetchall():
        return
    nomi = set(r[1] for r in con.execute('PRAGMA database_list'))
    if 'dati' not in nomi:
        return
    con.execute("""
        CREATE TEMP VIEW IF NOT EXISTS v_disponibili AS
        SELECT g.*, pr.punti_attesi, pr.metodo, pr.affidabilita
        FROM giocatori g
        LEFT JOIN proiezioni pr ON pr.id = g.id
        WHERE g.attivo = 1
          AND g.id NOT IN (SELECT giocatore_id FROM acquisti)""")


def _dividi_il_vecchio(percorso, dati):
    """Un `fanta.db` di prima diventa i due file di adesso, senza perdere nulla.

    Succede una volta sola, al primo avvio dopo l'aggiornamento. Se qualcuno
    aveva un'asta aperta, gli acquisti finiscono nel file dell'asta e i
    giocatori in quello dei dati, e al riavvio ritrova tutto com'era.
    """
    vecchio = percorso if os.path.exists(percorso) and percorso.endswith('fanta.db') \
        else percorsi.VECCHIO_DB
    if not os.path.exists(vecchio):
        return
    if os.path.exists(percorso) and os.path.exists(dati):
        return
    src = sqlite3.connect(vecchio)
    src.row_factory = sqlite3.Row
    tabelle = set(r['name'] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"))
    if not {'giocatori', 'acquisti'} <= tabelle:
        src.close()
        return
    _copia(src, dati, percorsi.risorsa('motore', 'schema_dati.sql'),
           ['squadre', 'giocatori', 'statistiche', 'avanzate', 'contesto',
            'gerarchie', 'accoppiate', 'calendario', 'prezzi_asta', 'proiezioni'])
    _copia(src, percorso, percorsi.risorsa('motore', 'schema_asta.sql'),
           ['asta', 'presidenti', 'acquisti'])
    src.close()
    os.rename(vecchio, vecchio + '.prima-della-divisione')


def _copia(src, destinazione, schema, tabelle):
    if os.path.exists(destinazione):
        return
    cartella = os.path.dirname(destinazione)
    if cartella and not os.path.isdir(cartella):
        os.makedirs(cartella)
    tmp = destinazione + '.parziale'
    if os.path.exists(tmp):
        os.remove(tmp)
    dst = sqlite3.connect(tmp)
    dst.row_factory = sqlite3.Row
    with open(schema, encoding='utf-8') as f:
        dst.executescript(f.read())
    for t in tabelle:
        try:
            righe = src.execute('SELECT * FROM %s' % t).fetchall()
        except sqlite3.OperationalError:
            continue
        if not righe:
            continue
        colonne = righe[0].keys()
        sue = set(r['name'] for r in dst.execute('PRAGMA table_info(%s)' % t))
        tenute = [c for c in colonne if c in sue]
        dst.executemany(
            'INSERT INTO %s (%s) VALUES (%s)'
            % (t, ','.join(tenute), ','.join('?' * len(tenute))),
            [tuple(r[c] for c in tenute) for r in righe])
    dst.commit()
    dst.close()
    os.rename(tmp, destinazione)


# ------------------------------------------------------------- migrazioni
NUOVE_COLONNE = [
    ('asta',       'turno',          'INTEGER'),
    ('giocatori',  'eta',            'INTEGER'),
    ('giocatori',  'nuovo_acquisto', 'INTEGER DEFAULT 0'),
    ('giocatori',  'fvm',            'INTEGER'),
    ('gerarchie',  'fuori_lista',    'INTEGER DEFAULT 0'),
    ('proiezioni', 'fuori_lista',    'INTEGER DEFAULT 0'),
    ('proiezioni', 'titolarita',     'REAL'),
    ('proiezioni', 'posto_reparto',  'INTEGER'),
    ('proiezioni', 'in_reparto',     'INTEGER'),
    ('proiezioni', 'grado',          'TEXT'),
    ('proiezioni', 'certezza',       'REAL'),
    ('acquisti',   'limite',         'INTEGER'),
]


def migra(con):
    """Aggiunge le colonne comparse dopo, senza rifare i database.

    Vale per tutti e due i file, ciascuno per le sue tabelle. Sull'asta serve
    a non buttare via una serata quando il software si aggiorna; sui dati
    serve a leggere un file scaricato prima che una colonna esistesse.
    """
    schemi = [r[1] for r in con.execute('PRAGMA database_list')]
    fatto = False
    for tabella, colonna, tipo in NUOVE_COLONNE:
        for schema in schemi:
            try:
                colonne = set(r['name'] for r in con.execute(
                    'PRAGMA %s.table_info(%s)' % (schema, tabella)))
            except sqlite3.OperationalError:
                continue
            if not colonne or colonna in colonne:
                continue
            con.execute('ALTER TABLE %s.%s ADD COLUMN %s %s'
                        % (schema, tabella, colonna, tipo))
            fatto = True
            break
    if fatto:
        con.commit()


# ------------------------------------------------------- costruzione dati
def _carica_csv(con, tabella, file_csv, colonne, rinomina=None):
    """Copia un CSV in una tabella. `colonne` sono i nomi nella tabella."""
    rinomina = rinomina or {}
    percorso = os.path.join(DATABASE, file_csv)
    with open(percorso, encoding='utf-8', newline='') as f:
        righe = list(csv.DictReader(f))
    dati = []
    for r in righe:
        dati.append(tuple(_v(r.get(rinomina.get(c, c))) for c in colonne))
    con.executemany(
        'INSERT INTO %s (%s) VALUES (%s)' % (
            tabella, ','.join(colonne), ','.join('?' * len(colonne))),
        dati)
    return len(dati)


def _carica_opzionale(con, tabella, file_csv, colonne):
    """Come `_carica_csv`, ma se il file non c'e' non e' un errore.

    Le gerarchie vengono dal web e si rifanno a parte: chi ricostruisce il
    database senza averle raccolte deve ottenere un programma funzionante,
    non un errore di caricamento.
    """
    if not os.path.exists(os.path.join(DATABASE, file_csv)):
        return 0
    return _carica_csv(con, tabella, file_csv, colonne)


def crea_dati(percorso=None, verboso=True, generato_il=None):
    """Costruisce il file dei dati dai CSV. Non tocca l'asta.

    E' questo il file che si pubblica e si scarica: contiene solo cose che si
    possono rifare, quindi cancellarlo e riscriverlo e' sempre sicuro.
    """
    percorso = percorso or DATI_PATH
    cartella = os.path.dirname(percorso)
    if cartella and not os.path.isdir(cartella):
        os.makedirs(cartella)
    if os.path.exists(percorso):
        os.remove(percorso)
    con = sqlite3.connect(percorso)
    con.row_factory = sqlite3.Row
    with open(percorsi.risorsa('motore', 'schema_dati.sql'), encoding='utf-8') as f:
        con.executescript(f.read())

    n = {}
    n['squadre'] = _carica_csv(con, 'squadre', 'squadre.csv',
        ['squadra', 'nome_ufficiale', 'allenatore', 'promossa', 'gf_prec', 'gs_prec'])
    n['giocatori'] = _carica_csv(con, 'giocatori', 'giocatori.csv',
        ['id', 'nome', 'nome_completo', 'squadra', 'ruolo', 'qi', 'qa',
         'fvm', 'eta', 'nuovo_acquisto', 'attivo', 'id_ufficiale'])
    n['statistiche'] = _carica_csv(con, 'statistiche', 'statistiche.csv',
        ['id', 'stagione', 'squadra', 'ruolo', 'minuti', 'pg', 'mv', 'mf', 'gf',
         'gs', 'rp', 'rc', 'rpiu', 'rmeno', 'ass', 'amm', 'esp', 'au'])
    n['avanzate'] = _carica_csv(con, 'avanzate', 'avanzate.csv',
        ['id', 'stagione', 'squadra', 'partite', 'minuti', 'gol', 'assist', 'xg',
         'npxg', 'xa', 'tiri', 'passaggi_chiave', 'xg_chain', 'xg_buildup',
         'posizione_fonte'])
    n['contesto'] = _carica_csv(con, 'contesto', 'contesto.csv',
        ['id', 'titolarita', 'quota_minuti', 'ballottaggio_con', 'rigorista',
         'fonte_rigorista', 'calci_piazzati', 'corner', 'stato',
         'rientro_stimato', 'fascia', 'nota_listone', 'consiglio_sos', 'accoppiata'],
        rinomina={'quota_minuti': 'quota_minuti_2025_26'})
    n['calendario'] = _carica_csv(con, 'calendario', 'calendario.csv',
        ['giornata', 'data', 'casa', 'trasferta'])
    # Le due tabelle costruite dal consenso delle guide. Possono non esserci:
    # il programma funziona anche senza, solo peggio.
    n['gerarchie'] = _carica_opzionale(con, 'gerarchie', 'gerarchie.csv',
        ['id', 'titolarita', 'accordo', 'presenze_web', 'fonti',
         'ballottaggio_con', 'ballottaggio_pct', 'rigorista', 'stato',
         'rientro_stimato', 'partite_saltate', 'fuori_lista'])
    n['accoppiate'] = _carica_opzionale(con, 'accoppiate', 'accoppiate.csv',
        ['id_titolare', 'id_vice', 'squadra', 'ruolo', 'tipo',
         'titolarita_titolare', 'titolarita_vice', 'presenze_titolare',
         'presenze_vice', 'giornate_coperte', 'copertura', 'peso_fonti',
         'fonti', 'nota'])

    # I prezzi d'asta hanno righe senza id (nomi non piu' nel listone): si scartano.
    with open(os.path.join(DATABASE, 'prezzi_asta.csv'), encoding='utf-8', newline='') as f:
        righe = [r for r in csv.DictReader(f) if r['id']]
    con.executemany(
        'INSERT INTO prezzi_asta (id, nome, prezzo_medio_per_1000, fonte) VALUES (?,?,?,?)',
        [(r['id'], r['nome'], _v(r['prezzo_medio_per_1000']), r['fonte']) for r in righe])
    n['prezzi_asta'] = len(righe)

    con.executemany('INSERT INTO meta (chiave, valore) VALUES (?,?)',
                    [('schema', str(SCHEMA_DATI)),
                     ('generato_il', generato_il or _data_manifest())])
    con.commit()
    if verboso:
        print('Dati creati: %s' % percorso)
        for k in ('squadre', 'giocatori', 'statistiche', 'avanzate', 'contesto',
                  'calendario', 'prezzi_asta', 'gerarchie', 'accoppiate'):
            print('  %-14s %5d righe' % (k, n[k]))
    con.close()
    return n


def _data_manifest():
    """La data di generazione dichiarata dalla pipeline, se c'e'."""
    import json
    p = os.path.join(DATABASE, 'manifest.json')
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f).get('generato_il') or ''
    except Exception:
        return ''


def crea_asta(percorso=None):
    """Un file d'asta vuoto. Cancella quello che c'era: usarlo con attenzione."""
    percorso = _cartella(percorso or DB_PATH)
    if os.path.exists(percorso):
        os.remove(percorso)
    con = sqlite3.connect(percorso)
    con.row_factory = sqlite3.Row
    with open(percorsi.risorsa('motore', 'schema_asta.sql'), encoding='utf-8') as f:
        con.executescript(f.read())
    con.commit()
    con.close()
    return percorso


@contextlib.contextmanager
def asta_di_servizio(dati=None):
    """I dati veri, un'asta finta: per gli script che devono giocare un'asta.

    Le prove, i confronti fra i due motori e le analisi hanno tutti bisogno di
    un'asta su cui lavorare, e la creavano chiamando `inizializza()` sulla
    connessione normale &mdash; cioe' **sul file dell'asta vera**, cancellando
    quella di chi stava giocando. Non e' un rischio teorico: e' successo
    mentre giravano le verifiche, e l'asta appena preparata e' sparita.

    La divisione in due database protegge i dati dagli aggiornamenti; questo
    protegge l'asta dagli script. Il file temporaneo porta nel nome il
    processo, cosi' due script in parallelo non si pestano i piedi, e sparisce
    da solo alla fine.
    """
    percorso = os.path.join(
        MOTORE, 'servizio_%d_%d.db' % (os.getpid(), int(time.time() * 1000) % 100000))
    crea_asta(percorso)
    con = connetti(percorso, dati)
    try:
        yield con
    finally:
        try:
            con.close()
        except sqlite3.Error:
            pass
        for coda in ('', '-journal', '-wal', '-shm'):
            try:
                if os.path.exists(percorso + coda):
                    os.remove(percorso + coda)
            except OSError:
                pass


def crea(percorso=None, verboso=True, dati=None):
    """Rifa' tutto: i dati dai CSV e un'asta vuota. Restituisce la connessione."""
    percorso = percorso or DB_PATH
    dati = dati or DATI_PATH
    crea_dati(dati, verboso=verboso)
    crea_asta(percorso)
    return connetti(percorso, dati)


def dati_generati_il(con):
    """La data dei dati caricati, per mostrarla a schermo."""
    try:
        r = con.execute("SELECT valore FROM dati.meta WHERE chiave='generato_il'").fetchone()
        return r['valore'] if r else ''
    except sqlite3.OperationalError:
        return ''


if __name__ == '__main__':
    con = crea()
    q = lambda s: con.execute(s).fetchone()[0]
    print('\nControlli:')
    print('  giocatori per ruolo: %s' % dict(
        (r['ruolo'], r['n']) for r in con.execute(
            'SELECT ruolo, COUNT(*) n FROM giocatori GROUP BY ruolo')))
    print('  con almeno una stagione di storico: %d' % q(
        'SELECT COUNT(DISTINCT id) FROM statistiche'))
    print('  con dati avanzati (xG):             %d' % q(
        'SELECT COUNT(DISTINCT id) FROM avanzate'))
    print('  con prezzo d\'asta di riferimento:   %d' % q(
        'SELECT COUNT(DISTINCT id) FROM prezzi_asta'))
    print('  dati generati il:                   %s' % dati_generati_il(con))
    con.close()
