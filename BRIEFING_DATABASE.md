# Briefing: costruzione del database per assistente d'asta Fantacalcio (modalità Classic)

> Documento operativo destinato a un assistente AI con accesso al web.
> Obiettivo: produrre un pacchetto dati completo, verificato e strutturato, che verrà poi
> consumato da un software desktop di supporto all'asta live.

---

## 0. Contesto

Stiamo costruendo un software per Windows che assiste durante l'asta del fantacalcio.
Il software deve, per ogni giocatore chiamato all'asta, calcolare **in tempo reale** tre numeri:

1. **Prezzo di mercato** — quanto vale ora, dati i crediti ancora in circolo nella lega
2. **Prezzo di chiusura atteso** — quanto probabilmente costerà, dati gli avversari ancora in grado di rilanciare
3. **Massimo consigliato** — oltre quale cifra l'acquisto peggiora la rosa complessiva

Per farlo il motore ha bisogno di stimare, per ogni giocatore, i **punti fantacalcio attesi
sulla stagione**. Tutto il resto del calcolo è aritmetica. Quindi:

> **La qualità del database determina la qualità del software. Nient'altro.**
> Un motore matematicamente perfetto su dati approssimativi produce risposte
> precise alla domanda sbagliata.

**Modalità di gioco: solo Classic.** Ignorare completamente i ruoli Mantra
(Por, Dc, Dd, Ds, E, M, C, W, T, A, Pc). I ruoli da usare sono esclusivamente i quattro
classici: `P`, `D`, `C`, `A`.

---

## 1. Regole di ingaggio — leggere prima di tutto il resto

Queste regole hanno precedenza su qualsiasi altra istruzione del documento.

### 1.1 — Non inventare mai un numero

Ogni valore numerico presente nei file di consegna deve provenire da:

- un file scaricato da una fonte ufficiale, **oppure**
- una pagina web consultata di cui viene registrata l'URL, **oppure**
- un calcolo deterministico su dati delle due categorie precedenti

Se un dato non è reperibile: **lasciare la cella vuota** e registrare la mancanza in
`lacune.csv`. Una cella vuota è un'informazione utile. Un numero plausibile ma inventato
avvelena silenziosamente tutto il modello a valle, ed è indistinguibile da un dato buono.

**Vietato in particolare:**
- stimare a memoria statistiche di giocatori
- riempire con `0` un dato mancante (`0` significa "zero gol", non "non lo so")
- arrotondare o "aggiustare" valori per farli sembrare coerenti
- completare una riga parziale deducendo i campi mancanti

### 1.2 — Non trascrivere a mano grandi tabelle

Il dataset finale conta circa **550 giocatori × 3 stagioni**. Trascrivere manualmente
migliaia di celle produce errori di battitura e allucinazioni, indipendentemente dall'attenzione.

**Approccio corretto:** produrre uno **script Python di pipeline** che
scarica/legge le fonti e le trasforma nel formato di consegna. Lo script è parte della
consegna e deve essere rieseguibile ogni stagione.

**Approccio manuale accettabile** solo per i campi genuinamente editoriali della
sezione `contesto.csv` (rigoristi, titolarità, ballottaggi): sono poche centinaia di
valori e non esistono in forma strutturata.

### 1.3 — Rispettare i termini d'uso delle fonti

Preferire sempre, in quest'ordine:
1. export ufficiali scaricabili (`.xlsx`, `.csv`)
2. API pubbliche documentate
3. consultazione manuale di pagine web

Lo scraping automatico di siti che lo vietano nei termini di servizio non è un'opzione.
Dove una fonte impone limiti di frequenza, rispettarli.

### 1.4 — Tracciabilità

Ogni file consegnato deve poter essere ricondotto alla sua origine. Il `manifest.json`
(sezione 8) è obbligatorio, non decorativo.

---

## 2. Divisione del lavoro

| Blocco | Come ottenerlo | Difficoltà |
|---|---|---|
| Anagrafica e quotazioni | Export ufficiale, lettura diretta | Bassa |
| Statistiche storiche | Export ufficiale, lettura diretta | Bassa |
| Minuti giocati | Fonte statistica esterna + join sui nomi | **Media/alta** |
| xG / xA | Fonte statistica esterna + join sui nomi | Media |
| Calendario | Fonte ufficiale o API | Bassa |
| Titolarità, rigoristi, calci piazzati | Ricerca editoriale, inserimento manuale | Alta (ma poco volume) |
| Prezzi d'asta di riferimento | Seed già fornito + eventuale integrazione | Bassa |

