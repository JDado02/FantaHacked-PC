# -*- coding: utf-8 -*-
"""Costruisce il database dell'assistente d'asta a partire dalle fonti in ../fonti.

Rieseguibile: cancella e riscrive tutti i CSV di output.
Non inventa mai un valore: cio' che non e' derivabile resta vuoto ed e'
registrato in lacune.csv.

Uso:  python build.py
"""
import csv, json, os, sys, collections, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nomi import norm, variants, split_fanta, chiavi_understat, combacia_iniziale

BASE  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTI = os.path.join(BASE, 'fonti')
OUT   = BASE

STAGIONE_CORRENTE = '2026-27'
STAGIONI_STORICHE = ['2025-26', '2024-25', '2023-24']
# Stagioni dei due listoni del seed, verificate confrontando i gol con la
# fonte statistica indipendente: 99.2% e 99.6% di accordo.
LISTONE_SEASON = {'seed_listone_stagione_recente.csv':    '2025-26',
                  'seed_listone_stagione_precedente.csv': '2024-25'}
UNDERSTAT_SEASON = {2023: '2023-24', 2024: '2024-25', 2025: '2025-26'}
MINUTI_STAGIONE = 38 * 90

lacune = []
def lacuna(file, id_, colonna, motivo, fonte=''):
    lacune.append({'file': file, 'id': id_, 'colonna': colonna,
                   'motivo': motivo, 'fonte_tentata': fonte})

def leggi(nome, enc='utf-8'):
    with open(os.path.join(FONTI, nome), encoding=enc, newline='') as f:
        return list(csv.DictReader(f))

def carica(nome):
    with open(os.path.join(OUT, nome), encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))

def scrivi(nome, campi, righe):
    with open(os.path.join(OUT, nome), 'w', encoding='utf-8', newline='') as f:
        wr = csv.DictWriter(f, fieldnames=campi, lineterminator='\n',
                            extrasaction='ignore')
        wr.writeheader()
        wr.writerows(righe)
    print("  %-24s %5d righe" % (nome, len(righe)))
    return len(righe)

def num(v, tipo=float):
    if v is None or v == '':
        return ''
    try:
        x = tipo(v)
        if tipo is float and x == int(x):
            return int(x)
        return x
    except (TypeError, ValueError):
        return ''

# Ogni fonte scrive i club a modo suo.
ALIAS_SQUADRA = {'ac milan': 'Milan', 'parma calcio 1913': 'Parma',
                 'hellas verona': 'Verona', 'internazionale': 'Inter'}
def sq(nome):
    n = str(nome).strip()
    return ALIAS_SQUADRA.get(n.lower(), n)

def sq_set(campo):
    """Understat unisce con virgola i club di chi si e' trasferito a stagione in corso."""
    return set(sq(p) for p in str(campo).split(',') if p.strip())


print("=" * 64)
print("BUILD DATABASE ASSISTENTE D'ASTA - modalita' Classic")
print("=" * 64)

# ---------------------------------------------------------------- 1. FONTI
print("\n[1] Lettura fonti")
correnti = leggi('seed_giocatori_correnti.csv')
prezzi   = leggi('seed_prezzi_asta.csv')
listoni  = dict((stag, leggi(f)) for f, stag in LISTONE_SEASON.items())
calend   = leggi('calendario_seriea_2026_27.csv', enc='utf-8-sig')
print("  listone corrente          %5d giocatori" % len(correnti))
for s in sorted(listoni):
    print("  statistiche %s       %5d righe" % (s, len(listoni[s])))
print("  calendario %s          %5d partite" % (STAGIONE_CORRENTE, len(calend)))

understat = {}
for anno in UNDERSTAT_SEASON:
    with open(os.path.join(FONTI, 'understat_seriea_%d.json' % anno), encoding='utf-8') as f:
        d = json.load(f)
    for p in d['players']:
        e = understat.setdefault(p['id'], {'id': p['id'], 'name': p['player_name'],
                                           'teams': set(), 'seasons': {}})
        e['teams'] |= sq_set(p['team_title'])
        e['seasons'][anno] = p
print("  fonte statistica avanzata %5d giocatori su 3 stagioni" % len(understat))


