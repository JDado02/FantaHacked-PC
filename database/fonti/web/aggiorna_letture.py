# -*- coding: utf-8 -*-
"""Da una lettura datata del web ai CSV che il consenso e la pipeline usano.

Ogni volta che si rileggono le fonti, quello che si e' letto va in una
cartella sua, `letture/AAAA-MM-GG/`, cosi' com'e' uscito dalle pagine. Questo
script lo mette al suo posto:

  probabili_g*.psv          -> formazioni_tipo.csv    (fonte fantacalcio.it)
  statistiche_AAAA_AA.psv   -> formazioni_tipo.csv    (fonte campo-AAAA-AA)
                            -> ../seed_listone_stagione_in_corso.csv
  quotazioni.psv            -> ../seed_giocatori_correnti.csv
  understat_AAAA.psv        -> ../understat_seriea_AAAA.json
  infortuni.csv             -> infortuni.csv          (si sostituisce)
  rigoristi_fantacalcio.psv -> rigoristi.csv          (fonte fantacalcio.it-rigori)
                               + chi li ha tirati davvero (campo-AAAA-AA-rigori)

e aggiorna `fonti.csv` con le date e i pesi.

**Non cancella niente che non sostituisca.** Le guide d'agosto restano nei
CSV: a campionato iniziato pesano di meno, non spariscono. Il problema che
risolve e' quello di `raccolta_2026_27.py`, che riscriveva tutti i CSV da capo
con la sola lettura del 3 settembre: rilanciarlo cancellava in silenzio ogni
lettura successiva. Qui ogni lettura ha la sua cartella, e rilanciare lo
stesso comando sulla stessa cartella da' sempre gli stessi file.

Uso:
    python aggiorna_letture.py               l'ultima cartella in letture/
    python aggiorna_letture.py 2026-09-28    una lettura precisa

Poi, come sempre:
    python ../../pipeline/build.py
    python ../../pipeline/consenso.py
"""
import collections, csv, io, json, os, sys

QUI = os.path.dirname(os.path.abspath(__file__))
FONTI = os.path.dirname(QUI)
DATABASE = os.path.dirname(FONTI)
LETTURE = os.path.join(QUI, 'letture')
sys.path.insert(0, os.path.join(os.path.dirname(DATABASE), 'motore'))
import stagione

# Quanto pesa ogni fonte nel consenso. Le probabili formazioni di giornata e
# quello che e' successo in campo valgono il doppio di una guida; le guide
# scritte ad agosto, a campionato cominciato, valgono meno: raccontano chi
# pensava di giocare, non chi sta giocando. Non si buttano, perche' su chi
# e' fermo o in ballottaggio dicono ancora qualcosa.
PESO_GIORNATA = 2.0
PESO_CAMPO = 2.0
PESO_RIGORI_FANTACALCIO = 1.5
PESO_RIGORI_CAMPO = 1.5
PESO_GUIDE_AGOSTO = {'fantacalcio-online': 0.75, 'sosfanta': 0.5,
                     'calciodangolo': 0.5, 'fantamaster': 0.5,
                     'fantamaster-g3': 0.5}
# Da quante giornate giocate le guide d'agosto scendono di peso.
GIORNATE_PER_SCALARE = 3


def _psv(percorso):
    with io.open(percorso, encoding='utf-8') as f:
        righe = [l.rstrip('\n').split('|') for l in f if l.strip()]
    testa = righe[0]
    return [dict(zip(testa, r)) for r in righe[1:]]