Il collo di bottiglia reale sono **i minuti giocati** e il **join dei nomi** fra fonti
diverse. Vanno affrontati per primi, perché se falliscono l'intero blocco delle
statistiche avanzate diventa inutilizzabile.

---

## 3. Formato di consegna

### 3.1 Struttura

Una singola cartella `database/` contenente:

```
database/
├── manifest.json                  ← metadati e provenienza (obbligatorio)
├── giocatori.csv                  ← anagrafica stagione corrente
├── statistiche.csv                ← stat storiche, una riga per giocatore-stagione
├── contesto.csv                   ← dati editoriali stagione corrente
├── avanzate.csv                   ← xG/xA e metriche avanzate (opzionale ma prezioso)
├── squadre.csv                    ← anagrafica club
├── calendario.csv                 ← calendario Serie A stagione corrente
├── prezzi_asta.csv                ← riferimento prezzi d'asta storici
├── mappa_nomi.csv                 ← tabella di raccordo fra le fonti
├── lacune.csv                     ← registro dei dati non reperiti
└── pipeline/
    ├── build.py                   ← script rieseguibile
    ├── requirements.txt
    └── README.md                  ← come rieseguirlo la prossima stagione
```

Va consegnato anche `regole_lega.json` come **template vuoto commentato** (sezione 7):
lo compilerà l'utente con le regole della propria lega.

### 3.2 Convenzioni obbligatorie per tutti i CSV

Queste convenzioni non sono negoziabili: il software le assume.

| Aspetto | Valore richiesto |
|---|---|
| Codifica | UTF-8 **senza BOM** |
| Separatore di campo | virgola `,` |
| Separatore decimale | punto `.` |
| Separatore migliaia | **nessuno** |
| Fine riga | `\n` |
| Prima riga | header, nomi colonna esattamente come specificati |
| Valore mancante | stringa vuota (nessun `NA`, `N/D`, `-`, `null`, `0`) |
| Date | ISO 8601, `AAAA-MM-GG` |
| Booleani | `0` / `1` |
| Virgolette | doppie `"`, solo dove il campo contiene virgole o virgolette |
| Ordinamento righe | per `id` crescente |

> **Attenzione ricorrente:** gli strumenti italiani salvano di default i CSV con `;`
> come separatore e `,` come decimale. È il formato sbagliato. Verificare aprendo il file
> con un editor di testo, non con Excel.

---

## 4. Schema dei file

### 4.1 `giocatori.csv` — anagrafica stagione corrente

Una riga per giocatore presente nel listone della stagione in corso.

| Colonna | Tipo | Obbl. | Descrizione |
|---|---|---|---|
| `id` | int | ✅ | **ID ufficiale Fantacalcio.** Chiave primaria di tutto il database |
| `nome` | string | ✅ | Nome come appare nel listone, es. `Martinez Jo.` |
| `nome_completo` | string | | Nome esteso per disambiguare, es. `Josep Martinez` |
| `squadra` | string | ✅ | Club, normalizzato secondo `squadre.csv` |
| `ruolo` | enum | ✅ | Uno fra `P`, `D`, `C`, `A` |
| `qi` | int | ✅ | Quotazione iniziale Classic |
| `qa` | int | ✅ | Quotazione attuale Classic |
| `fvm` | int | | Indice di valore di mercato, se la fonte lo espone |
| `eta` | int | | Età al 1° settembre della stagione |
| `nuovo_acquisto` | 0/1 | | `1` se ha cambiato squadra nella sessione di mercato corrente |
| `attivo` | 0/1 | ✅ | `0` per svincolati o fuori rosa: restano nel file ma non vanno all'asta |

**Note critiche:**
- `id` deve essere lo **stesso identificativo** usato negli export storici, altrimenti
  il collegamento con `statistiche.csv` salta. Verificarlo su un campione di 20 giocatori.