# ------------------------------------------- 2. ABBINAMENTO CON LA FONTE
# Livelli decrescenti di confidenza. Un abbinamento ambiguo non viene mai
# risolto a caso: resta non abbinato e finisce in lacune.csv.
print("\n[2] Abbinamento nomi listone -> fonte statistica")

idx_pieno = collections.defaultdict(list)   # cognome semplice e composto
idx_token = collections.defaultdict(list)   # singoli token oltre il nome proprio
for e in understat.values():
    for k in chiavi_understat(e['name']):
        idx_pieno[k].append(e)
    for t in norm(e['name']).split()[1:]:
        if len(t) >= 4:
            for v in variants(t):
                idx_token[v].append(e)

def candidati(indice, testo):
    out = []
    for v in variants(testo):
        for e in indice.get(v, []):
            if e not in out:
                out.append(e)
    return out

mappa, match_us = [], {}
conta = collections.Counter()
dettaglio = {}      # nome di listone -> (metodo, confidenza, iniziali)

for r in correnti:
    cognome, iniziali = split_fanta(r['nome'])
    metodo, conf, cands = None, 0.0, []

    c = candidati(idx_pieno, cognome)
    if c:
        metodo, conf, cands = 'cognome', 0.95, c
    else:
        toks = norm(cognome).split()
        for pos, t in enumerate(toks):
            if len(t) < 4:
                continue
            c = candidati(idx_token, t)
            # Guardia contro i cognomi comuni. Nel listone il nome e' un
            # cognome, eventualmente composto, e il token che conta e' il
            # primo. Se un nome a piu' token combacia solo sull'ultimo, quel
            # token e' probabilmente un cognome diffuso (Carlos, Gomez) e il
            # primo token e' un nome proprio: si rischia di attribuire a un
            # giocatore le statistiche di un altro. Si accetta solo se anche
            # il primo token compare nel nome della fonte.
            if c and len(toks) > 1 and pos == len(toks) - 1:
                c = [x for x in c if toks[0] in norm(x['name']).split()]
            if c:
                metodo, conf, cands = 'token_parziale', 0.70, c
                break

    if cands and iniziali:
        f = [x for x in cands if combacia_iniziale(x['name'], iniziali)]
        if f:
            cands, metodo, conf = f, metodo + '+iniziale', min(conf + 0.03, 0.99)
    if len(cands) > 1:
        f = [x for x in cands if sq(r['squadra']) in x['teams']]
        if len(f) == 1:
            cands, metodo, conf = f, metodo + '+squadra', min(conf + 0.02, 0.99)

    voce = {'nome_fantacalcio': r['nome'], 'squadra': sq(r['squadra']),
            'nome_normalizzato': norm(r['nome'])}
    dettaglio[r['nome']] = (metodo, conf, iniziali)
    if len(cands) == 1:
        e = cands[0]
        match_us[r['nome']] = e
        conta[metodo] += 1
        voce.update({'id_fonte_stat': e['id'], 'nome_fonte_stat': e['name'],
                     'metodo': metodo, 'confidenza': round(conf, 2)})
    else:
        motivo = 'ambiguo' if cands else 'assente_nella_fonte'
        conta[motivo] += 1
        voce.update({'id_fonte_stat': '',
                     'nome_fonte_stat': ' | '.join(x['name'] for x in cands),
                     'metodo': motivo, 'confidenza': 0.0})
    mappa.append(voce)

# --- un giocatore, una riga di statistiche ------------------------------
# Il vincolo di squadra non basta quando il listone contiene due nomi che si
# somigliano: il Frosinone ha `Oyono A.` e `Oyono J.`, e la fonte statistica
# conosce un solo Oyono. Il filtro sull'iniziale c'era gia', ma cedeva: se
# nessun candidato aveva l'iniziale giusta lo teneva lo stesso, e cosi' le
# statistiche di Anthony finivano anche addosso a suo fratello. Da li' in poi
# i due erano indistinguibili, e le guide che scrivevano `Oyono` non si
# abbinavano piu' a nessuno dei due: un titolare del Frosinone risultava non
# schierato da nessuno.
#
# La voce contesa la tiene chi ha anche l'iniziale giusta; gli altri restano
# senza, che e' la risposta onesta.
reclami = collections.defaultdict(list)
for nome_l, e in match_us.items():
    reclami[e['id']].append(nome_l)