def _csv(percorso):
    with io.open(percorso, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def _scrivi(percorso, campi, righe):
    with io.open(percorso, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campi, lineterminator='\n',
                           extrasaction='ignore')
        w.writeheader()
        w.writerows(righe)
    print('  %-40s %5d righe' % (os.path.relpath(percorso, DATABASE), len(righe)))


def _numero(testo):
    """'6,62' -> 6.62; '' -> ''."""
    testo = (testo or '').strip().replace(',', '.')
    if testo in ('', '-'):
        return ''
    try:
        x = float(testo)
    except ValueError:
        return ''
    return int(x) if x == int(x) else x


def _cerca(nome):
    for f in sorted(os.listdir(CARTELLA)):
        if f.startswith(nome):
            return os.path.join(CARTELLA, f)
    return None


# ------------------------------------------------------------ listone
def aggiorna_listone(data):
    """Quotazioni, FVM, squadre e giocatori nuovi dal listone ufficiale.

    La quotazione che il programma usa e' quella **attuale** (QA): e' quella
    che la stanza vede la sera dell'asta. La prima lettura del 7 settembre
    aveva fatto lo stesso, per questo a meta' stagione i numeri si muovono.
    """
    p = _cerca('quotazioni')
    if not p:
        return None
    seed_p = os.path.join(FONTI, 'seed_giocatori_correnti.csv')
    with io.open(seed_p, encoding='utf-8', newline='') as f:
        lettore = csv.DictReader(f)
        campi = lettore.fieldnames
        seed = list(lettore)
    per_id = dict((int(r['id_ufficiale']), r) for r in seed if r.get('id_ufficiale'))
    ufficiale = _psv(p)

    # Il nome della squadra come lo scrive il listone, dalla sigla della pagina.
    squadra_di = {}
    for r in ufficiale:
        voce = per_id.get(int(r['id']))
        if voce:
            squadra_di.setdefault(r['squadra_slug'], collections.Counter())[voce['squadra']] += 1
    squadra_di = dict((k, v.most_common(1)[0][0]) for k, v in squadra_di.items())

    nomi = set(r['nome'] for r in seed)
    nuovi = cambiati = 0
    for r in ufficiale:
        ident = int(r['id'])
        squadra = squadra_di.get(r['squadra_slug'])
        voce = per_id.get(ident)
        if voce is None:
            if not squadra or r['giocatore'] in nomi:
                print('    da controllare a mano: %s (%s)' % (r['giocatore'], r['squadra_slug']))
                continue
            voce = dict((c, '') for c in campi)
            voce.update({'ruolo': r['ruolo'], 'nome': r['giocatore'],
                         'squadra': squadra,
                         'note': 'aggiunto dal listone ufficiale del %s' % data,
                         'id_ufficiale': str(ident)})
            seed.append(voce)
            per_id[ident] = voce
            nomi.add(r['giocatore'])
            nuovi += 1
        prima = (voce['qt_fanta'], voce.get('fvm'), voce['squadra'], voce['ruolo'])
        voce['qt_fanta'] = r['qa']
        voce['fvm'] = r['fvm']
        if squadra:
            voce['squadra'] = squadra
        voce['ruolo'] = r['ruolo']
        if prima != (voce['qt_fanta'], voce.get('fvm'), voce['squadra'], voce['ruolo']):
            cambiati += 1
    _scrivi(seed_p, campi, seed)
    print('    %d giocatori nuovi, %d con quotazione o squadra cambiata' % (nuovi, cambiati))
    return dict((int(r['id_ufficiale']), r) for r in seed if r.get('id_ufficiale'))


# -------------------------------------------------------- formazioni
def aggiorna_formazioni(listone, giocate, data):
    p = os.path.join(QUI, 'formazioni_tipo.csv')
    righe = _csv(p)
    campi = ['fonte', 'squadra', 'modulo', 'posto', 'giocatore', 'ruolo', 'pct', 'id']
    nuove_fonti = set()

    prob = _cerca('probabili')
    giornata = ''
    if prob:
        giornata = os.path.basename(prob).split('_')[1].split('.')[0].lstrip('g')
        nuove_fonti.add('fantacalcio.it')
    stat = _cerca('statistiche')
    fonte_campo = 'campo-' + stagione.CORRENTE
    if stat and giocate > 0:
        nuove_fonti.add(fonte_campo)

    tenute = [r for r in righe if r['fonte'] not in nuove_fonti]
    if prob:
        for r in _psv(prob):
            posto = int(r['posto']) + (11 if r['sezione'] == 'R' else 0)
            tenute.append({'fonte': 'fantacalcio.it', 'squadra': r['squadra'],
                           'modulo': r['modulo'], 'posto': posto,
                           'giocatore': r['giocatore'], 'ruolo': r['ruolo'],
                           'pct': r['pct'], 'id': r['id']})
    if stat and giocate > 0:
        # Chi ha preso voto, e quante volte, nelle giornate gia' giocate: e'
        # l'unica fonte che non e' un'opinione.
        for r in _psv(stat):
            voce = listone.get(int(r['id']))
            pv = int(_numero(r['pv']) or 0)
            if not voce or pv <= 0:
                continue
            tenute.append({'fonte': fonte_campo, 'squadra': voce['squadra'],
                           'modulo': '', 'posto': '', 'giocatore': voce['nome'],
                           'ruolo': voce['ruolo'],
                           'pct': int(round(100.0 * min(pv, giocate) / giocate)),
                           'id': r['id']})
    _scrivi(p, campi, tenute)

    # I ballottaggi della giornata vecchia se ne vanno con la sua formazione.
    if prob:
        pb = os.path.join(QUI, 'ballottaggi.csv')
        b = _csv(pb)
        _scrivi(pb, ['fonte', 'squadra', 'giocatore_a', 'giocatore_b', 'pct_a', 'pct_b'],
                [r for r in b if r['fonte'] != 'fantacalcio.it'])
    return giornata


# --------------------------------------------------- statistiche in corso
def stagione_in_corso(listone):
    """Le giornate giocate, nel formato dei listoni delle stagioni scorse."""
    p = _cerca('statistiche')
    if not p:
        return 0
    righe = []
    for r in _psv(p):
        voce = listone.get(int(r['id']))
        if not voce:
            continue
        segnati, _, calciati = (r.get('rig_segnati_calciati') or '0/0').partition('/')
        segnati, calciati = int(segnati or 0), int(calciati or 0)
        righe.append({'id': r['id'], 'ruolo': voce['ruolo'], 'nome': voce['nome'],
                      'squadra': voce['squadra'], 'pg': _numero(r['pv']),
                      'mv': _numero(r['mv']), 'mf': _numero(r['fm']),
                      'gf': _numero(r['gol']), 'gs': _numero(r['gs']),
                      'rp': _numero(r['rp']), 'rc': calciati, 'rpiu': segnati,
                      'rmeno': calciati - segnati, 'ass': _numero(r['ass']),
                      'amm': _numero(r['amm']), 'esp': _numero(r['esp']), 'au': ''})
    righe.sort(key=lambda r: int(r['id']))
    _scrivi(os.path.join(FONTI, 'seed_listone_stagione_in_corso.csv'),
            ['id', 'ruolo', 'nome', 'squadra', 'pg', 'mv', 'mf', 'gf', 'gs', 'rp',
             'rc', 'rpiu', 'rmeno', 'ass', 'amm', 'esp', 'au'], righe)
    return len(righe)


def understat():
    """Minuti e xG della stagione in corso, nello stesso formato degli altri anni."""
    p = _cerca('understat_')
    if not p:
        return 0
    anno = os.path.basename(p).split('_')[1].split('.')[0]
    giocatori = []
    for r in _psv(p):
        voce = dict(r)
        voce['id'] = r['id']
        giocatori.append(voce)
    uscita = os.path.join(FONTI, 'understat_seriea_%s.json' % anno)
    with io.open(uscita, 'w', encoding='utf-8') as f:
        json.dump({'players': giocatori}, f, ensure_ascii=False, indent=0)
    print('  %-40s %5d giocatori' % (os.path.relpath(uscita, DATABASE), len(giocatori)))
    return len(giocatori)


# ------------------------------------------------------ infortuni, rigori
def infortuni():
    p = os.path.join(CARTELLA, 'infortuni.csv')
    if not os.path.exists(p):
        return False
    righe = _csv(p)
    _scrivi(os.path.join(QUI, 'infortuni.csv'),
            ['squadra', 'giocatore', 'problema', 'rientro_testo', 'rientro_stimato'],
            righe)
    return True


def rigoristi(listone):
    p = os.path.join(QUI, 'rigoristi.csv')
    fonte_campo = 'campo-%s-rigori' % stagione.CORRENTE
    nuove = set()
    aggiunte = []
    pf = _cerca('rigoristi_fantacalcio')
    if pf:
        nuove.add('fantacalcio.it-rigori')
        for r in _psv(pf):
            aggiunte.append({'fonte': 'fantacalcio.it-rigori', 'squadra': r['squadra'],
                             'ordine': r['ordine'], 'giocatore': r['giocatore']})
    ps = _cerca('statistiche')
    if ps:
        nuove.add(fonte_campo)
        for r in _psv(ps):
            voce = listone.get(int(r['id']))
            calciati = int(((r.get('rig_segnati_calciati') or '0/0').partition('/')[2]) or 0)
            if voce and calciati > 0:
                aggiunte.append({'fonte': fonte_campo, 'squadra': voce['squadra'],
                                 'ordine': 1, 'giocatore': voce['nome']})
    righe = [r for r in _csv(p) if r['fonte'] not in nuove] + aggiunte
    _scrivi(p, ['fonte', 'squadra', 'ordine', 'giocatore'], righe)


def aggiorna_fonti(data, giocate, giornata):
    p = os.path.join(QUI, 'fonti.csv')
    righe = _csv(p)
    per_nome = collections.OrderedDict((r['fonte'], r) for r in righe)

    def metti(nome, **kw):
        voce = per_nome.setdefault(nome, {'fonte': nome, 'url': '', 'tipo': '',
                                          'peso': '1.0', 'letta_il': '', 'nota': ''})
        voce.update(dict((k, str(v)) for k, v in kw.items()))

    if giornata:
        metti('fantacalcio.it',
              url='https://www.fantacalcio.it/probabili-formazioni-serie-a',
              tipo='probabili formazioni della giornata, titolari e panchina con percentuali di impiego',
              peso=PESO_GIORNATA, letta_il=data,
              nota='giornata %s: tutte e venti le squadre, con la panchina e la probabilita di impiego di ciascuno' % giornata)
    if giocate > 0 and _cerca('statistiche'):
        metti('campo-' + stagione.CORRENTE,
              url='https://www.fantacalcio.it/statistiche-serie-a/%s/fantacalcio/medie' % stagione.CORRENTE,
              tipo='partite a voto nelle giornate gia giocate',
              peso=PESO_CAMPO, letta_il=data,
              nota='quota = partite a voto / %d giornate giocate' % giocate)
        metti('campo-%s-rigori' % stagione.CORRENTE,
              url='https://www.fantacalcio.it/statistiche-serie-a/%s/fantacalcio/medie' % stagione.CORRENTE,
              tipo='chi ha calciato i rigori in campionato',
              peso=PESO_RIGORI_CAMPO, letta_il=data, nota='')
    if _cerca('rigoristi_fantacalcio'):
        metti('fantacalcio.it-rigori', url='https://www.fantacalcio.it/rigoristi-serie-a',
              tipo='gerarchie dal dischetto', peso=PESO_RIGORI_FANTACALCIO,
              letta_il=data, nota='')
    if os.path.exists(os.path.join(CARTELLA, 'infortuni.csv')):
        n = len(_csv(os.path.join(CARTELLA, 'infortuni.csv')))
        metti('fantacalcio.it-infortuni', url='https://www.fantacalcio.it/infortunati-serie-a',
              tipo='infortunati e indisponibili', letta_il=data,
              nota='riletta per intero il %s: %d indisponibili' % (data, n))
    if giocate >= GIORNATE_PER_SCALARE:
        for nome, peso in PESO_GUIDE_AGOSTO.items():
            if nome in per_nome:
                voce = per_nome[nome]
                voce['peso'] = str(peso)
                if 'pesata meno' not in voce['nota']:
                    voce['nota'] = ((voce['nota'] + '; ') if voce['nota'] else '') + (
                        'guida di inizio stagione: pesata meno dopo %d giornate giocate' % giocate)
    _scrivi(p, ['fonte', 'url', 'tipo', 'peso', 'letta_il', 'nota'], list(per_nome.values()))


# ---------------------------------------------------------------- main
def main(argv):
    global CARTELLA
    date = sorted(d for d in os.listdir(LETTURE) if os.path.isdir(os.path.join(LETTURE, d)))
    data = argv[1] if len(argv) > 1 else date[-1]
    CARTELLA = os.path.join(LETTURE, data)
    if not os.path.isdir(CARTELLA):
        raise SystemExit('nessuna lettura in %s' % CARTELLA)
    cal = [(r['giornata'], r['data'])
           for r in _csv(os.path.join(DATABASE, 'calendario.csv'))]
    giocate = stagione.giornate_giocate(cal, data)
    print('Lettura del %s: %d giornate giocate' % (data, giocate))

    listone = aggiorna_listone(data) or dict(
        (int(r['id_ufficiale']), r)
        for r in _csv(os.path.join(FONTI, 'seed_giocatori_correnti.csv'))
        if r.get('id_ufficiale'))
    giornata = aggiorna_formazioni(listone, giocate, data)
    stagione_in_corso(listone)
    understat()
    infortuni()
    rigoristi(listone)
    aggiorna_fonti(data, giocate, giornata)


CARTELLA = None

if __name__ == '__main__':
    main(sys.argv)
