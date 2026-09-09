# -*- coding: utf-8 -*-
"""Chi gioca davvero: il posto in gerarchia, non la fantamedia.

E' il buco piu' grande che il database aveva. Le proiezioni sanno quanto rende
un giocatore quando gioca, ma non sanno **quante volte scendera' in campo
quest'anno**: quella informazione sta negli allenamenti e nelle conferenze
stampa, non nelle statistiche dell'anno scorso. Il risultato e' l'errore piu'
costoso che si possa fare in asta: comprare una fantamedia alta prodotta da
sette presenze.

Qui l'informazione si ricava dall'unica cosa che il database sa davvero: i
minuti. Non i minuti del singolo, che dicono poco, ma **i minuti del suo
reparto**. In una squadra di serie A i posti in difesa sono quelli che sono: se
le proiezioni promettono ai dieci difensori della Roma il 49% di minuti in piu'
di quanti ne esistano, qualcuno quei minuti non li giochera'. E non sara' il
primo della gerarchia: sara' l'ultimo.

Tre passaggi:

  1. **Quanti minuti esistono.** Non si assume un modulo: la capienza di un
     reparto e' la mediana di quel reparto su tutte e venti le squadre. Cosi'
     una squadra che gioca con una punta sola non viene forzata a due, e una
     con tre difensori centrali non viene gonfiata a quattro. E' il campionato
     a dire quanto e' grande un reparto, non io.

  2. **L'eccedenza si toglie dal fondo.** Se un reparto promette piu' minuti di
     quanti ne esistano, il taglio parte dall'ultimo della gerarchia e risale.
     Toglierlo in proporzione sarebbe sbagliato due volte: punirebbe il
     titolare, che gioca comunque, e salverebbe la riserva, che e' proprio
     quella che non giochera'.

  3. **Nessuno viene gonfiato.** Un reparto che promette meno minuti della
     mediana non e' un errore da correggere: e' una squadra che gioca con meno
     giocatori in quel ruolo, o che ha meno rosa a listone. Inventare minuti
     sarebbe peggio che non correggere niente.

La gerarchia dentro il reparto non la decidono i soli minuti. I minuti sanno
com'e' andata l'anno scorso; il prezzo pagato in asta negli anni scorsi sa cosa
si aspetta la gente per quest'anno, e sull'undici titolare la sala di solito ci
prende. I due segnali si mescolano: e' l'ordine risultante a dire chi, in un
reparto sovraffollato, i minuti li perdera'.

Quello che ne esce, per ogni giocatore:

    quota      0..1   la quota di stagione in cui ci si aspetta prenda voto
    posto      1..n   il suo posto nella gerarchia del reparto della sua squadra
    grado             titolare / ballottaggio / rotazione / riserva
    certezza   0..1   quanto e' solido quel giudizio
    sicuro     bool   titolare con poco margine di dubbio: e' il filtro che
                      serve quando si cerca l'alternativa a un big

La quota si misura sulle **presenze**, non sui minuti. Nel fantacalcio conta
prendere il voto, e chi entra al 60' il voto lo prende: un attaccante che parte
titolare trenta volte e viene sempre sostituito ha il 60% dei minuti ma il 79%
delle presenze, ed e' un titolare a tutti gli effetti. Misurarlo sui minuti lo
farebbe passare per un uomo in ballottaggio.
"""
import collections, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

GIORNATE = 38
MINUTI_STAGIONE = GIORNATE * 90

# Posti nell'undici tipo, per ruolo del listone. Servono solo come misura di
# scala: la capienza vera di ogni reparto la fissa la mediana della lega.
POSTI = {'P': 1.0, 'D': 4.0, 'C': 4.0, 'A': 2.0}

# Soglie sulla quota di presenze. 0.72 sono 27 partite con voto: sotto, un
# posto da titolare non e' garantito.
SOGLIA_TITOLARE = 0.72
SOGLIA_BALLOTTAGGIO = 0.50
SOGLIA_ROTAZIONE = 0.28

# Quanto ci si deve allontanare da una soglia perche' il giudizio sia solido.
# 0.12 sono quattro partite e mezzo: meno di cosi', il grado potrebbe
# ribaltarsi per un infortunio o un cambio di modulo.
MARGINE_PIENO = 0.12

# Quanto pesa il mercato nel decidere l'ordine dentro un reparto. I minuti
# dicono com'e' andata, il prezzo d'asta dice cosa ci si aspetta adesso.
PESO_MERCATO = 0.35

