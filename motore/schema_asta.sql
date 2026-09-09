-- FantaHacked - lo stato dell'asta.
--
-- Questo file resta **sul dispositivo**, sempre. Contiene chi ha comprato
-- chi e a quanto, ed e' l'unica cosa che non si puo' riscaricare: se si
-- perde, si e' persa la serata.
--
-- I dati dei giocatori stanno nel file a fianco, agganciato come `dati`.
-- ============================================================ 3. STATO ASTA

CREATE TABLE asta (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    creata_il         TEXT NOT NULL,
    partecipanti      INTEGER NOT NULL,
    crediti_iniziali  INTEGER NOT NULL,
    regole_json       TEXT NOT NULL,  -- copia delle regole al momento della creazione
    turno             INTEGER         -- presidente a cui tocca chiamare
);

CREATE TABLE presidenti (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL,
    io      INTEGER NOT NULL DEFAULT 0   -- 1 per la squadra dell'utente
);

CREATE TABLE acquisti (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,  -- ordine di chiamata, serve per l'undo
    -- Niente chiave esterna verso `giocatori`: quella tabella vive
    -- nell'altro file, e SQLite non sa far rispettare un vincolo che
    -- attraversa due database. Il controllo lo fa `asta.registra`, che
    -- comunque deve gia' leggere ruolo e prezzo del giocatore.
    giocatore_id   INTEGER NOT NULL,
    presidente_id  INTEGER NOT NULL REFERENCES presidenti(id),
    prezzo         INTEGER NOT NULL CHECK (prezzo >= 1),
    ruolo          TEXT NOT NULL,
    istante        TEXT NOT NULL,
    -- Il prezzo massimo che il motore dava a quel giocatore NEL MOMENTO della
    -- chiamata. Serve a giudicare la decisione con le informazioni che c'erano
    -- allora, invece che col senno di poi: e' l'unica misura che dica se un
    -- acquisto e' stato un errore, e non semplicemente se e' costato piu' della
    -- media di mercato (che per un giocatore fuori scala e' quasi sempre vero).
    limite         INTEGER
);
CREATE UNIQUE INDEX ix_acquisti_giocatore ON acquisti(giocatore_id);
CREATE INDEX ix_acquisti_presidente ON acquisti(presidente_id);

-- Vista di comodo: situazione corrente di ogni presidente.
CREATE VIEW v_presidenti AS
SELECT
    p.id,
    p.nome,
    p.io,
    (SELECT crediti_iniziali FROM asta WHERE id = 1)
        - COALESCE((SELECT SUM(prezzo) FROM acquisti a WHERE a.presidente_id = p.id), 0) AS crediti,
    COALESCE((SELECT COUNT(*) FROM acquisti a WHERE a.presidente_id = p.id AND a.ruolo='P'), 0) AS n_p,
    COALESCE((SELECT COUNT(*) FROM acquisti a WHERE a.presidente_id = p.id AND a.ruolo='D'), 0) AS n_d,
    COALESCE((SELECT COUNT(*) FROM acquisti a WHERE a.presidente_id = p.id AND a.ruolo='C'), 0) AS n_c,
    COALESCE((SELECT COUNT(*) FROM acquisti a WHERE a.presidente_id = p.id AND a.ruolo='A'), 0) AS n_a
FROM presidenti p;