- Nessun `id` duplicato.
- Includere **tutti** i giocatori del listone, anche le riserve da 1 credito: il motore
  ha bisogno del pool completo per calcolare il livello di rimpiazzo.

---

### 4.2 `statistiche.csv` — rendimento storico

Una riga per **giocatore-stagione**. Servono le ultime **3 stagioni concluse**;
2 sono il minimo accettabile.

| Colonna | Tipo | Obbl. | Descrizione |
|---|---|---|---|
| `id` | int | ✅ | Riferimento a `giocatori.id` |
| `stagione` | string | ✅ | Formato `AAAA-AA`, es. `2025-26` |
| `squadra` | string | ✅ | Club **in quella stagione** |
| `ruolo` | enum | ✅ | Ruolo **in quella stagione** |
| `pg` | int | ✅ | Partite con voto |
| `minuti` | int | ⚠️ | **Minuti totali giocati.** Vedi riquadro sotto |
| `mv` | float | ✅ | Media voto |
| `mf` | float | ✅ | Fantamedia |
| `gf` | int | ✅ | Gol fatti |
| `gs` | int | ✅ | Gol subiti (portieri) |
| `rp` | int | ✅ | Rigori parati (portieri) |
| `rc` | int | ✅ | Rigori calciati |
| `rpiu` | int | ✅ | Rigori segnati |
| `rmeno` | int | ✅ | Rigori sbagliati |
| `ass` | int | ✅ | Assist |
| `asf` | int | | Assist "da fantacalcio", se la fonte li distingue |
| `amm` | int | ✅ | Ammonizioni |
| `esp` | int | ✅ | Espulsioni |
| `au` | int | ✅ | Autogol |

> ### ⚠️ I minuti sono il campo più importante di tutto il database
>
> Gli export ufficiali del fantacalcio riportano solo le **partite con voto**: un
> subentrante entrato al 75' per dieci volte risulta con 10 presenze, esattamente come un
> titolare che ha giocato dieci partite intere. Sono due giocatori completamente diversi,
> e senza i minuti il modello non può distinguerli.
>
> I minuti **non sono nell'export del fantacalcio** e vanno presi da una fonte statistica
> esterna (sezione 5.3), con un join sui nomi. È il pezzo di lavoro più delicato
> dell'intero incarico. Se per un giocatore i minuti non si trovano, lasciare vuoto e
> registrare in `lacune.csv` — **non stimare `pg × 90`**, sarebbe esattamente l'errore
> che questo campo serve a evitare.

**Coerenza da verificare:** `rpiu + rmeno` deve essere uguale a `rc`. Se non lo è,
la fonte usa una convenzione diversa: documentarlo nel `manifest.json`.

---

### 4.3 `contesto.csv` — situazione stagione corrente

Una riga per giocatore attivo. È il blocco a più alto valore aggiunto e quello che
richiede lavoro editoriale: qui l'inserimento manuale è legittimo.

| Colonna | Tipo | Obbl. | Descrizione |
|---|---|---|---|
| `id` | int | ✅ | Riferimento a `giocatori.id` |
| `titolarita` | float | ⚠️ | Probabilità di partire titolare, da `0.0` a `1.0`. Vedi scala sotto |
| `ballottaggio_con` | string | | Nome del concorrente diretto per il posto |
| `rigorista` | int | | `0` non rigorista · `1` primo rigorista · `2` secondo |
| `calci_piazzati` | 0/1 | | Batte punizioni |
| `corner` | 0/1 | | Batte i corner |
| `stato` | enum | | `ok` · `infortunato` · `squalificato` · `fuori_rosa` |
| `rientro_stimato` | date | | Solo se `stato` ≠ `ok` |
| `fascia` | string | | Fascia di consiglio editoriale, se disponibile |
| `nota` | string | | Testo libero, max 200 caratteri |

**Scala consigliata per `titolarita`** — dichiararla nel manifest se se ne usa un'altra:

| Valore | Significato |
|---|---|
| `1.00` | Titolare inamovibile |
| `0.80` | Titolare con turnover occasionale |
| `0.60` | Ballottaggio favorevole |
| `0.40` | Ballottaggio sfavorevole |
| `0.20` | Subentrante abituale |
| `0.05` | Fuori dalle rotazioni |