# Quanto pesa il consenso delle guide, quando c'e'. Domina, ed e' giusto:
# minuti e prezzi sono indizi indiretti su chi giochera', le guide lo dicono
# e basta. Restano indizi utili dove le guide tacciono.
PESO_CONSENSO = 0.60

# Un titolare si considera "sicuro" da qui in su. Sotto, e' un'ipotesi.
CERTEZZA_SICURO = 0.55

GRADI = ('titolare', 'ballottaggio', 'rotazione', 'riserva')

ETICHETTA = {'titolare': 'Titolare', 'ballottaggio': 'Ballottaggio',
             'rotazione': 'Rotazione', 'riserva': 'Riserva'}


class Posizione(object):
    """Il verdetto su un giocatore. Leggibile e senza sorprese."""
    __slots__ = ('id', 'quota', 'minuti', 'presenze', 'posto', 'in_reparto',
                 'grado', 'certezza', 'sicuro', 'tagliato', 'affollamento')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    @property
    def etichetta(self):
        return ETICHETTA[self.grado]

    def __repr__(self):
        return '<%s %s %.2f (%d/%d) cert %.2f>' % (
            self.id, self.grado, self.quota, self.posto, self.in_reparto,
            self.certezza)


def _mediana(valori):
    v = sorted(valori)
    if not v:
        return 0.0
    n = len(v)
    return v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])


def capienze(giocatori):
    """Quanti minuti ha da distribuire un reparto, per ciascun ruolo.

    `giocatori` e' un elenco di dizionari con squadra, ruolo, minuti.
    """
    somme = collections.defaultdict(float)
    squadre = collections.defaultdict(set)
    for g in giocatori:
        somme[(g['squadra'], g['ruolo'])] += max(0.0, g['minuti'] or 0.0)
        squadre[g['ruolo']].add(g['squadra'])
    out = {}
    for ruolo, elenco in squadre.items():
        valori = [somme[(s, ruolo)] for s in elenco]
        med = _mediana(valori)
        # La mediana e' la misura di riferimento, ma non puo' scendere sotto
        # il minimo tecnico: i posti dell'undici tipo esistono comunque.
        out[ruolo] = max(med, POSTI.get(ruolo, 1.0) * MINUTI_STAGIONE * 0.55)
    return out


def _ordine_reparto(elenco):
    """L'ordine gerarchico dentro un reparto.

    Tre segnali, in ordine di autorevolezza: quello che dicono le guide di
    quest'anno, i minuti dell'anno scorso, il prezzo che il mercato gli da'.
    Le guide vincono quando ci sono, perche' sono le uniche che parlano della
    stagione che deve cominciare; le altre due restano a dire la loro dove le
    guide tacciono, che e' meta' del listone.
    """
    max_min = max([g.get('minuti') or 0.0 for g in elenco] or [0.0]) or 1.0
    max_mer = max([g.get('mercato') or 0.0 for g in elenco] or [0.0])
    ha_mercato = max_mer > 0
    ha_web = any(g.get('titolarita_web') is not None for g in elenco)

    def punteggio(g):
        m = (g.get('minuti') or 0.0) / max_min
        q = ((g.get('mercato') or 0.0) / max_mer) if ha_mercato else 0.0
        peso_m = PESO_MERCATO if ha_mercato else 0.0
        base = (1.0 - peso_m) * m + peso_m * q
        if not ha_web:
            return base
        w = g.get('titolarita_web')
        if w is None:
            # In un reparto dove le guide hanno parlato, non essere nominati
            # e' esso stesso un'informazione: si resta dietro a chi lo e'.
            w = 0.0
        return (1.0 - PESO_CONSENSO) * base + PESO_CONSENSO * w

    return sorted(elenco, key=lambda g: -punteggio(g))