for _id, nomi in reclami.items():
    if len(nomi) < 2:
        continue
    def _voto(nome_l):
        metodo, conf, ini = dettaglio[nome_l]
        ok = 2 if (ini and combacia_iniziale(match_us[nome_l]['name'], ini)) \
             else (1 if not ini else 0)
        return (ok, conf, nome_l)
    vincitore = max(nomi, key=_voto)
    for nome_l in nomi:
        if nome_l == vincitore:
            continue
        del match_us[nome_l]
        conta[dettaglio[nome_l][0]] -= 1
        conta['omonimo_gia_assegnato'] += 1
        for voce in mappa:
            if voce['nome_fantacalcio'] == nome_l:
                voce.update({'id_fonte_stat': '', 'metodo': 'omonimo_gia_assegnato',
                             'confidenza': 0.0})
        lacuna('giocatori.csv', '', 'nome_completo',
               '%s: la voce statistica e gia di %s' % (nome_l, vincitore),
               'understat')

n = len(correnti)
abbinati = sum(v for k, v in conta.items()
               if k not in ('ambiguo', 'assente_nella_fonte',
                            'omonimo_gia_assegnato'))
for k, v in conta.most_common():
    print("  %-28s %4d  (%5.1f%%)" % (k, v, 100.0 * v / n))
print("  %-28s %4d  (%5.1f%%)" % ('ABBINATI', abbinati, 100.0 * abbinati / n))


# ----------------------------------------- 3. ID UFFICIALI FANTACALCIO
# L'id lo porta il listone corrente, quando la fonte lo espone: e' quello che
# usa la piattaforma, ed e' con quello che si rileggono le rose esportate a
# fine asta. Prima veniva **indovinato** cercando il nome nei listoni storici,
# e chi non aveva uno storico -- un arrivo dall'estero, un ragazzo delle
# giovanili -- riceveva un id inventato >= 900001. Erano 138 su 531: piu' di un
# giocatore su quattro, e nessuno di loro si riconosceva nel file dell'asta.
#
# Quando l'id ufficiale c'e', lo storico si cerca **per id** e non per nome:
# gli omonimi smettono di essere un problema, e chi ha cambiato squadra si
# porta dietro le proprie statistiche invece di perderle.
print("\n[3] Assegnazione id")
idx_listone = collections.defaultdict(list)
per_id_storico = collections.defaultdict(list)
for stag in listoni:
    for row in listoni[stag]:
        idx_listone[norm(row['nome'])].append((stag, row))
        per_id_storico[int(row['id'])].append((stag, row))

id_di, righe_storiche = {}, {}
ufficiali = dal_listone = 0
for r in correnti:
    dato = num(r.get('id_ufficiale'), int)
    if dato:
        id_di[r['nome']] = dato
        righe_storiche[r['nome']] = per_id_storico.get(dato, [])
        ufficiali += 1
        dal_listone += 1
        continue
    cands = idx_listone.get(norm(r['nome']), [])
    same = [c for c in cands if c[1]['ruolo'] == r['ruolo']]
    scelti = same or cands
    ids = set(c[1]['id'] for c in scelti)
    if len(ids) == 1:
        id_di[r['nome']] = int(scelti[0][1]['id'])
        righe_storiche[r['nome']] = scelti
        ufficiali += 1
print("  id presi dal listone      %4d" % dal_listone)

prossimo = 900001
for r in sorted(correnti, key=lambda x: (x['ruolo'], norm(x['nome']))):
    if r['nome'] not in id_di:
        id_di[r['nome']] = prossimo
        prossimo += 1
        lacuna('giocatori.csv', id_di[r['nome']], 'id',
               'nessuno storico Serie A: id sintetico assegnato', 'listoni ufficiali')
print("  id ufficiali Fantacalcio  %4d  (%5.1f%%)" % (ufficiali, 100.0 * ufficiali / n))
print("  id sintetici (>=900001)   %4d  (%5.1f%%)" % (n - ufficiali, 100.0 * (n - ufficiali) / n))