**Trucco per i rigoristi:** oltre alle fonti editoriali, i rigoristi si deducono dallo
storico. Un giocatore con `rc ≥ 3` nella stagione precedente era quasi certamente il
rigorista designato. Usare questo come verifica incrociata e segnalare le discordanze.

---

### 4.4 `avanzate.csv` — metriche predittive

Opzionale ma con il miglior rapporto valore/fatica di tutto il database. Una riga per
giocatore-stagione, per le ultime 2 stagioni.

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id` | int | Riferimento a `giocatori.id` |
| `stagione` | string | Formato `AAAA-AA` |
| `minuti` | int | Minuti secondo **questa** fonte (può differire da `statistiche.minuti`) |
| `xg` | float | Gol attesi, totale stagione |
| `npxg` | float | Gol attesi esclusi i rigori |
| `xa` | float | Assist attesi, totale stagione |
| `tiri` | int | Tiri totali |
| `tiri_porta` | int | Tiri nello specchio |
| `tocchi_area` | int | Tocchi in area avversaria |
| `passaggi_chiave` | int | Passaggi che generano un tiro |

> **Perché serve:** i gol segnati sono un dato rumoroso. Un attaccante che ha segnato 15
> gol con 9 xG ha quasi certamente avuto una stagione fortunata e l'anno dopo calerà;
> chi ne ha segnati 6 con 11 xG è sottovalutato dal mercato. Gli xG predicono i gol della
> stagione successiva sensibilmente meglio dei gol della stagione precedente. È
> l'informazione che il mercato del fantacalcio prezza peggio, quindi è lì che si trova
> il vantaggio.

---

### 4.5 `squadre.csv`

Una riga per club di Serie A della stagione corrente (20 righe).

| Colonna | Tipo | Obbl. | Descrizione |
|---|---|---|---|
| `squadra` | string | ✅ | Chiave normalizzata, coerente con `giocatori.squadra` |
| `nome_ufficiale` | string | | Denominazione estesa |
| `allenatore` | string | | |
| `promossa` | 0/1 | ✅ | `1` se neopromossa: lo storico dei suoi giocatori è di Serie B e va pesato meno |
| `gf_prec` | int | | Gol fatti nella stagione precedente in Serie A |
| `gs_prec` | int | | Gol subiti nella stagione precedente in Serie A |

---

### 4.6 `calendario.csv`

Una riga per partita, 380 righe per una stagione completa.

| Colonna | Tipo | Obbl. | Descrizione |
|---|---|---|---|
| `giornata` | int | ✅ | Da 1 a 38 |
| `data` | date | | `AAAA-MM-GG` |
| `casa` | string | ✅ | Chiave da `squadre.csv` |
| `trasferta` | string | ✅ | Chiave da `squadre.csv` |

Serve al software per calcolare la difficoltà delle prime giornate, che pesa sulla
scelta fra due giocatori di valore simile.

---

### 4.7 `prezzi_asta.csv`

Prezzi di riferimento realmente pagati nelle aste, **normalizzati su 1000 crediti**
per essere indipendenti dal budget della lega.

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id` | int | Riferimento a `giocatori.id`, dove ricostruibile |
| `nome` | string | Nome come nella fonte |
| `prezzo_medio_per_1000` | float | Media dei prezzi pagati, per 1000 crediti di budget |
| `mediana_per_1000` | float | Mediana |
| `p25` | float | 25° percentile |
| `p75` | float | 75° percentile |
| `n_campioni` | int | Numero di aste su cui è calcolato |
| `partecipanti` | int | Numero di squadre della lega, se la fonte lo segmenta |
| `fonte` | string | Identificativo della fonte |

Un seed di 531 righe è **già disponibile** (sezione 9). Va integrato e, se possibile,
arricchito con mediana e quartili: la dispersione dei prezzi indica quanto un giocatore
è contendibile, ed è più informativa della sola media.

---

### 4.8 `mappa_nomi.csv` — la tabella di raccordo

Indispensabile, perché ogni fonte scrive i nomi in modo diverso.

