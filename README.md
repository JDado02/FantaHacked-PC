# FantaHacked — assistente d'asta per il fantacalcio

Dice **fino a quanto conviene spingersi** su ogni giocatore, durante l'asta,
mentre l'asta è in corso.

## ⬇️ [Scarica FantaHacked.exe](https://github.com/JDado02/FantaHacked-PC/raw/main/FantaHacked.exe)

**22 MB, Windows, un file solo.** Si mette dove si vuole — anche su una
chiavetta — e si apre con un doppio clic: non c'è niente da installare e
niente da configurare.

Due avvisi, la prima volta, e sono due cose diverse:

- **il browser** dice che il file «non viene scaricato spesso» e lo blocca:
  nel riquadro dei download, `⋯` → *Mantieni*;
- **Windows SmartScreen** dice «Windows ha protetto il PC», perché
  l'eseguibile non ha una firma digitale a pagamento: *Ulteriori informazioni*
  → *Esegui comunque*.

Al primo avvio si scarica i dati dei giocatori (mezzo mega) e si crea accanto
`database/` e `motore/`. Da lì in poi funziona anche senza rete.

C'è anche [per Android](https://github.com/JDado02/FantaHacked-Android).

---

Non è un listone con dei voti accanto. È un ottimizzatore: a ogni chiamata
risponde alla domanda *«oltre quale prezzo comprarlo peggiora la mia rosa
finale?»*, e la risposta cambia dopo ogni acquisto — tuo e degli altri.

In **trecento** aste simulate contro avversari che pagano i prezzi realmente
pagati nelle aste vere, ne vince **288**: 96%, e non esce mai dal podio.

Lo stesso motore gira anche sul telefono, e non è una versione ridotta:
duecento aste giocate dal computer e duecento dal telefono, con lo stesso
generatore casuale e gli stessi semi, danno **4.800 numeri identici e zero
differenze**.

---

## Come si usa

**Un file solo.** `FantaHacked.exe` si copia dove si vuole — anche su una
chiavetta, anche in una cartella vuota — e funziona: interfaccia, motore,
schemi e regolamento predefinito viaggiano dentro l'eseguibile. Al primo
avvio si scarica i dati dei giocatori (mezzo mega) e si crea accanto le due
cartelle che gli servono:

```
FantaHacked.exe
├── database/dati.db     scaricato, si può ributtare via quando si vuole
└── motore/asta.db       la tua asta, che non esce mai da qui
```

Doppio clic su `FantaHacked.exe`. Si apre una finestra con la sua icona: non è
una scheda del browser, e per uscire si chiude come qualunque programma.

1. **Nuova asta**, con le regole lette da `database/regole_lega.json`.
2. Si danno i nomi alle squadre. La prima è la tua: tutto è calcolato dal tuo
   punto di vista.
3. Quando tocca a te, la scheda **«chi chiamare»** propone due liste separate:
   chi conviene prendere, e chi conviene **far pagare agli altri**.
4. Quando esce un giocatore lo cerchi per nome (tasto `/`) e leggi fino a
   quanto vale la pena spingerti.
5. Registri chi se l'è aggiudicato e a quanto. **Tutti i prezzi si
   ricalcolano** su chi è già uscito, sulle rose di tutti e sui crediti
   rimasti a ciascuno.

La regola che conta è una: **il limite è un muro, non un obiettivo.** In
seimilanovecento acquisti non ha mai pagato un credito sopra il proprio
limite, e nel 77% dei casi ha chiuso sotto il prezzo di mercato. Il foglio
completo è in [`REGOLE_PER_L_ASTA.md`](REGOLE_PER_L_ASTA.md).

---

## Come è fatto

```
FantaHacked.exe          l'eseguibile (si costruisce, non sta nel repository)
├── app/
│   ├── server.py        server locale su 127.0.0.1, espone /api/*
│   └── web/             l'interfaccia: una pagina, niente framework
├── motore/
│   ├── db.py            i due database SQLite e come si aprono insieme
│   ├── aggiornamento.py scarica i dati pubblicati, rifà le proiezioni
│   ├── proiezioni.py    da statistiche e gerarchie ai punti attesi
│   ├── valutazione.py   VOR, curva dei prezzi, prezzo atteso
│   ├── ottimizzatore.py knapsack esatto, max_bid
│   ├── strategia.py     verdetti, classifiche, chi far pagare agli altri
│   └── asta.py          lo stato dell'asta
├── database/
│   ├── pipeline/        ricostruisce i CSV dalle fonti, e li pubblica
│   └── fonti/           le fonti grezze, così come sono state lette
├── build/
│   ├── FantaHacked.spec come si costruisce l'eseguibile
│   └── marchio.py       il marchio, in nove misure, da una geometria sola
└── simulazioni/         trecento aste per misurare ogni modifica
```

### Nessuna richiesta alla rete per disegnarsi

I caratteri sono quelli del sistema — Bahnschrift per i numeri, Segoe per il
testo — e non si scaricano da nessuna parte. Un foglio di stile esterno blocca
il primo disegno della pagina finché non arriva o non scade, e la sera
dell'asta il wifi della stanza fa quello che vuole. L'unica richiesta che il
programma fa è per i dati dei giocatori, e sa già cosa fare se non risponde.

### I due database