# -------------------------------------------------------------- 4. SQUADRE
print("\n[4] Scrittura tabelle")
squadre_correnti = sorted(set(sq(r['squadra']) for r in correnti))
# Un club conta come "ha giocato in Serie A" solo se ha una rosa vera nel
# listone. Qualche riga residua di squadre retrocesse resta nei file di
# origine: senza questa soglia, un club con un solo giocatore risulterebbe
# non promosso e con zero gol subiti, e il suo portiere sembrerebbe imbattibile.
MIN_ROSA_STORICA = 15
_rose = collections.Counter(sq(r['squadra']) for r in listoni['2025-26'])
storiche_2526 = set(t for t, n in _rose.items() if n >= MIN_ROSA_STORICA)
gf_prec, gs_prec = collections.Counter(), collections.Counter()
for row in listoni['2025-26']:
    t = sq(row['squadra'])
    gf_prec[t] += num(row['gf'], int) or 0
    gs_prec[t] += num(row['gs'], int) or 0

righe = []
for t in squadre_correnti:
    promossa = 0 if t in storiche_2526 else 1
    righe.append({'squadra': t, 'nome_ufficiale': '', 'allenatore': '',
                  'promossa': promossa,
                  'gf_prec': gf_prec[t] if not promossa else '',
                  'gs_prec': gs_prec[t] if not promossa else ''})
    if promossa:
        lacuna('squadre.csv', '', 'gf_prec/gs_prec',
               'neopromossa %s: nessun dato di Serie A' % t, '')
lacuna('squadre.csv', '', 'allenatore', 'nessuna fonte strutturata disponibile', '')
n_squadre = scrivi('squadre.csv',
    ['squadra', 'nome_ufficiale', 'allenatore', 'promossa', 'gf_prec', 'gs_prec'], righe)


# ------------------------------------------------------------ 5. GIOCATORI
squadra_2526 = dict((int(row['id']), sq(row['squadra'])) for row in listoni['2025-26'])

righe = []
for r in correnti:
    pid = id_di[r['nome']]
    prec = squadra_2526.get(pid)
    nuovo = '' if prec is None else (1 if prec != sq(r['squadra']) else 0)
    u = match_us.get(r['nome'])
    righe.append({
        'id': pid, 'nome': r['nome'],
        'nome_completo': u['name'] if u else '',
        'squadra': sq(r['squadra']), 'ruolo': r['ruolo'],
        'qi': num(r['qt_fanta'], int), 'qa': num(r['qt_fanta'], int),
        'fvm': num(r.get('fvm'), int) or '',
        'eta': num(r.get('eta'), int) or '',
        'nuovo_acquisto': nuovo, 'attivo': 1,
        'id_ufficiale': 1 if pid < 900000 else 0,
    })
    if not u:
        lacuna('giocatori.csv', pid, 'nome_completo',
               'non abbinato alla fonte statistica', 'understat')
    if nuovo == '':
        lacuna('giocatori.csv', pid, 'nuovo_acquisto',
               'nessuna squadra nota per la stagione 2025-26', '')
righe.sort(key=lambda x: x['id'])
n_gioc = scrivi('giocatori.csv',
    ['id', 'nome', 'nome_completo', 'squadra', 'ruolo', 'qi', 'qa', 'fvm',
     'eta', 'nuovo_acquisto', 'attivo', 'id_ufficiale'], righe)
lacuna('giocatori.csv', '', 'qa',
       'il listone disponibile espone una sola quotazione: qa impostata = qi', '')
# Il valore di mercato (FVM, su base 1000) e l'eta' arrivano dal listone
# ufficiale: sono due colonne che prima restavano vuote.
for _r in righe:
    for _c in ('fvm', 'eta'):
        if _r[_c] == '':
            lacuna('giocatori.csv', _r['id'], _c,
                   'il listone non lo espone per questo giocatore',
                   'listone ufficiale')


# ----------------------------------------------------------- 6. STATISTICHE
CAMPI_ST = ['pg', 'mv', 'mf', 'gf', 'gs', 'rp', 'rc', 'rpiu', 'rmeno',
            'ass', 'amm', 'esp', 'au']
inv_stag = dict((v, k) for k, v in UNDERSTAT_SEASON.items())
righe, minuti_di = [], {}
for r in correnti:
    pid = id_di[r['nome']]
    u = match_us.get(r['nome'])
    visti = set()
    for stag, src in righe_storiche.get(r['nome'], []):
        # I listoni di origine contengono qualche riga duplicata: una sola
        # riga per (giocatore, stagione).
        if stag in visti:
            continue
        visti.add(stag)
        anno = inv_stag[stag]
        us = u['seasons'].get(anno) if u else None
        minuti = num(us['time'], int) if us else ''
        if stag == '2025-26':
            minuti_di[pid] = minuti
        riga = {'id': pid, 'stagione': stag, 'squadra': sq(src['squadra']),
                'ruolo': src['ruolo'], 'minuti': minuti}
        for c in CAMPI_ST:
            riga[c] = num(src[c])
        righe.append(riga)
        if minuti == '' and (num(src['pg'], int) or 0) > 0:
            lacuna('statistiche.csv', pid, 'minuti',
                   '%s: giocatore non abbinato alla fonte dei minuti' % stag, 'understat')