| Colonna | Tipo | Descrizione |
|---|---|---|
| `id` | int | ID Fantacalcio |
| `nome_fantacalcio` | string | Come nel listone |
| `nome_fonte_stat` | string | Come nella fonte dei minuti/xG |
| `nome_normalizzato` | string | Forma canonica: minuscolo, senza accenti, senza punti |
| `metodo` | enum | `esatto` · `fuzzy` · `manuale` |
| `confidenza` | float | Da `0.0` a `1.0` |

**Procedura di join richiesta:**

1. Normalizzare entrambi i lati: minuscolo, rimozione accenti e diacritici,
   rimozione punteggiatura, compressione degli spazi.
2. Tentare il match esatto su `nome_normalizzato` + `squadra`.
3. Per i residui, match fuzzy (distanza di Levenshtein o simile) **con soglia alta**,
   sempre vincolato dalla squadra.
4. **Tutto ciò che non raggiunge la soglia va rivisto a mano.** Un match sbagliato è
   peggiore di un match mancato: attribuisce a un giocatore le statistiche di un altro,
   e nessun controllo a valle se ne accorge.
5. Riportare `metodo` e `confidenza` per ogni riga.

**Trappole note in Serie A:** omonimi nella stessa squadra (`Martinez Jo.` / `Martinez L.`),
nomi doppi accorciati diversamente da fonte a fonte, giocatori sudamericani registrati con
il nome di battesimo in una fonte e il cognome nell'altra, trascrizioni diverse dei nomi
dell'Europa dell'Est.

---

### 4.9 `lacune.csv` — registro delle mancanze

| Colonna | Tipo | Descrizione |
|---|---|---|
| `file` | string | File interessato |
| `id` | int | Giocatore, se applicabile |
| `colonna` | string | Campo mancante |
| `motivo` | string | Perché non è stato reperito |
| `fonte_tentata` | string | Dove è stato cercato |

Questo file è parte della consegna a pieno titolo. Un database con 40 lacune dichiarate
è utilizzabile; un database con 40 lacune riempite a caso non lo è.

---

## 5. Fonti dei dati

> Le indicazioni seguenti riflettono l'assetto noto delle fonti. **Verificare che siano
> ancora attive, accessibili e nel formato descritto** prima di costruirci sopra la
> pipeline: siti e API cambiano. Se una fonte non è più valida, cercarne una equivalente
> e documentare la sostituzione nel manifest.

### 5.1 Anagrafica, quotazioni, statistiche ufficiali

**Fantacalcio.it** e **Leghe Fantacalcio** pubblicano il *listone* ufficiale e le
statistiche stagionali in formato `.xlsx` scaricabile dall'area riservata. Sono la fonte
**canonica** per: `id`, `ruolo`, `qi`, `qa`, e tutte le colonne di `statistiche.csv`
tranne i minuti.

È la fonte da cui partire, ed è quella che definisce gli `id` che fanno da chiave a tutto
il resto. Il formato dell'export statistiche corrisponde esattamente alle colonne
`Id, R, Nome, Squadra, Pg, Mv, Mf, Gf, Gs, Rp, Rc, R+, R−, Ass, Amm, Esp, Au`
dei file di seed già forniti — quindi la pipeline che li legge funziona su entrambi.

### 5.2 Prezzi d'asta

**Fantalab** è la fonte più nota per dati e strumenti d'asta, incluse statistiche sui
prezzi realmente pagati. Verificare se espone i dati in forma esportabile.

In assenza, il seed fornito (531 giocatori con prezzo medio normalizzato) è una base
sufficiente per far partire il software; l'arricchimento con mediana e quartili è un
miglioramento successivo, non un requisito bloccante.

### 5.3 Minuti giocati e metriche avanzate

**FBref** (Sports Reference) pubblica per la Serie A, gratuitamente, statistiche per
giocatore con minuti, xG, npxG, xA, tiri, tocchi in area e passaggi chiave, con tabelle
esportabili in CSV. È la fonte consigliata sia per `statistiche.minuti` sia per
`avanzate.csv`. Rispettarne i limiti di frequenza dichiarati.

**Understat** copre la Serie A con xG e xA e ha una struttura dati facilmente leggibile.
Utile come fonte alternativa o di verifica incrociata.

