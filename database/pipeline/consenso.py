# -*- coding: utf-8 -*-
"""Dalle cinque guide raccolte dal web a una riga per giocatore.

Il problema che risolve non e' tecnico, e' di merito: **le guide non sono
d'accordo**. Sull'attacco del Bologna una dice Piccoli e un'altra Dovbyk; sul
Como una dice Kean e un'altra Douvikas; sul centrocampo del Milan dieci guide
mettono dieci nomi diversi su quattro maglie. Prendere la prima che capita
significa comprare la sua opinione senza saperlo.

Qui le opinioni si contano. Per ogni giocatore esce:

    titolarita   0..1   quota pesata delle fonti che lo mettono in campo
    accordo      0..1   quanto le fonti sono concordi su di lui
    ballottaggio chi si gioca il posto con lui, e con che percentuali
    rigorista    1/2/3  gerarchia dal dischetto, per maggioranza

Il peso delle fonti non e' uguale: le probabili formazioni della giornata
valgono il doppio di una guida d'agosto, perche' sono la formazione di domani
e non un'ipotesi di due settimane fa.

**Un nome si accetta solo se esiste nel listone con quella squadra.** E' il
controllo che rende sicuro tutto il resto: se una guida scrive "Pinamonti" fra
gli attaccanti del Sassuolo &mdash; ed e' successo davvero &mdash; l'abbinamento
fallisce e il nome finisce nelle lacune invece di inquinare i dati. Un
abbinamento sbagliato e' peggio di un abbinamento mancato.

Uso:  python consenso.py
"""
import collections, csv, os, sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
from nomi import norm, variants, split_fanta, combacia_iniziale

DATABASE = os.path.dirname(QUI)
WEB = os.path.join(DATABASE, 'fonti', 'web')

# Quante fonti servono perche' un'assenza voglia dire qualcosa. Se una squadra
# e' coperta da una guida sola, non essere nel suo undici non prova niente.
FONTI_MINIME = 3

# Il giorno in cui le pagine sono state lette. Serve a contare gli infortuni
# nel modo giusto: le giornate gia' giocate non le salta nessuno da qui in
# avanti, e includerle farebbe sembrare un affaticamento un crociato.
OGGI = '2026-09-07'

GIORNATE = 38

# Posti nell'undici tipo per ruolo del listone: servono a dire, dentro un
# reparto, chi era il titolare e chi no.
POSTI_TITOLARI = {'P': 1, 'D': 4, 'C': 4, 'A': 2}

# Un reparto entra nella misura solo se le presenze che ha totalizzato nella
# stagione stanno in piedi da sole: almeno l'85% delle partite che quel numero
# di maglie avrebbe dovuto coprire.
#
# **E' la riga che corregge l'errore piu' grosso che questo file abbia fatto.**
# Le costanti di prima (28 presenze per un portiere titolare) erano misurate
# sulla media di *tutti* i reparti, compresi quelli a cui manca meta' della
# stagione: il portiere che a gennaio e' andato all'estero esce dal listone, e
# con lui escono le sue venti partite, ma la squadra resta nel conto come se
# quelle partite non le avesse giocate nessuno. Sui portieri il danno era
# massimo, perche' la maglia e' una sola e basta un buco per dimezzare il
# reparto: la media scendeva da 35 a 26. Il software finiva per dire che un
# primo portiere gioca il 78% della stagione, che chiunque abbia visto una
# partita sa essere falso. Con il filtro, i venti reparti completi dicono
# 35.1 presenze di media e 37 di mediana: il portiere gioca sempre.
COMPLETEZZA_MINIMA = 0.85

# Valori di riserva, usati solo se `statistiche.csv` non c'e'. Sono quelli che
# la misura qui sotto restituisce sul campionato 2024-25 e 2025-26.
PRESENZE_TITOLARE = {'P': 35.1, 'D': 30.1, 'C': 30.2, 'A': 30.1}
PRESENZE_RISERVA = {'P': 2.0, 'D': 13.7, 'C': 14.5, 'A': 14.7}