def calcola(giocatori):
    """Da minuti attesi grezzi a gerarchia di reparto.

    `giocatori`: elenco di dizionari con id, squadra, ruolo, minuti, presenze,
    affidabilita (0..1), nuovo (bool), mercato (prezzo d'asta di riferimento,
    facoltativo). Restituisce {id: Posizione}.
    """
    cap = capienze(giocatori)
    per_reparto = collections.defaultdict(list)
    for g in giocatori:
        per_reparto[(g['squadra'], g['ruolo'])].append(g)

    out = {}
    for (squadra, ruolo), elenco in per_reparto.items():
        capienza = cap.get(ruolo, POSTI.get(ruolo, 1.0) * MINUTI_STAGIONE)
        elenco = _ordine_reparto(elenco)
        minuti = [max(0.0, g.get('minuti') or 0.0) for g in elenco]
        somma = sum(minuti)
        affollamento = (somma / capienza) if capienza > 0 else 1.0

        # --- il taglio, dal fondo della gerarchia in su ------------------
        eccesso = max(0.0, somma - capienza)
        tagliati = [0.0] * len(minuti)
        i = len(minuti) - 1
        while eccesso > 1e-6 and i >= 0:
            # Nessuno scende sotto un quarto dei minuti che aveva: il taglio
            # dice "giochera' meno", non "sparira' dai campi".
            quanto = min(minuti[i] * 0.75, eccesso)
            minuti[i] -= quanto
            tagliati[i] = quanto
            eccesso -= quanto
            i -= 1
        if eccesso > 1e-6 and sum(minuti) > 0:
            # Reparto talmente affollato che nemmeno tagliando il 75% a tutti
            # si rientra: si scala quel che resta in proporzione.
            k = max(0.0, 1.0 - eccesso / sum(minuti))
            minuti = [m * k for m in minuti]

        # Il taglio si decide sull'ordine gerarchico; il posto che si mostra e'
        # invece quello che ne risulta, in presenze. Sono la stessa cosa per
        # chi il taglio l'ha subito, e mostrare il secondo evita di scrivere
        # "terzo del reparto" accanto a chi gioca piu' di tutti.
        finali = []
        for indice, (g, m) in enumerate(zip(elenco, minuti)):
            prima = max(0.0, g.get('minuti') or 0.0)
            k = (m / prima) if prima > 0 else 1.0
            presenze = min(float(GIORNATE), max(0.0, g.get('presenze') or 0.0) * k)
            finali.append((g, m, presenze, tagliati[indice]))
        finali.sort(key=lambda t: -t[2])
        quote = [min(1.0, t[2] / float(GIORNATE)) for t in finali]

        for posto, (g, m, presenze, tagliato) in enumerate(finali, start=1):
            quota = quote[posto - 1]
            # Chi gli sta dietro: e' lui a prendergli il posto se lo perde, ed
            # e' la distanza da lui a dire quanto quel posto e' saldo.
            stacco = quota - (quote[posto] if posto < len(quote) else 0.0)
            grado = _grado(ruolo, quota, posto)
            out[g['id']] = Posizione(
                id=g['id'], quota=quota, minuti=m, presenze=presenze, posto=posto,
                in_reparto=len(finali), grado=grado,
                certezza=_certezza(quota, g, posto, ruolo, grado, stacco),
                sicuro=False, tagliato=tagliato, affollamento=affollamento)

    for p in out.values():
        p.sicuro = (p.grado == 'titolare' and p.certezza >= CERTEZZA_SICURO)
    return out


def _grado(ruolo, quota, posto):
    if ruolo == 'P':
        # Il portiere e' un caso a se': o gioca lui o non gioca. Non esiste il
        # portiere che fa mezza stagione perche' e' in ballottaggio, e infatti
        # chi va in panchina non prende voto.
        if posto == 1 and quota >= 0.45:
            return 'titolare'
        if posto == 1:
            return 'ballottaggio'
        return 'riserva'
    if quota >= SOGLIA_TITOLARE:
        return 'titolare'
    if quota >= SOGLIA_BALLOTTAGGIO:
        return 'ballottaggio'
    if quota >= SOGLIA_ROTAZIONE:
        return 'rotazione'
    return 'riserva'


def _margine(quota, grado):
    """Di quanto la quota supera il confine che gli ha assegnato quel grado.

    Un titolare a 27 partite esatte e un titolare a 35 non meritano lo stesso
    credito: il primo scivola nel grado sotto per un infortunio, il secondo no.
    """
    if grado == 'titolare':
        return quota - SOGLIA_TITOLARE
    if grado == 'riserva':
        return SOGLIA_ROTAZIONE - quota
    if grado == 'ballottaggio':
        return min(quota - SOGLIA_BALLOTTAGGIO, SOGLIA_TITOLARE - quota)
    return min(quota - SOGLIA_ROTAZIONE, SOGLIA_BALLOTTAGGIO - quota)


