-- FantaHacked - i dati di riferimento.
--
-- Questo file descrive il database **scaricabile**: listone, statistiche,
-- gerarchie, proiezioni. E' di sola lettura per il programma, uguale per
-- tutti, e si sostituisce in blocco quando esce un aggiornamento.
--
-- Sta separato dall'asta apposta. Finche' erano un file solo, aggiornare i
-- dati voleva dire riscrivere il file che contiene anche gli acquisti: o si
-- rinunciava ad aggiornare, o si rischiava di perdere un'asta in corso.
-- Adesso il file dei dati si puo' buttare e riscrivere quando si vuole.

PRAGMA foreign_keys = ON;

-- Versione dello schema. Il programma rifiuta un file di dati piu' nuovo di
-- quello che sa leggere, invece di aprirlo e rompersi a meta' asta.
CREATE TABLE meta (
    chiave  TEXT PRIMARY KEY,
    valore  TEXT
);
-- ============================================================ 1. ANAGRAFICA

CREATE TABLE squadre (
    squadra        TEXT PRIMARY KEY,
    nome_ufficiale TEXT,
    allenatore     TEXT,
    promossa       INTEGER NOT NULL DEFAULT 0,
    gf_prec        INTEGER,
    gs_prec        INTEGER
);

CREATE TABLE giocatori (
    id             INTEGER PRIMARY KEY,
    nome           TEXT NOT NULL,
    nome_completo  TEXT,
    squadra        TEXT NOT NULL REFERENCES squadre(squadra),
    ruolo          TEXT NOT NULL CHECK (ruolo IN ('P','D','C','A')),
    qi             INTEGER,
    qa             INTEGER,
    fvm            INTEGER,   -- valore di mercato del listone, su base 1000
    eta            INTEGER,
    nuovo_acquisto INTEGER DEFAULT 0,  -- ha cambiato squadra quest'anno
    attivo         INTEGER NOT NULL DEFAULT 1,
    id_ufficiale   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_giocatori_ruolo ON giocatori(ruolo);
CREATE INDEX ix_giocatori_squadra ON giocatori(squadra);

CREATE TABLE statistiche (
    id        INTEGER NOT NULL REFERENCES giocatori(id),
    stagione  TEXT    NOT NULL,
    squadra   TEXT,
    ruolo     TEXT,
    minuti    INTEGER,
    pg        INTEGER,
    mv        REAL,
    mf        REAL,
    gf        INTEGER,
    gs        INTEGER,
    rp        INTEGER,
    rc        INTEGER,
    rpiu      INTEGER,
    rmeno     INTEGER,
    ass       INTEGER,
    amm       INTEGER,
    esp       INTEGER,
    au        INTEGER,
    PRIMARY KEY (id, stagione)
);

CREATE TABLE avanzate (
    id              INTEGER NOT NULL REFERENCES giocatori(id),
    stagione        TEXT    NOT NULL,
    squadra         TEXT,
    partite         INTEGER,
    minuti          INTEGER,
    gol             INTEGER,
    assist          INTEGER,
    xg              REAL,
    npxg            REAL,
    xa              REAL,
    tiri            INTEGER,
    passaggi_chiave INTEGER,
    xg_chain        REAL,
    xg_buildup      REAL,
    posizione_fonte TEXT,
    PRIMARY KEY (id, stagione)
);

CREATE TABLE contesto (
    id                   INTEGER PRIMARY KEY REFERENCES giocatori(id),
    titolarita           REAL,     -- giudizio prospettico, 0..1; vuoto se non compilato
    quota_minuti         REAL,     -- minuti giocati / minuti disponibili, ultima stagione
    ballottaggio_con     TEXT,
    rigorista            INTEGER,  -- 0 no, 1 primo, 2 secondo
    fonte_rigorista      TEXT,
    calci_piazzati       INTEGER,
    corner               INTEGER,
    stato                TEXT,
    rientro_stimato      TEXT,
    fascia               TEXT,
    nota_listone         TEXT,
    consiglio_sos        TEXT,
    accoppiata           TEXT
);

-- Chi gioca davvero, secondo le guide lette dal web il 3 settembre 2026.
-- Separata da `contesto` apposta: quella viene dal foglio dell'utente, questa
-- dal consenso di cinque fonti indipendenti. Tenerle distinte permette di
-- rifare l'una senza toccare l'altra, e di sapere sempre da dove viene un
-- numero. La costruisce database/pipeline/consenso.py.
CREATE TABLE gerarchie (
    id               INTEGER PRIMARY KEY REFERENCES giocatori(id),
    titolarita       REAL,     -- 0..1, quota pesata di guide che lo schierano
    accordo          REAL,     -- 0..1, quanto le guide sono concordi su di lui
    presenze_web     REAL,     -- presenze attese implicate dal consenso
    fonti            INTEGER,  -- quante guide lo mettono in campo
    ballottaggio_con TEXT,     -- id dei rivali per la maglia, separati da |
    ballottaggio_pct TEXT,     -- percentuali corrispondenti, dove esistono
    rigorista        INTEGER,  -- 1 primo, 2 secondo, 3 terzo
    stato            TEXT,     -- infortunio in corso
    rientro_stimato  TEXT,     -- data stimata di rientro
    partite_saltate  INTEGER,  -- giornate che salta da oggi al rientro
    -- Non iscritto alla lista di serie A: non e' un infortunio lungo, e'
    -- l'impossibilita' di scendere in campo. Zero presenze, e il motore non
    -- deve poterlo consigliare nemmeno per un credito.
    fuori_lista      INTEGER DEFAULT 0
);

-- Le coppie che si dividono la stessa maglia: quando non gioca uno gioca
-- l'altro. E' l'informazione con cui si compra il secondo a due crediti dopo
-- averne spesi quaranta per il primo.
CREATE TABLE accoppiate (
    id_titolare      INTEGER NOT NULL REFERENCES giocatori(id),
    id_vice          INTEGER NOT NULL REFERENCES giocatori(id),
    squadra          TEXT,
    ruolo            TEXT,
    tipo             TEXT,     -- 'ballottaggio' oppure 'vice'
    titolarita_titolare REAL,
    titolarita_vice  REAL,
    presenze_titolare REAL,
    presenze_vice    REAL,
    giornate_coperte REAL,     -- giornate su 38 coperte da almeno uno dei due
    copertura        REAL,
    peso_fonti       REAL,
    fonti            TEXT,
    nota             TEXT,
    PRIMARY KEY (id_titolare, id_vice)
);
CREATE INDEX ix_accoppiate_vice ON accoppiate(id_vice);

CREATE TABLE calendario (
    giornata   INTEGER NOT NULL,
    data       TEXT,
    casa       TEXT NOT NULL REFERENCES squadre(squadra),
    trasferta  TEXT NOT NULL REFERENCES squadre(squadra),
    PRIMARY KEY (giornata, casa)
);

CREATE TABLE prezzi_asta (
    id                    INTEGER REFERENCES giocatori(id),
    nome                  TEXT,
    prezzo_medio_per_1000 REAL,
    fonte                 TEXT
);
CREATE INDEX ix_prezzi_id ON prezzi_asta(id);

-- ============================================================ 2. PROIEZIONI
-- Ricalcolate da proiezioni.py. Una riga per giocatore.

CREATE TABLE proiezioni (
    id                INTEGER PRIMARY KEY REFERENCES giocatori(id),
    minuti_attesi     REAL,
    presenze_attese   REAL,
    mv_attesa         REAL,
    gol_attesi        REAL,
    assist_attesi     REAL,
    amm_attese        REAL,
    esp_attese        REAL,
    gs_attesi         REAL,   -- portieri
    rp_attesi         REAL,   -- portieri
    imbattuto_attese  REAL,   -- portieri: partite senza gol subiti
    bonus_per_partita REAL,
    fantamedia_attesa REAL,
    punti_attesi      REAL,   -- presenze_attese * fantamedia_attesa
    metodo            TEXT,   -- 'storico' oppure 'imputato_da_quotazione'
    affidabilita      REAL,   -- 0..1, quanto campione c'e' dietro la stima
    -- Gerarchia di reparto, calcolata da titolarita.py. E' la risposta a
    -- "gioca davvero?", che la sola fantamedia non da'.
    titolarita        REAL,   -- 0..1, quota di stagione che ci si aspetta giochi
    posto_reparto     INTEGER,-- 1 = primo del suo ruolo nella sua squadra
    in_reparto        INTEGER,-- quanti sono a listone in quel reparto
    grado             TEXT,   -- titolare / ballottaggio / rotazione / riserva
    certezza          REAL,   -- 0..1, quanto e' solido quel giudizio
    -- Non iscritto alla lista di serie A: tutti i numeri qui sopra sono zero,
    -- e il motore non deve proporlo nemmeno come riempitivo da un credito.
    fuori_lista       INTEGER DEFAULT 0
);