def misura_presenze():
    """Quante partite gioca davvero un titolare, e quante chi titolare non e'.

    Non e' una costante scritta a tavolino: si conta sul campionato appena
    finito. Per ogni squadra e ruolo si ordina il reparto per presenze, si
    prendono i primi N (N = i posti dell'undici tipo) come titolari e tutti
    gli altri come alternative, e si fa la media delle due meta'.

    I reparti con i dati bucati vengono buttati via, vedi COMPLETEZZA_MINIMA.
    """
    percorso = os.path.join(DATABASE, 'statistiche.csv')
    if not os.path.exists(percorso):
        return dict(PRESENZE_TITOLARE), dict(PRESENZE_RISERVA)
    reparti = collections.defaultdict(list)
    for r in leggi(percorso):
        try:
            pg = float(r.get('pg') or 0)
        except ValueError:
            pg = 0.0
        reparti[(r.get('stagione'), r.get('squadra'), r.get('ruolo'))].append(pg)

    titolare, riserva = {}, {}
    for ruolo, posti in POSTI_TITOLARI.items():
        soglia = posti * GIORNATE * COMPLETEZZA_MINIMA
        tit, ris = [], []
        for (_, _, ru), presenze in reparti.items():
            if ru != ruolo or sum(presenze) < soglia:
                continue
            presenze.sort(reverse=True)
            tit.extend(presenze[:posti])
            ris.extend(presenze[posti:])
        titolare[ruolo] = (round(sum(tit) / len(tit), 1) if tit
                           else PRESENZE_TITOLARE[ruolo])
        riserva[ruolo] = (round(sum(ris) / len(ris), 1) if ris
                          else PRESENZE_RISERVA[ruolo])
    return titolare, riserva

# Quanto pesa il parere delle guide rispetto allo storico del giocatore.
# Alto per chi le guide nominano: sanno in che squadra gioca **adesso**, che e'
# esattamente cio' che lo storico non puo' sapere dopo un mercato. Piu' basso
# per chi non nominano: il silenzio e' un indizio, non una prova.
PESO_WEB_CITATO = 0.65
PESO_WEB_IGNORATO = 0.35


