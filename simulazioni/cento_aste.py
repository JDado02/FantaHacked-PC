# -*- coding: utf-8 -*-
"""Cento aste giocate dal posto di Davide, per collaudare il motore.

Diversa da `cinque_aste.py` in un punto che cambia tutto il senso del
risultato: **da chi prendono il prezzo gli avversari.**

In `cinque_aste.py` offrono partendo da `prezzo_base`, cioe' da un numero che
calcola il nostro motore. Va bene per vedere se il programma sta in piedi, ma
come misura del suo vantaggio non vale niente: sono avversari i cui prezzi sono
definiti dal modello che si vuole giudicare. Migliorare il modello sposta anche
loro, e la partita finisce sempre uguale.

Qui l'ancora e' `prezzo_riferimento`, cioe' i prezzi **realmente pagati** nelle
aste vere, riportati in scala sul monte crediti della lega. Gli avversari
diventano una stanza normale che paga quello che si paga di solito, e il motore
deve batterla sapendo cose che il listino non scrive: i minuti, le gerarchie,
il modificatore, le coppie che si dividono la maglia.

Uso:
    python cento_aste.py              cento aste, avversari a prezzi di mercato
    python cento_aste.py 40           quaranta aste
    python cento_aste.py 100 motore   avversari ancorati al nostro modello
"""
import json, math, multiprocessing, os, random, shutil, statistics, sys, time

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(QUI)
sys.path.insert(0, os.path.join(BASE, 'motore'))
sys.path.insert(0, QUI)

import percorsi, db as dbmod, regole as regmod
from asta import StatoAsta, ErroreAsta
from valutazione import Valutatore
from ottimizzatore import Ottimizzatore
from strategia import Consigliere
from modificatore import Modificatore

import cinque_aste as base
import copertura

RUOLI = ('P', 'D', 'C', 'A')
NOMI = base.NOMI

# Manopole che `manopole.py` gira dall'esterno. Vivono qui e non fra i
# parametri perche' `multiprocessing` deve poterle impostare nel figlio prima
# che l'asta cominci, e un parametro in piu' su `gioca` non aiuterebbe: la
# funzione la chiama lui, non chi le prova.
MARGINE = 0.0     # di quanto rilanciare oltre il proprio limite
FIDUCIA = None    # sovrascrive fiducia_nel_mercato


def punteggio(rosa, reg):
    """I punti di stagione di una rosa, **modificatore di difesa compreso**.

    Il punteggio precedente sommava solo `presenze x fantamedia` dell'undici
    titolare, e quella omissione ha quasi fatto prendere una decisione
    sbagliata. In questa lega il modificatore vale fino a sei punti a giornata
    &mdash; oltre duecento in stagione, dieci volte gli scarti che si stavano
    misurando &mdash; e premia esattamente il reparto su cui le due varianti in
    confronto la pensavano diversamente. Con il metro corto, spostare crediti
    in difesa risultava sempre uno spreco: si contava quello che i difensori
    costano e non tutto quello che rendono.

    Il portiere e i tre difensori migliori per media voto sono quelli che
    entrano nel calcolo, come dice il regolamento della lega.
    """
    totale = base.undici_atteso(rosa)
    mod = Modificatore(reg)
    if not mod.attivo:
        return totale
    n_por = reg.mod_dif_n_por
    n_dif = reg.mod_dif_n_dif
    por = sorted(rosa['P'], key=lambda d: -(d.get('mv') or 0))[:n_por]
    dif = sorted(rosa['D'], key=lambda d: -(d.get('mv') or 0))[:n_dif]
    scelti = por + dif
    if len(scelti) < n_por + n_dif:
        return totale
    media = sum(d.get('mv') or 0 for d in scelti) / float(len(scelti))
    return totale + mod.punti_stagione(media)