def _certezza(quota, g, posto, ruolo, grado, stacco=0.0):
    """Quanto e' solido il giudizio, fra 0 e 1.

    Tre cose lo rendono fragile: una quota appoggiata al confine fra due gradi,
    poco campione alle spalle della proiezione, e l'essere appena arrivato in
    una squadra nuova, dove lo storico dice poco di dove giochera'.
    """
    base = max(0.0, min(1.0, _margine(quota, grado) / MARGINE_PIENO))
    if ruolo == 'P' and posto == 1:
        # Il portiere non ha soglie: il posto e' suo o non lo e'. Quello che
        # conta e' quanto stacca il secondo, ed e' l'indicazione piu'
        # affidabile che ci sia in tutto il listone.
        base = max(base, min(1.0, stacco / 0.25))
    # Cinque guide che dicono la stessa cosa valgono piu' di qualunque
    # margine calcolato: quando sono unanimi il dubbio non e' nostro.
    accordo = g.get('accordo')
    if accordo is not None and (g.get('fonti_web') or 0) > 0:
        base = max(base, float(accordo))
    campione = 0.60 + 0.40 * max(0.0, min(1.0, g.get('affidabilita') or 0.0))
    novita = 0.78 if g.get('nuovo') else 1.0
    return round(max(0.0, min(1.0, base * campione * novita)), 3)


# ------------------------------------------------------------------ database
def dal_database(con):
    """Legge quel che serve dal database e restituisce {id: Posizione}."""
    righe = []
    for r in con.execute("""
            SELECT g.id, g.squadra, g.ruolo,
                   COALESCE(g.nuovo_acquisto, 0) nuovo,
                   p.minuti_attesi, p.presenze_attese, p.affidabilita,
                   ge.titolarita, ge.accordo, ge.fonti,
                   pa.prezzo_medio_per_1000
            FROM giocatori g
            LEFT JOIN proiezioni p ON p.id = g.id
            LEFT JOIN gerarchie ge ON ge.id = g.id
            LEFT JOIN prezzi_asta pa ON pa.id = g.id
            WHERE g.attivo = 1"""):
        righe.append({'id': r['id'], 'squadra': r['squadra'], 'ruolo': r['ruolo'],
                      'minuti': r['minuti_attesi'] or 0.0,
                      'presenze': r['presenze_attese'] or 0.0,
                      'affidabilita': r['affidabilita'] or 0.0,
                      'mercato': r['prezzo_medio_per_1000'] or 0.0,
                      'titolarita_web': r['titolarita'],
                      'accordo': r['accordo'], 'fonti_web': r['fonti'],
                      'nuovo': bool(r['nuovo'])})
    return calcola(righe)


if __name__ == '__main__':
    import db as dbmod
    con = dbmod.connetti()
    pos = dal_database(con)
    nomi = dict((r['id'], (r['nome'], r['squadra'], r['ruolo']))
                for r in con.execute('SELECT id, nome, squadra, ruolo FROM giocatori'))
    conta = collections.Counter(p.grado for p in pos.values())
    print('Gerarchia calcolata su %d giocatori: %s' % (len(pos), dict(conta)))
    print('  titolari con poco dubbio: %d' % sum(1 for p in pos.values() if p.sicuro))
    for ruolo in ('P', 'D', 'C', 'A'):
        elenco = [(p, nomi[p.id]) for p in pos.values()
                  if nomi.get(p.id) and nomi[p.id][2] == ruolo]
        elenco.sort(key=lambda t: -(t[0].quota * t[0].certezza))
        print('\n-- %s : i piu\' sicuri --' % ruolo)
        for p, (nome, sq, _) in elenco[:6]:
            print('   %-18s %-11s quota %.2f  posto %d/%d  %-13s cert %.2f'
                  % (nome[:18], sq[:11], p.quota, p.posto, p.in_reparto,
                     p.etichetta, p.certezza))
        dubbi = [t for t in elenco
                 if t[0].posto <= POSTI[ruolo] and t[0].certezza < 0.5]
        if dubbi:
            print('   -- primi del reparto, ma con poca certezza --')
            for p, (nome, sq, _) in dubbi[:4]:
                print('   %-18s %-11s quota %.2f  posto %d/%d  %-13s cert %.2f'
                      % (nome[:18], sq[:11], p.quota, p.posto, p.in_reparto,
                         p.etichetta, p.certezza))
    con.close()