righe.sort(key=lambda x: (x['id'], x['stagione']))
n_stat = scrivi('statistiche.csv',
    ['id', 'stagione', 'squadra', 'ruolo', 'minuti'] + CAMPI_ST, righe)


# ------------------------------------------------------------- 7. AVANZATE
righe = []
for r in correnti:
    u = match_us.get(r['nome'])
    if not u:
        continue
    pid = id_di[r['nome']]
    for anno in sorted(u['seasons']):
        rec = u['seasons'][anno]
        righe.append({
            'id': pid, 'stagione': UNDERSTAT_SEASON[anno],
            'squadra': ' | '.join(sorted(sq_set(rec['team_title']))),
            'partite': num(rec['games'], int), 'minuti': num(rec['time'], int),
            'gol': num(rec['goals'], int), 'assist': num(rec['assists'], int),
            'xg': round(float(rec['xG']), 4), 'npxg': round(float(rec['npxG']), 4),
            'xa': round(float(rec['xA']), 4),
            'tiri': num(rec['shots'], int),
            'passaggi_chiave': num(rec['key_passes'], int),
            'xg_chain': round(float(rec['xGChain']), 4),
            'xg_buildup': round(float(rec['xGBuildup']), 4),
            'posizione_fonte': rec['position'],
        })
righe.sort(key=lambda x: (x['id'], x['stagione']))
n_avan = scrivi('avanzate.csv',
    ['id', 'stagione', 'squadra', 'partite', 'minuti', 'gol', 'assist', 'xg',
     'npxg', 'xa', 'tiri', 'passaggi_chiave', 'xg_chain', 'xg_buildup',
     'posizione_fonte'], righe)
lacuna('avanzate.csv', '', 'tocchi_area', 'non esposto dalla fonte utilizzata', 'understat')


# ------------------------------------------------------------- 8. CONTESTO
# titolarita NON viene stimata: e' un giudizio prospettico. Viene fornita solo
# la quota minuti storica, che e' un dato calcolato su fonte reale.
rig_2526 = dict((int(row['id']), num(row['rc'], int) or 0) for row in listoni['2025-26'])

righe = []
for r in correnti:
    pid = id_di[r['nome']]
    m = minuti_di.get(pid, '')
    quota = round(float(m) / MINUTI_STAGIONE, 3) if isinstance(m, int) and m else ''
    rc = rig_2526.get(pid)
    if rc is None:
        rigorista, fonte_rig = '', ''
        lacuna('contesto.csv', pid, 'rigorista', 'nessuno storico rigori calciati', '')
    else:
        rigorista = 1 if rc >= 3 else (2 if rc >= 1 else 0)
        fonte_rig = 'derivato_da_rigori_calciati_2025-26'
    righe.append({
        'id': pid, 'titolarita': '', 'quota_minuti_2025_26': quota,
        'ballottaggio_con': '', 'rigorista': rigorista, 'fonte_rigorista': fonte_rig,
        'calci_piazzati': '', 'corner': '', 'stato': '', 'rientro_stimato': '',
        'fascia': r['fascia_o_valore'], 'nota_listone': r['note'],
        'consiglio_sos': r['sos'], 'accoppiata': r['accoppiata'],
    })
    if quota == '':
        lacuna('contesto.csv', pid, 'quota_minuti_2025_26',
               'minuti non disponibili per questo giocatore', 'understat')
righe.sort(key=lambda x: x['id'])
n_ctx = scrivi('contesto.csv',
    ['id', 'titolarita', 'quota_minuti_2025_26', 'ballottaggio_con', 'rigorista',
     'fonte_rigorista', 'calci_piazzati', 'corner', 'stato', 'rientro_stimato',
     'fascia', 'nota_listone', 'consiglio_sos', 'accoppiata'], righe)
