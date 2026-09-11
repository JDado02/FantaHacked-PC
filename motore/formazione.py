# -*- coding: utf-8 -*-
"""Quante caselle della formazione riesci davvero a riempire ogni giornata.

E' la domanda che mancava a tutto il resto del motore, e che decide piu' di
ogni altra come va la stagione.

La rosa ha otto difensori, ma in campo ne vanno quattro **ogni domenica**.

Fin qui il valore di un giocatore era `presenze x (fantamedia meno il
rimpiazzo)`, e il punteggio di una rosa la somma dei migliori per reparto. Vale
la pena essere precisi su cosa sbaglia quel conto, perche' non e' quello che
sembra a prima vista: sui punti del singolo e' giusto, e infatti misurando si
scopre che un giocatore discontinuo con fantamedia alta **non vale meno** dei
suoi punti, se dietro c'e' una panchina che copre le giornate in cui manca.

Quello che quel conto non vede sono due cose, e sono tutte e due decisive:

  - **la panchina non entra mai nel totale.** Sommando i quattro migliori, il
    quinto e il sesto difensore valgono zero. Ma giocano, e i punti li fanno:
    tanti di piu' quanto piu' i titolari saltano. E' la voce che manca, non
    una correzione a quelle che ci sono;
  - **le caselle che non si riempiono valgono zero, non poco.** Un reparto di
    quattro che giocano meta' campionato e nessun altro copre meno di due
    caselle su quattro: le altre due sono giornate giocate in dieci, e il
    conto lineare le contava come se qualcuno le riempisse sempre.

Da cui la regola che il programma segue durante l'asta: prima il nucleo che
scende in campo, poi &mdash; e solo poi &mdash; gli affari. Non perche' il
giocatore a mezzo servizio valga meno di quello che rende, ma perche' finche'
il nucleo non c'e' non ha nessuno dietro a coprirlo.

Qui si calcola invece la cosa esatta. Ogni giocatore prende voto in una
giornata qualunque con probabilita' pari alle sue presenze attese diviso
trentotto. Il numero di disponibili di un reparto e' allora una somma di
variabili di Bernoulli **diverse fra loro** &mdash; una Poisson-binomiale
&mdash; e la sua distribuzione si costruisce esattamente con una convoluzione,
un giocatore alla volta. Da li' escono i due numeri che servono:

  - `posti_coperti` : quante delle caselle in campo si riempiono in media;
  - `guadagno`      : quante ne aggiunge un giocatore in piu'.

Nessuna soglia, nessuna etichetta, nessun numero scelto a mano: si usano le
presenze attese, che sono gia' quello che il motore sa dire meglio.

Il conto e' ottimista in un punto, e va detto: le assenze si trattano come
indipendenti, mentre nella realta' sono correlate (turno infrasettimanale,
sosta, squalifiche di squadra). Il rischio vero e' quindi un po' piu' alto di
questo, mai piu' basso: quello che si legge qui e' un limite superiore alla
copertura, e usarlo per scegliere sbaglia sempre dalla parte prudente.
"""

GIORNATE = 38.0

# Quanti giocatori di ogni reparto scendono in campo ogni giornata: e' la
# formazione, non la rosa. Uno, quattro, quattro e due fanno undici, ed e' lo
# stesso `TITOLARI` che l'ottimizzatore usa da sempre per pesare la panchina:
# lo stesso concetto deve avere un numero solo in tutto il programma.
IN_CAMPO = {'P': 1, 'D': 4, 'C': 4, 'A': 2}


def quota(x):
    """Con che probabilita' prende voto in una giornata qualunque."""
    q = getattr(x, 'titolarita', None)
    if q is None:
        q = (getattr(x, 'presenze', 0) or 0) / GIORNATE
    return min(1.0, max(0.0, float(q)))


def distribuzione(quote):
    """Quanti ne saranno disponibili: la distribuzione esatta.

    Convoluzione una Bernoulli alla volta. Con otto giocatori sono sessanta
    moltiplicazioni: il costo non e' un argomento contro il conto esatto.
    """
    dist = [1.0]
    for q in quote:
        q = min(1.0, max(0.0, q))
        nuovo = [0.0] * (len(dist) + 1)
        for k, p in enumerate(dist):
            if p <= 0.0:
                continue
            nuovo[k] += p * (1.0 - q)
            nuovo[k + 1] += p * q
        dist = nuovo
    return dist


