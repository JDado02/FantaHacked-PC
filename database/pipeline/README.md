# Pipeline di costruzione del database

Ricostruisce da zero tutti i CSV in `../` a partire dalle fonti in `../fonti/`.

```bash
python build.py
```

Nessuna dipendenza esterna: solo la libreria standard di Python 3.8+.
`requirements.txt` è vuoto di proposito.

Lo script è **idempotente**: cancella e riscrive gli output a ogni esecuzione.
Termina stampando un report di copertura e validazione, e scrive `../lacune.csv`
e `../manifest.json`.

---

## File

| File | Ruolo |
|---|---|
| `build.py` | Pipeline completa: lettura fonti, abbinamento, scrittura, validazione |
| `nomi.py` | Normalizzazione e abbinamento dei nomi fra fonti diverse |

---

## Come rifarlo la prossima stagione

### 1. Sostituire le fonti in `../fonti/`

| File | Da dove | Note |
|---|---|---|
| `seed_giocatori_correnti.csv` | Listone ufficiale della nuova stagione | Colonne minime: `ruolo, nome, squadra, qt_fanta` |
| `seed_listone_stagione_recente.csv` | Export statistiche stagione appena conclusa | Deve contenere la colonna `id` |
| `seed_listone_stagione_precedente.csv` | Export statistiche stagione precedente | Idem |
| `understat_seriea_AAAA.json` | `https://understat.com/getLeagueData/Serie%20A/AAAA` | Header `X-Requested-With: XMLHttpRequest`, e `curl --compressed` |
| `calendario_seriea_AAAA_AA.csv` | `https://fixturedownload.com/download/serie-a-AAAA-UTC.csv` | 380 partite |
| `seed_prezzi_asta.csv` | Prezzi medi d'asta, normalizzati su 1000 crediti | Facoltativo ma consigliato |

### 2. Aggiornare le costanti in testa a `build.py`

```python
STAGIONE_CORRENTE = '2026-27'
STAGIONI_STORICHE = ['2025-26', '2024-25', '2023-24']
LISTONE_SEASON    = {...}   # quale file copre quale stagione
UNDERSTAT_SEASON  = {...}   # anno nell'URL -> etichetta stagione
```

> **Verifica sempre a quale stagione corrisponde ogni listone** invece di
> fidarti del nome del file. Il modo rapido: confrontare la colonna `gf` con i
> gol della fonte avanzata per la stessa annata. Se l'accordo supera il 99% la
> stagione è quella; se sta sotto il 40%, è un'altra. È così che sono state
> identificate le stagioni di questa edizione.

### 3. Eseguire e leggere il report

Controllare in quest'ordine:

1. **errori bloccanti** — devono essere zero
2. **`ABBINATI`** — sotto il 70% c'è quasi sempre un problema di normalizzazione dei nomi, non di dati
3. **copertura `statistiche.minuti`** — sotto l'85% conviene indagare
4. **`token_parziale`** in `../mappa_nomi.csv` — vanno **riletti uno per uno**

---

## L'abbinamento dei nomi

È il punto fragile di tutta la pipeline e merita attenzione a ogni riesecuzione.

Il listone scrive i cognomi (`Martinez Jo.`, `Pellegrini Lo.`), la fonte
statistica i nomi completi con i diacritici originali (`Josep Martínez`).
`nomi.py` riconcilia i due mondi con:

- traslitterazione dei caratteri che NFKD non scompone: `ø å æ ß đ ł ı þ`
- varianti ortografiche equivalenti: `N'Dicka` / `Ndicka`, `Del Prato` / `Delprato`
- riconoscimento del suffisso di disambiguazione: `Jo.`, `Lo.`, `Mas.`, `D.S.`

`build.py` applica poi livelli decrescenti di confidenza:

| Metodo | Confidenza | Descrizione |
|---|---|---|
| `cognome` | 0.95 | Cognome semplice o composto identico |
| `cognome+iniziale` | 0.98 | Disambiguato dall'iniziale del nome proprio |
| `cognome+squadra` | 0.97 | Disambiguato dal club |
| `token_parziale` | 0.70 | Un solo token in comune — **da rileggere a mano** |
| `ambiguo` | 0.00 | Più candidati, nessuno scartabile: **non abbinato** |
| `assente_nella_fonte` | 0.00 | Nessun candidato |

### La regola che non va rimossa

> **Un abbinamento sbagliato è peggio di un abbinamento mancato.**

Un match mancato lascia una cella vuota, che si vede. Un match sbagliato
attribuisce a un giocatore le statistiche di un altro, e nessun controllo a
valle se ne accorge.

Per questo il livello `token_parziale` ha una guardia: se un nome a più token
combacia **solo sull'ultimo**, quel token è probabilmente un cognome diffuso
(`Carlos`, `Gomez`) mentre il primo è un nome proprio. L'abbinamento è accettato
solo se anche il primo token compare nel nome della fonte. Senza questa guardia
la prima esecuzione produceva `Kevin Carlos → Diego Carlos` e
`Unai Gomez → Alejandro Gomez`: due giocatori diversi, con statistiche
perfettamente plausibili e completamente sbagliate.

Gli `ambiguo` restano deliberatamente non abbinati: sono pochi e vanno risolti
a mano guardando chi è realmente in rosa.

---

## Cosa la pipeline non fa, di proposito

Non stima `titolarita`, `calci_piazzati`, `corner` e `stato` infortuni. Sono
giudizi prospettici, non dati: nessuna fonte strutturata li espone, e riempirli
con una stima li renderebbe indistinguibili da dati veri.

Al loro posto viene fornito `quota_minuti_2025_26` — i minuti giocati divisi per
i minuti disponibili in una stagione — che è un **dato calcolato su fonte reale**
e un ottimo punto di partenza per costruirci sopra la propria stima.

Il campo `rigorista` fa eccezione: è derivato dai rigori calciati nell'ultima
stagione (≥3 → primo rigorista, 1–2 → secondo, 0 → nessuno). È una derivazione
deterministica su dati reali, non una stima, ed è tracciata nella colonna
`fonte_rigorista` per poterla distinguere da un dato editoriale confermato.
