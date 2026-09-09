# Portare FantaHacked su un altro computer

Provato davvero: la cartella minima qui sotto è stata copiata altrove e
lanciata in isolamento, con la cartella `database/` **vuota** a parte le
regole. Il programma è partito, ha scaricato i dati da solo in un quarto di
secondo, e ha cominciato a consigliare.

## Cosa serve sull'altro PC

**Niente da installare.** L'eseguibile si porta dentro Python. Serve Windows
con un browser fra Edge, Chrome o Brave — Edge c'è su ogni Windows 10 e 11, ed
è quello che apre la finestra dell'applicazione.

Serve **internet al primo avvio**, e solo al primo: da lì in poi i dati sono
sul disco e il programma funziona anche staccato dalla rete.

## La cartella minima — 22 MB

```
FantaHacked/
├── FantaHacked.exe
├── Avvia FantaHacked.bat        (comodo, non indispensabile)
├── Avvia FantaHacked.vbs        (lancia il .bat senza finestra nera)
├── app/
│   └── web/                     tutta la cartella: interfaccia
├── motore/
│   ├── schema_dati.sql          come è fatto il file dei dati
│   ├── schema_asta.sql          come è fatto il file dell'asta
│   └── preferenze.json          i nomi delle otto squadre
└── database/
    └── regole_lega.json         le regole della tua lega
```

Sono **196 KB** oltre all'eseguibile, e sono tutti file del programma: cambiano
quando cambia il programma, cioè quando ricopieresti comunque il `.exe`.

**I dati dei giocatori non ci sono, ed è voluto.** Al primo avvio il programma
li scarica da
[github.com/JDado02/DBFantaHacked](https://github.com/JDado02/DBFantaHacked):
mezzo mega, meno di un secondo. Da quel momento stanno in `database/dati.db`.

**L'interfaccia non è dentro l'eseguibile**: `app/web` viene letta dal disco a
ogni avvio. Se la dimentichi il programma parte e mostra una pagina vuota.

## Oppure: copia tutto e basta

Funziona anche quello, e resta la via più svelta se hai già la cartella intera
sotto mano: chiavetta, copia, doppio clic. Non c'è niente da togliere.

> **Nota di una correzione.** In una versione precedente di questo foglio
> c'era scritto di escludere `fanta.lock` e `fanta.porta` dalla copia. È stato
> provato apposta con una copia "sporca", quei due file compresi: sono
> **innocui**, il programma li riscrive all'avvio. L'indicazione era sbagliata.

## Aggiornare i dati senza ricopiare niente

È il motivo per cui i file sono due.

**`database/dati.db`** — listone, statistiche, gerarchie, proiezioni. Sola
lettura, uguale per tutti, si riscarica. Ogni volta che apri il programma,
questo chiede online se ce n'è una versione più recente: legge un file da due
kilobyte, e scarica il mezzo mega solo se la data è cambiata.

**`motore/asta.db`** — chi ha comprato chi e a quanto. Resta **sul dispositivo
che sta giocando l'asta**, sempre. Non si sincronizza, non si condivide, non
esce da lì.

Quindi puoi aggiornare i dati il giorno prima e ritrovarteli su qualunque
computer, senza spostare cartelle e senza toccare niente dell'asta.

### Quando internet non c'è

Non succede niente: il programma parte con i dati che ha già e scrive di
quando sono. L'attesa massima sulla rete è di sei secondi, e non blocca mai
l'avvio. Nella stanza dell'asta il wifi fa quello che vuole, e un assistente
che non si apre sarebbe peggio di uno con i dati di tre giorni prima.

### Come si pubblicano dati nuovi

Dal computer dove aggiorni le fonti:

```bash
cd "C:\Users\Davide\Desktop\Software fantacalcio" && python database/pipeline/pubblica.py --pubblica
```

Costruisce il pacchetto, lo comprime, scrive il manifest e lo manda su GitHub.
Se i dati sono identici a quelli già pubblicati non fa niente e te lo dice.

Dopo aver pubblicato, GitHub tiene i file in cache **cinque minuti**: un
programma acceso in quel momento può vedere ancora i dati di prima. Basta
riaprirlo poco dopo.

## Se un giorno cambia il formato dei dati

Il pacchetto porta un numero di versione. Se scarichi dati costruiti da una
versione più recente del programma, quello **si rifiuta di aprirli** e ti dice
di aggiornare FantaHacked, invece di aprirli a metà e rompersi durante l'asta.
Al contrario, dati più vecchi vengono riparati da soli.

## Se cambi le regole della lega

`database/regole_lega.json` non viene mai sovrascritto da un aggiornamento: è
tuo. E se lo modifichi, al primo avvio successivo il programma **rifà le
proiezioni** sul tuo regolamento — se ne accorge da solo, e ci mette due
secondi. Prima non lo faceva, e chi correggeva quel file continuava a vedere i
numeri di prima senza che niente glielo dicesse.