def ancore_di_mercato(v, reg):
    """Il prezzo da cui parte un avversario medio, per ogni giocatore.

    Sono i prezzi storici d'asta riportati in scala. La scala serve: il listino
    somma al 119% del monte crediti della lega, perche' sono medie condizionate
    all'essere stati venduti e non una ripartizione. Lasciato com'e', la stanza
    finisce i crediti a tre quarti d'asta.

    La riscalatura si fa **per reparto e con le proporzioni del listino**, non
    con quelle di `regole_lega.json`: quelle dicono come vuole spendere questa
    lega, e qui si sta costruendo apposta un avversario che spende come la
    media di tutte le altre.
    """
    quota = dict((r, reg.slot[r] * reg.partecipanti) for r in RUOLI)
    somma = {}
    for r in RUOLI:
        pool = sorted([x.prezzo_riferimento or 0.0
                       for x in v.g.values() if x.ruolo == r], reverse=True)
        somma[r] = sum(pool[:quota[r]]) or 1.0
    monte = float(reg.crediti_totali)
    totale = sum(somma.values())
    ancora = {}
    for x in v.g.values():
        budget_r = monte * somma[x.ruolo] / totale
        k = (budget_r - quota[x.ruolo]) / somma[x.ruolo]
        rif = x.prezzo_riferimento or 0.0
        if rif <= 0:
            # Senza storico non si inventa: si ripiega sulla quotazione
            # ufficiale, che e' l'altro numero che un avversario ha davanti.
            rif = float(x.qi or 1)
        ancora[x.id] = max(1.0, 1.0 + rif * k)
    return ancora


def gioca(seme, ancoraggio='mercato', patch_reg=None):
    rng = random.Random(seme)
    # Il nome porta dentro il processo: `manopole.py` gioca lo stesso seme con
    # manopole diverse, in parallelo, e due processi sullo stesso file SQLite
    # producono una copia corrotta invece di un errore.
    dst = os.path.join(QUI, 'cento_%d_%d.db' % (seme, os.getpid()))
    shutil.copyfile(percorsi.DB_FILE, dst)
    try:
        con = dbmod.connetti(dst)
        reg = regmod.carica()
        if FIDUCIA is not None:
            reg.fiducia_mercato = FIDUCIA
        if patch_reg is not None:
            patch_reg(reg)
        st = StatoAsta(con, reg)
        st.inizializza(NOMI[1:], mio_nome=NOMI[0])
        v = Valutatore(con, reg, st)
        o = Ottimizzatore(v)
        c = Consigliere(v, o)
        ancora = (ancore_di_mercato(v, reg) if ancoraggio == 'mercato'
                  else dict((x.id, x.prezzo_base or 1.0) for x in v.g.values()))
        carattere = base.caratteri(rng, reg)
        per_id = dict((p['nome'], p['id']) for p in st.presidenti())
        io_id = st.io()['id']
        speso = dict((n, dict((r, 0) for r in RUOLI)) for n in NOMI)

        # Diario di quello che fa il motore, per giudicarlo dopo.
        miei_limiti = []          # (limite, prezzo pagato, ancora, ruolo)
        persi_di_un_soffio = 0    # gliel'ha soffiato qualcuno per <=2 crediti

        while True:
            fase = c.fase()
            if fase is None:
                break
            liberi = [x for x in v.disponibili(fase)
                      if not (reg.portieri_pacchetto and fase == 'P'
                              and not x.titolare_por)]
            if not liberi:
                break
            finestra = sorted(liberi, key=lambda y: -ancora.get(y.id, 0))[:8]
            x = rng.choice(finestra)

            offerte = []
            for nome in NOMI[1:]:
                pid = per_id[nome]
                if st.slot_residui(pid, fase) <= 0:
                    continue
                off = offerta(rng, x, fase, carattere[nome], st.liquidita(pid),
                              st.slot_residui(pid, fase), speso[nome][fase],
                              reg, ancora)
                if off >= 1:
                    offerte.append((off, nome))

            mio = 0
            if st.slot_residui(io_id, fase) > 0:
                limite = o.max_bid(x)[0]
                # Il limite e' il punto di indifferenza: pagarlo esatto non
                # migliora e non peggiora la rosa. Perdere li' per un credito
                # costa zero in teoria, ma la teoria assume i punti giusti.
                # `MARGINE` misura se conviene comunque un rilancio in piu'.
                mio = int(limite * (1.0 + MARGINE)) if limite >= 1 else 0
                mio = min(mio, st.liquidita(io_id))
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
            if vincitore == NOMI[0]:
                miei_limiti.append((mio, prezzo, ancora.get(x.id, 0), fase))
            elif mio >= 1 and offerte[0][0] - mio <= 2:
                persi_di_un_soffio += 1
            try:
                st.registra(x.id, pid, prezzo)
            except ErroreAsta:
                v.g.pop(x.id, None)
                continue
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

        rose = {}
        for nome in NOMI:
            pid = per_id[nome]
            rosa = dict((r, []) for r in RUOLI)
            for a in st.acquisti():
                if a['presidente_id'] != pid:
                    continue
                g = v.g.get(a['giocatore_id'])
                rosa[a['ruolo']].append({
                    'nome': a['nome'], 'squadra': a['squadra'],
                    'prezzo': a['prezzo'],
                    'presenze': int(round(g.presenze)) if g else 0,
                    'punti': round(g.presenze * g.fm) if g else 0,
                    # La media voto serve per il modificatore di difesa, che
                    # in questa lega vale fino a sei punti a giornata e che il
                    # punteggio finale ignorava del tutto.
                    'mv': round(g.mv, 3) if g else 0.0,
                    'grado': (g.grado or '?') if g else '?',
                    'ancora': round(ancora.get(a['giocatore_id'], 0), 1),
                })
            rose[nome] = rosa

        esito = {
            'seme': seme,
            'punti': dict((n, punteggio(rose[n], reg)) for n in NOMI),
            'senza_modificatore': dict((n, base.undici_atteso(rose[n]))
                                       for n in NOMI),
            'spesa': dict((r, sum(d['prezzo'] for d in rose[NOMI[0]][r]))
                          for r in RUOLI),
            'avanzati': st.crediti(io_id),
            'slot': dict((r, len(rose[NOMI[0]][r])) for r in RUOLI),
            'rischio': copertura.rischio(rose[NOMI[0]], giornate=3000,
                                         seme=seme)[0],
            'limiti': miei_limiti,
            'soffiati': persi_di_un_soffio,
            'rosa': rose[NOMI[0]],
        }
        con.close()
        return esito
    finally:
        try:
            os.remove(dst)
        except OSError:
            pass


