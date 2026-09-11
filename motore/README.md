# Motore di valutazione

Nucleo di calcolo dell'assistente d'asta. Nessuna dipendenza esterna: solo la
libreria standard di Python 3.8+. Non ha interfaccia: è il pezzo che l'app
userà, ed è testabile da solo.

## Avvio

```bash
python db.py            # crea fanta.db dai CSV in ../database
python proiezioni.py    # calcola i punti attesi
python test_motore.py   # 24 verifiche
python demo.py          # listone valutato + simulazione di una chiamata
```

## Moduli

| File | Ruolo |
|---|---|
| `schema_dati.sql` | Schema del file che si scarica: anagrafica, statistiche, proiezioni |
| `schema_asta.sql` | Schema del file che resta locale: asta, presidenti, acquisti |
| `aggiornamento.py` | Scarica i dati pubblicati e rifa' le proiezioni se il regolamento e' cambiato |
| `db.py` | Creazione database e caricamento dei CSV |
| `regole.py` | Lettura e **validazione** di `regole_lega.json` |
| `proiezioni.py` | Da statistiche storiche a punti attesi |
| `modificatore.py` | Bonus atteso del modificatore di difesa |
| `formazione.py` | Quante caselle della formazione si riempiono davvero ogni giornata |
| `asta.py` | Stato dell'asta: acquisti, crediti, slot, annullamento |
| `valutazione.py` | VOR, prezzo di mercato, concorrenti, chiusura attesa |

---

## Come si arriva al prezzo

### 1. Punti attesi (`proiezioni.py`)

Media pesata delle ultime stagioni (peso 1.00 / 0.55 / 0.30), regressa verso la
media di ruolo in proporzione al campione disponibile. I gol si stimano dagli
**xG**, non dai gol segnati: i gol sono rumorosi, gli xG molto meno. I rigori si
contano a parte, perché npxG li esclude per costruzione.

Tutti i parametri — medie di ruolo, tassi per 90', conversione rigori, forza
difensiva delle squadre — si **auto-calibrano dal database** a ogni esecuzione.
Nessuna costante da ritoccare l'anno prossimo.