lacuna('contesto.csv', '', 'titolarita',
       'giudizio prospettico: nessuna fonte strutturata, va compilato a mano', 'redazionali')
lacuna('contesto.csv', '', 'calci_piazzati/corner',
       'nessuna fonte strutturata disponibile', 'redazionali')
lacuna('contesto.csv', '', 'stato/rientro_stimato',
       'infortuni: dato volatile, da aggiornare a ridosso dell asta', 'redazionali')


# ----------------------------------------------------------- 9. CALENDARIO
righe = []
for m in calend:
    d = ''
    try:
        d = datetime.datetime.strptime(m['Date'].split()[0], '%d/%m/%Y').strftime('%Y-%m-%d')
    except Exception:
        lacuna('calendario.csv', '', 'data',
               'formato non riconosciuto: %s' % m.get('Date'), '')
    righe.append({'giornata': int(m['Round Number']), 'data': d,
                  'casa': sq(m['Home Team']), 'trasferta': sq(m['Away Team'])})
righe.sort(key=lambda x: (x['giornata'], x['casa']))
n_cal = scrivi('calendario.csv', ['giornata', 'data', 'casa', 'trasferta'], righe)


# --------------------------------------------------------- 10. PREZZI ASTA
idx_nome = dict((norm(r['nome']), id_di[r['nome']]) for r in correnti)
righe = []
for p in prezzi:
    nome = p['nome_maiuscolo']
    pid = idx_nome.get(norm(nome), '')
    if pid == '':
        lacuna('prezzi_asta.csv', '', nome,
               'nome non presente nel listone corrente: riga senza id', '')
    righe.append({'id': pid, 'nome': nome,
                  'prezzo_medio_per_1000': num(p['prezzo_medio_per_1000_crediti']),
                  'mediana_per_1000': '', 'p25': '', 'p75': '',
                  'n_campioni': '', 'partecipanti': '',
                  'fonte': 'tabella_prezzi_medi_asta_seed'})
righe.sort(key=lambda x: (x['id'] == '', x['id'] if x['id'] != '' else 0))
n_prz = scrivi('prezzi_asta.csv',
    ['id', 'nome', 'prezzo_medio_per_1000', 'mediana_per_1000', 'p25', 'p75',
     'n_campioni', 'partecipanti', 'fonte'], righe)
lacuna('prezzi_asta.csv', '', 'mediana/p25/p75/n_campioni',
       'la fonte espone solo la media, non la distribuzione', '')


# ---------------------------------------------------------- 11. MAPPA NOMI
mappa.sort(key=lambda x: (x['metodo'], x['nome_fantacalcio']))
scrivi('mappa_nomi.csv',
    ['nome_fantacalcio', 'squadra', 'id_fonte_stat', 'nome_fonte_stat',
     'nome_normalizzato', 'metodo', 'confidenza'], mappa)
for m in mappa:
    if m['metodo'] == 'ambiguo':
        lacuna('mappa_nomi.csv', '', m['nome_fantacalcio'],
               'omonimia non risolta: %s' % m['nome_fonte_stat'], 'understat')
    elif m['metodo'].startswith('token_parziale'):
        lacuna('mappa_nomi.csv', '', m['nome_fantacalcio'],
               'abbinato per token parziale a "%s": da rileggere' % m['nome_fonte_stat'],
               'understat')


# ---------------------------------------------------------- 12. VALIDAZIONE
print("\n[5] Validazione")
G  = carica('giocatori.csv');  S = carica('statistiche.csv')
C  = carica('contesto.csv');   A = carica('avanzate.csv')
SQ = carica('squadre.csv');    K = carica('calendario.csv')

errori, avvisi = [], []
ids = set(int(r['id']) for r in G)
if len(ids) != len(G):
    errori.append('id duplicati in giocatori.csv')
for nome, tab in (('statistiche', S), ('contesto', C), ('avanzate', A)):
    orfani = set(int(r['id']) for r in tab) - ids
    if orfani:
        errori.append('%s.csv: %d id non presenti in giocatori.csv' % (nome, len(orfani)))
dup = collections.Counter((r['id'], r['stagione']) for r in S)
if any(v > 1 for v in dup.values()):
    errori.append('coppie (id,stagione) duplicate in statistiche.csv')
