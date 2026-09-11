# -*- coding: utf-8 -*-
"""Verifica delle proprieta' del motore. Uso:  python test_motore.py"""
import os, random, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# **Le prove girano su una copia usa e getta.** La prima cosa che fanno e'
# aprire un'asta nuova, e una nuova asta cancella quella precedente: puntate al
# database vero, distruggono l'asta in corso senza chiedere niente a nessuno.
# La variabile va messa prima di importare `percorsi`, che la legge una volta
# sola al caricamento.
# Da quando i file sono due si copiano tutti e due: le prove ricalcolano le
# proiezioni, che stanno nel file dei dati, e non devono riscriverlo a chi
# sta usando il programma.
if not os.environ.get('FANTAHACKED_DB'):
    import percorsi as _p
    _prove = tempfile.mkdtemp(prefix='fantahacked_prove_')
    _copia = os.path.join(_prove, 'asta.db')
    if os.path.exists(_p.DB_FILE):
        shutil.copyfile(_p.DB_FILE, _copia)
    _copia_dati = os.path.join(_prove, 'dati.db')
    if os.path.exists(_p.DATI_FILE):
        shutil.copyfile(_p.DATI_FILE, _copia_dati)
    os.environ['FANTAHACKED_DB'] = _copia
    os.environ['FANTAHACKED_DATI'] = _copia_dati
    for _modulo in ('percorsi',):
        sys.modules.pop(_modulo, None)

import db as dbmod, regole as regmod, proiezioni as prmod
from asta import StatoAsta, ErroreAsta
from valutazione import Valutatore

ok = fail = 0


def verifica(descrizione, condizione, dettaglio=''):
    global ok, fail
    if condizione:
        ok += 1
        print('  OK   %s' % descrizione)
    else:
        fail += 1
        print('  FAIL %s   %s' % (descrizione, dettaglio))


def main():
    # Le verifiche giocano aste vere e proprie: registrano acquisti, riempiono
    # rose, ricominciano da capo. Girando sul file dell'asta normale
    # cancellavano quella di chi stava giocando - ed e' successo. I dati sono
    # quelli veri, l'asta e' un file temporaneo che sparisce alla fine.
    with dbmod.asta_di_servizio() as con:
        return _prove(con)