def leggi(percorso):
    with open(percorso, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------- listone
class Listone(object):
    """Il listone dell'utente, indicizzato per squadra e per nome.

    L'indice e' per squadra apposta: due Esposito, due Thuram e tre Martinez
    nello stesso campionato non sono un'ipotesi, sono la norma, e senza il
    vincolo di squadra si abbinerebbero a caso.
    """

    def __init__(self, percorso):
        self.righe = leggi(percorso)
        self.per_id = {}
        self.indice = collections.defaultdict(dict)   # squadra -> chiave -> [id]
        self.token = collections.defaultdict(dict)    # squadra -> token -> [id]
        for r in self.righe:
            if r.get('attivo') not in (None, '', '1'):
                continue
            ident = int(r['id'])
            self.per_id[ident] = r
            sq = r['squadra']
            for chiave in self._chiavi(r):
                self.indice[sq].setdefault(chiave, [])
                if ident not in self.indice[sq][chiave]:
                    self.indice[sq][chiave].append(ident)
            for t in self._token(r):
                self.token[sq].setdefault(t, [])
                if ident not in self.token[sq][t]:
                    self.token[sq][t].append(ident)

    @staticmethod
    def _token(r):
        """Le singole parole del nome, per i cognomi composti.

        Una guida scrive `Anguissa`, il listone `Zambo Anguissa`; un'altra
        scrive `Pedro Goncalves` dove il listone ha `Goncalves P.`. Sono la
        stessa persona, e il vincolo di squadra rende sicuro riconoscerlo per
        parola: due `Anguissa` nel Napoli non ci sono.
        """
        parole = set()
        cognome, _ = split_fanta(r['nome'])
        for testo in (cognome, r.get('nome_completo') or ''):
            for t in norm(testo).split():
                if len(t) >= 4:
                    parole.add(t)
        return parole

    @staticmethod
    def _chiavi(r):
        """Sotto quali forme quel giocatore puo' comparire in una guida."""
        chiavi = set()
        cognome, _ = split_fanta(r['nome'])
        chiavi |= variants(cognome)
        chiavi |= variants(r['nome'])
        completo = (r.get('nome_completo') or '').strip()
        if completo:
            toks = norm(completo).split()
            if toks:
                chiavi |= variants(toks[-1])
                if len(toks) >= 2:
                    chiavi |= variants(' '.join(toks[-2:]))
                chiavi |= variants(completo)
        return {c for c in chiavi if len(c) >= 3}

    def trova(self, squadra, nome, ruolo_atteso=None):
        """L'id di quel nome in quella squadra, o None se e' ambiguo o assente.

        `ruolo_atteso` serve per la maglia numero uno: `Martinez` nell'Inter
        sono due, il portiere e l'attaccante, e in prima posizione di una
        formazione c'e' sempre il portiere.
        """
        cognome, iniziali = split_fanta(nome)
        candidati = []
        for chiave in list(variants(nome)) + list(variants(cognome)):
            for ident in self.indice.get(squadra, {}).get(chiave, []):
                if ident not in candidati:
                    candidati.append(ident)
        if not candidati:
            # Nessun accordo esatto: si prova per parole, che e' come si
            # incontrano i cognomi composti scritti a meta'.
            # Si intersecano solo le parole che nel listone esistono: il nome
            # proprio che la guida aggiunge e il listone non riporta (`Pedro`
            # in `Pedro Goncalves`) non deve far fallire l'abbinamento, ma un
            # nome che punta a un'altra persona deve farlo fallire eccome.
            trovati = None
            for t in norm(cognome).split():
                if len(t) < 4:
                    continue
                ids = set(self.token.get(squadra, {}).get(t, []))
                if not ids:
                    continue
                trovati = ids if trovati is None else (trovati & ids)
            if trovati:
                candidati = sorted(trovati)
        if not candidati:
            return None, 'assente'
        if len(candidati) > 1 and ruolo_atteso:
            stretti = [i for i in candidati
                       if self.per_id[i]['ruolo'] == ruolo_atteso]
            if len(stretti) == 1:
                return stretti[0], 'ruolo'
            candidati = stretti or candidati
        if len(candidati) > 1 and iniziali:
            # Due strade per la stessa domanda: l'iniziale del nome proprio
            # (`Jo.` -> Josep) e, quando il nome proprio non lo sappiamo,
            # l'iniziale che il listone stesso porta dietro il cognome.
            # Serve dove la fonte statistica non arriva: `Oyono J.` non ha un
            # nome completo, ma si chiama gia' `J.` per conto suo.
            def _sua(i):
                r = self.per_id[i]
                completo = (r.get('nome_completo') or '').strip()
                if completo and combacia_iniziale(completo, iniziali):
                    return True
                _, sue = split_fanta(r['nome'])
                return bool(sue) and sue == iniziali
            stretti = [i for i in candidati if _sua(i)]
            if len(stretti) == 1:
                return stretti[0], 'iniziale'
            candidati = stretti or candidati
        if len(candidati) > 1:
            # Ambiguo dentro la stessa squadra: meglio perderlo che sbagliarlo.
            return None, 'ambiguo'
        return candidati[0], 'nome'


# ------------------------------------------------------------- consenso
def calcola():
    listone = Listone(os.path.join(DATABASE, 'giocatori.csv'))
    pesi = dict((r['fonte'], float(r['peso'])) for r in
                leggi(os.path.join(WEB, 'fonti.csv')))

    formazioni = leggi(os.path.join(WEB, 'formazioni_tipo.csv'))
    ballottaggi = leggi(os.path.join(WEB, 'ballottaggi.csv'))
    rigoristi = leggi(os.path.join(WEB, 'rigoristi.csv'))

    mancati = []

    def abbina(squadra, nome, fonte, dove, ruolo_atteso=None):
        ident, come = listone.trova(squadra, nome, ruolo_atteso)
        if ident is None:
            mancati.append({'fonte': fonte, 'dove': dove, 'squadra': squadra,
                            'nome': nome, 'motivo': come})
        return ident

    # --- chi mette chi in campo -------------------------------------------
    # copertura[squadra] = peso totale delle fonti che hanno detto la loro
    copertura = collections.defaultdict(float)
    fonti_per_squadra = collections.defaultdict(set)
    for r in formazioni:
        chiave = (r['fonte'], r['squadra'])
        if chiave not in fonti_per_squadra[r['squadra']]:
            fonti_per_squadra[r['squadra']].add(chiave)
            copertura[r['squadra']] += pesi.get(r['fonte'], 1.0)

    voti = collections.defaultdict(float)      # id -> peso di chi lo schiera
    schierato_da = collections.defaultdict(list)
    for r in formazioni:
        # Il ruolo, quando la fonte lo dichiara, e' quello che distingue i due
        # Martinez dell'Inter senza dover indovinare. Dove manca resta la
        # vecchia regola: in prima posizione c'e' il portiere.
        atteso = r.get('ruolo') or ('P' if r['posto'] == '1' else None)
        ident = abbina(r['squadra'], r['giocatore'], r['fonte'], 'formazione',
                       atteso)
        if ident is None:
            continue
        # Una fonte che dichiara **quanto** e' probabile che giochi vale
        # quella frazione, non un voto intero. Prima era tutto o niente:
        # Kean, dato in panchina al 60%, contava come uno che non gioca mai,
        # e il terzo portiere all'1% contava esattamente come lui. Adesso i
        # due si distinguono, ed e' la differenza fra una riserva vera e una
        # mezza maglia che a fine stagione vale una ventina di presenze.
        quanto = 1.0
        if r.get('pct') not in (None, ''):
            quanto = max(0.0, min(1.0, float(r['pct']) / 100.0))
        voti[ident] += pesi.get(r['fonte'], 1.0) * quanto
        if quanto > 0:
            schierato_da[ident].append(r['fonte'])

    # --- chi si gioca il posto con chi ------------------------------------
    coppie = collections.defaultdict(lambda: {'peso': 0.0, 'pct': [], 'fonti': []})
    for r in ballottaggi:
        a = abbina(r['squadra'], r['giocatore_a'], r['fonte'], 'ballottaggio')
        b = abbina(r['squadra'], r['giocatore_b'], r['fonte'], 'ballottaggio')
        if a is None or b is None or a == b:
            continue
        k = (min(a, b), max(a, b))
        d = coppie[k]
        d['peso'] += pesi.get(r['fonte'], 1.0)
        d['fonti'].append(r['fonte'])
        if r['pct_a'] and r['pct_b']:
            # Le percentuali vanno riportate all'ordine canonico della coppia.
            pa, pb = float(r['pct_a']), float(r['pct_b'])
            if a != k[0]:
                pa, pb = pb, pa
            d['pct'].append((pa, pb))

    # --- dal dischetto -----------------------------------------------------
    rig = collections.defaultdict(list)        # id -> [ordine, ...]
    for r in rigoristi:
        ident = abbina(r['squadra'], r['giocatore'], r['fonte'], 'rigorista')
        if ident is None:
            continue
        rig[ident].append(int(r['ordine']))

    # --- chi non e' nemmeno iscritto alla lista ---------------------------
    # Un infortunio toglie giornate; l'esclusione dalla lista le toglie
    # **tutte**. Sono due cose diverse e il programma ne conosceva una sola:
    # Milik, fuori lista alla Juventus, risultava con 0,91 presenze attese
    # invece che con zero, e a fine asta il motore arrivava a proporlo per un
    # credito - "meglio lui che una casella vuota". Ma uno che non puo'
    # scendere in campo **e'** una casella vuota.
    #
    # Il regolamento permette di correggere la lista una volta a stagione, per
    # due giocatori di movimento: non e' una condanna definitiva. Per un'asta
    # pero' l'attesa giusta e' zero, e se rientra si compra allora.
    fuori = set()
    for r in leggi(os.path.join(WEB, 'fuori_lista.csv')):
        ident = abbina(r['squadra'], r['giocatore'], 'liste-serie-a',
                       'fuori lista')
        if ident is not None:
            fuori.add(ident)

    # --- chi e' fermo, e per quanto ---------------------------------------
    fermi = {}
    partite = partite_per_squadra()
    for r in leggi(os.path.join(WEB, 'infortuni.csv')):
        ident = abbina(r['squadra'], r['giocatore'], 'fantacalcio.it-infortuni',
                       'infortunio')
        if ident is None:
            continue
        rientro = r['rientro_stimato']
        # Solo le partite che deve ancora giocare: quelle gia' disputate le
        # ha perse chiunque, e contarle farebbe sembrare un affaticamento
        # muscolare grave quanto un crociato.
        saltate = sum(1 for d in partite.get(r['squadra'], [])
                      if OGGI <= d < rientro) if rientro else 0
        fermi[ident] = {'problema': r['problema'], 'rientro': rientro,
                        'saltate': saltate, 'testo': r['rientro_testo']}

    return listone, copertura, voti, schierato_da, coppie, rig, fermi, fuori, mancati


def partite_per_squadra():
    """Le date delle partite di ogni squadra: servono a contare le assenze.

    Un infortunio non si misura in settimane ma in **giornate saltate**, e
    quelle dipendono dal calendario: due squadre ferme lo stesso tempo possono
    perdere quattro partite o sei.
    """
    fuori = collections.defaultdict(list)
    for r in leggi(os.path.join(DATABASE, 'calendario.csv')):
        for squadra in (r['casa'], r['trasferta']):
            fuori[squadra].append(r['data'])
    for squadra in fuori:
        fuori[squadra].sort()
    return fuori


def righe_giocatore(listone, copertura, voti, schierato_da, coppie, rig, fermi,
                    fuori=(), presenze=None):
    """Una riga per giocatore, con quello che le fonti dicono di lui."""
    titolare, riserva = presenze or misura_presenze()
    # Per ogni giocatore, chi gli contende il posto.
    rivali = collections.defaultdict(list)
    for (a, b), d in coppie.items():
        media = None
        if d['pct']:
            media = (sum(p[0] for p in d['pct']) / len(d['pct']),
                     sum(p[1] for p in d['pct']) / len(d['pct']))
        rivali[a].append((b, d['peso'], media[0] if media else None))
        rivali[b].append((a, d['peso'], media[1] if media else None))

    out = []
    for ident, r in sorted(listone.per_id.items()):
        cop = copertura.get(r['squadra'], 0.0)
        peso = voti.get(ident, 0.0)
        quota = (peso / cop) if cop > 0 else None
        n_fonti = len(set(schierato_da.get(ident, [])))
        miei_rivali = sorted(rivali.get(ident, []), key=lambda t: -t[1])

        # Dalle guide alle partite: la quota di fonti che lo schiera si legge
        # sulla scala misurata sul campionato scorso. Per un giocatore di
        # movimento unanime non vuol dire 38 presenze ma 30: si riposa, si fa
        # male, salta un turno di squalifica. Per un portiere vuol dire 35,
        # perche' la maglia e' una sola e non si fa turnover fra i pali.
        ruolo = r['ruolo']
        base = riserva.get(ruolo, 12.0)
        piena = titolare.get(ruolo, 30.0)
        pres_web = None if quota is None else base + (piena - base) * quota
        saltate = fermi.get(ident, {}).get('saltate', 0) or 0
        if pres_web is not None and saltate:
            pres_web *= max(0.0, float(GIORNATE - saltate)) / GIORNATE
        # Quanto le fonti sono concordi su di lui: 1 se lo schierano tutte o
        # nessuna, 0 se si dividono a meta'. E' la certezza, e va tenuta
        # separata dal giudizio: "titolare al 50%" e "titolare sicuro" non
        # sono lo stesso numero con due nomi.
        accordo = None if quota is None else abs(2.0 * quota - 1.0)

        out.append({
            'id': ident, 'nome': r['nome'], 'squadra': r['squadra'],
            'ruolo': r['ruolo'],
            'fonti_squadra': round(cop, 2),
            'peso_titolare': round(peso, 2),
            'titolarita_web': None if quota is None else round(quota, 3),
            'accordo': None if accordo is None else round(accordo, 3),
            'presenze_web': None if pres_web is None else round(pres_web, 1),
            'fonti_che_lo_schierano': n_fonti,
            'ballottaggio_con': '|'.join(
                listone.per_id[b]['nome'] for b, _, _ in miei_rivali),
            'ballottaggio_id': '|'.join(str(b) for b, _, _ in miei_rivali),
            'ballottaggio_pct': '|'.join(
                ('' if p is None else '%d' % round(p)) for _, _, p in miei_rivali),
            'rigorista_web': (min(rig[ident]) if ident in rig else ''),
            'rigorista_fonti': len(rig.get(ident, [])),
            'stato': fermi.get(ident, {}).get('problema', ''),
            'rientro_stimato': fermi.get(ident, {}).get('rientro', ''),
            'partite_saltate': fermi.get(ident, {}).get('saltate', ''),
            'fuori_lista': 1 if ident in fuori else 0,
        })
        if ident in fuori:
            # Zero, non "poche": non e' una previsione prudente, e' il
            # regolamento. E la titolarita' va a zero con lei, altrimenti
            # resterebbe la gerarchia di uno che non puo' giocare.
            out[-1]['presenze_web'] = 0.0
            out[-1]['titolarita_web'] = 0.0
    return out


# --------------------------------------------------- coppie complementari
def accoppiate(listone, righe, coppie):
    """Le coppie che si dividono la stessa maglia.

    E' l'informazione che in asta vale piu' di tutte e che nessun listone
    scrive: quando non gioca l'uno gioca l'altro. Prendendoli entrambi quella
    maglia e' tua **tutte le giornate**, e il secondo costa una frazione del
    primo perche' il mercato paga i titolari, non le certezze.

    Due modi di formarsi, e vanno distinti perche' si comprano in modo diverso:

      **ballottaggio** &mdash; se la giocano adesso, nessuno dei due e' sicuro.
      Il prezzo di entrambi e' gonfiato dal dubbio, ma insieme coprono tutto.

      **vice** &mdash; uno e' il titolare, l'altro il suo cambio naturale.
      Il secondo costa pochissimo perche' da solo non vale niente; accanto al
      primo vale l'assicurazione su una maglia intera.
    """
    per_id = dict((r['id'], r) for r in righe)
    out = []
    visti = set()

    # 1. i ballottaggi dichiarati dalle fonti
    for (a, b), d in coppie.items():
        ra, rb = per_id.get(a), per_id.get(b)
        if not ra or not rb:
            continue
        visti.add((a, b))
        out.append(_coppia(ra, rb, 'ballottaggio', d['peso'],
                           sorted(set(d['fonti']))))

    # 2. il vice: primo e secondo dello stesso reparto, quando il secondo non
    #    e' gia' in ballottaggio con lui. Ordinati per quanto le guide li
    #    schierano, che e' la gerarchia vera.
    per_reparto = collections.defaultdict(list)
    for r in righe:
        per_reparto[(r['squadra'], r['ruolo'])].append(r)
    for (squadra, ruolo), elenco in per_reparto.items():
        elenco = sorted(elenco, key=lambda r: -(r['titolarita_web'] or 0))
        titolari = [r for r in elenco if (r['titolarita_web'] or 0) >= 0.5]
        # Solo chi qualche guida in campo ce lo mette davvero: il quinto
        # difensore che nessuno nomina non e' il vice di nessuno, e dirlo
        # sarebbe peggio che tacere. Per i portieri il ragionamento non
        # serve: il secondo portiere e' il secondo portiere.
        # Un infortunato non e' il vice di nessuno: e' fuori dai piani solo
        # per adesso, e quando rientra si riprende la maglia. Chiamarlo vice
        # sarebbe leggere un gesso come una gerarchia.
        panchina = [r for r in elenco
                    if (r['titolarita_web'] or 0) < 0.5
                    and (r['partite_saltate'] or 0) < 3
                    and (r['fonti_che_lo_schierano'] > 0 or ruolo == 'P')]
        if not titolari or not panchina:
            continue
        # Il primo della panchina fa da vice al piu' fragile dei titolari:
        # nel dubbio si assegna al meno sicuro, che e' quello che rischia di
        # lasciare la maglia scoperta.
        vice = panchina[0]
        piu_fragile = min(titolari, key=lambda r: r['titolarita_web'] or 0)
        k = (min(vice['id'], piu_fragile['id']), max(vice['id'], piu_fragile['id']))
        if k in visti:
            continue
        visti.add(k)
        out.append(_coppia(piu_fragile, vice, 'vice', 0.0, []))

    out.sort(key=lambda d: -d['copertura'])
    return out


def _coppia(ra, rb, tipo, peso, fonti):
    """Titolare per primo, comunque sia arrivata la coppia."""
    if (rb['titolarita_web'] or 0) > (ra['titolarita_web'] or 0):
        ra, rb = rb, ra
    pa = ra['presenze_web'] or 0.0
    pb = rb['presenze_web'] or 0.0
    return {
        'id_titolare': ra['id'], 'titolare': ra['nome'],
        'id_vice': rb['id'], 'vice': rb['nome'],
        'squadra': ra['squadra'], 'ruolo': ra['ruolo'], 'tipo': tipo,
        'titolarita_titolare': ra['titolarita_web'],
        'titolarita_vice': rb['titolarita_web'],
        'presenze_titolare': round(pa, 1), 'presenze_vice': round(pb, 1),
        # Quante giornate su 38 la maglia e' coperta da uno dei due. Il tetto
        # non e' 38 ma 36: capita la settimana in cui sono fuori tutti e due,
        # e promettere il 100% sarebbe l'unica cifra sicuramente falsa.
        'giornate_coperte': round(min(GIORNATE - 2.0, pa + pb), 1),
        'copertura': round(min(GIORNATE - 2.0, pa + pb) / GIORNATE, 3),
        'peso_fonti': round(peso, 2), 'fonti': '|'.join(fonti),
        # Se uno dei due e' fermo, la coppia oggi vale ancora di piu': la
        # maglia e' tutta dell'altro finche' il primo non rientra.
        'nota': ('%s fermo per %d giornate' % (rb['nome'], rb['partite_saltate'])
                 if (rb['partite_saltate'] or 0) >= 3 else
                 ('%s fermo per %d giornate' % (ra['nome'], ra['partite_saltate'])
                  if (ra['partite_saltate'] or 0) >= 3 else '')),
    }


def _o(x):
    """Vuoto invece di None: nel CSV `None` diventerebbe la stringa 'None'."""
    return '' if x is None else x


def main():
    listone, copertura, voti, schierato_da, coppie, rig, fermi, fuori, mancati = calcola()
    presenze = misura_presenze()
    print('presenze misurate  titolari %s' % presenze[0])
    print('                   alternative %s' % presenze[1])
    righe = righe_giocatore(listone, copertura, voti, schierato_da, coppie,
                            rig, fermi, fuori, presenze)

    p = os.path.join(WEB, 'consenso_giocatori.csv')
    campi = list(righe[0].keys())
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campi, lineterminator='\n')
        w.writeheader()
        w.writerows(righe)

    # Le coppie che si dividono una maglia: e' il file che l'asta usa per
    # sapere chi comprare a due crediti dopo aver speso quaranta.
    cop = accoppiate(listone, righe, coppie)
    p = os.path.join(DATABASE, 'accoppiate.csv')
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(cop[0].keys()),
                           lineterminator='\n')
        w.writeheader()
        w.writerows(cop)

    # La gerarchia, pronta per il database: una riga per giocatore.
    p = os.path.join(DATABASE, 'gerarchie.csv')
    campi_g = ['id', 'titolarita', 'accordo', 'presenze_web', 'fonti',
               'ballottaggio_con', 'ballottaggio_pct', 'rigorista',
               'stato', 'rientro_stimato', 'partite_saltate', 'fuori_lista']
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(campi_g)
        for r in righe:
            w.writerow([r['id'], _o(r['titolarita_web']), _o(r['accordo']),
                        _o(r['presenze_web']), r['fonti_che_lo_schierano'],
                        r['ballottaggio_id'], r['ballottaggio_pct'],
                        r['rigorista_web'], r['stato'], r['rientro_stimato'],
                        r['partite_saltate'], r['fuori_lista']])

    q = os.path.join(WEB, 'non_abbinati.csv')
    with open(q, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['fonte', 'dove', 'squadra', 'nome',
                                          'motivo'], lineterminator='\n')
        w.writeheader()
        w.writerows(mancati)

    citati = sum(1 for r in righe if r['fonti_che_lo_schierano'] > 0)
    unanimi = sum(1 for r in righe
                  if (r['titolarita_web'] or 0) >= 0.99 and r['fonti_squadra'] >= 3)
    print('Consenso su %d giocatori del listone' % len(righe))
    print('  schierati da almeno una guida : %d' % citati)
    print('  schierati da TUTTE le guide   : %d' % unanimi)
    print('  con un ballottaggio aperto    : %d'
          % sum(1 for r in righe if r['ballottaggio_con']))
    print('  rigoristi designati           : %d'
          % sum(1 for r in righe if r['rigorista_web'] == 1))
    lunghi = [r for r in righe if (r['partite_saltate'] or 0) >= 4]
    if fuori:
        print('  fuori dalla lista di serie A     : %d' % len(fuori))
        for r in righe:
            if r['fuori_lista']:
                print('      %-18s %-11s zero presenze: fuori lista'
                      % (r['nome'], r['squadra']))
    print('  fermi ai box                  : %d, di cui %d per almeno 4 giornate'
          % (sum(1 for r in righe if r['stato']), len(lunghi)))
    for r in sorted(lunghi, key=lambda x: -x['partite_saltate'])[:10]:
        print('      %-16s %-11s %2d giornate  (%s)'
              % (r['nome'], r['squadra'], r['partite_saltate'], r['stato']))
    print('  coppie che si dividono una maglia: %d  (%d ballottaggi, %d vice)'
          % (len(cop), sum(1 for c in cop if c['tipo'] == 'ballottaggio'),
             sum(1 for c in cop if c['tipo'] == 'vice')))
    print('\n  Le dieci coppie che coprono di piu\':')
    print('  %-18s %-18s %-11s %-13s %s'
          % ('titolare', 'vice', 'squadra', 'tipo', 'copertura'))
    for c in cop[:10]:
        print('  %-18s %-18s %-11s %-13s %3d%%'
              % (c['titolare'][:18], c['vice'][:18], c['squadra'][:11],
                 c['tipo'], round(100 * c['copertura'])))
    print('\nNomi delle guide non abbinati al listone: %d' % len(mancati))
    c = collections.Counter((m['squadra'], m['nome'], m['motivo']) for m in mancati)
    for (sq, nome, motivo), n in c.most_common(40):
        print('  %-12s %-22s %-9s (%d fonti)' % (sq, nome, motivo, n))


if __name__ == '__main__':
    main()