squadre_ok = set(r['squadra'] for r in SQ)
for r in G:
    if r['squadra'] not in squadre_ok:
        errori.append('giocatori: squadra sconosciuta %s' % r['squadra'])
for r in K:
    for c in ('casa', 'trasferta'):
        if r[c] not in squadre_ok:
            errori.append('calendario: squadra sconosciuta %s' % r[c])
for r in G:
    if r['ruolo'] not in ('P', 'D', 'C', 'A'):
        errori.append('ruolo non valido: %s' % r['ruolo'])
for r in S:
    pg, mv, mi = num(r['pg'], int), num(r['mv']), num(r['minuti'], int)
    if pg != '' and not (0 <= pg <= 38):
        errori.append('pg fuori scala id=%s' % r['id'])
    if mv != '' and not (0 <= mv <= 10):
        errori.append('mv fuori scala id=%s' % r['id'])
    if mi != '' and not (0 <= mi <= 3600):
        errori.append('minuti fuori scala id=%s' % r['id'])
    if mi != '' and pg not in ('', 0) and mi < pg * 20:
        avvisi.append("minuti bassi rispetto alle presenze id=%s (%s' / %spg)" % (r['id'], mi, pg))
    rc, rp_, rm = num(r['rc'], int), num(r['rpiu'], int), num(r['rmeno'], int)
    if '' not in (rc, rp_, rm) and rp_ + rm != rc:
        avvisi.append('rigori incoerenti id=%s: %s+%s != %s' % (r['id'], rp_, rm, rc))

# Portieri per squadra: e' l'unico reparto in cui un buco si paga subito.
# Con la regola dei portieri a pacchetto, chi compra il titolare si porta a casa
# le sue riserve; se a listone quella squadra ne ha meno di tre, si ritrova uno
# slot scoperto **dopo** aver pagato, e nessuno glielo aveva detto. E' successo
# con l'Atalanta, a cui il listone di partenza dava due portieri invece di tre.
por = collections.Counter(r['squadra'] for r in G if r['ruolo'] == 'P')
for squadra in sorted(set(r['squadra'] for r in G)):
    n = por[squadra]
    if n < 3:
        errori.append('%s ha solo %d portieri a listone: col pacchetto uno slot '
                      'resterebbe scoperto' % (squadra, n))

per_ruolo = collections.Counter(r['ruolo'] for r in G)
ATTESI = {'P': (60, 90), 'D': (170, 220), 'C': (180, 230), 'A': (70, 110)}
for ruolo in ('P', 'D', 'C', 'A'):
    lo, hi = ATTESI[ruolo]
    v = per_ruolo[ruolo]
    if not (lo <= v <= hi):
        avvisi.append('conteggio %s=%d fuori intervallo atteso %d-%d' % (ruolo, v, lo, hi))

def copertura(tab, col):
    if not tab:
        return 0.0
    return sum(1 for x in tab if x[col] not in ('', None)) / float(len(tab))

cop = collections.OrderedDict([
    ('statistiche.mv',         copertura(S, 'mv')),
    ('statistiche.minuti',     copertura(S, 'minuti')),
    ('contesto.quota_minuti',  copertura(C, 'quota_minuti_2025_26')),
    ('contesto.rigorista',     copertura(C, 'rigorista')),
    ('contesto.titolarita',    copertura(C, 'titolarita')),
    ('avanzate.xg',            copertura(A, 'xg')),
    ('giocatori.id_ufficiale', sum(1 for r in G if r['id_ufficiale'] == '1') / float(len(G))),
    ('giocatori.con_storico',  len(set(int(r['id']) for r in S)) / float(len(G))),
])
print("  copertura:")
for k in cop:
    print("    %-26s %6.1f%%" % (k, 100.0 * cop[k]))
print("  giocatori per ruolo: %s" % dict(per_ruolo))
print("  errori bloccanti: %d   avvisi: %d" % (len(errori), len(avvisi)))
for e in errori[:10]:
    print("    ERRORE  %s" % e)
for a in avvisi[:8]:
    print("    avviso  %s" % a)

n_lac = scrivi('lacune.csv', ['file', 'id', 'colonna', 'motivo', 'fonte_tentata'], lacune)