def _prove(con):
    reg = regmod.carica()
    if con.execute('SELECT COUNT(*) FROM proiezioni').fetchone()[0] == 0:
        prmod.esegui(con, reg)

    stato = StatoAsta(con, reg).inizializza(
        ['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo'], mio_nome='Davide')
    v = Valutatore(con, reg, stato)

    print('\n[1] Chiusura del mercato')
    assegnati = [x for r in ('P', 'D', 'C', 'A') for x in v.candidati[r]]
    verifica('i candidati sono esattamente i giocatori che verranno assegnati',
             len(assegnati) == reg.slot_lega,
             'candidati=%d slot=%d' % (len(assegnati), reg.slot_lega))
    somma = sum(x.prezzo_mercato for x in assegnati)
    verifica('la somma dei prezzi consigliati eguaglia i crediti della lega',
             abs(somma - v.crediti_residui) < 1.0,
             'somma=%.1f crediti=%d' % (somma, v.crediti_residui))
    verifica('ogni prezzo e\' almeno 1',
             all(x.prezzo_mercato >= 1.0 - 1e-9 for x in v.g.values()))
    verifica('il pool discrezionale e\' crediti meno slot',
             v.pool_discrezionale == v.crediti_residui - v.slot_residui)

    print('\n[2] Livello di rimpiazzo')
    for ruolo in ('P', 'D', 'C', 'A'):
        n = stato.slot_residui_ruolo(ruolo)
        verifica('%s: gli slot di lega valgono partecipanti x slot rosa' % ruolo,
                 n == reg.partecipanti * reg.slot[ruolo])
    # Col parere del mercato acceso, un giocatore sotto la linea puo' comunque
    # valere qualcosa: il mercato sa cose che il database non contiene. Quello
    # che non deve mai succedere e' un VOR negativo, o che valga qualcosa chi
    # sta sotto la linea E non ha nessun sostegno dal mercato.
    verifica('nessun VOR e\' negativo', all((x.vor or 0) >= 0 for x in v.g.values()))
    orfani = [x for x in v.g.values()
              if x.fm < v.rimpiazzo_fm[x.ruolo] - 0.15
              and (x.punti_mod or 0) <= 0
              and not (x.prezzo_riferimento or 0)
              and x.vor > 0]
    verifica('chi rende meno del rimpiazzo e non ha mercato ha VOR nullo',
             not orfani, str([x.nome for x in orfani[:4]]))

    print('\n[2b] Portieri a pacchetto')
    if reg.portieri_pacchetto:
        titolari = [x for x in v.candidati['P'] if x.titolare_por]
        # Uno per partecipante, piu' eventuali tappi: qualche squadra di serie
        # A ha solo due portieri a listone, e quel pacchetto non basta a
        # coprire i tre slot di una rosa.
        verifica('c\'e\' un pacchetto per ogni partecipante',
                 reg.partecipanti <= len(titolari) <= reg.partecipanti + 3,
                 'titolari fra i candidati: %d' % len(titolari))
        migliori = sorted([x for x in v.g.values()
                           if x.ruolo == 'P' and x.titolare_por],
                          key=lambda x: -x.vor)[:reg.partecipanti]
        verifica('i migliori titolari sono tutti fra i candidati',
                 all(x in v.candidati['P'] for x in migliori))
        con_riserve = [x for x in titolari if x.riserve_por]
        verifica('ogni titolare si porta dietro le sue riserve',
                 len(con_riserve) == len(titolari))
        riserve = [x for x in v.g.values()
                   if x.ruolo == 'P' and not x.titolare_por]
        verifica('le riserve non valgono piu\' di un credito',
                 all(round(x.prezzo_mercato) <= 1 for x in riserve))

    print('\n[2c] Riserve di budget per reparto')
    from ottimizzatore import Ottimizzatore
    o = Ottimizzatore(v)
    if any(reg.riserva_ruolo.values()):
        attesa = int(reg.riserva_ruolo['A'] * reg.crediti)
        verifica('gli attaccanti hanno i loro crediti accantonati',
                 o.riserva['A'] >= attesa - 1,
                 'riserva=%d attesa=%d' % (o.riserva['A'], attesa))
        verifica('le riserve non superano il budget',
                 sum(o.riserva.values()) <= reg.crediti)
        piano = o.piano()
        verifica('il piano destina agli attaccanti almeno la loro riserva',
                 piano['per_ruolo']['A']['crediti'] >= o.riserva['A'],
                 'piano=%d riserva=%d' % (piano['per_ruolo']['A']['crediti'],
                                          o.riserva['A']))

    print('\n[2d] Prezzi attesi contro prezzi di valore')
    somma_att = sum(x.prezzo_atteso for r in ('P', 'D', 'C', 'A')
                    for x in v.candidati[r])
    verifica('anche i prezzi attesi chiudono il mercato',
             abs(somma_att - v.crediti_residui) < 1.0,
             'somma=%.1f crediti=%d' % (somma_att, v.crediti_residui))
    # Il prezzo atteso segue la ripartizione **del mercato**, non quella del
    # piano: la domanda a cui risponde e' quanto costera', e quello dipende da
    # come spende la stanza, non da come vorrei uscire dall'asta io.
    quota_a = sum(x.prezzo_atteso for x in v.candidati['A']) / somma_att
    verifica('gli attaccanti assorbono la quota che la stanza gli dedica',
             abs(quota_a - reg.quota_mercato['A']) < 0.06,
             'attesa %.0f%% ottenuta %.0f%%' % (100 * reg.quota_mercato['A'],
                                                100 * quota_a))
    quota_piano = (sum(x.prezzo_piano for x in v.candidati['A'])
                   / sum(x.prezzo_piano for r in ('P', 'D', 'C', 'A')
                         for x in v.candidati[r]))
    verifica('e il prezzo con cui si pianifica segue invece il piano',
             abs(quota_piano - reg.quota_budget['A']) < 0.08,
             'piano %.0f%% ottenuta %.0f%%' % (100 * reg.quota_budget['A'],
                                               100 * quota_piano))

    print('\n[2e] La curva dei prezzi contro i prezzi realmente pagati')
    # Il prezzo non e' il valore. Spartendo i crediti del reparto in
    # proporzione al merito &mdash; com'era &mdash; l'errore contro i prezzi
    # storicamente pagati era del 39% pesato per i crediti in gioco; con la
    # curva stimata su quegli stessi prezzi scende sotto il 32%. La verifica
    # rifa' il conto tutte le volte, perche' e' l'unica cosa che tiene onesta
    # una costante scelta a occhio.
    import math as _m
    campione = [x for x in v.g.values() if (x.prezzo_riferimento or 0) >= 2]
    verifica('c\'e\' uno storico d\'asta su cui misurarsi', len(campione) >= 100,
             '%d giocatori' % len(campione))

    def errore(prezzo_di):
        crediti = scarto = 0.0
        for ruolo in ('P', 'D', 'C', 'A'):
            gruppo = [x for x in campione if x.ruolo == ruolo]
            if not gruppo:
                continue
            # I due totali si portano sulla stessa scala: la lega ha il suo
            # riparto fra i reparti, il listino storico un altro, e senza
            # questo si misurerebbe quello invece della forma della curva.
            k = (sum(prezzo_di(x) for x in gruppo)
                 / sum(x.prezzo_riferimento for x in gruppo))
            for x in gruppo:
                e = abs(_m.log(prezzo_di(x) / (x.prezzo_riferimento * k)))
                crediti += x.prezzo_riferimento
                scarto += x.prezzo_riferimento * e
        return _m.exp(scarto / crediti) - 1.0

    vor_ruolo = dict((r, sum(x.vor for x in v.candidati[r]))
                     for r in ('P', 'D', 'C', 'A'))

    def a_merito(x):
        pool = max(0.0, v.budget_ruolo[x.ruolo]
                   - max(0, stato.slot_residui_ruolo(x.ruolo)))
        if vor_ruolo[x.ruolo] <= 0 or pool <= 0:
            return 1.0
        return 1.0 + x.vor / vor_ruolo[x.ruolo] * pool

    con_curva = errore(lambda x: x.prezzo_atteso)
    solo_merito = errore(a_merito)
    verifica('la curva sbaglia meno del solo merito',
             con_curva < solo_merito,
             'curva %.0f%% contro merito %.0f%%'
             % (100 * con_curva, 100 * solo_merito))
    verifica('e sbaglia meno di un terzo',
             con_curva < 0.34, '%.0f%%' % (100 * con_curva))
    verifica('la curva non e\' stata stimata sui portieri a pacchetto',
             'P' not in v.curva,
             'con le riserve a 1 credito lo storico d\'asta descrive '
             'un\'altra lega')
    riserve = [x for x in v.g.values() if x.ruolo == 'P' and not x.titolare_por]
    verifica('le riserve dei portieri restano a un credito',
             riserve and all(x.prezzo_atteso <= 1.0 + 1e-6 for x in riserve),
             str([(x.nome, round(x.prezzo_atteso, 1)) for x in riserve
                  if x.prezzo_atteso > 1.0 + 1e-6][:4]))

    print('\n[2f] I prezzi attesi chiudono il mercato anche a meta\' asta')
    # `[2d]` lo controlla a rosa vuota, dove tornava. Venti aste ispezionate
    # passo per passo lo hanno visto rompersi appena chiude un reparto: con i
    # portieri a pacchetto, finiti i titolari restano a listone solo le
    # riserve, che arrivano in dote a un credito. Il motore continuava a
    # destinare al reparto duecentododici crediti per diciotto riserve da uno,
    # e quei centonovantaquattro crediti non finivano in nessun prezzo. Da li'
    # in poi ogni chiusura attesa era piu' bassa del vero del sei per cento, e
    # nella lega di Davide i portieri chiudono per primi.
    st2 = StatoAsta(con, reg).inizializza(
        ['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo'],
        mio_nome='Davide')
    v2 = Valutatore(con, reg, st2)
    # Si assegnano tutti i pacchetti dei portieri, come succede sempre per
    # primo, e si guarda cosa resta.
    presidenti = [p['id'] for p in st2.presidenti()]
    giro = 0
    for x in sorted([y for y in v2.disponibili('P') if y.titolare_por],
                    key=lambda y: -(y.presenze * y.fm)):
        pid = presidenti[giro % len(presidenti)]
        if st2.slot_residui(pid, 'P') < 1 + len(x.riserve_por or ()):
            giro += 1
            continue
        try:
            st2.registra(x.id, pid, max(1, min(st2.liquidita(pid), 30)))
        except ErroreAsta:
            continue
        for rid in (x.riserve_por or ()):
            if rid not in st2.venduti() and st2.slot_residui(pid, 'P') > 0:
                try:
                    st2.registra(rid, pid, 1)
                except ErroreAsta:
                    pass
        giro += 1
        if st2.slot_residui_ruolo('P') <= 0:
            break
    v2.aggiorna()
    somma2 = sum(x.prezzo_atteso for r in ('P', 'D', 'C', 'A')
                 for x in v2.candidati[r])
    verifica('il reparto dei portieri e\' andato avanti davvero',
             len(st2.venduti()) >= 12, '%d venduti' % len(st2.venduti()))
    verifica('a meta\' asta i prezzi attesi sommano ancora ai crediti in gioco',
             abs(somma2 - v2.crediti_residui) < 2.0,
             'somma %.0f contro %d crediti: %+.0f non assegnati a nessuno'
             % (somma2, v2.crediti_residui, somma2 - v2.crediti_residui))
    # E il reparto chiuso non deve trattenere crediti che non puo' spendere.
    resta_titolare = any(x.titolare_por for x in v2.disponibili('P'))
    if not resta_titolare and st2.slot_residui_ruolo('P') > 0:
        verifica('finiti i titolari, il reparto portieri vale un credito a slot',
                 v2.budget_ruolo['P'] <= st2.slot_residui_ruolo('P') + 1e-6,
                 'budget %.0f per %d slot da un credito'
                 % (v2.budget_ruolo['P'], st2.slot_residui_ruolo('P')))
    # Questa prova ha giocato mezza asta sullo stesso database, e le sezioni
    # che seguono partono dal presupposto di trovarla come l'hanno lasciata.
    # Si rimette com'era: `stato` e `v` sono gli stessi oggetti di prima.
    stato.inizializza(['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia',
                       'Hugo'], mio_nome='Davide')
    v.aggiorna()

    print('\n[3] Vincoli di acquisto')
    d = v.disponibili('A')[0]
    try:
        stato.registra(d.id, 1, 0)
        verifica('prezzo zero rifiutato', False)
    except ErroreAsta:
        verifica('prezzo zero rifiutato', True)
    try:
        stato.registra(d.id, 1, reg.crediti)
        verifica('offerta che impedisce di riempire la rosa rifiutata', False)
    except ErroreAsta:
        verifica('offerta che impedisce di riempire la rosa rifiutata', True)
    stato.registra(d.id, 1, 100)
    try:
        stato.registra(d.id, 2, 50)
        verifica('doppio acquisto dello stesso giocatore rifiutato', False)
    except ErroreAsta:
        verifica('doppio acquisto dello stesso giocatore rifiutato', True)
    verifica('i crediti scalano dopo l\'acquisto', stato.crediti(1) == reg.crediti - 100)
    verifica('la liquidita\' tiene 1 credito per slot residuo',
             stato.liquidita(1) == reg.crediti - 100 - (reg.slot_totali - 1 - 1))

    print('\n[4] Annullamento')
    stato.annulla_ultimo()
    verifica('i crediti tornano al valore iniziale', stato.crediti(1) == reg.crediti)
    verifica('il giocatore torna disponibile', d.id not in stato.venduti())

    print('\n[5] Reazione del mercato agli acquisti')
    v.aggiorna()
    prezzo_prima = {x.id: x.prezzo_mercato for x in v.g.values()}
    rimpiazzo_prima = dict(v.rimpiazzo_fm)
    # Sette avversari strapagano un attaccante a testa.
    for pid, g in zip(range(2, 9), v.disponibili('A')[:7]):
        stato.registra(g.id, pid, 120)
    v.aggiorna()
    verifica('spendendo molto presto, i prezzi successivi scendono',
             v.inflazione < 1.0, 'inflazione=%.3f' % v.inflazione)
    # Togliere i migliori consuma un giocatore E uno slot: il giocatore
    # marginale resta lo stesso, quindi il rimpiazzo non si muove.
    verifica('comprare dall\'alto lascia fermo il livello di rimpiazzo',
             abs(v.rimpiazzo_fm['A'] - rimpiazzo_prima['A']) < 1e-6,
             '%.2f -> %.2f' % (rimpiazzo_prima['A'], v.rimpiazzo_fm['A']))
    # Uno slot speso su un giocatore sotto la linea toglie un posto a chi era
    # sopra: il giocatore marginale, quello che ti ritroveresti in rosa se
    # lasciassi andare tutti gli altri, diventa piu' forte.
    #
    # La misura e' sui **punti attesi** del marginale, non sulla sua
    # fantamedia. Il pool si ordina per punti (presenze x fantamedia) apposta,
    # per tenere lontano dalla linea le riserve con quattro presenze e la media
    # gonfiata; ma allora risalire quella classifica non alza per forza la
    # fantamedia, perche' si incontra anche chi gioca molto e rende poco. La
    # fantamedia di rimpiazzo puo' oscillare di un decimo in entrambi i sensi:
    # e' il marginale a doversi muovere nel verso giusto, ed e' quello che il
    # resto del motore usa per decidere quanto vale uno slot.
    def marginale(ruolo):
        pool = sorted([x for x in v.g.values()
                       if x.ruolo == ruolo and x.id not in stato.venduti()],
                      key=lambda x: -(x.presenze * x.fm))
        n = stato.slot_residui_ruolo(ruolo)
        x = pool[min(n, len(pool) - 1)]
        return x.presenze * x.fm

    scarsi = sorted(v.disponibili('A'), key=lambda x: x.presenze * x.fm)[:6]
    prima_scarso = marginale('A')
    for pid, s_ in zip(range(2, 8), scarsi):
        stato.registra(s_.id, pid, 1)
    v.aggiorna()
    verifica('uno slot speso sotto la linea alza il livello del marginale',
             marginale('A') > prima_scarso,
             '%.1f -> %.1f punti' % (prima_scarso, marginale('A')))
    for _ in scarsi:
        stato.annulla_ultimo()
    v.aggiorna()
    rimasto = v.disponibili('C')[0]
    verifica('un centrocampista non toccato si sconta',
             v.g[rimasto.id].prezzo_mercato < prezzo_prima[rimasto.id],
             '%.1f -> %.1f' % (prezzo_prima[rimasto.id], v.g[rimasto.id].prezzo_mercato))

    print('\n[6] Saturazione dei ruoli')
    for _ in range(7):
        stato.annulla_ultimo()
    v.aggiorna()
    top = v.disponibili('D')[0]
    n_prima = len(v.concorrenti(top))
    # Riempio la difesa di un avversario e verifico che esca dai concorrenti.
    for g in v.disponibili('D')[1:1 + reg.slot['D']]:
        stato.registra(g.id, 2, 1)
    v.aggiorna()
    n_dopo = len(v.concorrenti(top))
    verifica('chi ha il reparto pieno esce dai concorrenti', n_dopo == n_prima - 1,
             'prima=%d dopo=%d' % (n_prima, n_dopo))

    print('\n[6b] Gli ultimi posti vanno riempiti, non valutati')
    # Il guasto, trovato su cento aste simulate: tre volte su cento il motore
    # chiudeva l'asta con quattro slot vuoti in attacco e cinque crediti in
    # mano, dopo aver risposto "lascialo" a ventinove attaccanti di fila. Non
    # era prudenza: coi riempitivi preventivati a due crediti e uno solo in
    # cassa per slot, il piano di spesa diventava impossibile e `opt`
    # restituiva NEG per chiunque. Il messaggio diceva "quello slot rende di
    # piu' su un altro giocatore", e non c'era nessun altro giocatore.
    st6 = StatoAsta(con, reg).inizializza(
        ['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo'],
        mio_nome='Davide')
    v6 = Valutatore(con, reg, st6)
    # Mi svuoto la cassa sui reparti che non sono l'attacco, come succede a chi
    # spende presto e bene: restano gli slot in attacco e le briciole.
    io6 = st6.io()['id']
    for ruolo in ('P', 'D', 'C'):
        for x in sorted(v6.disponibili(ruolo),
                        key=lambda y: -(y.presenze * y.fm)):
            if st6.slot_residui(io6, ruolo) <= 0:
                break
            # Prezzi alti apposta: serve arrivare in attacco con la
            # cassa quasi vuota, come ci arriva chi ha comprato bene.
            prezzo = max(1, min(st6.liquidita(io6), 60))
            try:
                st6.registra(x.id, io6, prezzo)
            except ErroreAsta:
                continue
    v6.aggiorna()
    o6 = Ottimizzatore(v6)
    crediti = st6.crediti(io6)
    slot_a = st6.slot_residui(io6, 'A')
    verifica('la prova costruisce davvero il caso limite',
             slot_a > 0 and crediti < 2 * slot_a + 4,
             '%d crediti per %d slot in attacco' % (crediti, slot_a))
    if slot_a > 0:
        liberi = sorted(v6.disponibili('A'),
                        key=lambda y: -(y.presenze * y.fm))[:25]
        zero = [x.nome for x in liberi if o6.max_bid(x)[0] < 1]
        verifica('con gli ultimi crediti nessun giocatore utile vale zero',
                 not zero, 'lasciati andare: %s' % str(zero[:5]))
        verifica('e la regola degli ultimi posti risulta attiva',
                 o6.ultimi_posti('A'),
                 '%d crediti, %d slot' % (crediti, slot_a))
    # A inizio asta invece la regola non deve scattare: li' un riempitivo da un
    # credito toglie davvero uno slot a un giocatore vero.
    st7 = StatoAsta(con, reg).inizializza(
        ['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo'],
        mio_nome='Davide')
    v7 = Valutatore(con, reg, st7)
    o7 = Ottimizzatore(v7)
    verifica('a rosa vuota la regola degli ultimi posti non scatta',
             not any(o7.ultimi_posti(r) for r in ('P', 'D', 'C', 'A')),
             'con %d crediti e %d slot non siamo alla frutta'
             % (o7.budget, sum(o7.serve.values())))


    print('\n[7] Asta completa simulata')
    stato.inizializza(['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo'],
                      mio_nome='Davide')
    v = Valutatore(con, reg, stato)
    random.seed(7)
    ordine = sorted(v.g.values(), key=lambda x: -x.punti)
    assegnati = 0
    for g in ordine:
        if assegnati >= reg.slot_lega:
            break
        candidati = [p for p in stato.presidenti()
                     if stato.slot_residui(p['id'], g.ruolo) > 0
                     and stato.liquidita(p['id']) >= 1]
        if not candidati:
            continue
        p = random.choice(candidati)
        prezzo = max(1, min(int(round(v.g[g.id].prezzo_mercato * random.uniform(0.7, 1.3))),
                            stato.liquidita(p['id'])))
        stato.registra(g.id, p['id'], prezzo)
        assegnati += 1
        if assegnati % 25 == 0:
            v.aggiorna()
    v.aggiorna()
    verifica('tutti gli slot della lega sono stati assegnati',
             assegnati == reg.slot_lega, 'assegnati=%d attesi=%d' % (assegnati, reg.slot_lega))
    verifica('nessun presidente ha sforato il budget',
             all(p['crediti'] >= 0 for p in stato.presidenti()))
    verifica('ogni rosa e\' completa',
             all(stato.slot_residui(p['id']) == 0 for p in stato.presidenti()))
    speso = reg.crediti_totali - stato.crediti_residui_lega
    verifica('il totale speso non supera i crediti della lega',
             speso <= reg.crediti_totali, 'speso=%d' % speso)
    print('       (simulazione: %d giocatori assegnati, %d crediti spesi su %d)'
          % (assegnati, speso, reg.crediti_totali))

    prove_squadre(con)
    prove_copertura()

    stato.inizializza(['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo'],
                      mio_nome='Davide')
    con.close()
    print('\n%s   %d superati, %d falliti' % ('TUTTO OK' if not fail else 'CI SONO ERRORI',
                                              ok, fail))
    return 1 if fail else 0