Se le due fonti divergono su un valore, **preferire la coerenza interna**: usare una sola
fonte per tutte le colonne avanzate, e dichiararla nel manifest. Mescolare xG di provenienze
diverse introduce distorsioni difficili da individuare.

### 5.4 Calendario

Il sito ufficiale della **Lega Serie A** pubblica il calendario completo. Esistono anche
API pubbliche per i calendari dei principali campionati europei con piani gratuiti
sufficienti a questo scopo. Verificare quale sia disponibile e documentarla.

### 5.5 Titolarità, rigoristi, calci piazzati, infortuni

Non esistono in forma strutturata e gratuita. Le fonti sono editoriali: sezioni
"probabili formazioni", "consigli asta" e "rigoristi" delle principali testate di settore
(Fantacalcio.it, SOS Fanta, Gazzetta dello Sport).

**Approccio consigliato:** consultazione manuale e compilazione diretta di `contesto.csv`,
integrata dalla deduzione dai rigori calciati storici. Non tentare di automatizzare questa
parte: le fonti sono prosa, cambiano ogni settimana, e un parser fragile produce dati
sbagliati con l'apparenza di dati buoni.

### 5.6 Trasferimenti e nuovi acquisti

Ricavabile confrontando la `squadra` del listone corrente con quella della stagione
precedente nei file storici: se differisce, `nuovo_acquisto = 1`. Non serve una fonte
esterna, ed è più affidabile.

---

## 6. Regole di validazione

La pipeline deve terminare eseguendo questi controlli e **stampare un report**.
Ogni violazione va risolta o giustificata in `lacune.csv`.

### 6.1 Integrità referenziale

- Ogni `id` in `statistiche`, `contesto`, `avanzate`, `prezzi_asta` esiste in `giocatori`
- Nessun `id` duplicato in `giocatori`
- Nessuna coppia `(id, stagione)` duplicata in `statistiche` e `avanzate`
- Ogni `squadra` in `giocatori` e `calendario` esiste in `squadre`

### 6.2 Domini e intervalli

- `ruolo` ∈ {`P`, `D`, `C`, `A`}
- `0 ≤ pg ≤ 38`
- `0 ≤ minuti ≤ 3600`, e `minuti ≥ pg × 20` (chi ha un voto ha giocato abbastanza)
- `0 ≤ mv ≤ 10`
- `mf` può essere negativa (malus), non va scartata
- `0 ≤ titolarita ≤ 1`
- `rpiu + rmeno == rc`, oppure convenzione diversa documentata
- `gs` e `rp` valorizzati solo per i portieri
- `qi ≥ 1`, `qa ≥ 1`

### 6.3 Plausibilità aggregata

Il conteggio dei giocatori per ruolo deve essere nell'ordine di grandezza atteso per un
listone di Serie A:

| Ruolo | Ordine di grandezza atteso |
|---|---|
| `P` | 60 – 90 |
| `D` | 170 – 220 |
| `C` | 180 – 230 |
| `A` | 70 – 110 |

Uno scostamento marcato segnala quasi sempre un errore di parsing o un filtro applicato
per sbaglio.

### 6.4 Copertura — da riportare esplicitamente

Per ogni colonna importante, la percentuale di righe valorizzate:

| Colonna | Copertura minima accettabile |
|---|---|
| `statistiche.pg`, `mv`, `mf` | 95 % dei giocatori con almeno una stagione |
| `statistiche.minuti` | 85 % |
| `contesto.titolarita` | 90 % dei giocatori attivi |
| `contesto.rigorista` | 100 % (dove non è rigorista, il valore è `0`, non vuoto) |
| `avanzate.xg`, `xa` | 80 % dei giocatori di movimento |

Sotto queste soglie, segnalarlo chiaramente nel report finale invece di consegnare
in silenzio.

---

## 7. Template `regole_lega.json`

Da consegnare **vuoto e commentato**: lo compilerà l'utente con le regole della sua lega.
Il software lo userà per convertire le statistiche in punti attesi, quindi la struttura
va rispettata.