# ------------------------------------------------------------ 13. MANIFEST
manifest = collections.OrderedDict([
    ('generato_il', datetime.date.today().isoformat()),
    ('stagione_corrente', STAGIONE_CORRENTE),
    ('stagioni_storiche', STAGIONI_STORICHE),
    ('modalita', 'classic'),
    ('fonti', [
        {'blocco': 'anagrafica_quotazioni',
         'nome': 'Listone corrente estratto dal foglio FantaAlgoritmo PRO',
         'url': 'locale: fonti/seed_giocatori_correnti.csv',
         'tipo': 'seed_estratto', 'scaricato_il': '2026-09-02',
         'note': 'Espone una sola quotazione: qa impostata uguale a qi.'},
        {'blocco': 'statistiche_storiche',
         'nome': 'Listoni statistici con id ufficiali Fantacalcio',
         'url': 'locale: fonti/seed_listone_stagione_*.csv',
         'tipo': 'seed_estratto', 'scaricato_il': '2026-09-02',
         'note': 'Stagioni identificate confrontando i gol con la fonte avanzata: '
                 'accordo 99.2% (2025-26) e 99.6% (2024-25).'},
        {'blocco': 'minuti_avanzate', 'nome': 'Understat - Serie A',
         'url': 'https://understat.com/getLeagueData/Serie%20A/{2023,2024,2025}',
         'tipo': 'endpoint_json', 'scaricato_il': '2026-09-02',
         'note': 'Fonte unica per minuti, xG, npxG, xA, tiri, passaggi chiave. '
                 'Non copre la Serie B: i giocatori delle neopromosse sono assenti.'},
        {'blocco': 'calendario', 'nome': 'fixturedownload.com - Serie A 2026/27',
         'url': 'https://fixturedownload.com/download/serie-a-2026-UTC.csv',
         'tipo': 'csv', 'scaricato_il': '2026-09-02',
         'note': '380 partite, 38 giornate, 20 squadre coerenti col listone.'},
        {'blocco': 'prezzi_asta', 'nome': 'Tabella prezzi medi d asta del foglio di partenza',
         'url': 'locale: fonti/seed_prezzi_asta.csv', 'tipo': 'seed_estratto',
         'scaricato_il': '2026-09-02', 'note': 'Solo media, normalizzata su 1000 crediti.'},
        {'blocco': 'contesto_editoriale', 'nome': 'NON REPERITO', 'url': '',
         'tipo': 'mancante', 'scaricato_il': '',
         'note': 'titolarita, ballottaggi, calci piazzati e infortuni richiedono '
                 'compilazione manuale: nessuna fonte strutturata disponibile.'},
    ]),
    ('conteggi', collections.OrderedDict([
        ('giocatori', n_gioc), ('per_ruolo', dict(per_ruolo)),
        ('righe_statistiche', n_stat), ('righe_avanzate', n_avan),
        ('righe_contesto', n_ctx), ('righe_calendario', n_cal),
        ('righe_prezzi', n_prz), ('squadre', n_squadre),
    ])),
    ('copertura', collections.OrderedDict((k, round(cop[k], 4)) for k in cop)),
    ('abbinamento_fonte_statistica', dict(conta)),
    ('convenzioni', collections.OrderedDict([
        ('titolarita', 'campo vuoto: non stimato. Usare quota_minuti_2025_26 come base.'),
        ('rigori', 'rpiu + rmeno == rc'),
        ('rigorista', 'derivato dai rigori calciati 2025-26: >=3 primo, 1-2 secondo, '
                      '0 nessuno. Da confermare manualmente.'),
        ('fonte_xg_unica', 'understat'),
        ('id_sintetici', 'id >= 900001 per chi non ha storico Serie A; id_ufficiale=0'),
        ('qa', 'uguale a qi: la fonte disponibile espone una sola quotazione'),
    ])),
    ('lacune_totali', n_lac),
    ('errori_validazione', errori),
    ('avvertenze', [
        'titolarita, calci_piazzati, corner e stato infortuni NON sono compilati.',
        'Gli abbinamenti con metodo token_parziale hanno confidenza 0.70 e vanno riletti.',
        'I giocatori delle neopromosse non hanno statistiche di Serie A: assenza corretta.',
        'qa e uguale a qi perche il listone disponibile espone una sola quotazione.',
    ]),
])
with open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
print("  manifest.json            scritto")

print("\n" + "=" * 64)
print("COMPLETATO" if not errori else "COMPLETATO CON %d ERRORI" % len(errori))
print("=" * 64)
