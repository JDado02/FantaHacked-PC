# -*- coding: utf-8 -*-
"""Venti aste guardate **mentre** si giocano, non solo alla fine.

`cento_aste.py` misura l'esito: chi vince, con che rosa, con quanti crediti
avanzati. Un motore puo' pero' vincere e insieme dire cose sbagliate lungo la
strada &mdash; consigliare un giocatore gia' venduto, proporre un limite piu'
alto dei crediti che si hanno, cambiare parere ogni chiamata. Quelle cose
all'esito non si vedono, e sono proprio quelle che si notano al tavolo.

Qui a ogni singola chiamata d'asta si controllano le proprieta' che devono
valere sempre. Ogni violazione viene contata e la prima di ogni tipo viene
scritta per esteso.
"""
import math, multiprocessing, os, random, shutil, statistics, sys, time

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

import percorsi, db as dbmod, regole as regmod
from asta import StatoAsta, ErroreAsta
from valutazione import Valutatore
from ottimizzatore import Ottimizzatore
from strategia import Consigliere
import cento_aste as cento

RUOLI = ('P', 'D', 'C', 'A')
NOMI = cento.NOMI
# Gli stessi verdetti che accetta `app/test_app.py` sotto "top acquisti":
# la lista e la scheda devono dire la stessa cosa, e la lista dei verdetti
# validi deve essere una sola per non finire a rincorrersi.
VALE = ('OCCASIONE', 'PRENDILO', 'AL PREZZO GIUSTO', 'DA UN CREDITO',
        'RIPIEGO')