```json
{
  "_commento": "Compilare con le regole effettive della propria lega prima di usare il software.",

  "partecipanti": 10,
  "crediti_iniziali": 250,

  "rosa": {
    "portieri": 3,
    "difensori": 8,
    "centrocampisti": 8,
    "attaccanti": 6
  },

  "bonus_malus": {
    "_commento": "Valori standard del fantacalcio classico. Verificare il regolamento della propria lega.",
    "gol_portiere": 3,
    "gol_difensore": 3,
    "gol_centrocampista": 3,
    "gol_attaccante": 3,
    "assist": 1,
    "gol_subito": -1,
    "rigore_parato": 3,
    "rigore_sbagliato": -3,
    "autogol": -2,
    "ammonizione": -0.5,
    "espulsione": -1
  },

  "portiere_imbattuto": {
    "attivo": true,
    "bonus": 1
  },

  "modificatore_difesa": {
    "_commento": "ATTENZIONE: la scala varia molto da lega a lega. Inserire quella del proprio regolamento. Se attivo, cambia radicalmente il valore di portieri e difensori: conta la media voto, non i bonus.",
    "attivo": true,
    "componenti": "portiere + 3 migliori difensori",
    "scala": [
      { "media_minima": 6.0, "bonus": 1 },
      { "media_minima": 6.5, "bonus": 2 },
      { "media_minima": 7.0, "bonus": 4 }
    ]
  },

  "modificatore_centrocampo": { "attivo": false },
  "modificatore_attacco":     { "attivo": false },
  "modificatore_fairplay":    { "attivo": false },

  "sostituzioni": 3
}
```

> Il modificatore di difesa merita attenzione particolare: quando è attivo, un portiere
> affidabile da 6,3 di media vale molto più di uno spettacolare ma discontinuo, e i
> difensori vanno valutati sulla media voto più che sui gol. È la singola regola che
> più cambia la strategia d'asta, ed è anche quella che il foglio Excel di partenza
> gestiva in modo difettoso.

---

## 8. `manifest.json`

Obbligatorio. Documenta cosa è stato costruito, da dove, e quando.

```json
{
  "generato_il": "2026-09-02",
  "stagione_corrente": "2026-27",
  "stagioni_storiche": ["2025-26", "2024-25", "2023-24"],
  "modalita": "classic",

  "fonti": [
    {
      "blocco": "anagrafica_quotazioni",
      "nome": "",
      "url": "",
      "tipo": "export_xlsx",
      "scaricato_il": "",
      "note": ""
    },
    {
      "blocco": "statistiche_storiche",
      "nome": "", "url": "", "tipo": "", "scaricato_il": "", "note": ""
    },
    {
      "blocco": "minuti_avanzate",
      "nome": "", "url": "", "tipo": "", "scaricato_il": "", "note": ""
    },
    {
      "blocco": "calendario",
      "nome": "", "url": "", "tipo": "", "scaricato_il": "", "note": ""
    },
    {
      "blocco": "contesto_editoriale",
      "nome": "", "url": "", "tipo": "manuale", "scaricato_il": "", "note": ""
    }
  ],

  "conteggi": {
    "giocatori": 0,
    "per_ruolo": { "P": 0, "D": 0, "C": 0, "A": 0 },
    "righe_statistiche": 0,
    "righe_avanzate": 0
  },

  "copertura": {
    "minuti": 0.0,
    "titolarita": 0.0,
    "xg": 0.0
  },

  "convenzioni": {
    "scala_titolarita": "descrizione della scala usata",
    "rigori": "rpiu + rmeno == rc",
    "fonte_xg_unica": ""
  },

  "lacune_totali": 0,
  "avvertenze": []
}
```

---

## 9. Dati di seed già disponibili

Nella cartella `seed/` ci sono file estratti da uno strumento Excel preesistente.
Sono **materiale di partenza e di verifica**, non la consegna finale.

| File | Righe | Contenuto | Come usarlo |
|---|---|---|---|
| `seed_listone_stagione_recente.csv` | 679 | Statistiche complete con **ID ufficiali** | Riferimento per il formato e per verificare la continuità degli `id` |
| `seed_listone_stagione_precedente.csv` | 679 | Idem, stagione precedente | Idem |
| `seed_storico_movimento.csv` | 493 | Due stagioni aggregate, giocatori di movimento | Verifica incrociata |
| `seed_storico_portieri.csv` | 75 | Due stagioni aggregate, portieri | Verifica incrociata |
| `seed_giocatori_correnti.csv` | 530 | Quotazioni + dati editoriali (fasce, note, consigli) | **Base per `contesto.csv`** |
| `seed_prezzi_asta.csv` | 531 | Prezzo medio d'asta per 1000 crediti | **Base per `prezzi_asta.csv`** |
| `seed_indice_appetibilita.csv` | 30 | Tabella quotazione → indice di appetibilità | Riferimento, uso opzionale |
| `seed_squadre.csv` | 20 | Elenco squadre | ⚠️ Vedi avvertenza |