def offerta(rng, x, ruolo, carattere, liquidita, slot_ruolo, speso_ruolo,
            reg, ancora):
    """Fin dove si spinge un avversario medio: come `cinque_aste`, altra ancora."""
    if slot_ruolo <= 0 or liquidita < 1:
        return 0
    inclinazione = carattere[ruolo] / max(1e-6, reg.quota_budget[ruolo])
    mu, sigma = base.RUMORE[ruolo]
    errore = rng.lognormvariate(math.log(mu), sigma)
    if rng.random() < (0.05 if ruolo == 'A' else 0.02):
        errore *= rng.uniform(1.4, 2.0)
    valore = ancora.get(x.id, 1.0) * (0.45 + 0.55 * inclinazione) * errore
    tetto = max(1.0, carattere[ruolo] * reg.crediti - speso_ruolo)
    valore = min(valore, tetto * 3.0 / max(1, slot_ruolo))
    return int(max(0, min(round(valore), liquidita)))


def _lavoro(argomenti):
    seme, ancoraggio = argomenti
    try:
        return gioca(seme, ancoraggio)
    except Exception as e:                      # una sola asta non deve
        return {'seme': seme, 'errore': repr(e)}  # far cadere le altre


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    ancoraggio = sys.argv[2] if len(sys.argv) > 2 else 'mercato'
    semi = [1000 + 7 * i for i in range(quante)]
    avvio = time.time()
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        esiti = pool.map(_lavoro, [(s, ancoraggio) for s in semi])
    rotte = [e for e in esiti if 'errore' in e]
    esiti = [e for e in esiti if 'errore' not in e]
    fuori = os.path.join(QUI, 'cento_aste_%s.json' % ancoraggio)
    with open(fuori, 'w', encoding='utf-8') as f:
        json.dump({'ancoraggio': ancoraggio, 'esiti': esiti}, f)
    print('%d aste in %.0f s su %d processi   (%d rotte)'
          % (len(esiti), time.time() - avvio, n, len(rotte)))
    if rotte:
        print('  ' + rotte[0]['errore'][:200])
    relazione(esiti, ancoraggio)