def ispeziona(seme):
    rng = random.Random(seme)
    dst = os.path.join(QUI, 'isp_%d_%d.db' % (seme, os.getpid()))
    shutil.copyfile(percorsi.DB_FILE, dst)
    guasti = {}
    tempi = []

    def guasto(tipo, testo):
        d = guasti.setdefault(tipo, [0, ''])
        d[0] += 1
        if not d[1]:
            d[1] = testo

    try:
        con = dbmod.connetti(dst)
        reg = regmod.carica()
        st = StatoAsta(con, reg)
        st.inizializza(NOMI[1:], mio_nome=NOMI[0])
        v = Valutatore(con, reg, st)
        o = Ottimizzatore(v)
        c = Consigliere(v, o)
        ancora = cento.ancore_di_mercato(v, reg)
        carattere = cento.base.caratteri(rng, reg)
        per_id = dict((p['nome'], p['id']) for p in st.presidenti())
        io_id = st.io()['id']
        speso = dict((n, dict((r, 0) for r in RUOLI)) for n in NOMI)

        while True:
            fase = c.fase()
            if fase is None:
                break
            liberi = [x for x in v.disponibili(fase)
                      if not (reg.portieri_pacchetto and fase == 'P'
                              and not x.titolare_por)]
            if not liberi:
                break

            # --- il consiglio, guardato come lo guarderebbe l'utente
            t0 = time.time()
            cons = c.consiglio()
            tempi.append(time.time() - t0)
            venduti = st.venduti()
            visti = {}
            # "da evitare" e "da far pagare agli altri" possono coincidere,
            # ed e' giusto: uno che non ti conviene e' proprio quello su cui
            # far spendere gli altri. Tutte le altre coppie no.
            coerenti = frozenset([frozenset(('evitare', 'svuotare'))])
            for gruppo in ('top', 'alternative', 'evitare', 'svuotare'):
                for d in (cons.get(gruppo) or []):
                    if d['id'] in venduti:
                        guasto('consiglia un giocatore gia venduto',
                               '%s in "%s"' % (d['nome'], gruppo))
                    altro = visti.get(d['id'])
                    if (altro and altro != gruppo
                            and frozenset((altro, gruppo)) not in coerenti):
                        guasto('lo stesso giocatore in due sezioni che si '
                               'contraddicono',
                               '%s in "%s" e "%s"' % (d['nome'], altro, gruppo))
                    visti[d['id']] = gruppo
                    for campo in ('chiusura', 'max_bid'):
                        val = d.get(campo)
                        if val is not None and not math.isfinite(float(val)):
                            guasto('numero non finito nel consiglio',
                                   '%s.%s = %r' % (d['nome'], campo, val))
                    if (d.get('max_bid') or 0) > st.liquidita(io_id):
                        guasto('limite oltre i crediti disponibili',
                               '%s: limite %s, liquidita %d'
                               % (d['nome'], d.get('max_bid'),
                                  st.liquidita(io_id)))
            for d in (cons.get('top') or []):
                if d.get('verdetto') not in VALE:
                    guasto('sotto "top acquisti" un verdetto che dice di lasciare',
                           '%s: %s' % (d['nome'], d.get('verdetto')))
            for d in (cons.get('svuotare') or []):
                tetto = d.get('tetto_sicuro')
                x = v.g[d['id']]
                # Le due garanzie che `_svuota` promette, misurate contro i
                # numeri giusti: `prezzo_base` (quanto varrebbe in una stanza
                # normale, e non si muove mai) e la chiusura attesa. Non
                # `costo_atteso`, che e' il prezzo del momento: a inizio asta
                # coincidono e a meta' no, e confrontarsi con quello faceva
                # sembrare un guasto una differenza fra due grandezze diverse.
                if tetto is None:
                    guasto('proposta di far pagare senza tetto', d['nome'])
                    continue
                if tetto > 1 and tetto >= (x.prezzo_base or 1):
                    guasto('tetto non sotto quanto vale in una stanza normale',
                           '%s: tetto %s, vale %.0f'
                           % (d['nome'], tetto, x.prezzo_base or 1))
                if tetto > 1 and tetto > d['chiusura']:
                    guasto('tetto sopra la chiusura attesa',
                           '%s: tetto %s, chiusura %s'
                           % (d['nome'], tetto, d['chiusura']))
                if (d.get('contendenti') or 0) < 2:
                    guasto('far pagare con meno di due contendenti',
                           '%s: %s' % (d['nome'], d.get('contendenti')))

            # --- prezzi e budget
            for x in v.g.values():
                for campo in ('prezzo_atteso', 'prezzo_base', 'prezzo_mercato'):
                    val = getattr(x, campo, None)
                    if val is None or not math.isfinite(val) or val < 1.0 - 1e-6:
                        guasto('prezzo fuori scala', '%s.%s = %r'
                               % (x.nome, campo, val))
            somma = sum(x.prezzo_atteso for r in RUOLI for x in v.candidati[r])
            # Tre crediti di tolleranza: i prezzi si arrotondano a schermo e
            # duecento arrotondamenti fanno qualche credito di scarto.
            if abs(somma - v.crediti_residui) > 3.0:
                guasto('i prezzi attesi non chiudono il mercato',
                       'somma %.0f contro %d crediti'
                       % (somma, v.crediti_residui))
            if o.ultimi_posti(fase) and o.budget > 3 * sum(o.serve.values()):
                guasto('la regola degli ultimi posti scatta troppo presto',
                       '%d crediti per %d slot' % (o.budget, sum(o.serve.values())))

            # --- si gioca il lotto
            x = rng.choice(sorted(liberi, key=lambda y: -ancora.get(y.id, 0))[:8])
            offerte = []
            for nome in NOMI[1:]:
                pid = per_id[nome]
                if st.slot_residui(pid, fase) <= 0:
                    continue
                b = cento.offerta(rng, x, fase, carattere[nome],
                                  st.liquidita(pid), st.slot_residui(pid, fase),
                                  speso[nome][fase], reg, ancora)
                if b >= 1:
                    offerte.append((b, nome))
            mio = 0
            if st.slot_residui(io_id, fase) > 0:
                limite = o.max_bid(x)[0]
                if limite > st.liquidita(io_id):
                    guasto('il limite supera la liquidita',
                           '%s: %d contro %d'
                           % (x.nome, limite, st.liquidita(io_id)))
                mio = min(int(limite), st.liquidita(io_id))
            if mio >= 1:
                offerte.append((mio, NOMI[0]))
            if not offerte:
                v.g.pop(x.id, None)
                continue
            offerte.sort(reverse=True)
            vincitore = offerte[0][1]
            secondo = offerte[1][0] if len(offerte) > 1 else 0
            prezzo = max(1, min(offerte[0][0], secondo + 1))
            pid = per_id[vincitore]
            prezzo = min(prezzo, st.liquidita(pid))
            if prezzo < 1:
                v.g.pop(x.id, None)
                continue
            prima = st.crediti(pid)
            try:
                st.registra(x.id, pid, prezzo)
            except ErroreAsta:
                v.g.pop(x.id, None)
                continue
            if st.crediti(pid) != prima - prezzo:
                guasto('i crediti non tornano dopo un acquisto',
                       '%s: %d - %d != %d'
                       % (vincitore, prima, prezzo, st.crediti(pid)))
            speso[vincitore][fase] += prezzo
            if reg.portieri_pacchetto and fase == 'P':
                for rid in v.riserve_di(x.id):
                    if rid in st.venduti() or st.slot_residui(pid, 'P') <= 0:
                        continue
                    try:
                        st.registra(rid, pid, 1)
                        speso[vincitore]['P'] += 1
                    except ErroreAsta:
                        pass
            c.aggiorna()

        # --- controlli di fine asta
        for p in st.presidenti():
            if st.crediti(p['id']) < 0:
                guasto('crediti negativi a fine asta', p['nome'])
            for r in RUOLI:
                if st.slot_residui(p['id'], r) < 0:
                    guasto('piu giocatori degli slot', '%s %s' % (p['nome'], r))
        mancanti = sum(max(0, st.slot_residui(io_id, r)) for r in RUOLI)
        if mancanti:
            guasto('la mia rosa resta incompleta', '%d slot vuoti' % mancanti)
        con.close()
    finally:
        try:
            os.remove(dst)
        except OSError:
            pass
    return seme, guasti, tempi


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    semi = [20000 + 23 * i for i in range(quante)]
    avvio = time.time()
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        esiti = pool.map(ispeziona, semi)
    tutti, tempi = {}, []
    for seme, guasti, ts in esiti:
        tempi += ts
        for tipo, (quante_, esempio) in guasti.items():
            d = tutti.setdefault(tipo, [0, 0, ''])
            d[0] += quante_
            d[1] += 1
            if not d[2]:
                d[2] = 'seme %d: %s' % (seme, esempio)
    print('%d aste ispezionate in %.0f s' % (len(esiti), time.time() - avvio))
    print('%d chiamate al consiglio, %.0f ms l\'una (peggiore %.0f ms)'
          % (len(tempi), 1000 * statistics.mean(tempi), 1000 * max(tempi)))
    if not tutti:
        print('\nNessuna violazione: le proprieta\' tengono su tutte le aste.')
        return
    print('\n%-46s %8s %7s' % ('cosa non torna', 'volte', 'aste'))
    for tipo, (quante_, aste, esempio) in sorted(tutti.items(),
                                                 key=lambda t: -t[1][0]):
        print('%-46s %8d %7d' % (tipo[:46], quante_, aste))
        print('      %s' % esempio[:110])


if __name__ == '__main__':
    main()