Chi non ha storico di Serie A (neopromosse, arrivi dall'estero: il 25,5%) viene
imputato da una regressione sulla quotazione, ed è marcato
`metodo = imputato_da_quotazione` con `affidabilita = 0`. L'interfaccia deve
mostrarlo: sono le stime da prendere con le pinze.

### 2. Valore rispetto al rimpiazzo (`valutazione.py`)

```
valore = presenze_attese × (fantamedia − fantamedia_rimpiazzo) + contributo_modificatore
```

Il confronto è sulla **fantamedia**, non sui punti stagionali. Ogni giornata
schieri undici giocatori: conta quanto uno rende rispetto a chi metteresti al
suo posto, moltiplicato per quante volte puoi schierarlo.

> Confrontare i totali di stagione premia chi gioca sempre a prescindere da come
> rende. Nella prima versione questo sopravvalutava pesantemente i portieri:
> Falcone risultava da 58 crediti contro gli 8 realmente pagati sul mercato.

Il livello di rimpiazzo è l'ultimo slot di rosa che verrà assegnato in lega
(`partecipanti × slot_ruolo`), stimato con una **media locale** su cinque
giocatori attorno alla linea — le fantamedie si accavallano a decimi di punto e
sulla linea capita un fondo-rosa con poche presenze e media gonfiata.

Il livello si **ricalcola a ogni acquisto** sui soli giocatori ancora liberi.
Due proprietà, entrambe verificate nei test:

- comprare dall'alto **non muove** il rimpiazzo: si consuma un giocatore e uno slot
- uno slot speso **sotto** la linea lo **alza**: un posto in meno per chi era sopra

### 2b. Quante caselle riempi davvero (`formazione.py`)

Il valore qui sopra è lineare nelle presenze, e sui punti del singolo è
giusto. Restano fuori due cose, e decidono la stagione:

- **la panchina non entra nel totale.** Sommando i migliori per reparto, il
  quinto e il sesto difensore valgono zero. Ma giocano, e i punti li fanno —
  tanti di più quanto più i titolari saltano.
- **le caselle che non si riempiono valgono zero, non poco.** Quattro
  difensori da diciotto presenze e nessun altro coprono meno di due caselle su
  quattro: le altre due sono giornate giocate in dieci.

`formazione.py` calcola l'una e l'altra in modo esatto: ogni giocatore prende
voto con probabilità pari alle sue presenze attese diviso trentotto, il numero
di disponibili di un reparto è una Poisson-binomiale, e da lì escono
`posti_coperti` (quante caselle si riempiono) e `guadagno` (quante ne aggiunge
un giocatore in più). Nessuna soglia scelta a mano.

Da qui la regola che il pannello dei consigli segue durante l'asta: **finché il
nucleo che scende in campo non è coperto, chi gioca viene prima di chi
conviene.** Non perché il giocatore a mezzo servizio valga meno di quello che
rende, ma perché finché il nucleo non c'è non ha nessuno dietro a coprirlo.

Misurato su 400 aste giocate seguendo il pannello, con gli stessi semi nelle
due varianti: 389 vittorie contro 371, **+11 punti di stagione in media**
(t = 5,5) e sette centesimi di giornata in meno passati a schierare in dieci.

### 3. Prezzo di mercato

```
D = crediti_residui_lega − slot_residui_lega     (pool discrezionale)
V = somma dei VOR sui giocatori che entreranno in rosa
prezzo(g) = 1 + VOR(g) / V × D
```

La proprietà che lo rende affidabile: **la somma dei prezzi consigliati è
esattamente uguale ai crediti ancora in mano alla lega**. Il mercato si chiude
per costruzione, e non c'è nessuna costante da tarare.

Ne segue l'auto-correzione: se la stanza brucia i crediti presto, `D` cala più
in fretta di `V` e i prezzi successivi scendono. L'indicatore `inflazione`
espone il rapporto rispetto all'inizio dell'asta.

---

## Il modificatore di difesa

Il regolamento lo definisce a gradini sulla media dei voti di portiere e tre
migliori difensori. Ma quella media si calcola **ogni giornata**, e i voti
oscillano: una difesa da 6,24 di media supera comunque la soglia dei 6,25 in
circa metà delle giornate.

Il bonus atteso non è quindi `bonus(media)`, ma il valore atteso della funzione
a gradini rispetto al rumore giornaliero. Integrando, la funzione diventa liscia
e crescente, e ogni decimo di media voto acquista valore — il che rende
calcolabile il valore marginale di un difensore.

| media attesa | a gradini | atteso | punti stagione |
|---|---|---|---|
| 6,00 | +1 | 0,80 | 30 |
| 6,20 | +1 | 1,43 | 54 |
| 6,25 | +2 | 1,61 | 61 |
| 6,40 | +2 | 2,21 | 84 |

**Nota sulla scala di questa lega:** sembra generosa (fino a +6), ma le fasce
alte sono di fatto irraggiungibili. Prendendo il miglior portiere e i tre
migliori difensori della Serie A la media dei quattro è 6,40, cioè +2.
Realisticamente si oscilla tra +1 e +2.

Assunzione dichiarata: la deviazione standard di un singolo voto è circa 0,65,
quindi 0,325 sulla media di quattro. Non è ricavabile dal database, che contiene
medie stagionali e non voti partita per partita. È esposta come parametro in
`modificatore.py`.

### Perché rompe l'additività

Il valore di un difensore dipende dagli **altri** difensori della rosa: il
quarto non tocca la media, il primo sì. Qui è approssimato come contributo
marginale su una difesa di riferimento, con un peso di inclusione che vale 1 per
chi rientra nei posti utili di lega e scende a zero sull'ultimo assegnato.

Il valore esatto per la propria rosa lo calcolerà l'ottimizzatore, che è il
prossimo pezzo da costruire.

---

## Stato dell'asta

Il registro degli acquisti è la **sorgente unica di verità**: crediti e slot non
sono mai memorizzati, si ricavano sempre dal registro. L'annullamento è quindi
esatto per costruzione e non può lasciare lo stato incoerente — il difetto che
il foglio Excel di partenza aveva.

`liquidita()` è il massimo che un presidente può offrire restando in grado di
riempire la rosa: tiene almeno 1 credito per ogni slot che resterà scoperto. È
il calcolo che impedisce di arrivare agli ultimi tre attaccanti con 4 crediti.

`concorrenti()` esclude chi ha il reparto pieno, **per quanti crediti abbia**.
È il vantaggio informativo più concreto del software: sapere che su un difensore
possono ancora rilanciare solo due avversari cambia il modo di fare le offerte.

---

## Quello che ancora manca

- **Ottimizzatore di rosa** e `max_bid` esatto: `OPT(con il giocatore) − OPT(senza)`
- **Aggressività appresa** degli avversari dagli scarti fra prezzo pagato e prezzo di mercato
- **Interfaccia**: il motore è pronto, l'app no
- **`titolarita`**: il campo è vuoto in `contesto.csv` (nessuna fonte strutturata).
  Finché resta vuoto, il modello si basa sui minuti storici e sovrastima chi ha
  giocato molto ma ha perso il posto. Compilarlo è il singolo intervento con più
  resa sulla qualità dei prezzi.

## Verifiche automatiche

`test_motore.py` copre 24 proprietà: chiusura del mercato, livelli di rimpiazzo,
vincoli di acquisto, annullamento, reazione ai prezzi pagati, saturazione dei
ruoli, e una simulazione completa di 200 assegnazioni con controllo che nessuna
rosa sfori il budget e che tutte si chiudano complete.