| file | cosa c'è | dove sta |
|---|---|---|
| `database/dati.db` | listone, statistiche, gerarchie, proiezioni | **si scarica** da [DBFantaHacked](https://github.com/JDado02/DBFantaHacked) |
| `motore/asta.db` | asta, presidenti, acquisti | resta sul dispositivo, non esce mai |

Il primo si può sostituire in blocco quando si vuole, anche a stagione
iniziata, senza sfiorare il secondo. All'avvio il programma controlla se ce
n'è una versione più recente leggendo un file da 310 byte; se internet non
c'è, parte lo stesso con quello che ha.

---

## Le idee che lo fanno funzionare

**Il prezzo non è il valore.** Sui prezzi realmente pagati, spartire i crediti
in proporzione al merito sbaglia del 48%; la sola quotazione ufficiale del 40%;
i due insieme del 34%. La curva dei prezzi è quella media.

**Il numero da mostrare e il numero con cui decidere non sono lo stesso
numero.** `prezzo_atteso` risponde a *quanto costerà*, `prezzo_piano` a *quanto
offrire*. Tenerli uniti costa sette vittorie su cento.

**Una casella vuota non fa punti.** Verso la fine dell'asta il valore sopra il
rimpiazzo va a zero per tutti insieme, e il motore diceva «lascialo» a
ventinove attaccanti di fila. Ora sa che uno scarso batte comunque il vuoto.

**Le coppie si comprano in due.** Due giocatori della stessa squadra che si
dividono un posto coprono la maglia quasi ogni giornata, e il secondo costa una
frazione del primo.

**Chi non può giocare vale zero, non poco.** Un infortunio toglie giornate;
l'esclusione dalla lista di serie A le toglie tutte.

Il racconto completo, con i numeri di ogni modifica e degli errori corretti, è
in [`PROGRESSI.md`](PROGRESSI.md).

---

## Rifare tutto da zero

```bash
python database/pipeline/build.py      # dai file grezzi ai CSV
python database/pipeline/consenso.py   # il consenso fra le guide
python motore/db.py                    # i due database
python motore/proiezioni.py            # i punti attesi
```

E per pubblicare i dati aggiornati:

```bash
python database/pipeline/pubblica.py --pubblica
```

### Costruire l'eseguibile

```bash
python -m PyInstaller --clean --distpath . --workpath build/lavoro build/FantaHacked.spec
```

Va lanciato **dalla cartella del progetto**: lo `.spec` ha percorsi relativi, e
da un'altra cartella produce un eseguibile che non parte.

Se accanto all'eseguibile c'è una copia vera di `app/web`, `motore/schema_*.sql`
o `database/regole_lega.json`, vince quella su quella impacchettata. Serve a
due cose opposte: lavorare sull'interfaccia senza ricostruire l'exe a ogni
riga, e permettere di correggersi il proprio regolamento senza toccare il
programma.

---

## Dove sta il resto

| | |
|---|---|
| [FantaHacked-Android](https://github.com/JDado02/FantaHacked-Android) | la stessa cosa sul telefono: il motore tradotto in JavaScript |
| [DBFantaHacked](https://github.com/JDado02/DBFantaHacked) | i dati pubblicati, che entrambi scaricano |

## Le verifiche

```bash
python motore/test_motore.py           # 47 sul motore
python motore/test_aggiornamento.py    # 23 sui due database e sull'aggiornamento
python app/test_app.py                 # 264 sull'applicazione, contro un server vero
python simulazioni/cento_aste.py 300   # trecento aste complete
python build/marchio.py                # icone e SVG, se cambia il marchio
```

E le due che tengono allineati i due motori. Il motore Python fotografa i
propri numeri in quattro momenti di un'asta, la parte JavaScript li rilegge e
li confronta uno per uno:

```bash
python simulazioni/dump_equivalenza.py  <FantaHacked-Android>/prove/attesi.json
python simulazioni/dump_consiglio.py    <FantaHacked-Android>/prove/attesi_consiglio.json
```

E una terza, che non guarda i numeri ma **le aste**: duecento partite intere
giocate dai due motori con lo stesso generatore casuale e gli stessi semi.

```bash
python simulazioni/cento_aste.py 200
# poi si copia simulazioni/cento_aste_mercato.json in
# <FantaHacked-Android>/prove/attesi_aste.json e si apre prove/aste.html
```

Oggi: **22.356 numeri, 44 liste e 200 aste (4.800 numeri), zero differenze.** La soglia e' un
milionesimo in relativo, e zero sugli interi &mdash; dove uno scarto non e'
virgola mobile, e' una decisione diversa.

Girano su copie usa e getta dei database: non toccano mai l'asta in corso.

E una che serve quando cambiano i dati e il numero di vittorie si muove:

```bash
python simulazioni/confronta_esiti.py prima.json simulazioni/cento_aste_mercato.json
```

Confronta le stesse aste, seme per seme, e dice **quali** hanno cambiato esito
e di quanto si è mosso il punteggio di ciascuna delle otto squadre. Serve a
distinguere un peggioramento vero dal rumore: un'asta è un sistema caotico, e
un rilancio diverso a metà reparto cambia da lì in poi la rosa di tutti.

Una dipendenza sola, e conviene sapere perché: **numpy**. Lo zaino esatto
gira su vettori interi, e con numpy un consiglio completo esce in 35
millisecondi contro 58, e un limite in 2,4 contro 7,4. Senza, il motore non si
limita a rallentare: pota il pool a 45 giocatori (`POOL_MAX_SENZA_NUMPY`) e
**dà numeri diversi**. Tutte le misure di questo file — le trecento aste, le
prove di equivalenza — sono fatte con numpy, ed è per questo che
`FantaHacked.exe` se lo porta dentro. Tutto il resto è libreria standard di
Python 3.8+.
