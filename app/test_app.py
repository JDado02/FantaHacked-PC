# -*- coding: utf-8 -*-
"""Collaudo dell'applicazione: un'asta intera, attraverso l'API vera.

Non e' un test di unita': parla HTTP con il server come farebbe il browser,
gioca 200 chiamate rispettando le fasi per ruolo, e controlla che alla fine
tutte e otto le rose siano complete e che nessuno abbia sforato. Serve a
prendere i guai che si vedono solo agli estremi: gli ultimi slot, i crediti
che finiscono, un reparto che si satura.

Uso:
    python test_app.py            avvia un server di prova e lo collauda
    python test_app.py 8730       collauda un server gia' avviato
"""
import json, os, random, shutil, subprocess, sys, tempfile, time
import urllib.error
import urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
RUOLI = ('P', 'D', 'C', 'A')

ok = fail = 0

# L'ambiente con cui e' stato avviato il server delle prove: serve alla
# verifica [7], che deve poter lanciare un intruso **sullo stesso database**.
AMBIENTE = None


def verifica(descrizione, condizione, dettaglio=''):
    global ok, fail
    if condizione:
        ok += 1
        print('  OK   %s' % descrizione)
    else:
        fail += 1
        print('  FAIL %s   %s' % (descrizione, dettaglio))