def prove_squadre(con):
    """[8] Cambiare il numero di squadre deve cambiare i numeri.

    Non e' un'impostazione cosmetica: da quante squadre siamo dipende quanti
    giocatori verranno assegnati in tutto, e quindi **chi e' il rimpiazzo
    gratis** di ognuno. In una lega da sei il ventesimo portiere resta sul
    listone e ti costa un credito; in una da venti quel portiere e' titolare
    da qualcuno. Il valore di un giocatore e' la distanza da quel rimpiazzo,
    quindi cresce con la lega; e il prezzo cresce anche di piu', perche' i
    crediti in gioco si moltiplicano mentre i giocatori forti restano quelli.

    Qui si controllano le **direzioni**, non i numeri: i numeri cambiano ogni
    volta che si aggiorna il database, le direzioni no.
    """
    from ottimizzatore import Ottimizzatore
    print('')
    print('[8] Il numero di squadre cambia prezzi e strategia')
    misure = {}
    for n in (6, 10, 16):
        reg = regmod.carica(modifiche={'partecipanti': n})
        st = StatoAsta(con, reg).inizializza(
            ['S%d' % i for i in range(1, n)], mio_nome='Io')
        v = Valutatore(con, reg, st)
        o = Ottimizzatore(v)
        top = {}
        for r in ('P', 'D', 'C', 'A'):
            x = v.disponibili(r, 1)[0]
            top[r] = {'nome': x.nome, 'vor': x.vor,
                      'mercato': x.prezzo_atteso or 0}
        misure[n] = {'reg': reg, 'rimpiazzo': dict(v.rimpiazzo_fm), 'top': top,
                     'consigliati': len([x for x in v.disponibili('P', 40)
                                         if o.max_bid(x)[0] >= 1])}
    verifica('i crediti in gioco seguono il numero di squadre',
             all(misure[n]['reg'].crediti_totali == n * 500 for n in misure))
    verifica("con piu' squadre il rimpiazzo gratis peggiora",
             misure[6]['rimpiazzo']['P'] > misure[10]['rimpiazzo']['P']
             > misure[16]['rimpiazzo']['P'],
             ' '.join('%d:%.2f' % (n, misure[n]['rimpiazzo']['P']) for n in misure))
    for r in ('P', 'C', 'A'):
        verifica("il migliore fra i %s vale di piu' in una lega piu' grande" % r,
                 misure[6]['top'][r]['vor'] < misure[16]['top'][r]['vor'],
                 '%s: 6 sq %.1f, 16 sq %.1f' % (r, misure[6]['top'][r]['vor'],
                                                misure[16]['top'][r]['vor']))
        verifica("e costa di piu' (%s)" % r,
                 misure[6]['top'][r]['mercato'] < misure[16]['top'][r]['mercato'],
                 '%s: 6 sq %.0f, 16 sq %.0f' % (r, misure[6]['top'][r]['mercato'],
                                                misure[16]['top'][r]['mercato']))
    verifica("in una lega grande vale la pena puntare su piu' portieri",
             misure[16]['consigliati'] > misure[6]['consigliati'],
             '6 sq: %d, 16 sq: %d' % (misure[6]['consigliati'],
                                      misure[16]['consigliati']))
    reg = regmod.carica()
    StatoAsta(con, reg).inizializza(
        ['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo'],
        mio_nome='Davide')


