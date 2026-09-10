# FantaHacked — stato dei lavori

> File di ripresa. Se la sessione si interrompe, **leggi questo per primo**:
> dice cos'è fatto, dove sta, e qual è il passo successivo.
>
> Ultimo aggiornamento: **10 settembre 2026 (decimo giro) &mdash; gli
> infortuni riletti, e due difetti nel metro.**
>
> I dati pubblicati sono di oggi: 53 indisponibili invece di 50, con Locatelli
> fermo fino a gennaio e Felici fino a marzo. Un'installazione da zero scarica
> e apre in **meno di un secondo**; il telefono prende gli stessi numeri.
>
> Due difetti trovati misurando, e corretti:
>
> - **le prove cancellavano l'asta vera.** `test_motore.py` e i due script di
>   confronto giocavano la loro asta finta sul database normale. Adesso c'e'
>   `db.asta_di_servizio()`: dati veri, asta temporanea che sparisce da sola.
> - **il simulatore poteva chiudere un'asta a meta'.** Se un reparto restava
>   senza giocatori da chiamare, i reparti successivi non venivano chiamati
>   affatto, e quell'asta finiva lo stesso nella media.
>
> Rimisurato su trecento aste: **288 vinte, zero rose incomplete**. Il calo da
> 98/100 a 92/100 visto coi dati nuovi era rumore &mdash; sugli stessi semi i
> dati vecchi davano 292/300 e i nuovi 288/300, McNemar p = 0,50.
>
> Il codice sta adesso in tre repository:
> [FantaHacked-PC](https://github.com/JDado02/FantaHacked-PC),
> [FantaHacked-Android](https://github.com/JDado02/FantaHacked-Android),
> [DBFantaHacked](https://github.com/JDado02/DBFantaHacked).
>
> 47 + 23 + 264 verifiche superate, 288 aste vinte su 300.
>
> *(giri precedenti: gli infortuni riletti il 10 settembre e i due difetti nel
> metro; i due motori e la prova che dicono la stessa cosa; i dati che si
> scaricano e l'asta che resta locale; il listone riletto a mercato chiuso e le
> due ripartizioni; la lista di serie A.)*
---

## Come si avvia e come si chiude

**Doppio clic su `FantaHacked.exe`.** Si apre una finestra intitolata FantaHacked,
con la sua icona nella barra delle applicazioni. **Per uscire si chiude la
finestra**, come per qualsiasi programma: il motore si spegne insieme a lei.
Nessun processo che resta acceso senza che si veda.

Non serve avere Python installato: l'eseguibile se lo porta dentro.
L'asta è salvata sul disco a ogni acquisto e si ritrova al riavvio.

**Come funziona.** L'interfaccia è una pagina, ma non si apre in una scheda del
browser: il programma lancia Edge (o Chrome) in modalità applicazione, con un
profilo tutto suo, e quella finestra non ha né barra degli indirizzi né schede.
Il programma tiene d'occhio quel processo: quando finisce, si spegne. Il
profilo della finestra sta in `%LOCALAPPDATA%\FantaHacked`, fuori dalla cartella
del progetto.

Se sul computer non ci fosse nessun browser adatto, si ripiega su quello
predefinito, e allora è la pagina stessa ad avvisare quando viene chiusa
(un semplice ricaricamento non spegne niente: il programma aspetta qualche
secondo, e se la pagina torna annulla l'annuncio).

Resta il pulsante **Chiudi** in alto a destra, per chi lo preferisce.

Se l'antivirus blocca l'`.exe` (capita con i programmi impacchettati), c'è
`Avvia FantaHacked.vbs`, che fa la stessa cosa usando il Python del computer.
`Avvia FantaHacked.bat` è la stessa cosa ma con la finestra nera a vista: serve
a leggere gli errori quando qualcosa non va.

---

## Cosa fa il software

1. **Nuova asta** con le regole lette da `database/regole_lega.json`
   (8 squadre, 500 crediti, 3P/8D/8C/6A, modificatore di difesa attivo).
2. Si danno i nomi alle 8 squadre. La prima è la tua: **tutto è calcolato dal
   tuo punto di vista**, le altre sette sono avversari.
3. L'asta va **per reparti**: si chiamano portieri finché tutti e otto non ne
   hanno tre, poi difensori, centrocampisti, attaccanti. La fase avanza da sola.
4. **Il turno di chiamata lo indichi tu**, cliccando la squadra nella colonna
   di sinistra (o "successivo" per andare a giro).
5. Quando tocca a te, la scheda **"Chi chiamare"** propone due liste separate:
   chi conviene prendere, e chi conviene far pagare agli altri.
6. Quando esce un giocatore lo cerchi per nome (tasto `/`) e ottieni **fino a
   quanto vale la pena spingerti**, o se lasciar perdere.
7. Registri chi se l'è aggiudicato e a quanto: **tutti i prezzi si ricalcolano**
   su chi è già uscito, sulle rose di tutti e sui crediti rimasti a ciascuno.

---

## Struttura del progetto

```
Software fantacalcio/
├── FantaHacked.exe              ← DOPPIO CLIC QUI
├── Avvia FantaHacked.vbs        ← riserva, usa il Python del computer
├── Avvia FantaHacked.bat        ← come sopra, ma mostra gli errori
├── PROGRESSI.md               ← questo file
├── BRIEFING_DATABASE.md       ← come è stato costruito il database
├── database/                  ← i dati (CSV) + regole_lega.json
├── seed/                      ← estratti grezzi dal vecchio Excel
├── motore/                    ← nucleo di calcolo, senza interfaccia
│   ├── percorsi.py            dove stanno i file, da sorgente e da .exe
│   ├── schema_dati.sql  schema_asta.sql  db.py  aggiornamento.py  regole.py
│   ├── proiezioni.py          statistiche storiche → punti attesi
│   ├── titolarita.py          chi gioca davvero: gerarchia di reparto
│   ├── modificatore.py        bonus atteso del modificatore di difesa
│   ├── asta.py                stato dell'asta: acquisti, crediti, turno
│   ├── valutazione.py         VOR + prezzo di mercato
│   ├── ottimizzatore.py       rosa ottima + max_bid personale
│   ├── strategia.py           verdetto sul giocatore + chi chiamare
│   ├── equilibrio.py          undici titolare, coperture, rischi di rosa
│   ├── test_motore.py         35 verifiche del motore
│   ├── fanta.db               database SQLite (si rigenera)
│   ├── fanta.lock             lucchetto: un solo FantaHacked per volta
│   └── fanta.porta            su che porta risponde l'istanza in corso
├── app/
│   ├── server.py              server locale + API JSON
│   ├── test_app.py            43 verifiche, asta intera via HTTP
│   ├── test_chiusura.py       12 verifiche di avvio e spegnimento
│   ├── fantahacked.ico        icona: pallone disegnato come rete di nodi
│   └── web/  index.html  stile.css  app.js
└── build/                     scarti di PyInstaller, si può cancellare
```

---

## Stato per fasi

| # | Fase | Stato |
|---|---|---|
| 0 | Database (530 giocatori, 3 stagioni, xG) | ✅ |
| 1 | Motore: proiezioni, VOR, prezzo di mercato | ✅ 24 test |
| 2 | Ottimizzatore di rosa + `max_bid` + strategia | ✅ |
| 3 | Server locale e API | ✅ |
| 4 | Interfaccia grafica | ✅ |
| 5 | Avvio con doppio clic / eseguibile | ✅ |
| 6 | Collaudo end-to-end di un'asta completa | ✅ 33 test |
| 7 | Rifiniture d'uso in asta | ✅ |
| 8 | Caccia ai bug e irrobustimento | ✅ |
| 9 | Avvio e chiusura da vera applicazione | ✅ 12 test |
| 10 | Nome, icona, coerenza dei consigli, correzioni | ✅ |
| 11 | Gerarchia di reparto, equilibrio di rosa, tempo reale | ✅ |

---

## Le idee su cui poggia il calcolo

### Prezzo di mercato — quanto vale per la lega

```
valore  = presenze_attese × (fantamedia − fantamedia_rimpiazzo) + modificatore
prezzo  = 1 + VOR/ΣVOR × (crediti_residui_lega − slot_residui_lega)
```

Proprietà verificata dai test: **la somma dei prezzi consigliati è esattamente
uguale ai crediti ancora in mano alla lega**. Il mercato si chiude per
costruzione, non c'è nessuna costante da tarare.

### `max_bid` — quanto vale per la TUA rosa

```
max_bid(g) = il prezzo P più alto per cui
             OPT(rosa con g, budget − P)  ≥  OPT(rosa senza g, budget)
```

`OPT` è la migliore rosa completabile con gli slot e i crediti rimasti,
calcolata con uno zaino per ruolo e una convoluzione max-più fra i quattro
ruoli. Sopra quel prezzo, comprarlo **peggiora** la rosa finale.

Tre cose che il prezzo di mercato non può sapere e che qui entrano:

- **I crediti sono un vincolo.** 100 crediti su un attaccante sono 100 crediti
  che non hai più per gli altri 24 slot.
- **Non schieri 25 giocatori, ne schieri 11.** Il peso del k-esimo giocatore di
  un reparto è la probabilità che scenda in campo, calcolata con la binomiale
  cumulata sulla disponibilità misurata dal database. Viene: portieri
  `1.00 / 0.10 / 0.01`, difensori `1.00 ×4 poi 0.49 0.18 0.05 0.01`,
  attaccanti `1.00 1.00 0.28 0.06 0.01 0.00`.
  **È la ragione per cui il terzo portiere vale 1 credito** per quanto sia bravo.
- **Il modificatore di difesa non è additivo.** Il quarto difensore forte non
  alza la media di portiere + 3 migliori difensori. Il contributo è calcolato
  sulla *tua* rosa, non su una media di listone.

### Chiusura attesa — quanto costerà davvero

Metà modello, metà prezzo storicamente pagato in asta, riportato in scala sui
crediti ancora in circolo, e limitato dalla liquidità del secondo miglior
offerente. I due numeri sanno cose diverse: il modello conosce xG e minuti, il
prezzo storico conosce la titolarità e l'umore del mercato. Per stimare *quanto
costerà* il secondo conta almeno quanto il primo. Per stimare *quanto vale*, no.

Quando i due divergono di oltre il doppio, la scheda lo dice esplicitamente.

---

## Quello che si vede a schermo

**Barra in alto** — reparto in chiamata e quanti ne restano da assegnare in
lega; di chi è il turno; crediti ancora in circolo con l'indice di inflazione
(«prezzi in salita» se la stanza ha speso poco finora, «si compra a sconto» se
ha bruciato presto); i tuoi crediti e la tua offerta massima possibile.

**Colonna di sinistra** — le otto squadre. Crediti, barra di spesa, e un pallino
per ogni slot di ogni reparto. Chi ha il reparto in chiamata già pieno diventa
grigio: **non può più rilanciare**, ed è l'informazione più concreta che il
software ti dà. Un clic passa il turno a quella squadra; il pulsantino `rosa`
che compare passandoci sopra ne apre la rosa.

**Centro** — la ricerca (`/` in qualsiasi momento) e la scheda del giocatore
chiamato: il numero grande è **il tuo limite**, con sotto chiusura attesa,
prezzo di mercato, quanto si è pagato in asta negli anni scorsi, fantamedia
attesa e contributo al modificatore. Poi chi può ancora rilanciare e fino a
quanto, e tre alternative se lo perdi. In fondo si registra chi se l'è
aggiudicato: i tasti `1`–`8` scelgono la squadra, `Invio` conferma.

**Colonna di destra** — la tua rosa con il piano di spesa e **la squadra che
stai costruendo** (undici titolare, modulo, punti a giornata, caselle coperte da
un titolare sicuro, rigoristi); la scheda «Chi chiamare» (si apre da sola quando
il turno passa a te); e il listone completo.
La scheda dei consigli ha tre sezioni: **da prendere**, **da far pagare agli
altri**, e **se vanno via cari** — il piano B, cioe' chi puoi prendere *tutto*
con i crediti destinati a quel reparto, cosi' non ti ritrovi mai sul listone a
scegliere a caso. In cima compare un avviso quando i giocatori utili di quel
reparto stanno per finire.

I consigli sono in ordine di **utilità per la tua rosa**: il `+n` accanto al
nome sono i punti di stagione che guadagni prendendolo *al prezzo a cui andrà
via*, non quanto è forte in assoluto. Ordinare per convenienza metterebbe in
cima l'affare da tre crediti e in fondo il giocatore che cambia la squadra.

Tutto si ricalcola a **ogni** acquisto, anche degli avversari: liste, prezzi,
scheda aperta, undici titolare. Un acquisto sposta il livello di rimpiazzo e i
crediti di chi può rilanciare, quindi sposta ogni numero a schermo.

### Il listone ha tre colonne, e vogliono dire cose diverse

| colonna | significa |
|---|---|
| **pres** | presenze attese su 38 |
| **vale** | quanto varrebbe se in questa lega si pagasse a punti |
| **costa** | quanto ci vorrà **davvero** per portarlo via, viste le rose e i crediti di adesso |

La differenza fra «vale» e «costa» è l'affare. Erano lo stesso numero senza
etichetta, e si finiva per leggere il primo come se fosse il secondo. Il
pulsante **solo titolari** nasconde chi non gioca con ragionevole certezza.

Da qualunque rosa, la tua e quelle degli avversari, si puo' **togliere un
giocatore** con la crocetta: se sbagli a registrare un acquisto lo correggi
subito, altrimenti tutti i conti successivi sono falsi.

### I verdetti

| | |
|---|---|
| **OCCASIONE** | vale per te più di quanto costerà: chiamalo |
| **AL PREZZO GIUSTO** | prendilo entro il limite, sopra ci perdi |
| **PRENDILO** | nessun avversario può rilanciare |
| **DA UN CREDITO** | vale quanto tanti altri: riempi lo slot, non salire |
| **LASCIA** | ti dice anche **chi** preferirebbe al suo posto |
| **NON SERVE / NON PUOI** | reparto pieno, o crediti finiti |

## Difetti trovati e chiusi (quarto giro)

**Il listone mostrava un numero solo, e non era quello che sembrava.**
Accanto a Zappacosta compariva un valore senza etichetta, e si leggeva
naturalmente come «il prezzo». Era invece il *valore per la lega* — quanto
varrebbe se si pagasse a punti — che per i difensori sta sistematicamente
sopra il prezzo reale, e per gli attaccanti sotto. Adesso le colonne sono
tre, hanno un'intestazione, e la nota sotto spiega che la differenza fra le
due cifre **è** l'affare.

**Il filtro del listone non si accendeva mai.** Il CSS aspettava `attivo`,
l'interfaccia scriveva `attiva`: il ruolo selezionato restava identico agli
altri. Trovato leggendo, non da un test.

**Ottanta righe di listone facevano un migliaio di interrogazioni al
database.** `concorrenti()` dipende solo dal *ruolo*, non dal giocatore, ma
veniva ricalcolato per ogni riga. Messo in cache fino al prossimo acquisto:
l'asta completa di collaudo è passata da **809 ms a 70 ms** per chiamata.
È la differenza fra un'interfaccia che segue l'asta e una che la insegue.

**`.campo` era già preso.** La classe del campo da gioco aveva lo stesso nome
di quella dei campi del modulo iniziale: la seconda regola si mangiava la
prima e la schermata di avvio si sarebbe scomposta. Rinominata `formazione`.

**Una scheda dimenticata fa fallire il collaudo di spegnimento** — e non è un
difetto del programma. Il motore resta acceso finché *qualcuno sta usando
l'interfaccia*, ed è giusto così; ma una scheda lasciata su
`127.0.0.1:8730` in un browser qualunque si riaggancia da sola appena la porta
torna viva, e da quel momento tiene in piedi ogni prova di spegnimento. Costa
un'ora di caccia a un difetto che non c'è: adesso `test_chiusura.py`, quando
quella verifica fallisce, lo dice nel messaggio d'errore.

## Difetti trovati e chiusi (secondo giro)

Partiti da un «failed to fetch» premendo **Nuova asta**. La causa era che il
programma non era più in esecuzione e la pagina mostrava l'errore grezzo del
browser. Da lì sono usciti altri cinque difetti.

**1. Nessun avviso quando il programma muore.**
La pagina restava aperta a parlare con un processo morto. Ora c'è una spia
verde in alto, un pannello che spiega cos'è successo, e la pagina **si
ricollega da sola** appena il programma riparte. I nomi già scritti nella
schermata iniziale restano nel browser e non si ridigitano.

**2. Si potevano aprire due istanze sullo stesso database.** *(il più grave)*
Il controllo esisteva ma non era mai stato collegato: una modifica al codice
era andata a vuoto in silenzio. Due processi che scrivono lo stesso file SQLite
in asta significa crediti sbagliati e giocatori assegnati due volte. E il gesto
che lo provocava è naturale: il primo avvio impiega dieci secondi, sembra che
non succeda niente, si fa doppio clic un'altra volta.
Ora c'è un **lucchetto preso dal sistema operativo** prima ancora di aprire il
database. Verificato nei quattro casi: doppio clic ravvicinato, avvio a regime,
riavvio dopo chiusura pulita, riavvio dopo crash.

**3. Un nome di squadra lungo sfondava la barra in alto.**
Uscito da un collaudo a forza bruta con un nome da 500 caratteri. Ora il server
tronca a 24 caratteri e la barra tronca comunque il testo.

**4. Si potevano leggere file fuori dal programma.**
`http://127.0.0.1:8730/C:/Windows/win.ini` restituiva il file di sistema: su
Windows `os.path.join` scarta la cartella di partenza appena l'altro pezzo ha
una lettera di unità. Ora il percorso viene risolto e confrontato con la
cartella dell'interfaccia; tutto il resto è 403.

**5. Gli errori di input uscivano come guasti.**
Un parametro sbagliato dava 500 con dentro il messaggio di Python. Ora dà 400
con una frase in italiano. E un prezzo decimale veniva **troncato** (3,7 → 3)
invece che arrotondato: falsava la cassa in silenzio.

**6. I tasti 1-8 non funzionavano, e poi funzionavano male.**
Dopo aver aperto la scheda il fuoco restava nella ricerca, quindi le cifre ci
finivano dentro. Tolto il fuoco, la cifra sceglieva la squadra ma si scriveva
anche nel campo prezzo, cancellando il valore suggerito. Ora fa solo la prima
cosa.

Tutti e sei hanno una verifica automatica che li copre, così non tornano.

## Il mercato: valore contro prezzo

Questa e' la parte piu' delicata del software, e nasce da una domanda precisa:
*perche' il motore diceva che tutti gli attaccanti forti erano da lasciare?*

**Cosa dicono i dati.** Sui prezzi realmente pagati in asta, la ripartizione
del budget e' P 9% / D 16% / C 28% / **A 47%**, e in molte leghe sugli
attaccanti si arriva al 60%. Il motore, che distribuisce i crediti in
proporzione ai punti, ne metteva sugli attaccanti il 28%.

**Chi ha ragione?** Il controllo sui giocatori veri, stagione 2025-26:

| | proiezione del motore | realta' | pagato in asta |
|---|---|---|---|
| Martinez L. | fm 7,83 &middot; 31 pres | fm **8,25** &middot; 30 pres | **187** |
| Esposito Se. | fm 6,75 &middot; 34 pres | fm **6,88** &middot; 36 pres | **20** |
| Colombo | fm 6,59 &middot; 34 pres | fm **6,41** &middot; 37 pres | 30 |

Le proiezioni reggono (su Lautaro sono perfino conservative), e il mercato
paga davvero gli attaccanti molto piu' di quanto rendano. Il motore non
sbagliava i conti. Sbagliava un'altra cosa: **pianificava contro un mercato
immaginario**, usando i propri valori come se fossero prezzi. Cosi' vedeva i
difensori convenienti, ci caricava sopra il budget, e arrivava agli attaccanti
senza piu' crediti.

Da qui tre meccanismi distinti, tutti in `regole_lega.json` sotto `mercato`:

**1. `ripartizione_budget` &mdash; quanto costera'.** Il preventivo di come la
stanza spendera' i crediti, reparto per reparto. I prezzi si dividono prima
**fra i ruoli** secondo questo, e poi dentro ogni ruolo secondo il merito.
Con `impara_dall_asta` la previsione si corregge da sola: quello che e' gia'
stato speso e' un fatto, non una stima. E' impostato su A 60% come da tua
indicazione.

**2. `fiducia_nel_mercato` &mdash; quanto vale.** Da 0 a 1. Il modello conosce
xG, minuti e modificatore ma **non sa chi e' titolare** (quel campo del
database e' vuoto); il mercato la titolarita' la conosce ma paga male. A 0 il
software si fida solo dei propri numeri; a 1 si limita a seguire la stanza e
non ha piu' nessun vantaggio. Sta a **0,5**.

**3. `riserva_minima_per_ruolo` &mdash; quanto rischiare.** La quota del tuo
budget che va comunque a ogni reparto, qualunque cosa dicano i conti. Senza,
il motore compra sei attaccanti da un credito: e' difendibile in punti, ma ti
giochi tutto sul fatto che le proiezioni siano giuste su quattro giocatori
invece che su uno. E' una scelta di rischio, e spetta a chi fa l'asta.
Impostata a **P 4% / D 10% / C 15% / A 30%**.

> **Se vuoi due attaccanti veri invece di uno**, alza `attaccanti` nella
> riserva: a 30% il motore prende un attaccante da ~145 e riempie il resto a
> un credito; a 45% ne prende due. E' la manopola piu' importante che hai.

Effetto sulle cifre, prima e dopo:

| | prima | ora | pagato in asta |
|---|---|---|---|
| max_bid Martinez L. | 104 | **175** | 187 |
| max_bid Dimarco | 191 | 135 | 67 |
| piano per gli attaccanti | 7 crediti | **150 crediti** | &mdash; |

## Portieri a pacchetto

Regola di questa lega: chi prende il portiere titolare di una squadra di serie
A prende anche il secondo e il terzo a un credito. Non e' un dettaglio: cambia
la natura del reparto. Non sono ventiquattro scelte su settantacinque portieri,
sono **otto pacchetti su venti squadre**, e il rimpiazzo di un portiere non e'
il ventiquattresimo del listone ma il **nono titolare**.

Il software lo gestisce da solo: registra le riserve insieme al titolare, le
toglie insieme se annulli, e sa che quell'avversario esce dai concorrenti per
ogni altro portiere. Il titolare di ogni squadra e' dedotto dai minuti attesi,
non dalla media voto (un secondo portiere con tre partite buone ha spesso la
media migliore).

## Il verdetto si calcola una volta sola

C'era un difetto che rendeva il software inaffidabile proprio dove serviva:
un giocatore compariva nella lista **«da prendere»** e, aprendolo, la scheda
diceva **LASCIA**. I numeri erano gli stessi; era la lista a raggrupparli male,
mettendo sotto quel titolo anche chi aveva un margine negativo.

Adesso c'è una sola funzione, `decisione()`, e ci passa tutto: la scheda che si
apre quando un giocatore viene chiamato e le tre liste dei consigli. Le liste
non decidono più niente, si limitano a raggruppare per verdetto:

| lista | contiene |
|---|---|
| **Da prendere** | solo OCCASIONE, PRENDILO, AL PREZZO GIUSTO |
| **Da far pagare agli altri** | LASCIA e NON SERVE, se costano e c'è chi li vuole |
| **Se vanno via cari** | il piano B, alla portata del budget del reparto |

E il verdetto è scritto **su ogni riga**, con lo stesso colore che avrà nella
scheda: non c'è modo di leggere due cose diverse sullo stesso giocatore.
Una verifica automatica confronta lista e scheda su ogni voce e fallisce se
divergono anche di un credito.

Quando in un reparto non c'è niente che convenga, la lista lo dice invece di
riempirsi lo stesso: *«ai prezzi di adesso costano tutti più di quanto
renderebbero alla tua rosa»*.

## Correggere un acquisto sbagliato

In asta si sbaglia a registrare, ed è un guaio: da lì in poi crediti e slot di
tutti sono falsi. Si corregge da **tre posti**, tutti con la stessa crocetta:

- **«Ultimi assegnati»**, in fondo a *La mia rosa*: l'elenco degli ultimi
  acquisti di **chiunque**, con la crocetta accanto. È il posto più rapido.
- **La rosa di un avversario**: il pulsante `rosa` su ogni squadra nella
  colonna di sinistra, sempre visibile.
- **La tua rosa**, riga per riga.

Togliere un giocatore ricalcola tutto: crediti, slot, prezzi, consigli.

### I portieri di riserva si possono sostituire

Il secondo e il terzo portiere arrivano in dote col titolare a un credito, ma
non sono obbligatori: si tolgono con la crocetta e al loro posto si registra
un altro portiere **al prezzo che decidi tu**, cercandolo come una chiamata
normale. Il software non aggiunge riserve indesiderate quando lo fai, perché
lo slot che stai riempiendo è l'ultimo libero.

## Chi gioca davvero — `motore/titolarita.py`

Era il buco più grande. Le proiezioni sanno **quanto rende** un giocatore
quando gioca, non **quante volte scenderà in campo**: quella informazione sta
negli allenamenti, non nelle statistiche. Da lì l'errore più costoso che si
possa fare in asta, comprare una fantamedia alta prodotta da sette presenze.

La colonna `contesto.titolarita` è vuota e non esiste una fonte strutturata da
cui riempirla. L'informazione si ricava invece da quello che il database sa
davvero: **i minuti del reparto**, non quelli del singolo.

1. **Quanti minuti esistono.** La capienza di un reparto è la *mediana* di quel
   reparto sulle venti squadre. Nessun modulo assunto a priori: una squadra che
   gioca con una punta sola non viene forzata a due, una con tre centrali non
   viene gonfiata a quattro. È il campionato a dire quanto è grande un reparto.
2. **L'eccedenza si toglie dal fondo.** Se le proiezioni promettono ai dieci
   difensori della Roma il 49% di minuti in più di quanti ne esistano, qualcuno
   non li giocherà — e non sarà il primo della gerarchia. Il taglio parte
   dall'ultimo e risale. Toglierlo in proporzione punirebbe il titolare e
   salverebbe la riserva, cioè esattamente il contrario.
3. **Nessuno viene gonfiato.** Un reparto sotto la mediana non è un errore da
   correggere: è una squadra che in quel ruolo gioca con meno gente.

L'ordine gerarchico dentro il reparto non lo decidono i soli minuti: si mescola
col **prezzo pagato in asta** negli anni scorsi (35%). I minuti sanno com'è
andata, il mercato sa cosa ci si aspetta adesso, e sull'undici titolare la sala
di solito ci prende.

La quota si misura sulle **presenze**, non sui minuti: nel fantacalcio conta
prendere il voto, e chi entra al 60' il voto lo prende. Un attaccante che parte
trenta volte e viene sempre sostituito ha il 60% dei minuti e il 79% delle
presenze: è un titolare, e misurarlo sui minuti lo farebbe passare per un uomo
in ballottaggio.

| grado | presenze attese | in asta |
|---|---|---|
| **Titolare** | ≥ 27 su 38 | ci puoi contare |
| **Ballottaggio** | 19–27 | il posto non è suo |
| **Rotazione** | 11–19 | la fantamedia vale poco |
| **Riserva** | < 11 | qualunque media abbia, non lo vedi |

Accanto al grado c'è una **certezza** (0–1): quanto la quota è lontana dal
confine fra due gradi, quanto campione c'è dietro la proiezione, e se il
giocatore è arrivato quest'anno (lo storico dice meno). *Titolare* con certezza
≥ 0,55 è un **titolare sicuro**: è il filtro che regge il piano B, le
alternative nella scheda e il pulsante «solo titolari» del listone.

I minuti corretti tornano dentro le proiezioni: cambiano minuti, presenze e
punti di stagione, **non** media voto e fantamedia. Sono due cose diverse — un
tasso e un volume — e tenerle separate è quello che permette di dire «6,90 di
media, ma su otto partite».

## La squadra che stai costruendo — `motore/equilibrio.py`

Il resto del motore risponde su un giocatore alla volta. Questo modulo risponde
all'unica domanda che conta a fine asta: **che squadra ne esce?** Si ricalcola a
ogni acquisto, mio o altrui.

- **Undici titolare**: il miglior undici schierabile fra i moduli ammessi in
  Classic (343, 352, 442, 433, 451, 532, 541), con la somma delle fantamedie e
  il modificatore di difesa compreso. Le caselle non ancora comprate restano
  vuote invece di essere finte.
- **Caselle coperte**: per reparto, quante delle caselle dell'undici sono
  occupate da un **titolare sicuro** e quante da una scommessa.
- **Rigoristi** in rosa: cinque o sei gol garantiti valgono più di un decimo di
  fantamedia.
- **Concentrazione**: quanti giocatori della stessa squadra di serie A. È
  varianza, non valore.
- **Avvisi**, solo quando si può ancora rimediare *e* il tempo stringe: a
  inizio asta ogni casella è scoperta, dirlo sarebbe vero e inutile.

## Dati dal web: cinque guide incrociate, non una sola

Il database di partenza sapeva tutto del passato — tre stagioni di minuti, xG,
voti — e niente del presente: `contesto.titolarita` era vuota, i rigoristi
erano dedotti dai rigori calciati l'anno scorso (spesso in un'altra squadra),
gli infortuni non esistevano. Sono esattamente le cose che decidono un'asta, e
nessuna si ricava dalle statistiche.

**Il metodo, e perché cinque fonti e non una.** Le guide non sono d'accordo fra
loro: sull'attacco del Bologna una dice Piccoli e un'altra Dovbyk, sul Como una
dice Kean e un'altra Douvikas. Prendere la prima che capita vuol dire ereditare
i suoi errori senza saperlo. Sono state lette e trascritte verbatim cinque
guide indipendenti (`database/fonti/web/raccolta_2026_27.py`, con URL e data di
lettura in `fonti.csv`): le probabili formazioni di giornata (che contano il
doppio, sono la formazione di domani non un'ipotesi di agosto), quattro guide
alle formazioni tipo, due alle gerarchie di rigore, gli infortunati.

`database/pipeline/consenso.py` le mette insieme:

- **titolarità** = quota pesata di guide che schierano quel giocatore, con
  l'abbinamento al listone fatto per squadra + cognome + iniziale + parola
  (due `Martinez` nell'Inter si distinguono per ruolo: il portiere è sempre il
  primo nome di una formazione). **Un nome si accetta solo se esiste nel
  listone con quella squadra** — un abbinamento sbagliato è peggio di uno
  mancato, e infatti due errori delle fonti stesse (un "Dybala" finito nel
  Milan, un "Pinamonti" nel Sassuolo — entrambi giocano altrove) sono stati
  scartati invece di forzati.
- **rigoristi**: la gerarchia di *quest'anno* sostituisce quella dedotta dai
  rigori dell'anno scorso in `proiezioni.py` — differenza reale su 5-6 gol a
  stagione quando il rigorista ha cambiato squadra.
- **infortuni**: ogni indisponibile è convertito in **giornate che salta da
  oggi al rientro**, usando il calendario vero della sua squadra, e quelle
  presenze vengono tolte dalla proiezione (`applica_consenso()` in
  `proiezioni.py`). Yildiz (frattura, torna a fine novembre) passa da 34 a 21
  presenze attese; la fantamedia non si tocca, cambia solo quante volte gioca.
- **`motore/titolarita.py`** ora pesa il consenso web (60%) sopra minuti e
  mercato quando le guide hanno parlato, e ci ricade sotto quando tacciono:
  metà del listone le guide non lo nominano nemmeno, ed è lì che minuti e
  prezzo storico restano l'unica bussola.

Verificato: `python database/pipeline/consenso.py` stampa quante fonti
coprono ogni squadra, quanti giocatori sono unanimi (145 su 530), quante
coppie complementari ne escono, e la lista di ogni nome che non si è riuscito
ad abbinare (2 righe rimaste: un El Shaarawy e un Rodriguez che non sono nel
listone di quest'anno — non inventabili, non un errore).

## Giocatori complementari: il cuore della richiesta

La domanda che ha aperto questo lavoro: *quali coppie si dividono una maglia,
in modo da prenderle entrambe e pagare la seconda pochissimo?* Escono dallo
stesso consenso, in due forme:

- **ballottaggio** — se la giocano adesso, nessuno dei due è titolare sicuro.
  93 coppie.
- **vice** — un titolare e il suo cambio naturale nello stesso reparto. 50
  coppie.

Per ognuna, `copertura` dice quante giornate su 38 la maglia resta coperta da
**uno dei due**: 117 coppie coprono almeno il 90%. Tutto in
`database/accoppiate.csv` e nella tabella `accoppiate` del database.

**Nel motore** (`valutazione.Valutatore._carica_coppie`,
`ottimizzatore.Ottimizzatore._coppie_da_chiudere`): se possiedo già un
giocatore, il suo socio libero riceve un bonus di valore proporzionale alle
giornate che il titolare lascia scoperte, capato dalle presenze attese del
socio stesso — non gli si promette più partite di quante gliene diano le sue
proiezioni. Il `max_bid` sale di conseguenza. Verificato dal vivo: comprato
Kean, il `max_bid` di Douvikas passa da 73 a 106 crediti.

**Nell'interfaccia**: la scheda di ogni giocatore ha una sezione *"Chi copre la
maglia quando non gioca lui"* — le sue coppie, con prezzo se libero, nome
dell'avversario se già preso da qualcuno, "già tuo" se ce l'hai. Quando
comprarlo chiude una coppia che hai già, un avviso verde lo dice esplicitamente
con i punti extra inclusi nel limite.

## Un nome solo non è un consiglio — la classifica del reparto

Domanda che ha aperto il lavoro: *«Perché a volte quando apro il software mi
consiglia come occasione solo Vicario, altre volte lo chiudo, lo riavvio e
consiglia Svilar? Non capisco perché se un giocatore è una buona occasione
dovrebbe cambiare.»*

Non era un capriccio del programma, ed è la parte interessante. Il prezzo
massimo risponde a una domanda precisa: *comprare lui, adesso, è meglio del
piano che il motore farebbe altrimenti?* Con i portieri a pacchetto lo slot è
**uno solo**: il motore elegge il migliore e chiunque altro, occupando il posto
dell'eletto, risulta in perdita. A schermo restava un nome. E siccome i primi
cinque portieri distano fra loro **due o tre punti su duecento**, bastava un
acquisto altrui a far cambiare l'eletto. Era una volata decisa per un
centimetro, raccontata come se ci fosse un corridore solo.

La cosa che mancava non era un ordinamento diverso: era **un metro che non
dipendesse da chi altro c'è**. Ora ce ne sono due, e fanno due mestieri:

    resa(g)          punti di stagione che aggiunge nel primo slot libero
                     del suo reparto, pesati per la profondità di rosa e per
                     il modificatore di difesa
    tasso_ruolo(r)   punti per credito che si stanno pagando in quel reparto,
                     misurati su chi verrà davvero venduto
    convenienza(g)   resa(g) − prezzo × tasso_ruolo(r)

La convenienza non guarda i rivali, quindi si può mettere in fila. Il tasso è
**per reparto** e non generale, e il motivo si vede sul caso limite: in questa
lega gli attaccanti si portano via il 60% del budget, e col metro comune
risultavano **tutti** in perdita, dal primo all'ultimo. Vero, e inutile: sei
attaccanti vanno comprati lo stesso. La domanda giusta non è «conviene comprare
attaccanti» ma «di questi, quali rendono più di quanto costano *rispetto agli
altri attaccanti*».

**Tre fasce, come richiesto**, e ognuna con la sua domanda:

| sezione | chi ci finisce | ordine |
|---|---|---|
| **Top acquisti** | convenienza sopra soglia, oppure il prezzo massimo dice già di prenderlo | per **utilità**: quanto sposta la rosa |
| **Da evitare** | costa almeno 5 crediti e rende nettamente meno di quello che quei crediti comprano nel reparto | per pericolo: prima le trappole care |
| **Alternative** | in mezzo: né affare né errore, costa quello che vale | prima i titolari veri |
| Da far pagare agli altri | non è un obiettivo ma costa caro agli avversari | invariata |

L'ordine dentro «Top acquisti» è per **utilità**, non per convenienza, ed è una
scelta: se devo prendere un portiere solo voglio in cima quello che mi fa fare
più punti, non quello che costa meno. La convenienza decide *se* uno merita la
fascia; l'utilità decide *in che ordine*. Sono due numeri e si vedono
entrambi, perché servono a due cose diverse.

Dalla seconda riga in giù il verdetto è **RIPIEGO**, ed è nuovo. Prima si
leggeva LASCIA, che era falso: quello è il portiere che prendi se il primo vola
via. Dire «lascia» a Maignan perché esiste Vicario è vero solo finché Vicario
c'è. Ogni riga dice anche **di quanto** è distante dal primo: *«rende 4 punti
meno di Vicario, ma ne costa 5 in meno»*. Se la distanza è di due punti,
vuol dire che si equivalgono, e allora conta il prezzo.

Vengono valutati i 90 giocatori più utili del reparto (tutti, se sono meno):
sotto quella soglia ci sono solo riempitivi da un credito, che compaiono
comunque fra le alternative. Costa circa 200 ms per i portieri e 300 per i
difensori, una volta per acquisto.

---

## Il portiere gioca sempre — un numero sbagliato di sette partite

Domanda: *«Come fai a dire che un primo portiere ha l'80% di potenziale di
presenze? Giocano praticamente sempre.»*

Aveva ragione, ed era un errore di misura, non di modello. La costante era
`PRESENZE_TITOLARE['P'] = 28`, con scritto accanto che era *misurata* sul
campionato scorso. Lo era, ma male: la media era presa su **tutti** i reparti,
compresi quelli a cui manca mezza stagione. Il portiere che a gennaio va
all'estero esce dal listone, e con lui escono le sue venti partite; la squadra
però resta nel conto come se quelle partite non le avesse giocate nessuno. Sui
portieri il danno è massimo, perché la maglia è una sola e basta un buco per
dimezzare il reparto.

La misura ora la fa il codice (`consenso.misura_presenze()`) e **scarta i
reparti con i dati bucati**: entra solo chi ha totalizzato almeno l'85% delle
partite che quel numero di maglie avrebbe dovuto coprire. Sui venti reparti
completi:

| ruolo | titolari (misurato) | prima diceva | alternative |
|---|---|---|---|
| P | **35,1** presenze (mediana 37) | 28,0 | 2,0 |
| D | 30,1 | 29,0 | 13,7 |
| C | 30,2 | 29,0 | 14,5 |
| A | 30,1 | 27,0 | 14,7 |

Sui portieri erano **sette partite di sottostima a testa**, cioè un quinto della
stagione, su ogni primo portiere della lega.

### Il secondo errore, trovato tirando il filo

Sistemata la scala, Josep Martinez restava a 26 presenze pur essendo dato
titolare dell'Inter da **tutte e quattro** le guide. Lo storico dice cinque
partite in due stagioni, da secondo portiere, e il consenso pesava fisso 0,65:
usciva una media fra «gioca sempre» e «ha giocato cinque volte» che non descrive
nessuno dei due mondi possibili.

Lo storico non ha *nessuna* informazione da aggiungere sul fatto che oggi sia il
titolare: è esattamente la cosa che non può sapere. Perciò il peso delle guide
ora **cresce con quanto sono d'accordo fra loro** — da 0,65 quando si dividono a
metà fino a 0,90 quando sono unanimi. Non 1,00: un decimo resta allo storico,
perché anche le guide sbagliano e perché chi si è rotto tre volte in due anni ha
buone probabilità di rompersi ancora, e quello le guide di agosto non lo dicono.

Risultato: i diciannove portieri su cui le guide sono unanimi stanno fra 34 e 35
presenze; Mandas, su cui le fonti si dividono (tre su quattro), resta a 26. È
giusto così: la Lazio ha un ballottaggio vero, e dargli 35 presenze sarebbe
inventare una certezza che non esiste.

---

## Coppie da chiudere: un riquadro fisso, in cima

Richiesta: *«Se c'è un ballottaggio di due persone e io ho comprato uno dei due,
metti l'altro nei consigliati fisso e fammelo notare.»*

C'è un riquadro **Coppie da chiudere** sopra tutto il resto, non dentro le tre
fasce. Il motivo è preciso: il secondo di una coppia rende poco da solo — è il
secondo, appunto — e infilarlo in una classifica ordinata per resa sarebbe il
modo migliore di non vederlo mai. Resta lì finché non lo prendi tu o non lo
prende qualcun altro, e non compare due volte nello stesso pannello.

### Il numero che c'era prima era gonfiato

Il file diceva che Molina e Lulli coprono il **95%** della stagione. Lulli gioca
tre partite. Due errori sovrapposti:

1. **La copertura veniva letta dal file**, e il file la calcola quando le guide
   vengono lette — prima che le proiezioni taglino i minuti del reparto. Per un
   giocatore che nessuna guida nomina usa la media dei non titolari, quattordici
   partite; poi il taglio lo porta a tre, ma nel file resta scritto quattordici.
2. **Rispondeva alla domanda sbagliata.** Quante giornate coprono in due è un
   numero alto comunque, se il primo è titolare, e non distingue niente.

Adesso la copertura si **ricalcola sulle presenze proiettate**, quelle che il
motore usa davvero, e misura **quanti dei buchi del titolare il secondo riempie**:

    buchi      = 38 − presenze del titolare
    coperti    = min(presenze del secondo, buchi)
    copertura  = coperti / buchi

Molina salta 6 giornate, Lulli ne copre 3: **53%**. Onesto, e utile: è quello che
si compra quando si compra la seconda metà di una maglia.

---

## In positivo o in negativo: chi sta facendo affari e chi si sta rovinando

Richiesta: *«Se clicco la rosa di un giocatore mostrami se è in positivo con gli
acquisti fatti o in negativo.»*

Ogni rosa — la tua e quella degli avversari — porta il confronto fra **speso** e
**valore**. Il metro è il `prezzo_atteso`, quello calibrato sulla spesa reale per
reparto, non il valore a punti: è quanto quel giocatore sarebbe costato in una
stanza normale. Confondere i due numeri fa sembrare rubato ogni portiere, ed è
lo stesso errore che era già costato caro altrove in questo progetto.

Si vede in tre posti, dal più compatto al più dettagliato:

- **nella colonna delle squadre**, un `+50` rosso o un `−30` verde accanto ai
  crediti: due presidenti con gli stessi crediti residui non sono nella stessa
  posizione se uno ha in rosa 120 crediti di roba e l'altro 180;
- **in cima alla rosa**, il riquadro con speso, valore e la frase per esteso;
- **su ogni acquisto**, di quanto si è scostato dal prezzo atteso.

---

## I nomi delle squadre non si ridigitano

Richiesta: *«Ho inserito i nomi delle squadre, da ora in poi tienili sempre come
predefiniti.»*

Erano già ricordati, ma nel browser — e il browser lega quello che salva
all'**indirizzo**. Il programma cambia porta a ogni avvio se quella di prima è
occupata, e per il browser una porta diversa è un altro sito: i nomi sparivano
senza che si capisse perché.

Ora li tiene il programma, in `motore/preferenze.json`, e li rimanda indietro
con lo stato. Restano modificabili — sono un riempimento, non un vincolo — e la
memoria del browser resta come rete di sicurezza mentre si scrive. Il collaudo
scrive su un file suo (`FANTAHACKED_PREFERENZE`): apre e chiude decine di aste
con nomi finti, e senza quella separazione cancellerebbe proprio i nomi veri che
il file esiste per non far ridigitare.

---

## Il metro che si accorciava — `prezzo_base`

Sintomo: *«Quando acquisto il portiere, nella rosa viene scritto a tutti un
valore negativo, perché il valore atteso di tutti i portieri risulta 1.»*

Il bilancio confrontava quanto si era pagato con `prezzo_atteso`, che risponde
a **quanto costerà adesso**: divide i crediti che restano fra gli slot che
restano. Quando l'ultimo portiere della lega è assegnato non ne resta nessuno
da comprare, i crediti destinati al reparto sono finiti, e il prezzo atteso di
tutti i portieri collassa a un credito. Da quel momento chiunque avesse pagato
quaranta crediti il suo portiere — cioè tutti — risultava in perdita di
trentanove. Non era un giudizio sull'asta: era il metro che si accorciava.

C'è ora un terzo prezzo, `prezzo_base`, calcolato **una volta sola** in
`Valutatore._prezzi_base()`, sul listone intero e sul budget intero della lega,
come se l'asta dovesse ancora cominciare. Risponde alla sola domanda che ha
senso fare a un acquisto già fatto: *in una stanza normale, quanto sarebbe
costato?* Non si muove mai, e i tre numeri restano distinti:

| numero | domanda | si muove? |
|---|---|---|
| `prezzo_mercato` | quanto vale alla lega, se si pagasse a punti | sì |
| `prezzo_atteso` | quanto costerà adesso, viste rose e crediti | sì |
| `prezzo_base` | quanto sarebbe costato in una stanza normale | **no** |

Il calcolo è deliberatamente separato da quello vivo anche se gli somiglia:
metterli in comune vorrebbe dire che una modifica pensata per il prezzo del
momento — e ce ne saranno — si porterebbe dietro anche il metro, che invece
deve restare fermo. Verifica: la somma dei `prezzo_base` dei giocatori che
entreranno in rosa fa esattamente il budget di reparto (280 / 480 / 840 / 2400
su 4000).

---

## Il listone si ordina dalle intestazioni

Le colonne sono cliccabili: **giocatore**, **pres**, **vale**, **costa**.
Quella attiva è in ambra con la freccia, e si ordina sempre dal più alto.

Nel farlo è saltato fuori che l'ordinamento predefinito era per `prezzo_atteso`
mentre la colonna mostrata era la **chiusura attesa**: due numeri vicini ma non
uguali, e la lista non seguiva la colonna sotto gli occhi. Adesso il criterio
predefinito è `costa`, cioè esattamente quello che si legge.

---

## Una lista vuota non è una risposta

Sintomo: *«Non avevo ancora 8 difensori, ne avevo 5, e ha smesso di
consigliarmene, quindi non sapevo chi prendere.»*

Riprodotto simulando aste intere e registrando ogni stato in cui la fascia
**Top acquisti** restava vuota mentre gli slot no. Succede, ed è perfino
corretto nel merito: se il piano destina cinque crediti agli ultimi due
difensori perché il resto rende di più in attacco, nessun difensore supera la
soglia dell'occasione. Ma chi sta facendo l'asta quei due slot deve riempirli
lo stesso, e trovarsi la sezione vuota vuol dire non sapere chi chiamare —
che è esattamente il momento in cui si compra a caso.

Ora, quando la fascia alta resta vuota, i primi della fascia di mezzo vengono
promossi con l'etichetta giusta e la ragione scritta: *«Nessuno in questo
reparto è un affare ai prezzi di adesso, ma 3 slot vanno riempiti e il piano ci
destina 6 crediti: fra quelli alla portata, questo è il migliore che gioca.»*
E l'indicazione in cima dice dove sono finiti i crediti, invece di limitarsi a
dire che non conviene nessuno. Verificato: su 188 acquisti simulati, zero stati
con la sezione vuota.

---

## Riempitivi che almeno giocano

Sugli ultimi slot di un reparto il peso di profondità è quasi zero: l'ottavo
centrocampista entra così di rado che, per la funzione da massimizzare,
prenderne uno da centottanta punti o uno da due è **quasi** la stessa cosa.
Quasi: e la programmazione dinamica, davanti a un pareggio, sceglie il primo
che le capita.

Il piano proponeva così, a un credito, giocatori con zero presenze attese
mentre a un credito c'erano titolari veri. Nessun danno al calcolo — il valore
ottimo non cambia — ma un piano che consiglia chi non gioca, potendo
consigliare chi gioca allo stesso prezzo, non merita di essere creduto sul
resto.

`Ottimizzatore._migliora_riempitivi()` scambia i riempitivi (fino a 2 crediti,
meno di 5 punti sopra il rimpiazzo) col migliore **allo stesso costo**, quindi
il budget non si muove e l'ottimo non può peggiorare. Il criterio è solo
`presenze × fantamedia`: il valore sopra il rimpiazzo si ignora del tutto,
perché a quel livello vale zero virgola qualcosa per tutti e ordinare per quel
numero fa vincere lo scarto di un decimo a chi gioca sei partite contro chi ne
gioca trenta.

Effetto sul piano: gli otto slot da un credito passano da gente con 0–6
presenze a titolari con 30 (Idzes, Gallo, Coco, Coulibaly, Pierotti,
Piotrowski, Colombo). L'undici titolare atteso sale da 2179 a 2218 punti di
stagione, **a parità di spesa**.

---

## Cinque aste giocate dal posto di Davide

`scratchpad/cinque_aste.py` fa giocare al motore la propria squadra contro
sette avversari umani: pagano intorno al prezzo giusto ma sbagliano, quasi
sempre in eccesso, e ognuno ha il suo carattere sui reparti (Dirichlet attorno
alla ripartizione della lega). Vince chi offre di più e paga la seconda offerta
più un credito, che è come finisce davvero un rilancio. Il motore usa
`max_bid` vero, ricalcolato dopo ogni assegnazione.

| asta | P | D | C | A | totale | posizione |
|---|---|---|---|---|---|---|
| 1 | 20 | 122 | 170 | 185 | 497 | **1ª** con 2182 |
| 2 | 3 | 160 | 177 | 154 | 494 | **1ª** con 2236 |
| 3 | 13 | 105 | 212 | 168 | 498 | **1ª** con 2174 |
| 4 | 24 | 100 | 195 | 176 | 495 | **1ª** con 2234 |
| 5 | 16 | 142 | 179 | 154 | 491 | 2ª con 2178 |

Quattro vittorie su cinque, un secondo posto. Il margine è dell'1–4%: un
vantaggio vero e non una goleada, che è quello che ci si deve aspettare da un
vantaggio informativo in un gioco dove gli altri non giocano a caso.

Il tratto ricorrente è **quanto poco spende in porta** (3–24 crediti contro i
47 del piano teorico): appena la stanza porta i portieri sopra il suo limite,
il motore lascia perdere, ne prende uno da pochi crediti e sposta quei
quaranta crediti a centrocampo, dove il reparto è più profondo e le occasioni
non finiscono mai.

---

## Il rischio di restare in dieci — `Equilibrio.rischio_undici()`

Domanda: *«Se ho i principali forti ma le riserve non giocano, rischio di
rimanere in dieci. Il software lo considera?»*

**No, non lo considerava.** L'ottimizzatore massimizza i punti dell'undici e
pesa ogni giocatore per le giornate in cui scende davvero in campo: chi non
gioca mai vale **zero** in quella funzione. Ma una casella vuota in formazione
non è un giocatore che fa zero punti, è una giornata giocata in dieci — e la
funzione da massimizzare non lo sa.

Adesso il numero c'è, e si vede mentre si compra invece che a dicembre. Il
conto è **esatto, non simulato**: con al massimo otto giocatori per reparto la
distribuzione di quanti saranno disponibili si calcola per intero
(Poisson-binomiale, sessanta moltiplicazioni), e si somma su tutte le
combinazioni che un modulo ammesso riesce a coprire. Un numero che compare a
schermo a ogni acquisto non deve tremare per via del seme del generatore.

Due scelte di modello, e vanno dette perché tirano in direzioni opposte:

- le assenze si estraggono **indipendenti**, mentre nella realtà sono correlate
  (turni infrasettimanali, soste): il rischio vero è un po' più alto;
- i **portieri della stessa squadra no**: si dividono una maglia sola, e in
  porta ci va sempre qualcuno. Trattarli come due monete separate diceva che il
  7% delle giornate si resta senza portiere, il che è assurdo per chi possiede
  un pacchetto intero — la seconda moneta esce testa *proprio* quando la prima
  esce croce. Con la correzione, quel 7% diventa 0,4%.

Gli slot ancora da comprare contano come un giocatore normale del reparto:
altrimenti a inizio asta il rischio sarebbe del 100%, vero e inutile. La
domanda a cui risponde è **se completi la rosa così come stai andando**.

### Cosa dicono i numeri

| rosa | giornate a rischio | caselle vuote a giornata |
|---|---|---|
| piano del motore | **0,6 su 38** (1,6%) | 0,02 |
| le cinque aste simulate | 0,7 – 1,5 | 0,02 – 0,04 |
| rosa "a punte" (metà forti, metà panchina che non gioca) | **22,8 su 38** (60%) | 1,17 |

Quindi: il motore **rispettava già** la copertura, ma per effetto collaterale
(il peso di profondità più i riempitivi che ora giocano), non perché la
misurasse. Il pericolo che temevi è reale — 60% delle giornate su una rosa
sbilanciata — e ora è sotto gli occhi mentre si compra, con l'avviso che dice
anche **quale reparto ti tiene fermo**, ricalcolato aggiungendo un giocatore
per volta e guardando dove il rischio scende di più.

---

## Il motore impara quanto paga la stanza — `Valutatore._aggressivita()`

Era il buco più grosso rimasto, ed era scritto in "Cosa manca" da tre giri: il
prezzo di chiusura si stimava assumendo che **tutti** valutassero al consenso
di mercato. A un tavolo vero non è così, e la differenza si vede dopo tre
chiamate: c'è chi paga il 30% sopra qualunque cosa gli piaccia e chi aspetta
gli avanzi. Stimare la chiusura con lo stesso numero per entrambi vuol dire
sbagliare in due direzioni opposte — si perde l'obiettivo contro il primo e si
paga troppo contro il secondo.

La misura c'era già: è la stessa che compare accanto a ogni squadra nella
colonna di sinistra, quanto ha speso diviso quanto quella roba sarebbe costata
in una stanza normale (`prezzo_base`). Adesso diventa un moltiplicatore per
presidente:

    aggressivita = (speso + 80) / (atteso + 80)      limitata a [0,65 – 1,75]

Gli 80 crediti di prudenza sono il modo di dire *«un acquisto non fa una
tendenza»* senza dover contare gli acquisti: contano i **crediti**, che è la
misura giusta di quanto quell'avversario ha scoperto le carte. Chi ha comprato
per 30 crediti roba che ne valeva 20 risulta appena sopra la media; chi lo fa
per 300 risulta un compratore caro sul serio.

Effetto misurato: in una stanza che ha appena pagato il triplo nove difensori,
la chiusura attesa del decimo passa da 12,7 a 20,5 crediti — **+61%**. Prima il
motore ci mandava a rilanciare fino a 13 e li perdeva tutti.

### Il risultato al tavolo

Le stesse cinque aste, stesso seme, prima e dopo le migliorie di questo giro
(portiere dell'Atalanta, riempitivi che giocano, aggressività appresa):

| asta | prima | dopo |
|---|---|---|
| 1 | 1ª — 2182 | **1ª — 2209** |
| 2 | 1ª — 2236 | 1ª — 2214 |
| 3 | 1ª — 2174 | 1ª — 2174 |
| 4 | 1ª — 2234 | **1ª — 2247** |
| 5 | **2ª** — 2178 | **1ª — 2203** |

Da quattro vittorie su cinque a **cinque su cinque**, e il rischio di restare in
dieci sceso da 3,2–6,6% a 1,8–3,9%.

---

## Dati: il terzo portiere dell'Atalanta

Segnalazione: *«Alcuni portieri, se li prendi, ti assegnano solo 1 altro
portiere e il terzo resta scoperto.»*

Vera, e per una sola squadra: **l'Atalanta aveva due portieri a listone invece
di tre**. Chi si aggiudicava il pacchetto Carnesecchi si ritrovava con due slot
su tre riempiti, e lo scopriva dopo aver pagato.

Verificato incrociando tre guide. Due (Goal.com e SosFanta) indicano **Pompei**
come terzo; calciodangolo indica un altro nome ed è rimasta in minoranza,
quindi non fa testo da sola — è la stessa regola con cui si scartano i nomi
dubbi in `consenso.py`. Lo stesso incrocio ha **confermato** i terzi portieri
di Roma (De Marzi), Lazio (Renzetti) e Sassuolo (Satalino), su cui
calciodangolo dissentiva: lì il database aveva già ragione.

Aggiunto al seed e al listone, rifatta la pipeline: adesso tutte e venti le
squadre chiudono il reparto con un pacchetto solo.

Perché non succeda più, due presidi:

- **nella pipeline** (`build.py`): una squadra con meno di tre portieri è ora un
  **errore** di validazione, non un silenzio;
- **nella scheda**: il messaggio non promette più «chiude tutto il reparto
  portieri» a scatola chiusa. Conta gli slot che chiude davvero e, se sono
  meno di tre, lo dice in ambra prima che si paghi.

### Il resto del database

Controllato l'organico di tutte le venti squadre per ruolo. Nessun altro
reparto sotto la soglia: i portieri sono 3–4 ovunque, e i pochi attacchi da due
nomi (Milan, Bologna, Lazio) sono corretti — in Classic gli esterni offensivi
come Pulisic, Orsolini e Zaccagni sono centrocampisti, non attaccanti.

---

## Due numeri veri che sembravano contraddirsi — `acquisti.limite`

Domanda: *«Dimarco: "occasione, non oltre 144", chiusura attesa 63. Se lo pago
100 dovrei avere un vantaggio. Perché allora nella rosa mi dice +37 in rosso?»*

Erano **entrambi giusti e misuravano cose diverse**, ma uno dei due era scritto
come un'accusa. Verificato rigiocando lo stato di quel momento:

| domanda | numero | risposta |
|---|---|---|
| quanto vale **per la mia rosa** | `max_bid` 144 | oltre 144 la rosa che riesco a completare peggiora |
| quanto costerà **in questa stanza** | `chiusura` 63 | quello che pagheranno gli altri |
| quanto costerebbe **in una stanza normale** | `prezzo_base` 63 | il metro con cui si giudicano gli avversari |

Pagandolo 100, la rosa finale vale **+23,8 punti di stagione** rispetto a non
prenderlo. Il vantaggio c'era davvero. Ma il bilancio della rosa confrontava il
pagato col prezzo di mercato e ne concludeva *«34 crediti buttati»*, che su un
giocatore fuori scala è semplicemente **falso**: quei 37 crediti sopra il
mercato hanno comprato 23,8 punti.

La radice: per un giocatore molto sopra la media del suo ruolo, il prezzo di
mercato (la sua fetta del budget difensori) e il valore per una rosa che se lo
può permettere non coincidono — ed è esattamente l'arbitraggio per cui il
motore esiste. Giudicare quell'acquisto col metro del mercato vuol dire dare
dell'errore alla cosa giusta.

**Soluzione: si salva il limite.** La tabella `acquisti` ha una colonna nuova,
`limite`: il prezzo massimo che il motore dava a quel giocatore **nell'istante
della chiamata**. Si legge un attimo prima di registrare, perché subito dopo lo
slot è occupato e quel numero non esiste più. Da lì:

- **la mia rosa** si giudica sui limiti — *«tutti dentro il limite, 48 crediti
  di margine»* — e ogni riga mostra quanto si è stati sotto o sopra il proprio
  tetto, non sopra il mercato;
- **gli avversari** restano sul metro di mercato, che è l'unico disponibile: di
  quanto vale un giocatore per la rosa di un altro non so niente, e inventarlo
  sarebbe peggio che non dirlo.

Per le aste già aperte prima della colonna c'è `motore/recupera_limiti.py`, che
rigioca l'asta su una copia e ricostruisce i limiti mancanti chiedendoli al
motore stato per stato.

---

## Il collaudo non deve toccare l'asta vera

**Questo l'ho imparato rompendo qualcosa.** `app/test_app.py` girava sul
database vero, e ogni verifica comincia con una "nuova asta" — che cancella
quella precedente. Lanciato mentre c'era un'asta in corso, il collaudo l'ha
distrutta: venticinque acquisti persi senza una domanda e senza un backup.

Adesso `percorsi.DB_FILE` legge `FANTAHACKED_DB` dall'ambiente, e le prove si
copiano il database in una cartella temporanea che cancellano alla fine. Il
file vero non lo apre nessuno. È lo stesso presidio già in piedi per i nomi
delle squadre (`FANTAHACKED_PREFERENZE`), esteso alla cosa che valeva di più.

Nota per chi riprende in mano il progetto: **prima di lanciare i collaudi non
serve più chiudere l'asta**, ma se si scrivono prove nuove che parlano col
motore direttamente (non via HTTP) vanno fatte lavorare su una copia, come fa
`recupera_limiti.py`.

---

## Perché a volte si apriva nel browser invece che in finestra

`main()` ha due strade. Quella normale lancia Edge in modalità `--app` con un
profilo dedicato: finestra sua, niente barra degli indirizzi, niente schede.
L'altra è quella che si prende quando **il lucchetto è già occupato**, cioè
quando un FantaHacked è già acceso: lì il programma si limitava a fare
`webbrowser.open`, che apre una scheda normale.

Bastava quindi un doppio clic mentre il programma era già in esecuzione — anche
solo perché la finestra era finita dietro le altre — per vederselo comparire
dentro il browser. Sembrava che cambiasse forma a caso.

Adesso anche la seconda apertura passa da `apri_finestra()`, e `webbrowser.open`
resta solo per il caso in cui sul computer non ci sia nessun browser adatto.

---

## Far pagare gli altri senza rimetterci — un tetto, non una chiusura

Idea presa da `fantabot` (`domain/asta/drain.py`), che su questo punto era più
prudente di FantaHacked.

La sezione «da far pagare agli altri» mostrava la **chiusura attesa** — 46
crediti, poniamo — e si poteva leggere come *spingi fino a 46*. Ma se in quel
momento gli altri si fermano, quei 46 li paghi tu, per un giocatore che non
volevi. Il rischio c'era e non era coperto da niente.

Ora la cifra è un **tetto di sicurezza**, non una previsione, e vale la stessa
doppia garanzia che usa fantabot:

1. **Il tetto sta sotto quanto quel giocatore vale sul mercato** (`prezzo_base`
   meno uno). Se nessuno rilancia e te lo aggiudichi, ti resta in rosa uno
   pagato meno di quanto valga: non è il piano, ma non è una perdita.
2. **Servono almeno due avversari che possano superare quel tetto.** Con uno
   solo, se passa la mano il giocatore è tuo — e uno che passa la mano capita
   tutte le sere. Con nessuno, stai solo comprando a caso.

Chi non soddisfa entrambe non compare più nella lista.

---

## Il collaudo poteva ancora distruggere l'asta, e l'ha fatto

Il presidio del giro precedente — le prove su una copia usa e getta del
database — **non bastava**, e me ne sono accorto rompendo la stessa cosa una
seconda volta.

`test_app.py` avvia il suo server e poi parla con la porta 8730. Se su quella
porta risponde già un FantaHacked (l'utente ce l'ha aperto, o l'istanza
precedente non ha ancora finito di spegnersi), il server delle prove esce per
via del lucchetto e **le prove parlano con l'istanza vera**: la copia usa e
getta resta lì intatta mentre la prima "nuova asta" cancella l'asta in corso.

Adesso `/api/ping` dichiara su che database sta lavorando, e le prove si
fermano prima di toccare qualsiasi cosa se quel percorso non è la loro copia:

```
ATTENZIONE: risponde un FantaHacked gia' avviato, che lavora su
  C:\Users\Davide\Desktop\Software fantacalcio\motore\fanta.db
Chiudilo e rilancia le prove: cosi' cancellerebbero l'asta vera.
```

Verificato in tutti e due i versi: con un server acceso sul database vero le
prove si rifiutano di partire; chiuso quello, girano e l'asta resta dov'è.

---

---

# Sesto giro — la curva dei prezzi, e cosa si è preso da `fantabot`

## Il prezzo non è il valore — `Valutatore._curva_prezzi()`

Fino a questo giro i crediti di un reparto si spartivano **in proporzione al
merito**: `prezzo_atteso ∝ VOR`. Quanto vale, tanto costa. È elegante ed è
sbagliato, e ora si sa di quanto.

Il conto è fatto contro i prezzi realmente pagati (`prezzi_asta`, 225 giocatori
con uno storico d'asta), fuori campione, su duecento divisioni casuali a metà
del campione:

| previsione del prezzo | errore tipico |
|---|---|
| solo il nostro modello di punti | **48 %** |
| solo la quotazione ufficiale | 40 % |
| i due insieme, coi pesi stimati | **34 %** |

Il nostro modello, da solo, era il peggiore dei tre. Non perché sbagliasse i
giocatori — l'ordine dentro il reparto lo azzecca, correlazione di rango
0,86-0,89 — ma perché **la stanza non paga in proporzione al merito**. Paga in
proporzione alla quotazione, e la paga più che proporzionalmente:

```
log(prezzo) = a + b·log(quotazione) + c·log(punti attesi)

  D   -3,66   +1,47   +0,54
  C   -2,55   +1,67   +0,25
  A   -2,60   +2,07   +0,10
```

L'esponente 2,07 sugli attaccanti dice una cosa precisa: **un attaccante
quotato il doppio non costa il doppio, costa quattro volte tanto.** Nessuna
spartizione lineare può produrre quella curva, per quanto buoni siano i punti.

E il modello serve lo stesso. Al netto della quotazione, il suo scarto è
correlato **+0,41** con lo scarto del mercato: sa qualcosa che il listone non
scrive — i minuti, i ballottaggi, il modificatore. Solo che ne sa molto meno di
quanto pesasse.

### Il peso non si sceglie, si misura

`PESO_CURVA` sta a 0,6, in media geometrica col vecchio criterio. Non è una
preferenza: è il valore che sbaglia meno.

| PESO_CURVA | errore tipico | pesato per i crediti in gioco |
|---|---|---|
| 0,0 (com'era) | 34 % | 39 % |
| **0,6** | **29 %** | **29 %** |
| 1,0 (solo curva) | 40 % | 30 % |

Oltre 0,6 l'errore tipico riprende a salire, perché la curva estrapola sui
giocatori da pochi crediti, che sono tanti. Per reparto: **attacco da 69 % a
26 %** — ed è dove vanno il 60 % dei crediti; difesa da 33 % a 23 %;
centrocampo da 28 % a 33 %, che è il prezzo del compromesso, pagato dove le
cifre in gioco sono la metà.

**I portieri restano fuori.** Con `portieri_a_pacchetto` le riserve arrivano a
un credito col titolare, e lo storico d'asta descrive leghe dove venivano
comprate: sarebbero venti osservazioni di un'altra lega. Il reparto torna alla
spartizione a merito, e una verifica lo impone (`v.curva` non deve contenere
`'P'`).

### Effetto collaterale: le coppie funzionano meglio

Su venticinque coppie complementari, comprando il titolare al prezzo di
chiusura:

| | il socio sale | scende | resta uguale |
|---|---|---|---|
| a merito | 3 | **5** | 17 |
| con la curva | **9** | **0** | 16 |

Era esattamente la proprietà che una prova diceva di controllare, e la
controllava su una coppia sola comprata a **quaranta crediti fissi** — che per
metà listone vuol dire pagarne otto volte il valore. Adesso ne guarda sei,
ognuna pagata quello che costa.

### Quello che la simulazione non può dire

Dieci aste simulate: 9 vittorie su 10 prima, **10 su 10** dopo, con punti medi
praticamente identici (2226 contro 2214). Il risultato è onesto ma **non è una
prova**: nella simulazione gli avversari offrono partendo dalla chiusura attesa
del motore stesso, quindi rendere più accurato il prezzo non può aiutare contro
avversari i cui prezzi sono definiti da quello stesso numero. La prova vera è
la misura fuori campione contro i prezzi pagati; la simulazione dice solo che
non si è rotto niente.

---

## Cosa si è verificato del `fantabot` di Baratto, e cosa non ha retto

Il repository non spedisce prezzi: li raccoglie. Quindi il confronto è fra
**metodi**, misurati sui nostri dati.

### Presa: la curva prezzo/quotazione

Il loro `target_price` è `QI × fattore`, dove il fattore viene da una
regressione su `log(qa/qi)` — e la scelta del logaritmo è motivata proprio come
serviva a noi: `(qa−qi)/qi` è asimmetrico, un giocatore che raddoppia legge
+100 % e uno che dimezza solo −50 %, così quattro sorprese da tre crediti si
mangiano la retta. È la ragione per cui anche la nostra curva è stimata in
scala logaritmica.

### Non ha retto: lo sconto per squadra

Loro applicano uno sconto a Napoli e Milan e **rifiutano di generalizzarlo**
alle altre squadre, perché su una o due stagioni il segnale è rumore. Sui
nostri dati l'effetto squadra esiste ed è grosso — misurato in due modi
indipendenti, che concordano a 0,95:

| | contro le nostre proiezioni | contro la quotazione ufficiale |
|---|---|---|
| Inter | +47 % | +26 % |
| Roma | +39 % | +6 % |
| Milan | +30 % | −1 % |
| Napoli | **−13 %** | +2 % |
| Bologna | −52 % | −41 % |
| Sassuolo | −71 % | −59 % |

Napoli, da noi, va a **sconto**: il contrario di quello che dice il loro
studio. E soprattutto **non serve implementarlo**: il nostro
`prezzo_riferimento` è già per giocatore, quindi l'effetto squadra è dentro il
dato, non da aggiungere sopra. Un fattore per squadra lo conterebbe due volte.

### Non ha retto: lo scarto del campione sottile

La loro regola più citata: fidarsi del rendimento precedente **solo** fra 25 e
38 presenze, perché sotto la correlazione crolla da −0,19 a −0,01. Il caso che
gliel'ha fatta scrivere è Malen — 18 presenze, fantamedia 9,0 da una striscia
di quattordici gol.

È lo stesso Malen che il nostro motore prezza a **294 crediti su 500**, contro
i 218 del mercato: il singolo errore più grosso del listone, il 9 % di tutto lo
scarto residuo. Quindi il caso è reale anche da noi. **La regola, no.**
Dividendo il listone per affidabilità del campione:

| | sovrastima mediana del prezzo |
|---|---|
| poca storia (affidabilità < 0,70, n=57) | −33 % |
| storia piena (≥ 0,70, n=113) | −32 % |

Identiche. La correlazione fra affidabilità e sovrastima è −0,10: niente.
Malen è un caso singolo, non una classe — e il suo npxG dice 0,73 ogni 90
minuti, il più alto del campionato, quindi non è nemmeno solo fortuna sotto
porta. Applicare la loro regola qui avrebbe spostato crediti su un segnale che
nei nostri dati non esiste.

### Verificato e innocuo: la scala del listino prezzi

I 200 giocatori che verrebbero davvero venduti sommano al **119 %** del monte
crediti della lega. Il listino è quindi gonfio di circa un quinto — sono medie
di prezzi condizionate all'essere stati venduti, non una ripartizione. Non
propaga: il motore normalizza dentro il reparto sul budget del reparto, quindi
la scala si riassorbe e resta solo la forma, che è quello che serve.

---

## Correggere i nomi senza perdere l'asta — `/api/rinomina`

L'asta era già cominciata con otto nomi sbagliati, e l'unico modo di
correggerli era «nuova asta», che cancella tutti gli acquisti registrati. Un
errore di battitura costava la serata.

Adesso c'è **rinomina** accanto a «Le squadre»: cambia le etichette e basta —
identificativi, crediti e acquisti restano dove sono — e i nuovi nomi
diventano anche i predefiniti della prossima asta. Rifiuta i doppioni e gli
elenchi incompleti.

---

## Il collaudo e l'asta vera, terza e ultima volta

Le due protezioni precedenti non bastavano, e i nomi delle squadre lo hanno
dimostrato: il database era salvo, `preferenze.json` no. Le prove ci avevano
scritto dentro `Bea, Chiara, Dario…`, e l'asta successiva è partita con quelli.

Due cambiamenti, e questa volta il problema è tolto invece che presidiato:

1. **Il lucchetto sta accanto al database che protegge**, non in una cartella
   fissa. Il collaudo gira su una copia usa e getta, quindi si prende un
   lucchetto suo, una porta sua — che scrive nel proprio `fanta.porta`, dove le
   prove la vanno a leggere — e **non incontra mai l'istanza dell'utente**.
   Prima bussava alla 8730 o niente, e con il programma aperto quella porta è
   sua.
2. `/api/ping` dichiara **tutti e due** i file, database e preferenze, e le
   prove si fermano se uno dei due non è il proprio.

Verificato: col programma dell'utente acceso, le prove girano fino in fondo
(40 + 104 verifiche) e l'asta in corso resta con i suoi 25 acquisti.

---

---

# Settimo giro — cento aste, e tre cose che non andavano

## Il banco di prova: `simulazioni/cento_aste.py`

`cinque_aste.py` faceva offrire gli avversari partendo da `prezzo_base`, cioè
da un numero che calcola il nostro motore. Va bene per vedere se il programma
sta in piedi; come misura del suo vantaggio non vale niente, perché sono
avversari i cui prezzi sono definiti dal modello che si vuole giudicare.
Migliorare il modello sposta anche loro, e la partita finisce sempre uguale.

Qui l'ancora sono i **prezzi realmente pagati** (`prezzi_asta`), riscalati sul
monte crediti della lega — con le proporzioni del listino, non con quelle di
`regole_lega.json`, perché si vuole apposta una stanza che spende come la media
di tutte le altre.

### E il punteggio contava la cosa sbagliata

`undici_atteso` sommava `presenze × fantamedia` dell'undici titolare. In questa
lega il **modificatore di difesa** vale fino a sei punti a giornata — oltre
duecento in stagione, dieci volte gli scarti che si stavano misurando — e
premia esattamente il reparto su cui le varianti a confronto la pensavano
diversamente. Col metro corto, spostare crediti in difesa risultava sempre uno
spreco: si contava quello che i difensori costano e non tutto quello che
rendono. Adesso `punteggio()` lo include, e ogni numero qui sotto è misurato
col metro giusto.

---

## 1. Il guasto: quattro slot vuoti e nessuno da chiamare

**Tre aste su cento** finivano con la rosa incompleta. La peggiore: due
attaccanti su sei, cinque crediti in mano, e il motore che aveva risposto
«lascialo» a **ventinove attaccanti di fila**, uno dopo l'altro, fino
all'ultimo del listone.

Non era prudenza. Coi riempitivi preventivati a due crediti e uno solo in cassa
per slot, il piano di spesa diventava impossibile: `opt` non trovava più
nessuna rosa completa e restituiva NEG per chiunque. Il messaggio a schermo
diceva *«quello slot rende di più su un altro giocatore»*, e non c'era nessun
altro giocatore.

È il punto cieco di fondo dell'ottimizzatore, in versione acuta: la funzione da
massimizzare vede i punti dell'undici, e in quella funzione **un giocatore che
non gioca mai vale zero, non meno di zero**. Una casella vuota in formazione
non vale zero: vale una giornata in dieci.

Rimedio, `Ottimizzatore.ultimi_posti()`: quando i crediti non bastano più
nemmeno per i riempitivi preventivati, oppure il listone del ruolo si sta
svuotando, il limite non può essere zero. A un credito, chiunque scenda in
campo vale più di una casella vuota.

| | prima | dopo |
|---|---|---|
| rose incomplete | 3 su 100 | **0 su 100** |
| rischio peggiore | 6,8 giornate su 38 | **2,8** |
| aste sopra 3 giornate di rischio | 3 | **0** |

Sui tre semi che fallivano: 2181 → 2224, 2235 → 2269, 2179 → 2207 punti.

---

## 2. Il numero da mostrare non è il numero con cui pianificare

Questo è il risultato che non mi aspettavo, e che ha resistito a tre tentativi
di smontarlo.

La curva dei prezzi del giro scorso è **più precisa** — 29 % di errore contro
39 % sui prezzi realmente pagati. Eppure, usata dentro il piano di spesa, fa
giocare **peggio**: su centocinquanta aste appaiate, −17 punti di stagione, 2,9
errori standard, e tre crediti e mezzo in meno avanzati. Lo scarto non cambia
con avversari non distorti, quindi non è una proprietà della stanza finta.

La ragione, una volta vista, è ovvia: **`max_bid` non è una previsione, è un
punto di indifferenza calcolato contro il piano.** Se il piano crede che i
sostituti costino poco, il limite su ogni singolo giocatore scende e il motore
lascia perdere più spesso — e lasciar perdere è il modo in cui si vince
un'asta. Un piano che prezza tutto al valore giusto è un piano modesto: alza i
limiti, e fa pagare di più per gli stessi punti.

Scomposto per reparto, si vede dove andavano:

| reparto | crediti (piano a merito) | crediti (piano con la curva) | crediti per punto |
|---|---|---|---|
| D | 100 | **138** | 0,071 → **0,093** |
| C | 187 | 176 | 0,125 → 0,124 |
| A | 174 | 157 | 0,178 → 0,163 |

Trentotto crediti in più in difesa per settantanove punti — quasi mezzo credito
a punto — tolti a centrocampo e attacco.

Quindi adesso ci sono due prezzi, e ognuno fa il suo mestiere:

- **`prezzo_atteso`**, con la curva: è quello che si legge a schermo, la
  chiusura attesa, la convenienza, l'occasione e la trappola. Deve essere
  preciso perché ci si decide sopra.
- **`prezzo_piano`**, a merito: è quello con cui l'ottimizzatore costruisce il
  piano e da cui esce il limite. Deve essere ottimista sui sostituti perché è
  l'ottimismo a rendere disciplinati.

L'ottimismo aveva un prezzo, ed era chiudere l'asta con quattro slot vuoti.
Adesso lo copre `ultimi_posti`, ed è diventato gratis.

---

## 3. Il bonus di chi chiude la coppia era sottopesato

Separando i due prezzi si perdeva una proprietà che serve: comprato il
titolare, il limite sul socio non saliva più. Il posto giusto dove rimetterla
non è il prezzo, è il bonus.

La formula contava solo i punti che il socio mette sulle giornate scoperte dal
titolare, sopra il livello di rimpiazzo. Non contava **la ragione per cui si
vogliono entrambi**: quelle giornate, senza di lui, non le copre un giocatore
medio del ruolo — le copre chi capita, o nessuno. Stesso punto cieco di
`ultimi_posti`.

`PESO_COPPIA = 2.0` è un tappabuchi, non una derivazione, ed è misurato:

| peso | il socio sale (su 25 coppie) | punti | giornate in dieci |
|---|---|---|---|
| 1,0 | 3 | 2295 | 1,1 |
| **2,0** | **8** | **2307** | 1,1 |
| 3,0 | 8 | 2295 | 1,1 |

A tre non migliora più niente, quindi due.

---

## Come gioca il motore, su cento aste

Il dato che dice di più non è il numero di vittorie: è **come spende**.
`regole_lega.json` dichiara P 7 / D 12 / C 21 / A 60. Il motore, contro una
stanza che paga i prezzi veri, spende così:

| reparto | dichiarato | speso davvero |
|---|---|---|
| P | 7 % | 4,6 % |
| D | 12 % | 20,7 % |
| C | 21 % | 36,2 % |
| A | 60 % | 36,9 % |

Non è un errore: è la strategia. La stanza paga gli attaccanti molto più di
quanto rendano, quindi il motore ne lascia una fetta agli altri e carica il
centrocampo, che è il reparto dove i punti costano meno. Il pavimento del 30 %
sugli attaccanti (`riserva_minima_per_ruolo`) resta la garanzia contro un
errore delle proiezioni; su cento aste non è costato niente («senza pavimenti»
pareggia), ma toglierlo vorrebbe dire scommettere tutto sulla loro bontà.

Le altre manopole, girate una alla volta su trenta aste ciascuna, non hanno
migliorato niente: rilanciare del 5-20 % oltre il proprio limite peggiora
sempre (−4, −6, −7 punti), e spostare `fiducia_nel_mercato` a 0,25 o 0,75 sta
dentro il rumore. Restano dove sono.

### Il quadro finale

| | |
|---|---|
| aste vinte | **100 su 100** |
| scarto dal secondo | +99 punti mediano, +24 nel caso peggiore |
| rose incomplete | 0 |
| rischio di restare in dieci | 1,1 giornate su 38 (peggiore 2,2) |
| acquisti pagati sopra il proprio limite | **0 su 2300** |
| acquisti pagati sotto il prezzo di mercato | 1771 su 2300 (77 %), risparmiando 9,2 crediti l'uno |

Restano due cose non risolte, e nessuna delle due è un guasto:

- **7,3 crediti avanzati in media, 44 nel caso peggiore.** Crediti non spesi
  sono punti non comprati. Succede quando i giocatori che il motore voleva
  sono volati oltre il limite e quelli rimasti non valevano il prezzo: è la
  risposta giusta a quella situazione, ma 44 crediti sono il 9 % del budget.
- **10,6 lotti per asta persi per due crediti o meno.** Il limite è il punto
  di indifferenza, quindi perderlo per un credito non costa niente in teoria.
  In pratica la teoria assume che i punti attesi siano giusti. Rilanciare oltre
  il limite è stato provato al 5, 10 e 20 %, e peggiora sempre (−4, −6, −7
  punti), quindi la teoria per adesso regge.

### Il caveat che va detto

I punti della simulazione li calcola **il nostro stesso modello di
proiezioni**. La prova quindi risponde a «date le nostre valutazioni, il motore
le sfrutta bene?» — e la risposta è sì. Non può rispondere a «le nostre
valutazioni sono giuste?», perché su quello simulatore e motore sono d'accordo
per costruzione. Quella domanda la decide solo la stagione.

---

---

# Ottavo giro — guardare l'asta mentre si gioca, non solo alla fine

`cento_aste.py` misura l'esito: chi vince, con che rosa, con quanti crediti
avanzati. Un motore però può vincere e insieme dire cose sbagliate lungo la
strada — consigliare un giocatore già venduto, proporre un limite più alto dei
crediti che si hanno, contraddirsi fra una sezione e l'altra. All'esito quelle
cose non si vedono, e sono proprio quelle che si notano al tavolo.

`simulazioni/ispeziona.py` gioca venti aste controllando a **ogni singola
chiamata** le proprietà che devono valere sempre. Ha trovato **quattro difetti
veri**, tutti invisibili al punteggio finale — e nessuno dei quattro sarebbe
uscito da un'altra tornata di aste simulate, perché nessuno dei quattro fa
perdere.

---

## 1. Il buco da 194 crediti — `Valutatore._tetto_reparto()`

Il più grave, e il più nascosto.

A metà asta i prezzi attesi smettevano di sommare ai crediti ancora in gioco:
**3150 contro 3344**. Centonovantaquattro crediti che la stanza avrebbe speso
eccome, e che il motore non aveva assegnato a nessun giocatore.

La causa sono i portieri a pacchetto. Quando tutti i titolari sono stati
assegnati, a listone restano solo le riserve — che arrivano in dote col
titolare e costano **un credito ciascuna**. Il motore continuava a destinare al
reparto i 212 crediti del preventivo per diciotto riserve da un credito l'una,
e quei 194 crediti restavano parcheggiati su un reparto che non poteva più
spenderli.

L'effetto: da quel momento in poi **ogni chiusura attesa dell'asta era più
bassa del vero, di circa il sei per cento**. Non su un giocatore: su tutti. E
in questa lega i portieri chiudono per primi, quindi capitava a ogni singola
asta, per tutto il resto della serata.

Adesso un reparto non può trattenere più di quello che i giocatori rimasti
possono davvero costare. Verificato: lo scarto passa da −194 a −1, che è
l'arrotondamento.

---

## 2. Due indicazioni opposte sullo stesso nome

Il consiglio deduplicava «da far pagare agli altri» contro «top acquisti», con
un commento che spiegava perché — *sono due indicazioni opposte, e a schermo
diventerebbero un invito a chiamarlo per poi non prenderlo* — ma **non contro
le alternative**, che sono comunque giocatori che potresti prendere. Sullo
schermo comparivano tutte e due, sullo stesso nome.

Con «da evitare» invece la sovrapposizione è giusta e resta: uno che non ti
conviene è esattamente quello su cui far spendere gli altri.

---

## 3. Il tetto per far pagare poteva stare sopra la chiusura attesa

`_svuota` calcolava due limiti — sotto il valore di mercato (`prezzo_base − 1`)
e non oltre la chiusura attesa — ma **mostrava solo il primo**. A inizio asta
coincidono; a metà, quando `prezzo_base` resta fermo e la chiusura attesa
scende, il pannello finiva per invitare a spingere sopra il prezzo a cui quel
giocatore sarebbe andato via da solo. Spingere lì non fa spendere niente a
nessuno: fa solo correre il rischio di aggiudicarselo.

Adesso il tetto mostrato è il più basso dei due.

---

## 4. Un nome in due sezioni che si contraddicono

Il difetto da cui è nato tutto questo lavoro — *«mi dice occasione, ma se lo
seleziono dice lascia»* — era rientrato dalla finestra, una volta su
cinquemila.

Quando le alternative vere sono poche, `_alternative` ripesca dal fondo del
listone con una vecchia regola che **non passa dalla classificazione in
fasce**. Da lì rientrava chi era già stato classificato trappola: Locatelli,
convenienza −3,6, finiva fra le «alternative», e da lì la regola che vieta la
lista vuota lo promuoveva fra i **top acquisti** — con la scheda che continuava
a dire LASCIA.

Tre tagli, uno per ogni punto in cui poteva passare: il ripescaggio scarta chi
è sotto la soglia della trappola, le alternative escludono chi è già fra quelli
da evitare, e la promozione «lista mai vuota» non promuove nessuno di cui la
scheda dica di lasciar perdere. Meglio una lista corta che una lista che si
contraddice.

E poi un quarto taglio che non guarda più il ragionamento ma **il risultato**.
Le tre deduplicazioni stanno ognuna al punto giusto del ragionamento, e ognuna
guarda le liste com'erano *in quel momento*: chi entra dopo, o per una strada
che quel punto non copre, passa lo stesso — ed è quello che continuava a
succedere, tre volte su cinquemila. Inseguire le strade una per una è tapparle
una alla volta e sperare. Adesso l'ultimo controllo è sulle liste come escono,
che è l'unica cosa che vedi: un nome fra i consigliati non può comparire anche
fra le alternative o fra quelli da far pagare agli altri, comunque ci sia
arrivato.

---

## E una cosa che sembrava un difetto e non lo era

La media geometrica fra merito e curva dei prezzi schiacciava proprio i
giocatori per cui la curva esisteva. Un giocatore che il modello valuta sotto
il livello di rimpiazzo ha merito zero, e la media geometrica di zero è zero:
il prodotto veniva salvato da un `max(0.01, ...)` messo lì solo perché il
logaritmo di zero non esiste. Colombo — mercato 30 crediti, curva 19 — usciva a
**3,5**, cioè quasi il valore che aveva prima che la curva ci fosse.

Adesso i due pareri si portano prima ognuno sul proprio prezzo, e si media fra
due prezzi. Un prezzo non è mai sotto un credito, quindi il pavimento non è più
un numero scelto per far tornare i conti: è il credito, che è quanto costa
davvero il giocatore più scarso del listone. Colombo passa da 3,5 a 6,5,
l'errore pesato per i crediti in gioco da 29,0 % a 27,6 %.

C'è anche una rete nuova per il caso opposto: quando l'offerta di un reparto
scende fino a pareggiare la domanda, il valore sopra il rimpiazzo va a zero per
tutti insieme — se restano sei pacchetti e sei rose da completare, nessuno di
quei sei è sopra il rimpiazzo, perché il rimpiazzo sono loro. Quando il
criterio si azzera in blocco si ripiega sui punti di stagione, che una
graduatoria ce l'hanno sempre.

---

## Il quadro dopo i rimedi

Venti aste, **5114 chiamate al consiglio** controllate una per una:

| | prima | dopo |
|---|---|---|
| prezzi che non chiudono il mercato | 199 volte, 9 aste | 0 |
| due sezioni che si contraddicono | 287 volte, 18 aste | 0 |
| tetto per far pagare fuori posto | 5935 volte, 20 aste | 0 |
| verdetto che smentisce la lista | 1 volta | 0 |

**Nessuna violazione**, su nessuna delle proprietà, in nessuna delle venti
aste.

Il costo di una chiamata al consiglio è **510 ms**, la peggiore 1,1 s: in
asta si aggiorna fra una chiamata e l'altra, quindi non si vede.

Due delle quattro cose che il primo giro aveva segnalato erano invece **sbagli
della prova, non del motore**: confrontava il tetto per far pagare con il
prezzo del momento invece che con il valore in una stanza normale, e non
ammetteva che «da evitare» e «da far pagare agli altri» possano coincidere —
mentre coincidere è esattamente quello che devono fare. Le due misure sono
state corrette perché una prova che grida al lupo su una proprietà che non
esiste è peggio di nessuna prova.

### E al tavolo?

Rifatte le cento aste con tutti i rimedi dentro: **100 vittorie su 100**, 2308
punti mediani contro 2303, +99 sul secondo, zero rose incomplete, zero acquisti
sopra il proprio limite. I quattro difetti non facevano perdere — facevano
dire cose sbagliate — e infatti sistemarli non sposta il punteggio. È il motivo
per cui un'altra tornata di aste simulate non li avrebbe mai trovati.

I crediti avanzati scendono da 7,3 a 4,9 in media, ed è l'unico effetto
visibile del buco da 194 crediti: sapendo che i prezzi del resto dell'asta
erano più alti di quanto credeva, il motore ne tiene meno in tasca.

---

---

# Quanto conta davvero dividere il budget fra i reparti

Il motore, lasciato libero contro una stanza che paga i prezzi veri, mette in
attacco il **34%** dei crediti, contro il 60% che `regole_lega.json` dichiara.
La domanda è arrivata da Davide nella forma giusta: *«devi contare anche che
gli attaccanti sono quelli che possono fare più gol»*.

## L'aritmetica dice una cosa

| | punti del migliore | punti dell'ultimo in rosa | differenza | +crediti | punti per credito |
|---|---|---|---|---|---|
| difensori | 188 | 171 | 17 | 13 | **1,35** (1,49 col modificatore) |
| centrocampisti | 195 | 176 | 20 | 14 | 1,43 |
| attaccanti | 212 | 134 | **78** | 71 | **1,09** |

Ha ragione su entrambi i pezzi: un attaccante forte fa più punti di qualunque
difensore, e soprattutto **in attacco la scelta pesa** — 78 punti fra un
attaccante vero e un riempitivo, contro 17 in difesa, dove uno vale l'altro.

E però quei 78 punti costano 71 crediti, e i 17 del difensore ne costano 13.
Al margine l'attacco è il reparto dove il credito rende **meno**, di circa un
quarto. Non perché gli attaccanti facciano pochi gol: perché li fanno, tutti lo
sanno, e il prezzo li ha già scontati.

## La prova dice un'altra

`simulazioni/quanto_in_attacco.py` alza il pavimento del reparto — la quota di
budget che il motore deve comunque destinargli — e rigioca le stesse aste.

| pavimento in attacco | vinte | punti | contro il 30% | speso davvero in A |
|---|---|---|---|---|
| 30% | 39/40 | 2298 | — | 34% |
| 40% | 37/40 | 2300 | +1 (0,1) | 41% |
| 50% | 40/40 | 2300 | +2 (0,3) | 50% |
| 60% | 40/40 | 2296 | −5 (−0,9) | 60% |

**Niente.** Spostare un quarto del budget da un reparto all'altro non muove il
punteggio: tutti gli scarti stanno sotto un errore standard.

## Perché l'aritmetica non prediceva l'esito

Perché quel «1,09 contro 1,35» è una media **sul listone**, e l'ottimizzatore
non compra la media: compra il meglio dentro il budget che ha. Con 190 crediti
per l'attacco trova due attaccanti buoni; con 300 ne trova tre, spendendo
peggio ma prendendo di più. I due effetti si annullano.

È una correzione a quello che avevo scritto io, e vale la pena tenerla scritta:
**la ripartizione del budget fra reparti non è la leva che sembra.** Conta per i
prezzi che si leggono a schermo — `prezzo_atteso` ne dipende — molto più che
per la rosa che esce.

## Cosa farne

Il pavimento del 30% in attacco resta, perché è il reparto dove sbagliare costa
di più e non ci si vuole arrivare senza crediti. Ma siccome alzarlo non costa
niente, portarlo a 45-50 è una scelta legittima per chi non si fida di vedere
il 34% in attacco: si cambia in `regole_lega.json`, `riserva_minima_per_ruolo`,
e gli altri reparti si stringono da soli.

**Il caveat vale anche qui**: la prova conta i punti col nostro stesso modello.
Se le proiezioni sottovalutano sistematicamente gli attaccanti — e sui gol, che
arrivano a grumi, è possibile — la simulazione non può accorgersene, perché
motore e simulatore usano lo stesso metro.

---

---

# L'interfaccia: due cose importanti che si davano fastidio

Guardando il programma acceso, e non il codice, la cosa che saltava all'occhio
era una sproporzione.

Lo schermo era diviso in tre: le squadre a sinistra (264px), il centro
(elastico, il più largo) e i pannelli a destra (340px). Il centro però restava
**vuoto** finché non si cercava un giocatore: mezzo schermo occupato da un
cerchietto grigio e dalla scritta *«Cerca il giocatore che è stato appena
chiamato»*. Nello stesso momento **la lista di chi chiamare** — cioè quello che
si guarda quando tocca a te, con dentro le occasioni, le trappole e le
alternative — stava schiacciata in una striscia da 340px, tre righe alla volta,
da scorrere.

Erano le due cose più importanti del programma: una occupava metà schermo per
non dire niente, l'altra non aveva posto per dirlo.

## I consigli sono passati al centro

Non è più una scheda fra le altre: è quello che c'è quando non c'è altro. La
colonna di destra resta con «La mia rosa» e «Listone», che sono stato e
consultazione.

Con la larghezza del centro la lista va **su due colonne**: dove prima si
vedevano tre nomi, adesso se ne vedono otto senza scorrere, e in asta lo
scorrimento è tempo che non hai.

Quando cerchi un giocatore la sua scheda prende quello spazio e i consigli si
fanno da parte; **Escape** (o svuotare il campo di ricerca) li riporta. Quella
via di ritorno prima non serviva e adesso sì: senza, l'unico modo di rivedere i
consigli era registrare l'acquisto o cercare un altro nome — due strade che
passano da un'azione che magari non volevi fare.

Effetto collaterale che vale da solo il cambio: con la scheda al centro il
blocco **«chi se l'è aggiudicato?»** — gli otto bottoni e il campo del prezzo,
cioè il gesto che fai a ogni singola chiamata — è finito **sopra la piega**.
Prima stava sotto, e ogni volta bisognava scorrere.

## Le spiegazioni si aprono, non stanno aperte

Sopra ogni lista c'erano cinque o sei righe che spiegano come leggerla. Sono
scritte bene e servono la prima volta; alla ventesima chiamata sono sei righe
fra te e il nome che stai cercando, e in asta non le legge nessuno.

Adesso sono dietro una pastiglia **«? come si legge»**: chiuse di default,
aperte se le vuoi. Il testo non è stato tagliato, solo spostato di un clic.

## I pallini delle rose si leggono

Ogni squadra nel rail mostra venticinque caselle che si riempiono, reparto per
reparto. A cinque pixel di diametro erano una macchia grigia: l'informazione
c'era e non si leggeva. Ora sono quadratini da sette pixel, staccati fra un
reparto e l'altro, e i vuoti hanno un contorno invece di sparire nel fondo.

## E un difetto vero, trovato per sbaglio

Cancellando l'asta a mano per fare le prove ho lasciato il database a metà — la
riga `asta` c'era, i presidenti no. Il server **moriva all'avvio**, con una
traccia di stack e nessuna finestra: `esiste()` guardava solo la riga `asta`, e
`Sessione.__init__` si fidava.

Non è un caso da laboratorio: basta il programma chiuso nel momento sbagliato
durante una «nuova asta», o un errore su disco, e il programma non parte più
finché qualcuno non cancella il database a mano. Adesso un'asta senza
presidenti non è un'asta a metà: è un'asta che non c'è, e la risposta giusta è
la schermata di partenza.

---

---

# Due difetti nati dallo spostamento dei consigli

## Il listone restava bianco

Cliccando «Listone» la colonna di destra si svuotava: la linguetta si
accendeva, il pannello no.

I pannelli si ricalcolano sul server e arrivano quando arrivano; per non far
sovrascrivere una risposta nuova da una vecchia, ogni richiesta si portava
dietro **il numero dell'ultima richiesta fatta** e vinceva solo l'ultima. Un
contatore solo, per tutti i pannelli. Funzionava finche' se ne caricava uno
alla volta.

Spostando i consigli al centro li ho fatti ricalcolare **a ogni ridisegno**, e
quindi due richieste partono sempre insieme: la seconda annullava la prima. La
risposta del listone arrivava gia' scaduta, invalidata da una richiesta che
riguardava un altro pannello.

La domanda giusta non e' «e' la richiesta piu' recente», e' «e' la piu' recente
**per questo pannello**». Adesso il numero e' per pannello.

## Dodici nomi per un posto solo

Comprati sette pacchetti di portieri su otto, la lista mostrava **dodici**
portieri per l'unico slot rimasto, tutti marchiati PRENDILO - perche' senza
piu' avversari nessuno puo' rilanciare - e tutti con la stessa riga sotto:
«rende 3 punti meno del primo e costa uguale». Dodici righe uguali per un posto
solo non sono una classifica: sono rumore, e spingevano fuori schermo le
sezioni sotto.

Quanti nomi mostrare non dipende dagli slot, dipende da **quanti te ne possono
soffiare**. Finche' c'e' qualcuno che puo' rilanciare serve profondita': i tuoi
primi obiettivi possono volare via e la lista deve arrivare fino a chi
prenderesti allora. Quando non e' rimasto nessuno che possa contenderteli, tre
bastano.

## E le sezioni vuote adesso dicono perche'

«Da evitare» si svuotava e restava «Niente da segnalare in questo reparto»,
che si legge come «ho smesso di rispondere». Non era un difetto - senza piu'
avversari nessun portiere puo' essere una trappola, perche' qualunque portiere
lo paghi un credito - ma quella frase non lo diceva.

Adesso ogni sezione vuota porta la sua ragione, e la ragione cambia col
momento dell'asta.

## Nota di lingua

In tre punti il singolare si ricavava togliendo l'ultima lettera al plurale, e
a schermo usciva «un portier», «un difensor», «un centrocampist». Sono quattro
parole: adesso sono scritte.

---

---

# La scheda di un giocatore adesso si chiude

Aprendo un giocatore **dal listone** non si tornava piu' ai consigli. La scheda
li copre - stanno nello stesso spazio al centro - e le due vie d'uscita che
avevo messo passavano tutte e due dal campo di ricerca: `Esc` era agganciato al
campo, non alla pagina, e "svuota la ricerca" non vuol dire niente se non hai
cercato niente. Chi arriva dal listone in quel campo non e' mai passato.

Due porte, adesso:

- un bottone **x consigli** in alto a destra sulla scheda, che si vede e dice
  dove porta. Una sola "x" avrebbe fatto pensare a "annulla l'acquisto";
- **Esc** da qualunque punto della pagina, non solo dal campo di ricerca.

Il bottone sta sulla scheda, quindi vale per ogni strada che porta ad aprire un
giocatore: ricerca, listone, riga dei consigliati.

---

---

# Fuori dalla lista di serie A

Segnalato dopo un'asta vera: il motore aveva proposto **Milik**, che alla
Juventus è escluso dalla lista campionato e quindi non può giocare **nemmeno
una partita**.

## Cosa sapeva il motore, e cosa non sapeva

Le proiezioni non erano cieche: gli davano **0,91 presenze attese**, titolarità
2%, grado «riserva». Sapevano che non gioca. Ma sapevano che gioca *poco*, non
che **non può giocare**, e nel mezzo c'è tutta la differenza.

Perché a fine asta, coi crediti finiti, scatta la regola degli ultimi posti —
*«meglio lui che una casella vuota»* — e il limite su Milik risaliva a **un
credito**. È giusto per un riempitivo scarso. È sbagliato per uno fuori lista:
**uno che non può scendere in campo *è* una casella vuota**, e per giunta
occupa uno slot che potrebbe tenere qualcuno che ogni tanto gioca.

Un infortunio toglie giornate; l'esclusione dalla lista le toglie tutte. Erano
due cose diverse e il programma ne conosceva una sola.

## Il rimedio

Una fonte nuova, `database/fonti/web/fuori_lista.csv`, che il consenso legge
insieme alle altre. Chi è dentro:

- ha **zero** presenze attese, non «poche»: non si mescola con niente e non
  passa dai pesi delle guide;
- non contribuisce al modificatore di difesa;
- ha limite **zero** in ogni fase dell'asta — il controllo sta in cima a
  `max_bid`, prima di ogni altro conto, perché ogni altro conto lo tratterebbe
  come un giocatore molto scarso e la regola degli ultimi posti lo ripescherebbe;
- ha un verdetto suo, **FUORI LISTA**, invece di RIPIEGO. Senza quel ramo la
  scheda diceva *«è chi prendere se i tuoi obiettivi volano via»* su uno che
  non può giocare;
- porta un cartellino rosso nel listone, così si vede senza aprire la scheda.

Oggi il file contiene i due della Juventus verificati su Tuttosport (Milik e
Khephren Thuram). **Non esiste un elenco unico per le venti squadre**: quando
ne trovi altri si aggiungono due righe al CSV e si rilancia `consenso.py`.

## Una precisazione dal regolamento

La lista si può correggere **una volta a stagione, per due giocatori di
movimento**. Quindi l'esclusione non è definitiva: se rientra, si rifà la
raccolta e torna dentro. Per l'asta però l'attesa giusta è zero — e se rientra
lo si compra allora.

---

## Cosa manca

- **Assenze correlate**: il rischio di restare in dieci estrae le
  indisponibilità come indipendenti, mentre nella realtà si concentrano nei
  turni infrasettimanali e dopo le soste. Il numero vero è un po' più alto di
  quello mostrato. Servirebbe una stima della correlazione per giornata, e i
  dati per farla non sono nel database.
- **Il costo della casella vuota non è nella funzione da massimizzare**: adesso
  si misura e si mostra, ma l'ottimizzatore continua a trattare un giocatore
  che non gioca come uno che vale zero, non come una giornata in dieci. Finché
  il rischio resta sotto il 4% l'effetto è di una decina di punti a stagione su
  2200; diventerebbe importante solo per chi si allontana molto dal piano.
- **L'elenco dei fuori lista è parziale**: ci sono i due della Juventus,
  verificati. Non esiste una pagina unica con gli esclusi delle venti squadre,
  e finché non si trova vanno aggiunti a mano in
  `database/fonti/web/fuori_lista.csv`. Ogni nome che manca è un giocatore che
  il motore può ancora proporre per un credito credendolo un riempitivo.
- **Storico di più aste**: oggi il database ne tiene una sola.
- **`nuovo_acquisto`** resta incompleto per 166 giocatori (chi ha cambiato
  squadra ma la fonte non lo segnalava): dove manca, `titolarita.py` non
  applica lo sconto di certezza dovuto alla novità.
- **Le cinque guide sono una fotografia del 3 settembre 2026**: dopo altre
  giornate di campionato le gerarchie si assestano. Rilanciare
  `raccolta_2026_27.py` con testo fresco e poi `consenso.py` + `proiezioni.py`
  è il modo per aggiornarle; non c'è ancora un modo automatico di andare a
  ripescare le pagine da soli.

## Come si ricostruisce tutto da zero

```bash
cd database/fonti/web
python raccolta_2026_27.py     # riscrive i CSV grezzi delle guide lette dal web
cd ../../pipeline
python consenso.py             # incrocia le guide -> gerarchie.csv e accoppiate.csv
cd ../../motore
python db.py             # ricrea fanta.db dai CSV, comprese gerarchie e accoppiate
python proiezioni.py     # ricalcola punti attesi, gerarchia di reparto, rigoristi
python titolarita.py     # mostra chi risulta titolare, e con quanta certezza
python test_motore.py    # 35 verifiche del motore
cd ../app
python test_app.py       # 64 verifiche, asta intera via HTTP
python test_chiusura.py  # 12 verifiche di avvio e spegnimento
```

I primi due passi servono solo per **rifare la raccolta dal web** (guide nuove,
giornata successiva): se non serve aggiornarla, si riparte direttamente da
`python db.py`, che legge `database/gerarchie.csv` e `database/accoppiate.csv`
così come sono — e se quei due file non esistono il programma funziona lo
stesso, solo senza il consenso delle guide (`db._carica_opzionale`).

Le tre suite vogliono la macchina libera: `test_app.py` e `test_chiusura.py`
avviano un motore vero, e due istanze sullo stesso database si escludono a
vicenda (che è il comportamento giusto, ed è verificato). Chiudere FantaHacked
prima di lanciarle.

Se cambiano le colonne di `proiezioni`, il server se ne accorge da solo: alla
partenza, se la gerarchia non è calcolata, rifà le proiezioni. Un database
vecchio non fa girare il programma senza sapere chi gioca.

`test_chiusura.py` avvia e spegne il programma per intero, quindi va lanciato
con **nessun'altra istanza in esecuzione**.

Per rifare l'eseguibile:

```bash
python -m PyInstaller --noconfirm --onefile --noconsole --name FantaHacked --icon "app/fantahacked.ico" --distpath . --workpath "build/lavoro" --specpath "build" --paths motore --hidden-import percorsi --hidden-import db --hidden-import regole --hidden-import proiezioni --hidden-import asta --hidden-import valutazione --hidden-import modificatore --hidden-import ottimizzatore --hidden-import strategia "app/server.py"
```

L'`.exe` deve restare **nella cartella del progetto**: cerca `database/`,
`motore/` e `app/web/` accanto a sé, così i dati restano modificabili.

---

# 7 settembre: il listone riletto a mercato chiuso

Il mercato ha chiuso il **1 settembre alle 20**. Il listone su cui girava il
programma era stato estratto il 2, e nel frattempo erano successe tre cose
diverse che si erano confuse in una sola: qualcuno era arrivato, qualcuno se
n'era andato, e qualcun altro era rimasto nel listone senza poter piu' giocare.

## Da dove arrivano adesso i dati

| Cosa | Fonte | Letta il |
|---|---|---|
| Listone, quotazioni, FVM, id ufficiali | fantacalcio.it &mdash; *Quotazioni* | 7 settembre |
| Chi e' ancora in serie A | fantacalcio-online.com &mdash; listone aggiornato ogni giorno | 7 settembre |
| Formazioni, panchine, probabilita' di impiego | fantacalcio.it &mdash; *Probabili formazioni*, giornata 3 completa | 7 settembre |
| Infortunati e tempi di rientro | fantacalcio.it &mdash; *Infortunati* | 7 settembre |
| Esclusi dalla lista di serie A | Tuttosport, Eurosport, Calciomercato.com | 7 settembre |

## L'id ufficiale, che prima veniva indovinato

Il listone di partenza non portava l'id della piattaforma, e la pipeline lo
cercava per nome nei listoni storici. Chi non aveva uno storico riceveva un id
**inventato** (>= 900001): erano **138 su 531**, piu' di un giocatore su
quattro. Nessuno di loro si riconosceva nel file delle rose esportato a fine
asta, e infatti su duecento acquisti dell'asta vera solo 164 si abbinavano per
id: gli altri passavano dal nome, che sugli omonimi non e' sicuro.

Adesso l'id arriva dalla fonte: **593 su 593, nessuno inventato.**

Effetto collaterale scoperto strada facendo: cercare lo storico *per id*
invece che per nome ha fatto emergere un difetto vecchio. Il Frosinone ha
`Oyono A.` e `Oyono J.`, la fonte statistica conosce un solo Oyono, e le
statistiche di Anthony finivano addosso a tutti e due. Da li' in poi i due
erano indistinguibili e le guide che scrivevano "Oyono" non si abbinavano piu'
a nessuno dei due: **un titolare del Frosinone risultava schierato da nessuno.**
Ora la voce contesa la tiene chi ha anche l'iniziale giusta, e l'altro resta
senza, che e' la risposta onesta.

## Le panchine, che prima non esistevano

La pagina delle probabili formazioni non da' solo l'undici: da' anche la
panchina, e per ognuno **quanto e' probabile che giochi**. Prima il programma
leggeva solo gli undici, e la lettura era tutto-o-niente: Kean, dato in
panchina al 60%, contava esattamente come il terzo portiere dato all'1%.
Entrambi "non schierati da nessuno", entrambi con le presenze da riserva.

Adesso una fonte che dichiara una percentuale vale **quella frazione** di voto.
Fra i due estremi ci sono una ventina di presenze a stagione, cioe' la
differenza fra una riserva vera e mezza maglia.

La stessa lettura ha portato tutte e venti le squadre da una fonte sola: prima
la pagina ne copriva quattordici e sei arrivavano da un'altra guida.

## Chi non puo' giocare: due casi diversi, stessa conclusione

Dal giro precedente il programma sa cosa vuol dire **essere fuori dalla lista
di serie A** (Milik). A mercato chiuso e' emerso un secondo caso, molto piu'
numeroso: chi la serie A l'ha proprio lasciata. Il mercato italiano chiude il
1 settembre, ma Turchia, Grecia e Arabia restano aperte, e fra il 2 e il 5
settembre sono partiti in sessantadue.

Il modo per riconoscerli senza fidarsi di una notizia sola e' incrociare tre
cose: fantacalcio-online li ha **tolti** dal proprio listone; fantacalcio.it li
tiene ancora; e nessuno di loro compare in **nessuna** rosa della giornata 3,
ne' fra i titolari ne' in panchina. Sessantadue su sessantaquattro passano tutti
e tre i controlli &mdash; gli altri due (Enem, Sierro) erano in panchina, e
infatti restano dentro.

Non vengono cancellati: restano cercabili, con limite **zero** e il verdetto
FUORI LISTA. Se in asta qualcuno chiama Leao, il programma deve saper rispondere
"vale zero", non "non lo trovo".

Nel motore c'era ancora una falla su questo. I sessantaquattro esclusi
prendevano comunque una **fetta dei crediti del reparto**, perche' il peso si
calcola anche dalla curva dei prezzi, che guarda la quotazione: Leao, quotato
18, si portava via crediti che dovevano andare a chi gioca. E per lo stesso
motivo entravano nella **stima della curva** &mdash; prezzo alto, zero punti
&mdash; storcendo la retta per tutti. Ora sono fuori da entrambe.

## Le due ripartizioni

La scoperta piu' grossa del giro, ed e' venuta dai duecento prezzi veri
dell'asta di Davide.

`ripartizione_budget` diceva **P 7 / D 12 / C 21 / A 60**. Confrontata con
quello che la stanza ha davvero pagato:

| | portieri | difensori | centrocampisti | attaccanti |
|---|---|---|---|---|
| pagato davvero | 300 | 697 | 1108 | 1819 |
| detto dal motore | 280 | 461 | 801 | 2386 |
| rapporto | 0,93 | **0,66** | **0,72** | **1,31** |

Il totale tornava &mdash; 3928 contro 3924 &mdash; ma la forma era sbagliata in
modo sistematico: **attaccanti sopravvalutati del 31%, difensori sottovalutati
del 34%**. Malen, pagato 184, ne "valeva" 379. Sui crediti l'errore era del
**50%**.

Con la ripartizione osservata (**8 / 18 / 28 / 46**) l'errore scende al **37%**
e la distorsione per reparto sparisce: 1,07 / 0,99 / 0,96 / 1,01.

Poi pero' cento aste hanno detto l'altra meta' della storia: usando quella
ripartizione **anche per pianificare**, le vittorie scendono da 98 a 91 e i
punti da 2285 a 2271. E' esattamente il caso di `PIANO_SEPARATO`: **il numero
da mostrare e il numero con cui decidere non sono lo stesso numero.**

Quindi adesso ce ne sono due. `ripartizione_budget` resta 7/12/21/60 e serve a
decidere quanto offrire; `ripartizione_mercato` e' 8/18/28/46 e serve a dire
quanto costera'. Cento aste con le due separate: **98 vittorie, 2285 punti,
zero rose incomplete** &mdash; identiche a prima, con i prezzi molto piu' giusti.

## Il valore di mercato (FVM), misurato e non adottato

Il listone ufficiale espone una colonna che il programma non aveva mai avuto:
il **FVM**, il valore di mercato su base 1000. Da solo prevede i prezzi veri
molto meglio della quotazione (48% di errore contro 72%), e sembrava il
candidato naturale per sostituire la quotazione dentro la curva dei prezzi.

Misurato, non lo e'. Dentro la curva &mdash; dove accanto alla quotazione ci
sono gia' i punti attesi &mdash; il FVM non aggiunge niente e peggiora un po':

| curva stimata su | errore tipico | pesato sui crediti |
|---|---|---|
| quotazione + punti (quella di oggi) | **35,8%** | **32,6%** |
| FVM + punti | 38,0% | 34,4% |
| quotazione + FVM + punti | 38,0% | 32,8% |

Il FVM resta nel database come informazione, ed e' li' se un giorno servira'.
Il modello dei prezzi non cambia.

## Cosa e' cambiato nel listone

**Aggiunti 62** giocatori che c'erano sulla piattaforma e non da noi. Sei
giocano davvero: **El Shaarawy** (Genoa, 7), **Rodriguez R.** (Torino, 5),
**Ehizibue** (Genoa, 4), **Enem** (Bologna, 2), **Sierro** (Parma, 1),
**Rossi F.** (Atalanta, 1). Gli altri 56 sono partiti, e stanno a zero.

Che non fosse teoria lo dice l'asta vera: **El Shaarawy era stato comprato** per
2 crediti da "Jesus morto in croce", ed era l'unico dei duecento acquisti che il
programma non sapeva riconoscere.

**Messi a zero 8** che erano gia' in listone: Thuram K. e Milik (esclusi dalla
lista della Juventus), **Romagnoli** (Lazio, quotato 6), Borrelli, Koutsoupias,
Paleari, Anjorin, Robinho Junior.

## Le assenze che contano per l'asta

Dalla rilettura degli infortunati, i nomi grossi:

| | quotazione | giornate saltate | rientro |
|---|---|---|---|
| Yildiz (Juventus) | 22 | 9 | fine novembre |
| McTominay (Napoli) | 27 | 3 | meta' ottobre |
| Orsolini (Bologna) | 25 | 2 | fine settembre |
| Thuram K. (Juventus) | 9 | 15 | gennaio |
| Kone I. (Sassuolo) | 8 | 10 | dicembre |
| Buongiorno (Napoli) | 6 | 8 | meta' novembre |
| Nicolussi Caviglia (Parma) | 6 | 8 | novembre |
| Parisi (Fiorentina) | 4 | 8 | novembre |

Il calendario fa da ammortizzatore e va guardato: fra la 5a e la 6a giornata ci
sono venti giorni di sosta, quindi "rientro a inizio ottobre" vuol dire saltare
**due** partite, non cinque. E' il motivo per cui le assenze si contano in
giornate e non in settimane.

Su Yildiz il motore dice quello che deve: prezzo atteso 75, **limite 3**.
Su McTominay dice il contrario: prezzo atteso 46, limite 76, OCCASIONE
&mdash; la stanza lo sconta perche' e' fermo, il motore sa che torna a ottobre.

## Numeri finali

- 593 giocatori (erano 531), **100% con id ufficiale**
- 64 a zero perche' non possono giocare
- 50 infortunati con i tempi di rientro dichiarati
- 460 righe di formazione dalla giornata 3, panchine comprese
- **47 verifiche del motore + 264 dell'applicazione**, tutte superate
- **98 aste vinte su 100** simulate, zero rose incomplete

---

# 9 settembre: i dati si scaricano, l'asta resta a casa

Un file solo conteneva due cose che non si somigliano per niente: il listone,
che e' uguale per tutti e si rifa' ogni volta che rileggo le fonti, e gli
acquisti dell'asta, che sono di quella sera e se si perdono non li rimette
insieme nessuno. Tenerle insieme aveva una conseguenza sola ma pesante:
**aggiornare i dati voleva dire riscrivere il file che contiene l'asta.**

Adesso i file sono due.

| | cosa c'e' | dove | come cambia |
|---|---|---|---|
| `database/dati.db` | listone, statistiche, gerarchie, proiezioni | scaricato | si sostituisce in blocco, quando si vuole |
| `motore/asta.db` | asta, presidenti, acquisti | sul dispositivo | non esce mai da li' |

Il pacchetto pubblicato sta su
[github.com/JDado02/DBFantaHacked](https://github.com/JDado02/DBFantaHacked):
**185 KB compressi**, 544 una volta aperto.

## Le query non sono cambiate di una virgola

SQLite sa aprire due file insieme (`ATTACH`) e risolvere da solo in quale dei
due sta ogni tabella. Una query che dice `FROM giocatori JOIN acquisti`
continua a funzionare tale e quale: le ~4.000 righe di motore non sono state
toccate. Un join fra i due file misura **un millisecondo**.

Due cose pero' il confine non lo attraversano, e vanno trattate:

**Le chiavi esterne.** `acquisti.giocatore_id` puntava a `giocatori`, che ora
sta nell'altro file, e SQLite non fa rispettare un vincolo fra due database:
non lo ignora, **fallisce l'inserimento** con "no such table: main.giocatori".
Il vincolo e' stato tolto dallo schema; quello verso `presidenti`, che resta
nello stesso file, e' rimasto e continua a funzionare.

**Le viste.** Una vista vede solo il database in cui e' definita.
`v_disponibili` incrocia il listone con gli acquisti, quindi non puo' stare ne'
di qua ne' di la': viene creata come **vista temporanea** a ogni connessione,
e cosi' vede tutto quello che la connessione ha aperto.

## Chi aveva un'asta aperta non la perde

Al primo avvio, se trova il vecchio `fanta.db`, il programma lo spezza in due:
i giocatori di qua, gli acquisti di la', ciascuno col suo limite salvato. Il
file di prima non viene cancellato ma rinominato in
`fanta.db.prima-della-divisione`. Provato con un'asta a meta': acquisti,
limiti e viste tornano tutti al loro posto.

## Il giro di aggiornamento

All'avvio il programma chiede **soltanto il `manifest.json`** &mdash; 310 byte
&mdash; e confronta la data. Se e' la stessa non scarica niente: 0,06 secondi.
Se e' cambiata scarica il pacchetto: 0,22 secondi in tutto, da cartella vuota
a database pronto.

Tre difese, e tutte e tre hanno una prova dedicata:

**Se la rete non c'e', si parte lo stesso.** Sei secondi di attesa massima, poi
si continua con quello che c'e' e la pagina dice di quando sono i dati. Un
assistente d'asta che non si apre perche' il wifi della stanza fa i capricci
sarebbe peggio di uno con i dati di tre giorni prima. Ci sono due frasi
diverse, perche' sono due cose diverse: *nessun pacchetto pubblicato a
quell'indirizzo* e *nessuna risposta da internet*.

**Un pacchetto rotto non sostituisce quello buono.** Si scarica di fianco, si
verifica la firma, si prova ad aprirlo e a contare i giocatori, e **solo
allora** si sposta. Un download interrotto a meta' lascia tutto com'era.

**Dati piu' nuovi del programma vengono rifiutati.** Il pacchetto porta un
numero di versione dello schema: se e' piu' alto di quello che il programma sa
leggere, si ferma e dice di aggiornare FantaHacked, invece di aprirli e
rompersi a meta' asta. Dati piu' vecchi invece vengono riparati aggiungendo le
colonne che mancano.

## Un difetto vecchio, venuto fuori per caso

Le proiezioni non sono un dato: sono un conto, e dipendono dal **regolamento**.
Un gol di difensore che vale 3 invece di 4 e cambiano i punti attesi di tutti.

Quindi il pacchetto porta con se' la firma del regolamento con cui e' stato
calcolato, e se non e' la tua le proiezioni si rifanno sul posto, in due
secondi, prima che il programma apra bocca.

Serviva comunque, anche senza niente da scaricare: **fino a ieri chi correggeva
`regole_lega.json` continuava a vedere le proiezioni di prima**, e nessuno
glielo diceva. Era li' da sempre, e si e' visto solo mettendo mano a questo.

## Il difetto che ha trovato il collaudo

La prima versione confrontava la data **dentro** il file scaricato con quella
del manifest. Se le due non coincidono &mdash; una svista di chi pubblica
&mdash; il programma riscarica lo stesso pacchetto **a ogni avvio, per
sempre**, senza che nessuno se ne accorga: mezzo mega ogni volta, e ogni volta
lo stesso risultato.

Adesso quello che conta e' cosa e' stato installato, non cosa il file dichiara
di essere. La prova che lo ha scoperto e' rimasta li', con la data storta
apposta.

## Perche' i file nel repository e non una release

Le release di GitHub stanno fuori dalla cronologia, quindi non fanno crescere
il repository. Ma richiedono `gh` installato su ogni computer da cui si
pubblica, e `gh` qui non c'era.

Il pacchetto compresso sono 185 KB: anche pubblicandolo ogni settimana per una
stagione intera si resta sotto i dieci mega. Fra i due difetti pesa meno lo
spazio, e cosi' per pubblicare basta `git`, che c'e' gia'.

La compressione e' resa **deterministica** (`mtime=0`), altrimenti gzip infila
l'ora dentro il file e lo stesso database compresso due volte da due file
diversi: ripubblicare dati identici sembrerebbe sempre un cambiamento, e il
repository crescerebbe di 185 KB a ogni giro. Adesso "niente da fare" vuol dire
davvero niente da fare.

## La prova che conta

Una cartella nuova, con dentro solo l'eseguibile, l'interfaccia, i due schemi e
`regole_lega.json` &mdash; **196 KB oltre al `.exe`**, e la cartella dei dati
vuota. Doppio clic: il programma parte, scarica mezzo mega in 0,22 secondi,
calcola le proiezioni e comincia a consigliare.

E' esattamente quello che serviva: **i dati si aggiornano da soli, il software
si copia una volta e basta, e l'asta non si sposta di li'.**

## Numeri

- 47 verifiche del motore + 264 dell'applicazione + **23 nuove** sulla
  divisione e sull'aggiornamento, tutte superate
- manifest 310 byte, pacchetto 185 KB, database 544 KB
- avvio senza aggiornamenti 0,06 s; con download 0,22 s

---

# 9 settembre: due motori, e la prova che dicono la stessa cosa

L'applicazione per telefono non poteva essere un client sottile: il calcolo
serve **fra un rilancio e l'altro**, e un consiglio completo che oggi esce in
quaranta millisecondi, dietro la rete, diventa mezzo secondo quando va bene e
«connessione persa» quando va male. Quindi il motore doveva finire dentro il
telefono, e per farci girare la stessa interfaccia doveva essere JavaScript.

Riscrivere quattromila righe tarate giro dopo giro e' il modo piu' facile di
perdere quella taratura senza accorgersene: nessun numero e' palesemente
sbagliato, semplicemente non sono piu' gli stessi.

## Come si e' evitato

Il motore Python **fotografa i propri numeri** in quattro momenti di un'asta
&mdash; vuota, dopo dieci acquisti, a meta', quasi finita &mdash; con gli
acquisti scritti nel file, cosi' che la parte JavaScript ricostruisca lo stesso
stato invece di sperare che coincida. Poi due pagine li rileggono e li
confrontano uno per uno.

| cosa si confronta | esito |
|---|---|
| punti, VOR, contributo al modificatore, prezzi (mercato, atteso, base, piano), pesi della curva, coefficienti delle regressioni, ottimo dello zaino, limiti, verdetti | **22.356 confronti, 0 differenze** |
| le cinque liste dei consigli: nomi, ordine, cifre, e le frasi delle sezioni vuote | **44 liste, 0 differenze** |

La soglia e' un milionesimo in relativo, e **zero** sui numeri interi &mdash;
dove uno scarto non e' virgola mobile, e' una decisione diversa.

Gli script sono `simulazioni/dump_equivalenza.py` e
`simulazioni/dump_consiglio.py`; le pagine stanno nel repository Android.

## Le tre cose che la prova ha trovato **qui**

Non erano difetti della traduzione. Erano fragilita' di questo motore, che con
un motore solo non c'era modo di vedere.

**Un valore da 1,2e-14.** De Silvestri, difensore di fondo listone, usciva con
valore `0,000000000000012` invece di zero: l'ultimo bit di una sottrazione fra
numeri quasi uguali. Indistinguibile da zero per chiunque, e sufficiente a
farlo entrare nel pool dello zaino al posto di un altro riempitivo, cambiando
il percorso della programmazione dinamica e da li' il limite su **un terzo
giocatore**. Adesso c'e' una soglia dichiarata: sotto un miliardesimo di punto,
zero.

**Pareggi risolti dall'ordine delle righe.** A parita' di costo e di valore
l'ordine dei giocatori nel pool veniva da come SQLite restituiva le righe.
Funzionava, ed era casuale: bastava che una query cambiasse piano perche' il
motore desse un altro numero. Adesso il pareggio e' l'id, che non cambia mai.
Vale anche per le liste mostrate: due giocatori appaiati non devono scambiarsi
di posto da soli fra un ricalcolo e l'altro.

**Due righe in fondo a `_svuota`.** Nella traduzione mancavano, e la lista «da
far pagare agli altri» usciva ordinata per quanto converrebbe **comprarli**,
che e' esattamente la domanda opposta. Tutti i numeri erano giusti; la lista
diceva un'altra cosa. E' il motivo per cui la seconda prova confronta anche
**l'ordine delle liste** e non solo la matematica: un motore puo' avere ragione
su ogni cifra e mettere in fila i nomi nel modo sbagliato.

## Due trappole di lingua, entrambe silenziose

**`Math.round(2.5)` fa 3; `round(2.5)` in Python fa 2.** Python arrotonda al
pari piu' vicino. Il costo di ogni giocatore nel piano di spesa e' un
arrotondamento, e un credito in piu' cambia il percorso dello zaino: la prova
lo ha trovato su un giocatore su seicento.

**JavaScript non ha `erf`.** L'approssimazione classica (Abramowitz e Stegun
7.1.26) sbaglia di 1,5e-7. Sembra niente; moltiplicata per 38 giornate ed
entrata nei punti, nel VOR e nel prezzo di ogni giocatore del reparto, produceva
scarti fino a due milionesimi in relativo &mdash; abbastanza da far scegliere
alla programmazione dinamica un percorso diverso e da spostare un limite di un
credito. Sostituita con la serie a termini tutti positivi, esatta in doppia
precisione.

## Le regole viaggiano coi dati

Le proiezioni **dipendono dal regolamento**, e l'applicazione per telefono non
sa rifarle: porta il motore di valutazione, non quello delle proiezioni, che
serve una volta al giorno e non durante l'asta. Con un regolamento diverso da
quello che ha prodotto quei numeri mostrerebbe cifre sbagliate senza modo di
accorgersene.

Quindi `regole_lega.json` sta **dentro `dati.json`**: le due cose arrivano
insieme o non arrivano. Sul computer resta il file locale, che e' tuo e non
viene mai sovrascritto; il pacchetto pubblicato porta la copia con cui sono
state calcolate le proiezioni.

## Cosa c'e' nei tre repository

| | |
|---|---|
| [FantaHacked-PC](https://github.com/JDado02/FantaHacked-PC) | motore, interfaccia, pipeline, simulazioni |
| [FantaHacked-Android](https://github.com/JDado02/FantaHacked-Android) | l'app: `web/` e' l'applicazione, `app/` l'involucro, `prove/` le due prove |
| [DBFantaHacked](https://github.com/JDado02/DBFantaHacked) | i dati: `dati.db.gz` per il computer, `dati.json` per il telefono, `manifest.json` per decidere se scaricare |

## L'app in se'

Novanta righe di Java che aprono una WebView, e basta: nessuna logica d'asta
fuori dal JavaScript. Un dettaglio che sembra tecnico e non lo e': i file si
servono da `https://appassets.androidplatform.net/` e non da `file://`, perche'
una pagina caricata da `file://` non ha un'origine e il browser le blocca ogni
richiesta verso l'esterno &mdash; l'app non riuscirebbe **mai** a scaricare i
dati.

Gradle impacchetta la cartella `web/` direttamente, quindi non ci sono copie da
tenere allineate: quella che si apre nel browser per lavorarci e' la stessa che
finisce nell'apk.

**L'asta resta sul telefono**, in `localStorage`, salvata a ogni acquisto. Non
si sincronizza con niente: due dispositivi che scrivono sulla stessa asta sono
un modo elaborato di perderla. Coi portieri a pacchetto, comprare il titolare
registra da solo anche le due riserve a un credito &mdash; tre gesti diventano
uno, e dimenticarsene falserebbe gli slot di tutti.

## Numeri

- motore in JavaScript: **1.900 righe**, sei moduli, nessuna libreria
- un consiglio completo: **40 ms** sul telefono, come sul computer
- il pacchetto per il telefono: 190 KB, che GitHub manda compressi a 43
- prima apertura da zero: **0,22 secondi** dallo scaricamento al primo consiglio
- 47 + 23 + 264 verifiche Python, **22.356 + 44 confronti** di equivalenza

---

# 10 settembre: gli infortuni di tre giorni dopo, e due difetti nel metro

Il pacchetto pubblicato il 7 settembre era stato letto il 7 settembre. Tre
giorni dopo gli indisponibili non erano piu' gli stessi: e' l'unica parte del
database che cambia da un giorno all'altro, ed e' anche quella che sposta di
piu' i prezzi, perche' non tocca la media voto &mdash; tocca le **giornate**.

## Cosa e' cambiato

Riletta per intero la pagina degli infortunati: **53 indisponibili** invece di
50. Otto sono rientrati (Mina, Havel, Cambiaso, McKennie, Sarr P., Patric,
Pellegrini Lu., Chakvetadze) e undici sono nuovi. Due contano davvero:

| | | |
|---|---|---|
| **Locatelli** | Juventus | menisco, rientro a gennaio: **15 giornate** |
| **Felici** | Cagliari | crociato, rientro a marzo: **24 giornate** |

Gli altri nove sono acciacchi da una o due giornate, che nei punti attesi si
vedono appena. Fra le proiezioni di prima e quelle di adesso si spostano di
piu' di otto punti **quindici giocatori su 593**; il piu' grosso e' Locatelli,
da 196 a 127.

## Le formazioni no, e la ragione va scritta

La stessa rilettura si poteva fare sulle probabili formazioni, che intanto sono
passate dalla terza giornata alla quarta. Non e' stata fatta, perche' la
trascrizione **non ha superato il controllo**: confrontando gli undici estratti
col listone, otto squadre su dieci verificate tornavano esatte e due no, con lo
stesso giocatore schierato da due squadre diverse. Su una fonte che pesa il
doppio delle altre, e a poche ore da un'asta, un errore cosi' vale piu' del
guadagno di avere le probabili di una giornata dopo.

Gli infortuni invece tornavano su 48 nomi su 50 &mdash; e le due differenze
erano proprio i rientri. E' questa la differenza fra le due letture: non
quanto sono fresche, ma se reggono un confronto con quello che gia' si sa.

## L'asta che non arrivava mai al centrocampo

Rimisurando su **trecento** aste invece di cento e' saltata fuori un'asta da
1072 punti invece di 2280. Non era il motore: erano tutte e otto le squadre a
fermarsi allo stesso punto, con tre portieri, otto difensori e quattordici
caselle vuote.

Il simulatore chiama i giocatori per reparto, e chi non riceve **nessuna**
offerta esce dal giro &mdash; giusto: e' il riempitivo che nessuno vuole. Ma se
capita agli ultimi rimasti di un reparto, il reparto si svuota mentre qualcuno
ha ancora slot scoperti, e li' l'asta finiva: i due reparti successivi non
venivano chiamati affatto. Quell'asta entrava comunque nella media, come se
fosse una partita vera.

Adesso il reparto vuoto si salta. Sullo stesso seme la rosa si chiude tutta e
i crediti vanno a zero, e su trecento aste le rose incomplete sono **zero**.

E' un difetto del metro, non del motore. Ma il metro e' quello con cui si e'
deciso ogni cambiamento da tre settimane, e una misura che ogni tanto inventa
un disastro rende impossibile distinguere un peggioramento vero dal rumore.

## Le prove cancellavano l'asta vera

L'altro difetto era peggiore, e si e' visto perche' e' successo.

`test_motore.py`, i due script che fotografano i numeri per il confronto con il
motore JavaScript e `analizza_asta.py` aprivano il database **normale** e ci
chiamavano `inizializza()`: cioe' giocavano la loro asta finta sopra quella
vera. Fra una verifica e l'altra, l'asta preparata coi nomi della lega e'
sparita. Non e' stato un caso fortunato: e' successo mentre nessuno stava
giocando. Fosse successo la sera dell'asta, sarebbe finita li'.

La divisione in due database protegge **i dati** dagli aggiornamenti; non
proteggeva **l'asta** dagli script. Adesso c'e' `db.asta_di_servizio()`: i dati
sono quelli veri, l'asta e' un file temporaneo col numero di processo nel nome
&mdash; cosi' due script in parallelo non si pestano i piedi &mdash; e sparisce
da solo alla fine. Le quarantasette verifiche del motore passano tutte, e
l'asta preparata e' ancora al suo posto, con gli otto nomi e zero acquisti.

La frase «girano su copie usa e getta dei database: non toccano mai l'asta in
corso» era nel README da ieri. Adesso e' vera.

## Novantotto, novantadue, novantasei

Le cento aste di prima ne davano 98 vinte; con i dati nuovi 92. Sei vittorie in
meno sembra un peggioramento, e non lo e'.

- la stessa serie rifatta **sui dati vecchi con lo stesso codice** ha ridato
  esattamente 98, e i CSV rigenerati erano identici byte per byte a quelli
  di ieri: la pipeline e' riproducibile, quindi la differenza e' nei dati;
- guardando le aste una per una, otto sono passate da vinte a perse e due da
  perse a vinte. Con dieci discordanze, otto da una parte e due dall'altra, il
  test di McNemar da' **p = 0,11**;
- il punteggio medio si e' mosso di **meno di mezzo punto percentuale per
  tutte e otto le squadre**, non solo per il motore.

Un'asta e' un sistema caotico: basta un rilancio diverso a meta' di un reparto
perche' da li' in poi ogni squadra prenda giocatori diversi. Le singole aste si
spostano di duecento punti in entrambe le direzioni; la media no.

La misura buona e' quella lunga. Su **trecento** aste, col simulatore corretto:

| dati | vinte | punti mediani | margine |
|---|---|---|---|
| 7 settembre | 292 su 300 (97%) | 2283 | +91 |
| 10 settembre | **288 su 300 (96%)** | 2280 | +89 |

Venti aste su trecento hanno cambiato esito, dodici in un verso e otto
nell'altro: McNemar **p = 0,50**. Quattro vittorie di differenza su trecento
sono un terzo di deviazione standard. Non e' successo niente &mdash; ed e'
esattamente quello che ci si aspetta da dieci infortuni in piu' su
seicento giocatori.

Il confronto lo fa `simulazioni/confronta_esiti.py`, che e' nato qui: prende
due serie con gli stessi semi e dice **quali** aste sono cambiate e di quanto
si e' mosso il punteggio di ciascuna delle otto squadre.

## Il ripiego che valeva zero

Nella lista «da prendere», sotto il primo della fascia, comparivano righe con
scritto *«e' il ripiego se Vicario vola oltre il tuo limite»* e accanto, in
grande, uno **0**.

Le due cose sembrano contraddirsi e non si contraddicono. Finche' Vicario e'
ancora in lista, quello slot rende di piu' aspettando lui: qualunque prezzo
pagato per il ripiego peggiora la rosa finale, e il limite giusto e'
esattamente zero. Ma detta in cifre e basta, la riga sembra dire due cose
opposte sullo stesso nome, e la sera dell'asta non c'e' tempo per chiedersi
quale delle due vale.

Adesso sotto c'e' la riga che mancava: *«adesso il suo limite e' zero:
conviene solo dopo che Vicario e' andato a qualcun altro»*. Nei due motori la
stessa frase, coi file attesi rigenerati e riconfrontati.

E la cifra grande non e' piu' lo zero. Il programma per computer lo faceva
gia': al posto del limite mostra **quanto dovrebbe chiudere**, in grigio e con
la tilde, con la spiegazione nel titolo. Sul telefono restava uno zero in
grande accanto alla parola «ripiego». Adesso le due applicazioni dicono la
stessa cosa nello stesso modo, che non e' un dettaglio estetico: chi passa dal
computer al telefono fra un'asta e l'altra non deve reimparare a leggerle.

## Il giro completo, verificato oggi

- pacchetto ricostruito e pubblicato: `generato_il` 2026-09-10, 593 giocatori
- **installazione da zero**, su un profilo vuoto: 0,94 secondi dallo
  scaricamento al motore pronto, 593 giocatori caricati
- il telefono, svuotata la memoria locale, riscarica e mostra i numeri nuovi:
  il limite su Vicario passa da 61 a 74, perche' il centrocampo che si libera
  finisce altrove
- 47 + 23 + 264 verifiche Python, tutte superate
- 22.356 confronti e 44 liste fra i due motori: **zero differenze**
- 33 verifiche sulle regole d'asta del telefono: zero fallite
- 288 aste vinte su 300, zero rose incomplete, zero acquisti sopra il proprio
  limite in 6.900 chiamate