def posti_coperti(quote, in_campo):
    """Quante delle `in_campo` caselle si riempiono in media, ogni giornata.

    E' `E[min(in_campo, disponibili)]`. Cresce con il numero di giocatori e
    con quanto giocano, e si ferma da sola a `in_campo`: il quinto difensore
    aggiunge poco, il nono niente. E' la forma giusta del rendimento
    decrescente della panchina, ed e' un teorema, non una curva scelta.
    """
    if in_campo <= 0:
        return 0.0
    dist = distribuzione(quote)
    return sum(p * min(in_campo, k) for k, p in enumerate(dist) if p > 0.0)


def guadagno(quote, in_campo, nuova, riferimento=0.0):
    """Quante caselle in piu' riempie un giocatore con quota `nuova`.

    `riferimento` e' quanto giocherebbe il tappabuchi che prenderesti al suo
    posto: il paragone giusto non e' con lo slot vuoto &mdash; a fine asta un
    giocatore da un credito lo trovi sempre &mdash; ma con quello. A parita' di
    tutto il resto e' la differenza fra chi gioca e chi riempie.
    """
    base = posti_coperti(list(quote) + [riferimento], in_campo)
    dopo = posti_coperti(list(quote) + [nuova], in_campo)
    return max(0.0, dopo - base)


def punti_giornata(giocatori, in_campo):
    """Punti attesi in una giornata dai titolari di un reparto.

    `giocatori` e' una lista di coppie (fantamedia, quota). In una giornata
    scendono in campo i migliori **fra quelli che hanno preso voto**: quindi
    ognuno porta i suoi punti quando gioca *e* quando fra i piu' forti di lui
    ce ne sono meno di `in_campo` disponibili. Le caselle che nessuno riempie
    valgono zero, ed e' proprio quello che il conto lineare `presenze x
    fantamedia` non sapeva vedere.

    E' l'ordine statistico esatto, non una simulazione: la probabilita' che
    resti posto si legge dalla distribuzione dei disponibili fra i migliori.
    """
    ordinati = sorted(giocatori, key=lambda t: -(t[0] or 0.0))
    tot = 0.0
    sopra = []
    for fm, q in ordinati:
        dist = distribuzione(sopra)
        posto = sum(p for k, p in enumerate(dist) if k < in_campo)
        tot += (fm or 0.0) * min(1.0, max(0.0, q)) * posto
        sopra.append(q)
    return tot


def punti_stagione(rosa, in_campo=None):
    """Punti di stagione dell'undici **davvero schierabile**.

    `rosa` e' un dizionario ruolo -> lista di dizionari con `fm` e `presenze`.
    E' il metro con cui giudicare una rosa: quello di prima sommava i punti
    dei migliori per ruolo dando per scontato che giocassero sempre, e con
    quella lente una difesa di quattro giocatori da meta' campionato valeva
    quanto una di quattro titolari. Con questo no.
    """
    in_campo = in_campo or IN_CAMPO
    tot = 0.0
    for ruolo, quanti in in_campo.items():
        gi = [((g.get('fm') or 0.0),
               min(1.0, (g.get('presenze') or 0) / GIORNATE))
              for g in rosa.get(ruolo, [])]
        tot += punti_giornata(gi, quanti)
    return tot * GIORNATE


def relazione(quote, in_campo):
    """Una riga leggibile: coperti, mancanti, e con che probabilita' si buca."""
    dist = distribuzione(quote)
    coperti = posti_coperti(quote, in_campo)
    scoperto = sum(p for k, p in enumerate(dist) if k < in_campo)
    return {'coperti': coperti,
            'mancano': max(0.0, in_campo - coperti),
            'servono': in_campo,
            'rischio_buco': scoperto}


if __name__ == '__main__':
    print('Quattro difensori in campo. Quante caselle si riempiono:\n')
    casi = [
        ('quattro titolari da 30 presenze', [30, 30, 30, 30]),
        ('  + quattro riempitivi da 10',    [30, 30, 30, 30, 10, 10, 10, 10]),
        ('quattro da 18 presenze',          [18, 18, 18, 18]),
        ('  + quattro riempitivi da 10',    [18, 18, 18, 18, 10, 10, 10, 10]),
        ('due titolari e sei riempitivi',   [31, 30, 10, 10, 10, 10, 10, 10]),
        ('otto titolari da 30',             [30] * 8),
    ]
    for nome, presenze in casi:
        q = [p / GIORNATE for p in presenze]
        r = relazione(q, 4)
        print('  %-34s coperti %.2f su 4   giornate con un buco %4.1f%%'
              % (nome, r['coperti'], 100 * r['rischio_buco']))