> ### ⚠️ Avvertenze sui file di seed
>
> - **`seed_squadre.csv` non è affidabile per la stagione corrente.** Contiene club che
>   con ogni probabilità non sono nella Serie A in corso. Va **sostituito** con l'elenco
>   ufficiale, non integrato.
> - I file di seed non contengono i **minuti giocati**: è proprio la lacuna che questo
>   incarico deve colmare.
> - Le colonne di prezzo nei seed (`p_med_aste`, `p_stat`, `p_gol_m`) sono **output di un
>   vecchio algoritmo**, non dati di input. Vanno ignorate: il nuovo software calcola i
>   propri prezzi.
> - La colonna `fv` è un rating di provenienza ignota e non ricostruibile. Può essere
>   trasportata come riferimento, ma **non va usata come dato autorevole** né come
>   sostituto di una proiezione calcolata sui dati reali.
> - Le colonne `note`, `sos`, `fascia_o_valore` sono giudizi editoriali di una stagione
>   passata: utili come esempio del vocabolario da usare, non come dato corrente.

---

## 10. Checklist finale di consegna

Prima di consegnare, verificare punto per punto:

- [ ] Tutti i file della sezione 3.1 sono presenti
- [ ] Tutti i CSV sono UTF-8 senza BOM, separatore virgola, decimale punto
- [ ] `manifest.json` compilato in ogni campo, con URL reali e date
- [ ] I controlli della sezione 6 sono stati eseguiti e il report è allegato
- [ ] Le percentuali di copertura sono dichiarate, anche quando sotto soglia
- [ ] `lacune.csv` è compilato e non vuoto (un file vuoto è sospetto)
- [ ] `mappa_nomi.csv` riporta metodo e confidenza per ogni riga
- [ ] I match fuzzy sotto soglia sono stati rivisti manualmente
- [ ] Lo script `pipeline/build.py` è rieseguibile da zero e documentato
- [ ] Nessun valore numerico è stato inserito a memoria o per stima
- [ ] Nessun ruolo Mantra è presente in nessun file
- [ ] `regole_lega.json` è consegnato vuoto e commentato

---

## 11. Priorità, se il tempo non basta

Se non è possibile completare tutto, consegnare in quest'ordine. Ogni livello è
utilizzabile da solo.

1. **Minimo funzionante** — `giocatori.csv` + `statistiche.csv` (senza minuti) +
   `squadre.csv` + `regole_lega.json`.
   Il software gira e calcola già prezzi migliori del foglio Excel di partenza.

2. **Buono** — aggiungere `contesto.csv` con almeno `titolarita` e `rigorista`, e
   `prezzi_asta.csv`.
   Le proiezioni diventano credibili.

3. **Ottimo** — aggiungere `statistiche.minuti` e `calendario.csv`.
   Il modello distingue titolari da subentranti: è il salto di qualità maggiore.

4. **Eccellente** — aggiungere `avanzate.csv` con xG e xA.
   Il software inizia a vedere quello che il mercato non prezza.

---

## 12. Cosa succede dopo

Il pacchetto verrà caricato in un database SQLite locale. Da lì il software calcolerà,
per ogni giocatore, i punti attesi sulla stagione; da questi il valore rispetto al
giocatore di rimpiazzo; e da questo, a ogni acquisto registrato durante l'asta, un prezzo
di mercato aggiornato in tempo reale.

Per questo la **completezza e l'onestà** del database contano più della sua ampiezza.
Un dato mancante e dichiarato viene gestito. Un dato sbagliato che sembra buono si
propaga in silenzio fino al consiglio d'acquisto, e nessuno se ne accorge finché non è
troppo tardi.