def prove_copertura():
    """[9] Quante caselle della formazione si riempiono davvero.

    E' il conto che manca a `presenze x fantamedia`, e le tre verifiche qui
    sotto sono i tre casi in cui quella formula sbaglia: la panchina che serve,
    il reparto di gente a mezzo servizio, e il rendimento che si ferma da solo
    quando il reparto e' pieno.
    """
    import formazione
    print('')
    print('[9] Le caselle che si riempiono ogni giornata')
    fisso = [30 / 38.0] * 4
    mezzo = [18 / 38.0] * 4
    verifica("quattro titolari coprono piu' di quattro da meta' campionato",
             formazione.posti_coperti(fisso, 4)
             > formazione.posti_coperti(mezzo, 4) + 1.0)
    verifica('la panchina aggiunge copertura, ma meno dei titolari',
             (formazione.posti_coperti(fisso + [10 / 38.0] * 4, 4)
              > formazione.posti_coperti(fisso, 4))
             and (formazione.posti_coperti(fisso + [10 / 38.0] * 4, 4)
                  < formazione.posti_coperti(fisso, 4) + 0.6))
    verifica('oltre le caselle in campo il guadagno si spegne',
             formazione.guadagno([30 / 38.0] * 8, 4, 30 / 38.0) < 0.02)
    verifica("un titolare copre piu' di uno da rotazione",
             formazione.guadagno(fisso[:2], 4, 30 / 38.0)
             > formazione.guadagno(fisso[:2], 4, 16 / 38.0) + 0.15)
    # E il punteggio "schierato" deve vedere quello che il conto vecchio non
    # vedeva. Il vecchio sommava i punti dei quattro migliori: due rose che
    # hanno gli stessi quattro migliori gli risultano identiche, anche se una
    # ha la panchina e l'altra no. Ma la panchina gioca, e i punti li fa.
    soli = {'D': [{'fm': 6.4, 'presenze': 30} for _ in range(4)]}
    con_panchina = {'D': soli['D'] + [{'fm': 5.8, 'presenze': 12}
                                      for _ in range(4)]}
    a = formazione.punti_stagione(soli, {'D': 4})
    b = formazione.punti_stagione(con_panchina, {'D': 4})
    verifica('la panchina vale punti, e il conto vecchio non la contava',
             b > a + 50, '%.0f senza panchina, %.0f con' % (a, b))
    # E quanto valga la panchina dipende da **quanto mancano i titolari**: e'
    # tutta qui la differenza fra i due modi di contare, e vale la pena
    # scriverla come verifica perche' e' controintuitiva. Con quattro titolari
    # veri la panchina prende poco campo e rende poco; con quattro che giocano
    # meta' campionato entra il doppio delle volte e rende il doppio. Quindi il
    # rischio non e' che un giocatore discontinuo valga meno di quanto dicono i
    # suoi punti: e' che **senza panchina** quelle giornate non le copra
    # nessuno. Il conto vecchio, che la panchina non la guardava affatto, non
    # poteva vedere ne' l'una ne' l'altra cosa.
    panca = [{'fm': 5.8, 'presenze': 12} for _ in range(4)]
    fissi = [{'fm': 6.0, 'presenze': 32} for _ in range(4)]
    saltuari = [{'fm': 6.0 * 32 / 18.0, 'presenze': 18} for _ in range(4)]
    resa_panca = lambda t: (formazione.punti_stagione({'D': t + panca}, {'D': 4})
                            - formazione.punti_stagione({'D': t}, {'D': 4}))
    verifica("la panchina rende di piu' dietro a titolari discontinui",
             resa_panca(saltuari) > 2 * resa_panca(fissi),
             '%.0f dietro ai fissi, %.0f dietro ai saltuari'
             % (resa_panca(fissi), resa_panca(saltuari)))
    verifica('senza panchina il reparto discontinuo lascia caselle vuote',
             formazione.relazione([18 / 38.0] * 4, 4)['coperti'] < 2.2
             and formazione.relazione([32 / 38.0] * 4, 4)['coperti'] > 3.2)


if __name__ == '__main__':
    sys.exit(main())