class Cliente(object):
    def __init__(self, porta):
        self.base = 'http://127.0.0.1:%d' % porta

    def _chiama(self, percorso, corpo=None):
        dati = None if corpo is None else json.dumps(corpo).encode('utf-8')
        req = urllib.request.Request(self.base + percorso, data=dati,
                                     headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return {'errore': json.loads(e.read().decode('utf-8')).get('errore'),
                    'codice': e.code}

    get = lambda self, p: self._chiama(p)
    post = lambda self, p, c=None: self._chiama(p, c or {})


def attendi(cliente, secondi=60):
    scadenza = time.time() + secondi
    while time.time() < scadenza:
        try:
            if cliente.get('/api/ping').get('app') == 'FantaHacked':
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def attendi_porta(cartella, secondi=40.0):
    """La porta che il server delle prove si e' scelto.

    La scrive accanto al proprio database appena l'ha aperta. Se non arriva si
    ripiega sulla porta preferita, cosi' l'errore che si vede e' quello vero
    ("il server non risponde") e non un file mancante.
    """
    percorso = os.path.join(cartella, 'fanta.porta')
    scadenza = time.time() + secondi
    while time.time() < scadenza:
        try:
            with open(percorso, encoding='utf-8') as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            time.sleep(0.3)
    return 8730


def main():
    processo = None
    prove = None
    if len(sys.argv) > 1:
        porta = int(sys.argv[1])
        cliente = Cliente(porta)
    else:
        porta = 8790
        env = dict(os.environ)
        # **Le prove girano su una copia usa e getta del database.** Ogni
        # verifica comincia con una "nuova asta", e una nuova asta cancella
        # quella precedente: puntate al file vero, queste duecento chiamate
        # distruggono l'asta che l'utente ha in corso senza chiedere niente a
        # nessuno. E' successo, e non deve poter succedere di nuovo.
        prove = tempfile.mkdtemp(prefix='fantahacked_prove_')
        copia = os.path.join(prove, 'asta.db')
        base = os.path.join(QUI, '..')
        if os.path.exists(os.path.join(base, 'motore', 'asta.db')):
            shutil.copyfile(os.path.join(base, 'motore', 'asta.db'), copia)
        # Anche i dati: le prove possono ricalcolare le proiezioni, che stanno
        # li' dentro, e il file vero non lo devono toccare.
        copia_dati = os.path.join(prove, 'dati.db')
        shutil.copyfile(os.path.join(base, 'database', 'dati.db'), copia_dati)
        env['FANTAHACKED_DB'] = copia
        env['FANTAHACKED_DATI'] = copia_dati
        # Niente rete durante il collaudo: le prove non devono dipendere da
        # una release pubblicata, ne' andarla a scaricare duecento volte.
        env['FANTAHACKED_NIENTE_RETE'] = '1'
        env['FANTAHACKED_PREFERENZE'] = os.path.join(prove, 'preferenze.json')
        globals()['AMBIENTE'] = env
        processo = subprocess.Popen(
            [sys.executable, os.path.join(QUI, 'server.py'), '--no-browser'],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        # Su che porta sia finito lo dice lui, scrivendolo accanto al proprio
        # database. Non e' un dettaglio: prima le prove bussavano alla 8730 e
        # basta, e con il programma dell'utente aperto quella porta e' sua.
        cliente = Cliente(attendi_porta(prove))
    print('Attendo il server...')
    if not attendi(cliente):
        print('Il server non risponde.')
        return 1

    # **Il server che risponde e' quello che abbiamo avviato noi?** Se un
    # FantaHacked era gia' acceso, si e' preso lui la porta e il nostro e'
    # uscito per via del lucchetto: le prove parlerebbero con l'istanza
    # dell'utente, e la prima "nuova asta" cancellerebbe l'asta vera. E'
    # successo. Adesso il server dichiara su che database sta lavorando, e se
    # non e' la copia usa e getta ci si ferma prima di toccare qualsiasi cosa.
    if prove:
        ping = cliente.get('/api/ping')
        # Due file, non uno. Il database e' l'asta in corso; le preferenze
        # sono i nomi delle squadre, digitati una volta e mai piu'. Le prove
        # bruciano tutti e due, e la seconda volta e' andata proprio cosi':
        # l'asta si e' salvata, i nomi sono diventati "Bea, Chiara, Dario".
        atteso = {'database': copia,
                  'preferenze': os.path.join(prove, 'preferenze.json')}
        for chiave, giusto in atteso.items():
            attivo = ping.get(chiave) or ''
            if os.path.abspath(attivo) != os.path.abspath(giusto):
                print("\nATTENZIONE: risponde un FantaHacked gia' "
                      "avviato, che lavora su\n  %s\nChiudilo e rilancia "
                      "le prove: cosi' cancellerebbero l'asta vera e i "
                      "nomi veri." % (attivo or 'altri file'))
                return 1

    try:
        return collauda(cliente)
    finally:
        if processo:
            try:
                cliente.post('/api/spegni')
                processo.wait(timeout=10)
            except Exception:
                processo.kill()
        if prove:
            shutil.rmtree(prove, ignore_errors=True)


def collauda(c):
    nomi = ['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo']

    print('\n[1] Nuova asta')
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    verifica('l\'asta parte con 8 presidenti', len(st['presidenti']) == 8)
    verifica('la prima fase e\' quella dei portieri', st['fase'] == 'P')
    verifica('tutti partono con i crediti pieni',
             all(p['crediti'] == st['regole']['crediti'] for p in st['presidenti']))
    verifica('il turno e\' assegnato', st['turno'] is not None)
    verifica('nessuno ha ancora giocatori',
             all(sum(p['slot'].values()) == 0 for p in st['presidenti']))

    print('\n[2] Ricerca e scheda')
    trovati = c.get('/api/cerca?q=dimarco')
    verifica('la ricerca trova Dimarco', any(x['nome'] == 'Dimarco' for x in trovati),
             str(trovati)[:120])
    dim = [x for x in trovati if x['nome'] == 'Dimarco'][0]
    sch = c.get('/api/scheda?id=%d' % dim['id'])
    verifica('la scheda ha un verdetto', bool(sch.get('verdetto')))
    verifica('il max_bid non supera la liquidita\'',
             sch['max_bid'] <= sch['liquidita'],
             'max=%s liq=%s' % (sch['max_bid'], sch['liquidita']))
    verifica('la scheda elenca le alternative', len(sch['alternative']) > 0)
    verifica('sette avversari possono rilanciare', len(sch['concorrenti']) == 7)

    print('\n[3] Vincoli')
    r = c.post('/api/acquisto', {'id': dim['id'], 'presidente': 2, 'prezzo': 0})
    verifica('prezzo zero rifiutato', r.get('codice') == 400, str(r)[:90])
    r = c.post('/api/acquisto', {'id': dim['id'], 'presidente': 2, 'prezzo': 500})
    verifica('offerta che svuota la cassa rifiutata', r.get('codice') == 400)
    st = c.post('/api/acquisto', {'id': dim['id'], 'presidente': 2, 'prezzo': 100})
    verifica('acquisto valido registrato',
             st['presidenti'][1]['crediti'] == 400 if not st.get('errore') else False,
             str(st)[:120])
    r = c.post('/api/acquisto', {'id': dim['id'], 'presidente': 3, 'prezzo': 50})
    verifica('doppio acquisto rifiutato', r.get('codice') == 400)
    st = c.post('/api/annulla', {'id': dim['id']})
    verifica('annullamento riporta i crediti',
             all(p['crediti'] == 500 for p in st['presidenti']))

    print('\n[4] Turno')
    st = c.post('/api/turno', {'presidente': 5})
    verifica('il turno si puo\' assegnare', st['turno'] == 5)
    st = c.post('/api/avanza')
    verifica('il turno avanza al successivo', st['turno'] == 6)

    print('\n[4b] Input ostili')
    # Un'interfaccia sbagliata, un doppio clic sfortunato o una richiesta
    # scritta a mano non devono mai poter buttare giu' il motore in asta.
    grezzo = [
        ('GET', '/api/scheda', None, 400),
        ('GET', '/api/scheda?id=abc', None, 400),
        ('GET', '/api/scheda?id=1.5', None, 400),
        ('GET', '/api/cerca?q=vi&n=abc', None, 400),
        ('GET', '/api/rosa?presidente=abc', None, 400),
        ('GET', '/api/rosa?presidente=99', None, 400),
        ('GET', '/api/inventato', None, 404),
        ('POST', '/api/turno', {'presidente': 'x'}, 400),
        ('POST', '/api/turno', {}, 400),
        ('POST', '/api/acquisto', {}, 400),
        ('POST', '/api/acquisto', {'id': 'x', 'presidente': 1, 'prezzo': 5}, 400),
        ('POST', '/api/acquisto', {'id': 1, 'presidente': 1, 'prezzo': None}, 400),
        ('POST', '/api/nuova', {'mio_nome': 'X', 'avversari': 'non-un-elenco'}, 400),
    ]
    sbagliati = []
    for metodo, percorso, corpo, atteso in grezzo:
        r = c._chiama(percorso, corpo) if metodo == 'POST' else c.get(percorso)
        if r.get('codice') != atteso and not (atteso == 200 and 'codice' not in r):
            sbagliati.append('%s %s -> %s invece di %s'
                             % (metodo, percorso, r.get('codice'), atteso))
    verifica('gli input non validi danno un errore chiaro, non un guasto',
             not sbagliati, '; '.join(sbagliati)[:200])
    verifica('il motore e\' ancora vivo dopo gli input ostili',
             c.get('/api/ping').get('app') == 'FantaHacked')

    # Nessun file fuori da app/web deve poter uscire dal server. Su Windows
    # os.path.join scarta la cartella base davanti a una lettera di unita':
    # senza il controllo sul percorso risolto si servivano file di sistema.
    fughe = []
    for percorso in ('/C:/Windows/win.ini', '//C:/Windows/win.ini',
                     '/app/server.py', '/motore/fanta.db',
                     '/../../server.py', '/%2e%2e/server.py'):
        try:
            with urllib.request.urlopen(c.base + percorso, timeout=10) as r:
                if r.status == 200:
                    fughe.append(percorso)
        except urllib.error.HTTPError:
            pass
        except Exception:
            pass
    verifica('nessun file fuori dall\'interfaccia e\' raggiungibile', not fughe,
             str(fughe))

    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    lungo = c.post('/api/nuova', {'mio_nome': 'X' * 400, 'avversari': nomi})
    verifica('un nome lunghissimo viene accorciato, non sfonda la barra',
             len(lungo['presidenti'][0]['nome']) <= 24,
             'lungo %d' % len(lungo['presidenti'][0]['nome']))

    trovati = c.get('/api/cerca?q=dimarco')
    dim2 = [x for x in trovati if x['nome'] == 'Dimarco'][0]
    st = c.post('/api/acquisto', {'id': dim2['id'], 'presidente': 2, 'prezzo': 3.7})
    rosa = c.get('/api/rosa?presidente=2')
    verifica('un prezzo decimale viene arrotondato, non troncato',
             rosa['D'] and rosa['D'][0]['prezzo'] == 4,
             str(rosa['D'])[:80])

    print('\n[4c] Portieri a pacchetto')
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    if st['regole'].get('portieri_pacchetto'):
        # Chi prende il titolare prende anche le riserve a 1 credito: il
        # reparto si chiude in un colpo solo, e quell'avversario esce dai
        # concorrenti per ogni altro portiere.
        listone = c.get('/api/listone?ruolo=P&n=200')
        capo = listone['righe'][0]
        sc_capo = c.get('/api/scheda?id=%d' % capo['id'])
        verifica('la scheda del titolare elenca le riserve in dote',
                 len(sc_capo.get('pacchetto') or []) >= 1,
                 str(sc_capo.get('pacchetto'))[:80])
        st = c.post('/api/acquisto', {'id': capo['id'], 'presidente': 2, 'prezzo': 40})
        verifica('le riserve vengono registrate insieme al titolare',
                 len(st.get('pacchetto') or []) >= 1, str(st.get('pacchetto'))[:80])
        avv = [p for p in st['presidenti'] if p['id'] == 2][0]
        n_riserve = len(st.get('pacchetto') or [])
        verifica('il reparto portieri si riempie in un colpo solo',
                 avv['slot']['P'] == 1 + n_riserve,
                 'slot P = %d' % avv['slot']['P'])
        verifica('le riserve costano un credito ciascuna',
                 avv['crediti'] == st['regole']['crediti'] - 40 - n_riserve,
                 'crediti %d' % avv['crediti'])
        libero = [x for x in c.get('/api/listone?ruolo=P&n=200')['righe']
                  if not x['venduto']][0]
        sc = c.get('/api/scheda?id=%d' % libero['id'])
        if avv['slot']['P'] >= st['regole']['slot']['P']:
            verifica('chi ha chiuso il reparto esce dai concorrenti',
                     all(x['id'] != 2 for x in sc['concorrenti']))
        st = c.post('/api/annulla', {'id': capo['id']})
        avv = [p for p in st['presidenti'] if p['id'] == 2][0]
        verifica('annullare il titolare riporta indietro anche le riserve',
                 avv['slot']['P'] == 0 and avv['crediti'] == st['regole']['crediti'],
                 'slot %d crediti %d' % (avv['slot']['P'], avv['crediti']))

    print('\n[4c-bis] Le riserve del portiere si possono sostituire')
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    if st['regole'].get('portieri_pacchetto'):
        capo = c.get('/api/listone?ruolo=P&n=200')['righe'][0]
        st = c.post('/api/acquisto', {'id': capo['id'], 'presidente': 1, 'prezzo': 40})
        rosa = c.get('/api/rosa?presidente=1')
        n_prima = len(rosa['P'])
        terzo = rosa['P'][-1]
        st = c.post('/api/annulla', {'id': terzo['id']})
        mio = [p for p in st['presidenti'] if p['id'] == 1][0]
        verifica('si puo\' togliere una singola riserva senza perdere il titolare',
                 mio['slot']['P'] == n_prima - 1 and mio['crediti'] == 459,
                 'slot %d crediti %d' % (mio['slot']['P'], mio['crediti']))
        liberi = [x for x in c.get('/api/listone?ruolo=P&n=200')['righe']
                  if not x['venduto']]
        scelto = liberi[3]
        st = c.post('/api/acquisto', {'id': scelto['id'], 'presidente': 1, 'prezzo': 7})
        mio = [p for p in st['presidenti'] if p['id'] == 1][0]
        verifica('al suo posto se ne compra un altro al prezzo che decido io',
                 mio['slot']['P'] == n_prima and mio['crediti'] == 452,
                 'slot %d crediti %d' % (mio['slot']['P'], mio['crediti']))
        verifica('sostituendo non arrivano riserve indesiderate',
                 not st.get('pacchetto'), str(st.get('pacchetto')))

    print('\n[4d] Piano B e riserve di budget')
    # Da un'asta pulita: la prova precedente lascia il reparto portieri gia'
    # completo, e a reparto pieno non c'e' nessun ripiego da proporre.
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    cons = c.get('/api/consiglio')
    verifica("c'e' sempre un ripiego proposto, non solo gli obiettivi",
             len(cons.get('ripiego') or []) > 0, str(cons.get('ripiego'))[:60])
    verifica('il consiglio dice quanti crediti spettano al reparto',
             cons.get('budget_ruolo', 0) > 0)
    piano = c.get('/api/piano')
    ris = piano.get('riserva') or {}
    verifica('il piano rispetta la riserva minima degli attaccanti',
             piano['per_ruolo']['A']['crediti'] >= ris.get('A', 0),
             'piano %s riserva %s' % (piano['per_ruolo']['A']['crediti'], ris.get('A')))
    # Sbagliare a registrare l'acquisto di un avversario e' facilissimo in
    # asta, e senza poterlo correggere tutti i conti successivi sono falsi.
    d = c.get('/api/listone?ruolo=D&n=20')['righe'][3]
    st = c.post('/api/acquisto', {'id': d['id'], 'presidente': 4, 'prezzo': 33})
    prima = [p for p in st['presidenti'] if p['id'] == 4][0]['crediti']
    st = c.post('/api/annulla', {'id': d['id']})
    dopo = [p for p in st['presidenti'] if p['id'] == 4][0]
    verifica("si puo' togliere un giocatore dalla rosa di un avversario",
             dopo['crediti'] == st['regole']['crediti'] and dopo['slot']['D'] == 0,
             'prima %d, dopo %d' % (prima, dopo['crediti']))

    print('\n[4e] La lista e la scheda devono dire la stessa cosa')
    # E' stato un difetto vero: un giocatore compariva sotto "da prendere" e
    # aprendolo diceva "lascia". Adesso il verdetto si calcola una volta sola,
    # e questa verifica serve a impedire che si torni a calcolarlo in due posti.
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    cons = c.get('/api/consiglio')
    # RIPIEGO e' un verdetto da lista dei consigli a pieno titolo: dice che
    # al prezzo suo rende piu' della media del reparto, ma che per quello
    # slot il motore ha una prima scelta. In un reparto da uno slot solo
    # - i portieri a pacchetto - e' il verdetto di tutti tranne uno.
    VALE = ('OCCASIONE', 'PRENDILO', 'AL PREZZO GIUSTO', 'DA UN CREDITO',
            'RIPIEGO')
    discordi, fuori_posto = [], []
    for gruppo in ('top', 'evitare', 'alternative', 'svuotare'):
        for d in cons.get(gruppo) or []:
            s = c.get('/api/scheda?id=%d' % d['id'])
            if (s['verdetto'], s['max_bid'], s['chiusura']) != \
               (d['verdetto'], d['max_bid'], d['chiusura']):
                discordi.append('%s: lista %s/%s scheda %s/%s'
                                % (d['nome'], d['verdetto'], d['max_bid'],
                                   s['verdetto'], s['max_bid']))
            if gruppo == 'top' and d['verdetto'] not in VALE:
                fuori_posto.append('%s (%s)' % (d['nome'], d['verdetto']))
    verifica('lista e scheda danno lo stesso verdetto e gli stessi numeri',
             not discordi, '; '.join(discordi)[:200])
    verifica('sotto "top acquisti" ci sono solo giocatori da prendere',
             not fuori_posto, '; '.join(fuori_posto)[:200])
    ids = [d['id'] for gruppo in ('top', 'alternative', 'evitare')
           for d in (cons.get(gruppo) or [])]
    verifica('le tre fasce non si ripetono a vicenda',
             len(ids) == len(set(ids)),
             str([i for i in ids if ids.count(i) > 1][:5]))
    # Un nome non puo' stare fra i consigliati e insieme fra quelli da far
    # pagare agli altri: sarebbe un invito a chiamarlo per poi non prenderlo.
    #
    # Vale per "top acquisti" **e per le alternative**, che sono comunque
    # giocatori che potresti prendere: venti aste ispezionate passo per passo
    # hanno trovato lo stesso nome nelle due sezioni, e la deduplica c'era
    # solo contro la prima. Con "da evitare" invece la sovrapposizione e'
    # giusta: uno che non ti conviene e' esattamente quello su cui far
    # spendere gli altri.
    prendibili = set(d['id'] for gruppo in ('top', 'alternative')
                     for d in (cons.get(gruppo) or []))
    doppi = prendibili & set(d['id'] for d in (cons.get('svuotare') or []))
    verifica('nessuno e\' insieme da prendere e da far pagare agli altri',
             not doppi, str(sorted(doppi)))
    # La classifica deve essere una classifica: se la prima riga non e' la piu'
    # utile, l'ordine sta mentendo, ed e' esattamente il difetto che si voleva
    # togliere mostrando tutto il reparto invece di un nome solo.
    utili = [d['utilita'] for d in (cons.get('top') or [])]
    verifica('i top acquisti sono in ordine di utilita\' per la rosa',
             utili == sorted(utili, reverse=True), str(utili))

    print('\n[4f] Chi gioca davvero, e che squadra ne esce')
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    GRADI = ('titolare', 'ballottaggio', 'rotazione', 'riserva', 'ignoto')
    righe = c.get('/api/listone?n=120')['righe']
    verifica('ogni riga del listone dice se quel giocatore gioca',
             all((r.get('gerarchia') or {}).get('grado') in GRADI for r in righe),
             str([r['nome'] for r in righe
                  if (r.get('gerarchia') or {}).get('grado') not in GRADI][:3]))
    # Il grado deve essere coerente con le presenze: un "titolare" che gioca
    # venti partite sarebbe un'etichetta che mente, ed e' proprio l'etichetta
    # su cui l'utente decidera' di spendere.
    incoerenti = [r['nome'] for r in righe
                  if (r.get('gerarchia') or {}).get('grado') == 'titolare'
                  and r['presenze'] < 25 and r['ruolo'] != 'P']
    verifica('chi e\' segnato titolare ha davvero le presenze di un titolare',
             not incoerenti, str(incoerenti[:5]))
    soli = c.get('/api/listone?n=60&titolari=1')['righe']
    verifica('il filtro "solo titolari" tiene solo i titolari sicuri',
             soli and all(r['gerarchia']['sicuro'] for r in soli),
             str([r['nome'] for r in soli if not r['gerarchia']['sicuro']][:3]))
    verifica('il listone distingue quanto vale da quanto costa',
             all('valore' in r and 'chiusura' in r for r in righe))

    # Il piano B esiste per riempire uno slot in fretta: proporre li' una
    # fantamedia alta prodotta da otto presenze e' il danno peggiore che il
    # programma possa fare.
    cons = c.get('/api/consiglio')
    non_titolari = [d['nome'] for d in (cons.get('ripiego') or [])
                    if not d['gerarchia']['sicuro']]
    verifica('il piano B propone titolari sicuri',
             not non_titolari, str(non_titolari[:4]))
    punteggi = [d.get('punteggio', 0) for d in (cons.get('prendere') or [])]
    verifica('i consigli sono in ordine di utilita\' per la mia rosa',
             punteggi == sorted(punteggi, reverse=True), str(punteggi[:6]))

    q = c.get('/api/equilibrio')
    verifica('il motore dice che squadra sto costruendo',
             q.get('undici', {}).get('modulo') and len(q['undici']['giocatori']) == 11,
             str(q.get('undici', {}).get('modulo')))
    verifica('a rosa vuota le undici caselle risultano tutte scoperte',
             q['undici']['caselle_vuote'] == 11)

    # Un acquisto deve cambiare tutto quello che c'e' a schermo: e' il punto
    # dell'intero programma. Se dopo un acquisto i consigli restano identici,
    # l'utente sta guardando numeri di dieci minuti fa.
    # Prima lo compra un AVVERSARIO: il mio reparto resta aperto, quindi al
    # posto di chi e' sparito ne deve subentrare un altro. (Comprandolo io,
    # con la regola del pacchetto il reparto portieri si chiuderebbe di colpo
    # e la lista sarebbe giustamente vuota: non proverebbe niente.)
    obiettivo = (cons.get('prendere') or cons.get('ripiego'))[0]
    prima_prezzi = dict((r['id'], r['chiusura']) for r in righe)
    c.post('/api/acquisto', {'id': obiettivo['id'], 'presidente': 3,
                             'prezzo': max(1, obiettivo['chiusura'])})
    dopo = c.get('/api/consiglio')
    dopo_righe = c.get('/api/listone?n=120')['righe']
    proposti = [d['id'] for d in (dopo.get('prendere') or [])
                + (dopo.get('ripiego') or [])]
    verifica('chi e\' stato appena preso sparisce dai consigli',
             obiettivo['id'] not in proposti)
    verifica('al suo posto ne subentra un altro', len(proposti) > 0,
             'la lista si e\' svuotata')
    cambiati = sum(1 for r in dopo_righe
                   if r['id'] in prima_prezzi and r['chiusura'] != prima_prezzi[r['id']])
    verifica('i prezzi degli altri si ricalcolano dopo ogni acquisto',
             cambiati > 0, 'nessun prezzo si e\' mosso')
    # E adesso uno per me: la squadra a schermo deve cambiare.
    mio = [d for d in (dopo.get('prendere') or []) + (dopo.get('ripiego') or [])][0]
    c.post('/api/acquisto', {'id': mio['id'], 'presidente': 1,
                             'prezzo': max(1, mio['chiusura'])})
    q2 = c.get('/api/equilibrio')
    verifica('la mia squadra si aggiorna con l\'acquisto',
             q2['in_rosa'] >= 1 and q2['undici']['caselle_vuote'] <= 10,
             'caselle %d, in rosa %d' % (q2['undici']['caselle_vuote'], q2['in_rosa']))

    print(chr(10) + "[4g] Giocatori complementari: comprarli insieme copre la maglia")
    # La domanda che ha aperto questo lavoro: due giocatori della stessa
    # squadra che si dividono un posto. Presi insieme, quella maglia e' tua
    # quasi ogni giornata, e il secondo deve costare una frazione del primo.
    #
    # La prova confrontava il limite sul socio **prima e dopo** aver comprato
    # il capo, e cosi' misurava due cose insieme: il bonus della coppia, che
    # lo alza, e i crediti appena spesi, che lo abbassano. Finche' le coppie
    # pescate erano di gente da pochi crediti vinceva il primo effetto; da
    # quando in cima al listone ci sono coppie da quaranta crediti vince il
    # secondo, e la prova falliva pur essendo tutto a posto.
    #
    # Il confronto giusto e' a parita' di spesa: comprare il capo della coppia
    # contro comprare un estraneo dello stesso ruolo allo stesso prezzo. Cosi'
    # resta solo la differenza che interessa.
    st = c.post("/api/nuova", {"mio_nome": "Davide", "avversari": nomi})
    coppie = []
    for r in c.get("/api/listone?n=600")["righe"]:
        sc = c.get("/api/scheda?id=%d" % r["id"])
        comp = [x for x in (sc.get("compagni_di_maglia") or [])
                if x["stato"] == "libero" and x["copertura_buchi"] >= 0.8]
        if comp:
            coppie.append((sc, comp[0]))
            if len(coppie) >= 5:
                break
    verifica("esiste almeno una coppia complementare con alta copertura",
             len(coppie) > 0)

    def _estraneo(ruolo, escludi, socio_id):
        """Un giocatore dello stesso ruolo che col socio non c'entra niente."""
        for r in c.get("/api/listone?ruolo=%s&n=200" % ruolo)["righe"]:
            if r["id"] in escludi:
                continue
            sc = c.get("/api/scheda?id=%d" % r["id"])
            soci = [x["id"] for x in (sc.get("compagni_di_maglia") or [])]
            if socio_id not in soci:
                return r["id"]
        return None

    meglio = pari = peggio = 0
    detto = None
    for capo, comp in coppie:
        prezzo = max(1, capo["costo_atteso"])
        estraneo = _estraneo(capo["ruolo"], {capo["id"], comp["id"]}, comp["id"])
        if estraneo is None:
            continue
        c.post("/api/nuova", {"mio_nome": "Davide", "avversari": nomi})
        c.post("/api/acquisto", {"id": capo["id"], "presidente": 1, "prezzo": prezzo})
        con_capo = c.get("/api/scheda?id=%d" % comp["id"])
        c.post("/api/nuova", {"mio_nome": "Davide", "avversari": nomi})
        c.post("/api/acquisto", {"id": estraneo, "presidente": 1, "prezzo": prezzo})
        con_altro = c.get("/api/scheda?id=%d" % comp["id"])["max_bid"]
        if con_capo["max_bid"] > con_altro:
            meglio += 1
        elif con_capo["max_bid"] == con_altro:
            pari += 1
        else:
            peggio += 1
        if detto is None and con_capo.get("chiude_coppia"):
            detto = con_capo["chiude_coppia"]
    verifica("a parita' di spesa il socio vale di piu' se ho comprato il capo",
             meglio > peggio,
             "meglio %d, pari %d, peggio %d" % (meglio, pari, peggio))
    verifica("la scheda del socio dice che chiude la coppia",
             detto is not None and detto.get("con"), str(detto))

    print('\n[4h] I consigli sono una classifica, non un vincitore unico')
    # Il difetto: coi portieri a pacchetto lo slot e' uno solo, il motore
    # eleggeva il migliore e tutti gli altri finivano a "lascia". A schermo
    # restava un nome, e siccome i primi portieri distano fra loro due o tre
    # punti su duecento bastava un acquisto altrui a farlo cambiare. Sembrava
    # un capriccio del programma; era una volata raccontata come se ci fosse un
    # corridore solo.
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    cons = c.get('/api/consiglio')
    verifica('nella fase dei portieri i consigli sono piu\' di uno',
             len(cons['top']) >= 3,
             'top = %s' % [d['nome'] for d in cons['top']])
    verifica('le tre fasce coprono buona parte del reparto',
             len(cons['top']) + len(cons['evitare']) + len(cons['alternative']) >= 10,
             'top %d evitare %d alternative %d' % (len(cons['top']),
                 len(cons['evitare']), len(cons['alternative'])))
    verifica('il consiglio dice quanti giocatori ha valutato',
             cons.get('valutati', 0) >= 10 and
             cons['valutati'] <= cons['liberi_nel_ruolo'],
             '%s su %s' % (cons.get('valutati'), cons.get('liberi_nel_ruolo')))
    # La classifica deve reggere a una perturbazione: se il primo se lo prende
    # un altro, il secondo di prima deve diventare il primo, non deve uscire
    # dalla lista un elenco diverso.
    ordine_prima = [d['id'] for d in cons['top']]
    if len(ordine_prima) >= 2:
        primo = cons['top'][0]
        c.post('/api/acquisto', {'id': primo['id'], 'presidente': 2,
                                 'prezzo': max(1, primo['chiusura'])})
        dopo = c.get('/api/consiglio')
        verifica('tolto il primo, il secondo prende il suo posto',
                 dopo['top'] and dopo['top'][0]['id'] == ordine_prima[1],
                 'atteso %s, trovato %s' % (ordine_prima[1],
                     dopo['top'][0]['id'] if dopo['top'] else None))
        c.post('/api/annulla', {'id': primo['id']})
    # Chi finisce fra quelli da evitare deve costare abbastanza da fare danno:
    # segnalare una trappola da un credito e' rumore.
    poco_cari = [d['nome'] for d in cons['evitare'] if d['chiusura'] < 5]
    verifica('fra quelli da evitare non ci sono riempitivi da un credito',
             not poco_cari, str(poco_cari[:5]))
    # E deve rendere meno di quello che quei crediti comprano nel reparto,
    # altrimenti l'etichetta mente.
    sbagliati = [d['nome'] for d in cons['evitare'] if d['convenienza'] > 0]
    verifica('chi e\' da evitare rende meno di quanto costa',
             not sbagliati, str(sbagliati[:5]))

    print('\n[4i] Il portiere titolare gioca quasi sempre')
    # Il numero era sbagliato, e di molto: 28 presenze su 38 per un primo
    # portiere, cioe' il 74% della stagione. La misura era stata fatta sulla
    # media di tutti i reparti, compresi quelli a cui manca meta' stagione
    # perche' il portiere e' andato all'estero a gennaio e non e' piu' nel
    # listone. Sui reparti completi la media vera e' 35 presenze.
    #
    # Il metro giusto non e' "i piu' cari": e' **quelli su cui le guide sono
    # unanimi**. Mandas sta in alto nei prezzi ma le fonti si dividono sul
    # portiere della Lazio, e dargli trentacinque presenze sarebbe inventare
    # una certezza che non esiste. Sono i titolari certi a dover stare in alto.
    por = [r for r in c.get('/api/listone?ruolo=P&n=200')['righe']
           if (r.get('gerarchia') or {}).get('grado') == 'titolare'
           and (r.get('gerarchia') or {}).get('certezza', 0) >= 0.9]
    verifica("ci sono portieri su cui le guide sono tutte d'accordo",
             len(por) >= 10, '%d trovati' % len(por))
    scarsi = [(r['nome'], r['presenze']) for r in por if r['presenze'] < 30]
    verifica('il portiere dato titolare da tutte le guide gioca sopra le 30',
             not scarsi, str(scarsi[:5]))
    # Un secondo portiere su cui le guide sono d'accordo gioca due partite.
    # Uno **conteso** e' un'altra cosa: da quando si leggono le formazioni
    # della giornata puo' capitare che la guida pre-campionato dica Tornqvist
    # e il campo dica Thiam. Li' sedici presenze non sono un errore, sono
    # l'attesa giusta di una maglia che vale 34 presenze e si vince a meta'.
    # La domanda da fare e' quindi sui portieri su cui il dubbio non c'e'.
    riserve = [r for r in c.get('/api/listone?ruolo=P&n=200')['righe']
               if (r.get('gerarchia') or {}).get('grado') == 'riserva'
               and (r.get('gerarchia') or {}).get('certezza', 0) >= 0.9]
    verifica('il secondo portiere non conteso resta dato per uno che non gioca',
             riserve and all(r['presenze'] <= 15 for r in riserve),
             str([(r['nome'], r['presenze']) for r in riserve[:3]]))
    contesi = [r for r in c.get('/api/listone?ruolo=P&n=200')['righe']
              if (r.get('gerarchia') or {}).get('grado') == 'riserva'
              and r['presenze'] > 15]
    verifica('e se un secondo portiere gioca, e perche' + chr(39) + ' e conteso',
             all((r.get('gerarchia') or {}).get('certezza', 1) < 0.5
                 for r in contesi),
             str([(r['nome'], r['presenze']) for r in contesi[:3]]))

    print('\n[4j] Mezza coppia in rosa: l\'altra meta\' resta sotto gli occhi')
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    # Non fra i portieri: li' comprare il titolare porta in rosa anche le sue
    # riserve, il socio smette di essere libero nello stesso istante, e non
    # resterebbe nessuna coppia da chiudere. E' il comportamento giusto, ma
    # rende quel reparto inutile per verificare questa cosa.
    coppia = None
    for r in c.get('/api/listone?n=530')['righe']:
        if r['ruolo'] == 'P':
            continue
        sc = c.get('/api/scheda?id=%d' % r['id'])
        liberi = [x for x in (sc.get('compagni_di_maglia') or [])
                  if x['stato'] == 'libero']
        if liberi:
            coppia = (sc, liberi[0])
            break
    verifica('nel listone c\'e\' almeno una coppia da chiudere', coppia is not None)
    if coppia:
        mio, socio = coppia
        vuoto = c.get('/api/consiglio')
        verifica('a rosa vuota non c\'e\' nessuna coppia da chiudere',
                 not vuoto.get('coppie'), str(vuoto.get('coppie'))[:120])
        c.post('/api/acquisto', {'id': mio['id'], 'presidente': 1, 'prezzo': 30})
        cons = c.get('/api/consiglio')
        aperte = [x['id'] for x in (cons.get('coppie') or [])]
        verifica('comprata mezza coppia, il socio compare fra quelle da chiudere',
                 socio['id'] in aperte,
                 'socio %s, coppie %s' % (socio['id'], aperte))
        voce = [x for x in cons['coppie'] if x['id'] == socio['id']]
        if voce:
            v = voce[0]
            verifica('la coppia dice di chi e\' il socio e quanto lo copre',
                     v['con'] == mio['nome'] and 0 <= v['copertura_buchi'] <= 1,
                     str(v)[:160])
            # La copertura non puo' promettere piu' giornate di quante il
            # titolare ne salti: era il difetto del numero letto dal file, che
            # dava il 95% a un vice con tre presenze.
            verifica('la copertura non promette piu\' di quanto il titolare salti',
                     v['giornate_coperte'] <= v['buchi'] + 0.51,
                     'coperte %s su buchi %s' % (v['giornate_coperte'], v['buchi']))
        # E non deve stare anche nelle tre fasce: sarebbe lo stesso nome due volte.
        altrove = [g for g in ('top', 'evitare', 'alternative')
                   if any(d['id'] == socio['id'] for d in (cons.get(g) or []))]
        verifica('il socio non compare due volte nello stesso pannello',
                 not altrove, str(altrove))

    print('\n[4k] Ha comprato bene o ha comprato caro')
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    caro = c.get('/api/listone?ruolo=P&n=40')['righe'][0]
    atteso = None
    for r in c.get('/api/rosa?presidente=2').get('P', []):
        atteso = r.get('atteso')
    c.post('/api/acquisto', {'id': caro['id'], 'presidente': 2,
                             'prezzo': min(200, max(2, caro['chiusura'] * 3))})
    r2 = c.get('/api/rosa?presidente=2')
    b = r2.get('bilancio') or {}
    verifica('chi paga il triplo risulta in negativo',
             b.get('verso') == 'negativo', str(b)[:160])
    verifica('il bilancio dice quanto ha speso e quanto vale',
             b.get('speso', 0) > 0 and b.get('atteso', 0) > 0 and
             b.get('scarto') == b['speso'] - b['atteso'], str(b)[:160])
    pagati = [x for x in r2.get('P', []) if x.get('scarto') is not None]
    verifica('ogni acquisto dice di quanto si e\' scostato dal prezzo atteso',
             len(pagati) == len(r2.get('P', [])),
             str([(x['nome'], x.get('scarto')) for x in r2.get('P', [])]))
    st = c.get('/api/stato')
    voce = [p for p in st['presidenti'] if p['id'] == 2][0]
    verifica('il bilancio si vede anche nella colonna delle squadre',
             (voce.get('bilancio') or {}).get('verso') == 'negativo',
             str(voce.get('bilancio'))[:120])

    print('\n[4l] I nomi delle squadre non si ridigitano ogni volta')
    miei = ['Zanzibar', 'Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo']
    c.post('/api/nuova', {'mio_nome': miei[0], 'avversari': miei[1:]})
    st = c.get('/api/stato')
    verifica('i nomi appena usati tornano come predefiniti',
             st.get('nomi_predefiniti') == miei,
             str(st.get('nomi_predefiniti')))
    c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})

    print('\n[4l-bis] Correggere un nome senza perdere l\'asta')
    # Il caso vero: l'asta era gia' cominciata con otto nomi sbagliati (li
    # aveva scritti il collaudo nelle preferenze). L'unico rimedio era "nuova
    # asta", che cancella tutti gli acquisti gia' registrati.
    c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    riga = next(x for x in c.get('/api/listone?n=60')['righe'] if not x['venduto'])
    c.post('/api/acquisto', {'id': riga['id'], 'presidente': 2, 'prezzo': 9})
    nuovi = ['Davide', 'Sempre Fanta', 'Real Bomber', 'Le Aquile',
             'Panchina Lunga', 'Fuorigioco', 'Terzo Portiere', 'Zona Cesarini']
    st = c.post('/api/rinomina', {'nomi': nuovi})
    verifica('i nomi cambiano davvero',
             [p['nome'] for p in st['presidenti']] == nuovi,
             str([p['nome'] for p in st['presidenti']]))
    verifica("l'acquisto gia' registrato non si e' perso",
             sum(sum(p['slot'].values()) for p in st['presidenti']) == 1,
             str([(p['nome'], p['slot']) for p in st['presidenti']]))
    verifica('i crediti restano quelli di prima',
             next(p['crediti'] for p in st['presidenti']
                  if p['nome'] == 'Sempre Fanta') == 491)
    verifica('i nomi corretti diventano i predefiniti',
             c.get('/api/stato').get('nomi_predefiniti') == nuovi)
    doppio = c.post('/api/rinomina', {'nomi': ['A'] * 8})
    verifica('due squadre con lo stesso nome vengono rifiutate',
             doppio.get('errore'), str(doppio)[:90])
    corto = c.post('/api/rinomina', {'nomi': ['A', 'B']})
    verifica('un elenco incompleto viene rifiutato', corto.get('errore'),
             str(corto)[:90])
    c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})

    print('\n[4p] Quando resta un solo slot, non servono dodici nomi')
    # Comprati sette pacchetti di portieri su otto, la lista dei consigliati
    # mostrava **dodici** portieri per l'unico slot rimasto, tutti con la
    # stessa riga sotto - "rende 3 punti meno del primo e costa uguale" - e
    # tutti marchiati PRENDILO, perche' senza piu' avversari nessuno puo'
    # rilanciare. Dodici righe uguali per un posto solo non sono una
    # classifica: sono rumore, e spingevano fuori schermo tutto il resto.
    c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    portieri = [r for r in c.get('/api/listone?n=530&ruolo=P')['righe']
                if not r['venduto']]
    presi, pres = 0, 2
    for r in portieri:
        if presi >= 7:
            break
        esito = c.post('/api/acquisto', {'id': r['id'], 'presidente': pres,
                                         'prezzo': max(1, int(r.get('costa') or 20))})
        if not esito.get('errore'):
            presi += 1
            pres += 1
    cons = c.get('/api/consiglio')
    verifica('la prova arriva davvero all\'ultimo slot da portiere',
             cons.get('serve') == 1, 'slot che mancano: %s' % cons.get('serve'))
    verifica('per un solo slot i consigliati sono al massimo tre',
             len(cons.get('top') or []) <= 3,
             '%d nomi per 1 slot' % len(cons.get('top') or []))

    # E una sezione vuota deve dire **perche'** e' vuota. Senza, sembra che il
    # programma abbia smesso di rispondere proprio quando serviva; quasi
    # sempre invece la risposta e' "non c'e' niente da segnalare".
    vuoti = cons.get('vuoti') or {}
    senza_ragione = [k for k in ('evitare', 'alternative', 'svuotare')
                     if not (cons.get(k) or []) and not vuoti.get(k)]
    verifica('ogni sezione vuota spiega perche\' e\' vuota',
             not senza_ragione, 'senza spiegazione: %s' % str(senza_ragione))
    verifica('la spiegazione e\' scritta in italiano, non tagliata a meta\'',
             not any('portier ' in (t + ' ') or 'difensor ' in (t + ' ')
                     or 'centrocampist ' in (t + ' ') or 'attaccant ' in (t + ' ')
                     for t in vuoti.values()),
             str(list(vuoti.values())[:1]))
    c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})

    print('\n[4q] Chi non e\' in lista non si compra, nemmeno per un credito')
    # Segnalato dopo un'asta vera: il motore aveva proposto Milik, che alla
    # Juventus e' **fuori dalla lista di serie A** e quindi non puo' giocare
    # nemmeno una partita. Le proiezioni gli davano 0,91 presenze - quasi
    # zero, non zero - e a fine asta la regola degli ultimi posti lo tirava su
    # lo stesso: "meglio lui che una casella vuota". Ma uno che non puo'
    # scendere in campo **e'** una casella vuota, e per giunta occupa uno slot.
    c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    fuori = [r for r in c.get('/api/listone?n=530')['righe'] if r.get('fuori_lista')]
    verifica('il listone sa chi e\' fuori lista', bool(fuori),
             'nessuno marcato: la fonte fuori_lista.csv non e\' arrivata')
    for r in fuori:
        sc = c.get('/api/scheda?id=%d' % r['id'])
        verifica('%s: la scheda lo dice invece di valutarlo' % r['nome'],
                 sc.get('verdetto') == 'FUORI LISTA',
                 'verdetto %s' % sc.get('verdetto'))
        verifica('%s: il limite e\' zero' % r['nome'], sc.get('max_bid') == 0,
                 'max_bid %s' % sc.get('max_bid'))
        verifica('%s: zero presenze attese' % r['nome'],
                 (sc.get('presenze') or 0) == 0,
                 'presenze %s' % sc.get('presenze'))

    # E soprattutto: non deve comparire fra i consigliati in nessuna fase, ne'
    # a rosa vuota ne' quando i crediti sono finiti e si riempie a un credito.
    ids_fuori = set(r['id'] for r in fuori)
    sporche = []
    for _ in range(4):
        cons = c.get('/api/consiglio')
        for gruppo in ('top', 'alternative', 'evitare', 'svuotare'):
            for d in (cons.get(gruppo) or []):
                if d['id'] in ids_fuori:
                    sporche.append('%s in %s' % (d['nome'], gruppo))
        # si avanza comprando, per arrivare anche alle fasi successive
        riga = next((x for x in c.get('/api/listone?n=200')['righe']
                     if not x['venduto']), None)
        if riga is None:
            break
        c.post('/api/acquisto', {'id': riga['id'], 'presidente': 2,
                                 'prezzo': max(1, int(riga['chiusura']))})
    verifica('non compare mai fra i consigliati', not sporche,
             '; '.join(sporche[:4]))
    c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})

    print('\n[4m] Rischio di restare in dieci')
    # L'ottimizzatore massimizza i punti dell'undici, e un giocatore che non
    # gioca mai in quella funzione vale zero, non meno di zero. Ma una casella
    # vuota in formazione non e' un giocatore da zero punti: e' una giornata in
    # dieci. Questo e' l'unico numero del motore che se ne accorge.
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    q = c.get('/api/equilibrio')
    r0 = q.get('rischio') or {}
    verifica('il quadro dice quante giornate rischi di restare in dieci',
             'quota' in r0 and 0 <= r0['quota'] <= 1, str(r0)[:140])
    verifica('a rosa vuota il rischio e\' quello di una rosa normale, non 100%',
             r0['quota'] < 0.25,
             'quota %.2f: conta gli slot da comprare come giocatori medi'
             % r0['quota'])
    # Una rosa fatta di riserve con la fantamedia alta deve risultare
    # nettamente peggio di una fatta di titolari, a parita' di slot.
    listone = c.get('/api/listone?n=530')['righe']
    def prendi(ruolo, quanti, chi):
        presi = 0
        for x in chi:
            if x['ruolo'] != ruolo or x['venduto']:
                continue
            r = c.post('/api/acquisto', {'id': x['id'], 'presidente': 1, 'prezzo': 1})
            if r.get('errore'):
                continue
            presi += 1
            if presi >= quanti:
                return
    reg = st['regole']
    fermi = sorted([x for x in listone if x['presenze'] <= 6],
                   key=lambda x: -x['fm'])
    for ruolo in ('D', 'C', 'A'):
        prendi(ruolo, reg['slot'][ruolo], fermi)
    q = c.get('/api/equilibrio')
    r1 = q.get('rischio') or {}
    verifica('una panchina che non gioca fa impennare il rischio',
             r1['quota'] > 0.30,
             'quota %.2f con %s disponibili' % (r1['quota'], r1.get('disponibili')))
    verifica('quando il rischio e\' alto il quadro lo dice a parole',
             any(a.get('tipo') == 'rischio' for a in q['avvisi']),
             str([a.get('tipo') for a in q['avvisi']]))
    verifica('il quadro indica quale reparto ti tiene fermo',
             (r1.get('reparto_stretto') or {}).get('ruolo') in ('P', 'D', 'C', 'A'),
             str(r1.get('reparto_stretto')))

    print('\n[4n] Il motore impara quanto paga la stanza')
    # Prima si assumeva che tutti valutassero al consenso di mercato. A un
    # tavolo vero non e' cosi': chi paga il trenta per cento sopra qualunque
    # cosa gli piaccia continuera' a farlo, e stimare la sua chiusura con lo
    # stesso numero di chi aspetta gli avanzi vuol dire perdere l'obiettivo per
    # due crediti ogni volta.
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    dif = [x for x in c.get('/api/listone?ruolo=D&n=40&ordine=costa')['righe']
           if not x['venduto']]
    bersaglio = dif[6]
    prima = c.get('/api/scheda?id=%d' % bersaglio['id'])['chiusura']
    # Tre avversari diversi strapagano: il triplo di quanto valeva.
    presi = 0
    for x in dif:
        if x['id'] == bersaglio['id']:
            continue
        r = c.post('/api/acquisto', {'id': x['id'], 'presidente': 2 + presi % 3,
                                     'prezzo': min(150, max(2, x['chiusura'] * 3))})
        if r.get('errore'):
            continue
        presi += 1
        if presi >= 9:
            break
    dopo = c.get('/api/scheda?id=%d' % bersaglio['id'])
    concorrenti = dopo['concorrenti']
    verifica('ogni avversario porta con se\' quanto paga sopra il dovuto',
             all('aggressivita' in x for x in concorrenti),
             str(concorrenti[:2]))
    caldi = [x for x in concorrenti if x['aggressivita'] > 1.1]
    verifica('chi ha strapagato risulta piu\' aggressivo della media',
             len(caldi) >= 1,
             str([(x['nome'], x['aggressivita']) for x in concorrenti]))
    # In una stanza che paga caro il motore deve alzare la stima di chiusura
    # rispetto a quella che farebbe credendoli tutti nella media. La verifica
    # e' indiretta ma solida: la chiusura non puo' essere crollata, malgrado
    # nove acquisti abbiano prosciugato i crediti del reparto.
    verifica('in una stanza che paga caro la chiusura non crolla',
             dopo['chiusura'] >= prima * 0.55,
             'prima %d, dopo %d' % (prima, dopo['chiusura']))

    print('\n[4o] Far pagare gli altri senza rimetterci')
    # Chiamare un big che non interessa e' una mossa vera, ma e' anche il modo
    # piu' rapido di ritrovarselo in rosa a quaranta crediti. Il pannello
    # mostrava la chiusura attesa, e si poteva leggere come "spingi fino a li'":
    # se in quel momento gli altri si fermano, quella cifra la paghi tu.
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    cons = c.get('/api/consiglio')
    svuota = cons.get('svuotare') or []
    verifica('c\'e\' qualcuno da far pagare agli altri', bool(svuota))
    if svuota:
        senza_tetto = [d['nome'] for d in svuota if not d.get('tetto_sicuro')]
        verifica('ogni proposta porta il suo tetto di sicurezza',
                 not senza_tetto, str(senza_tetto[:4]))
        # Il tetto deve stare sotto quanto vale sul mercato: se nessuno rilancia
        # e te lo aggiudichi, non ci hai comunque rimesso crediti.
        sopra = []
        for d in svuota:
            sc = c.get('/api/scheda?id=%d' % d['id'])
            if d['tetto_sicuro'] >= sc['costo_atteso'] and d['tetto_sicuro'] > 1:
                sopra.append((d['nome'], d['tetto_sicuro'], sc['costo_atteso']))
        verifica('il tetto sta sotto quanto quel giocatore vale',
                 not sopra, str(sopra[:4]))
        pochi = [d['nome'] for d in svuota if d.get('contendenti', 0) < 2]
        verifica('si propone solo con almeno due avversari che possono superarlo',
                 not pochi, str(pochi[:4]))

    print('\n[5] Asta completa, per reparti')
    random.seed(11)
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    reg = st['regole']
    assegnati = 0
    fasi_viste = []
    inizio = time.time()
    while st['fase'] is not None and assegnati < reg['partecipanti'] * reg['slot_totali']:
        fase = st['fase']
        if not fasi_viste or fasi_viste[-1] != fase:
            fasi_viste.append(fase)
        listone = c.get('/api/listone?ruolo=%s&n=200' % fase)
        liberi = [x for x in listone['righe'] if not x['venduto']]
        if not liberi:
            break
        # Chi puo' ancora comprare in questo ruolo.
        candidati = [p for p in st['presidenti']
                     if p['slot'][fase] < reg['slot'][fase] and p['liquidita'] >= 1]
        if not candidati:
            break
        g = liberi[0]
        p = random.choice(candidati)
        prezzo = max(1, min(int(round(g['mercato'] * random.uniform(0.6, 1.3))),
                            p['liquidita']))
        st = c.post('/api/acquisto',
                    {'id': g['id'], 'presidente': p['id'], 'prezzo': prezzo})
        if st.get('errore'):
            verifica('acquisto durante la simulazione', False, st['errore'])
            break
        # Non basta contare le chiamate: col pacchetto portieri una chiamata
        # sola assegna tre giocatori.
        assegnati = sum(sum(p['slot'].values()) for p in st['presidenti'])
    durata = time.time() - inizio

    attesi = reg['partecipanti'] * reg['slot_totali']
    verifica('sono stati assegnati tutti i giocatori', assegnati == attesi,
             'assegnati=%d attesi=%d' % (assegnati, attesi))
    verifica('le fasi si sono succedute nell\'ordine dei ruoli',
             fasi_viste == ['P', 'D', 'C', 'A'], str(fasi_viste))
    verifica('nessun presidente ha sforato il budget',
             all(p['crediti'] >= 0 for p in st['presidenti']))
    verifica('ogni rosa e\' completa',
             all(p['residui'] == 0 for p in st['presidenti']),
             str([(p['nome'], p['residui']) for p in st['presidenti']]))
    verifica('l\'asta risulta conclusa', st['fase'] is None)
    print('       (%d chiamate in %.1f s, %.0f ms l\'una)'
          % (assegnati, durata, 1000 * durata / max(1, assegnati)))

    print('\n[6] A rosa piena')
    sch = c.get('/api/scheda?id=%d' % dim['id'])
    verifica('un giocatore venduto risulta gia\' assegnato',
             bool(sch.get('gia_venduto')), str(sch.get('gia_venduto')))
    cons = c.get('/api/consiglio')
    verifica('il consiglio non esplode a fine asta', cons.get('fase') is None,
             str(cons)[:120])
    piano = c.get('/api/piano')
    verifica('il piano di spesa regge a rosa piena', 'per_ruolo' in piano)

    print('\n[7] Una sola istanza per volta')
    # Due processi sullo stesso file SQLite durante un'asta significano crediti
    # sbagliati e giocatori assegnati due volte. Il doppio doppio-clic e' un
    # gesto naturale, visto che il primo avvio ci mette una decina di secondi
    # e sembra che non stia succedendo niente.
    # L'intruso deve puntare **allo stesso database**, altrimenti non e' un
    # intruso: da quando il lucchetto sta accanto al file che protegge, due
    # istanze su due database diversi convivono benissimo, ed e' giusto cosi'
    # - e' proprio quello che permette a queste prove di girare mentre il
    # programma dell'utente e' aperto. Il fatto da difendere non e' "un solo
    # FantaHacked al mondo", e' "un solo FantaHacked per asta".
    intruso = subprocess.Popen(
        [sys.executable, os.path.join(QUI, 'server.py'), '--no-browser'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=AMBIENTE)
    try:
        intruso.wait(timeout=60)
        uscito = True
    except subprocess.TimeoutExpired:
        uscito = False
        intruso.kill()
    verifica('una seconda istanza sullo stesso database si chiude da sola',
             uscito)
    verifica('il motore originale e\' rimasto quello che risponde',
             c.get('/api/ping').get('app') == 'FantaHacked')

    print('\n[8] Ripristino')
    st = c.post('/api/nuova', {'mio_nome': 'Davide', 'avversari': nomi})
    verifica('si puo\' ricominciare da capo', st['fase'] == 'P' and st['io']['crediti'] == 500)

    print('\n%s   %d superati, %d falliti'
          % ('TUTTO OK' if not fail else 'CI SONO ERRORI', ok, fail))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