def relazione(esiti, ancoraggio):
    if not esiti:
        return
    io = NOMI[0]
    piazzamenti, scarti, punti = [], [], []
    for e in esiti:
        mio = e['punti'][io]
        altri = [p for n, p in e['punti'].items() if n != io]
        piazzamenti.append(1 + sum(1 for p in altri if p > mio))
        scarti.append(mio - max(altri))
        punti.append(mio)
    vinte = sum(1 for p in piazzamenti if p == 1)
    print('\n%s' % ('=' * 68))
    print('CENTO ASTE  (avversari ancorati a: %s)' % ancoraggio)
    print('=' * 68)
    print('  vinte              %d su %d  (%.0f%%)'
          % (vinte, len(esiti), 100.0 * vinte / len(esiti)))
    print('  podio              %d su %d'
          % (sum(1 for p in piazzamenti if p <= 3), len(esiti)))
    print('  piazzamento medio  %.2f' % (sum(piazzamenti) / len(piazzamenti)))
    print('  peggior asta       %d posto' % max(piazzamenti))
    print('  punti mediani      %.0f   (min %.0f, max %.0f)'
          % (statistics.median(punti), min(punti), max(punti)))
    print('  scarto dal secondo %+.0f punti mediano   (peggiore %+.0f)'
          % (statistics.median(scarti), min(scarti)))

    print('\n  Come spende il motore')
    for r in RUOLI:
        q = [e['spesa'][r] for e in esiti]
        print('    %s  %5.1f%% del budget   (%3.0f crediti, da %3d a %3d)'
              % (r, 100.0 * statistics.mean(q) / 500.0,
                 statistics.mean(q), min(q), max(q)))
    avanzati = [e['avanzati'] for e in esiti]
    print('    crediti non spesi  %.1f in media  (peggio: %d)'
          % (statistics.mean(avanzati), max(avanzati)))
    incomplete = [e for e in esiti if sum(e['slot'].values()) < 25]
    print('    rose incomplete    %d su %d' % (len(incomplete), len(esiti)))

    rischi = [e['rischio'] for e in esiti]
    print('\n  Rischio di restare in dieci')
    print('    giornate su 38     %.1f mediana   (peggiore %.1f)'
          % (38 * statistics.median(rischi), 38 * max(rischi)))
    print('    aste sopra 3 giornate  %d su %d'
          % (sum(1 for x in rischi if 38 * x > 3), len(esiti)))

    print('\n  Disciplina sul limite')
    sopra = sconti = tot = 0
    risparmio = []
    for e in esiti:
        for limite, prezzo, anc, _ in e['limiti']:
            tot += 1
            if prezzo > limite:
                sopra += 1
            if anc > 0 and prezzo < anc:
                sconti += 1
                risparmio.append(anc - prezzo)
    print('    acquisti totali    %d  (%.1f per asta)' % (tot, tot / len(esiti)))
    print('    pagati sopra il proprio limite  %d' % sopra)
    print('    pagati sotto il prezzo di mercato  %d su %d (%.0f%%)'
          % (sconti, tot, 100.0 * sconti / max(1, tot)))
    if risparmio:
        print('    risparmio medio quando compra  %.1f crediti'
              % statistics.mean(risparmio))
    soffiati = [e['soffiati'] for e in esiti]
    print('    persi per <=2 crediti  %.1f per asta' % statistics.mean(soffiati))


if __name__ == '__main__':
    main()
