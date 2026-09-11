# -*- coding: utf-8 -*-
"""Fotografa il motore Python, perche' quello JavaScript ci si possa misurare.

L'applicazione per telefono ha un motore riscritto in JavaScript. Riscritto,
non reinventato: deve dare **gli stessi numeri**, altrimenti telefono e
computer direbbero due cose diverse sullo stesso giocatore e non ci sarebbe
modo di sapere quale dei due ha ragione.

Questo script produce i numeri attesi: per ogni giocatore e per quattro
momenti diversi dell'asta - vuota, dopo dieci acquisti, a meta', quasi
finita - scrive prezzi, punti, VOR, limiti e verdetti. La pagina di prova
dell'app li rilegge e confronta uno per uno.

I momenti sono costruiti in modo **riproducibile**: gli acquisti sono scelti
con un seme fisso e scritti nel file, cosi' la parte JavaScript ricostruisce
esattamente lo stesso stato invece di sperare che coincida.

Uso:  python dump_equivalenza.py [file di uscita]
"""
import io, json, os, random, sys

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(QUI)
sys.path.insert(0, os.path.join(BASE, 'motore'))

import percorsi, db as dbmod, regole as regmod
from asta import StatoAsta
from valutazione import Valutatore
from ottimizzatore import Ottimizzatore
from strategia import Consigliere
from equilibrio import Equilibrio

NOMI = ['Davide', 'Luca', 'Windser', 'Jacopo', 'Giorgio', 'Viane', 'Fede', 'Canzia']
TAPPE = [0, 10, 60, 190]

# I regolamenti su cui si ripete il confronto. Non sono casi di scuola: sono
# le quattro combinazioni che una lega vera puo' davvero avere.
REGOLAMENTI = [
    {'partecipanti': 6, 'crediti_iniziali': 400, 'modificatore_difesa': False},
    {'partecipanti': 20, 'crediti_iniziali': 500},
    {'partecipanti': 10, 'crediti_iniziali': 300, 'portieri_a_pacchetto': False},
    {},
]


def scegli_acquisti(v, st, quanti, rng):
    """Una sequenza di acquisti plausibile e ripetibile.

    Non a caso puro: si pesca fra i primi del ruolo che tocca, a un prezzo
    vicino a quello atteso. Serve che lo stato sia **realistico**, perche' un
    motore sbagliato puo' benissimo dare i numeri giusti su un'asta vuota e
    sbagliarli tutti a meta' strada.
    """
    fatti = []
    presidenti = [p['id'] for p in st.presidenti()]
    tentativi = 0
    while len(fatti) < quanti and tentativi < 20000:
        tentativi += 1
        pid = presidenti[len(fatti) % len(presidenti)]
        # I ruoli in cui *quel* presidente ha ancora posto: cercare uno slot
        # che non c'e' e' il modo piu' facile di girare a vuoto per sempre.
        aperti = [r for r in ('P', 'D', 'C', 'A') if st.slot_residui(pid, r) > 0]
        if not aperti:
            # Rosa piena: si passa al successivo aggiungendo un segnaposto
            # che sposta il giro senza registrare niente.
            presidenti = [p for p in presidenti if p != pid] or [pid]
            if len(presidenti) == 1 and st.slot_residui(presidenti[0]) <= 0:
                break
            continue
        ruolo = aperti[rng.randrange(len(aperti))]
        liberi = v.disponibili(ruolo)[:30]
        if not liberi:
            continue
        x = liberi[rng.randrange(len(liberi))]
        liq = st.liquidita(pid)
        if liq < 1:
            continue
        prezzo = max(1, int(round((x.prezzo_atteso or 1) * rng.uniform(0.7, 1.15))))
        prezzo = max(1, min(prezzo, liq))
        try:
            st.registra(x.id, pid, prezzo, None)
        except Exception:
            continue
        fatti.append([x.id, pid, prezzo])
        v.aggiorna()
    return fatti


def scena_portieri_miei(v, st):
    """I miei tre portieri presi, gli altri no: la lega e' ancora sui portieri.

    E' il buco che l'utente ha trovato: da qui in poi non posso piu' fare
    un'offerta in questo reparto, e per sette chiamate il programma non aveva
    niente da dire. Adesso dev'esserci il reparto successivo, dichiarato come
    anticipo.
    """
    fatti = []
    presidenti = [p['id'] for p in st.presidenti()]
    io_id = st.io()['id']
    for pid in [io_id, presidenti[1], presidenti[2]]:
        fatti += _pacchetto_portiere(v, st, pid)
    return fatti


def scena_difesa_scoperta(v, st):
    """Tutti i portieri assegnati e due miei difensori: la fase e' la difesa.

    Con due difensori su quattro caselle la copertura manca, ed e' li' che
    l'ordine della fascia alta cambia: davanti chi scende in campo, dietro chi
    conviene. Serve che tutti i ventiquattro portieri siano andati, altrimenti
    la fase resta ai portieri.
    """
    fatti = []
    for p in st.presidenti():
        while st.slot_residui(p['id'], 'P') > 0:
            nuovi = _pacchetto_portiere(v, st, p['id'])
            if not nuovi:
                break
            fatti += nuovi
    io_id = st.io()['id']
    # Due difensori qualunque fra i primi: quello che conta e' che siano due e
    # non quattro.
    presi = 0
    for x in v.disponibili('D', 40):
        if presi >= 2:
            break
        prezzo = max(1, min(int(round(x.prezzo_atteso or 1)),
                            st.liquidita(io_id)))
        try:
            st.registra(x.id, io_id, prezzo, None)
        except Exception:
            continue
        fatti.append([x.id, io_id, prezzo])
        v.aggiorna()
        presi += 1
    return fatti


def _pacchetto_portiere(v, st, pid):
    """Un titolare piu' le sue riserve a un credito, come fa il programma."""
    fatti = []
    for x in v.disponibili('P', 60):
        if st.slot_residui(pid, 'P') <= 0:
            break
        if v.pacchetto and not x.titolare_por:
            continue
        prezzo = max(1, min(int(round(x.prezzo_atteso or 1)), st.liquidita(pid)))
        try:
            st.registra(x.id, pid, prezzo, None)
        except Exception:
            continue
        fatti.append([x.id, pid, prezzo])
        v.aggiorna()
        for rid in (v.riserve_di(x.id) if v.pacchetto else []):
            if st.slot_residui(pid, 'P') <= 0:
                break
            try:
                st.registra(rid, pid, 1, None)
            except Exception:
                continue
            fatti.append([rid, pid, 1])
            v.aggiorna()
        break
    return fatti


def istantanea(v, o, c, st):
    """Tutto quello che la parte JavaScript deve saper riprodurre."""
    gio = {}
    for x in v.g.values():
        gio[str(x.id)] = [
            round(x.punti or 0.0, 6), round(x.vor or 0.0, 6),
            round(x.punti_mod or 0.0, 6),
            round(x.prezzo_mercato or 0.0, 6), round(x.prezzo_atteso or 0.0, 6),
            round(x.prezzo_base or 0.0, 6), round(x.prezzo_piano or 0.0, 6),
            None if x.peso_prezzo is None else round(x.peso_prezzo, 6),
        ]
    # I limiti e i verdetti costano: si prendono su un campione fisso, scelto
    # per coprire i casi che contano - i piu' cari, i fuori lista, le coppie,
    # i portieri titolari e le riserve.
    campione = []
    visti = set()
    for x in sorted(v.g.values(), key=lambda y: -(y.prezzo_atteso or 0))[:40]:
        campione.append(x)
        visti.add(x.id)
    for x in v.g.values():
        if len(campione) >= 90:
            break
        if x.id in visti:
            continue
        if x.fuori_lista or (v.pacchetto and x.ruolo == 'P') or v.coppie.get(x.id):
            campione.append(x)
            visti.add(x.id)
    limiti = {}
    for x in campione:
        lim, d = o.max_bid(x)
        dec = c.decisione(x)
        limiti[str(x.id)] = [
            lim, round(d.get('opt_senza') or 0.0, 6), round(d.get('opt_con') or 0.0, 6),
            round(d.get('guadagno') or 0.0, 6),
            dec['verdetto'], dec['max_bid'], dec['chiusura'],
            round(dec['convenienza'], 6), round(dec['utilita'], 6),
        ]
    # Il quadro della rosa: undici migliore, coperture, rischio di restare in
    # dieci. E' l'unica parte del motore che guarda la squadra invece del
    # singolo giocatore, e finche' non stava qui la sua traduzione non era
    # verificata da niente.
    quadro = Equilibrio(v, o).quadro()
    return {
        'equilibrio': quadro,
        'globali': {
            'crediti_residui': v.crediti_residui,
            'slot_residui': v.slot_residui,
            'pool_discrezionale': v.pool_discrezionale,
            'vor_totale': round(v.vor_totale, 6),
            'densita': round(v._densita, 6),
            'inflazione': round(v.inflazione, 6),
            'rimpiazzo_fm': dict((r, round(v.rimpiazzo_fm[r], 6)) for r in 'PDCA'),
            'budget_ruolo': dict((r, round(v.budget_ruolo[r], 6)) for r in 'PDCA'),
            'budget_piano': dict((r, round(v.budget_piano[r], 6)) for r in 'PDCA'),
            'aggressivita': dict((str(k), round(x, 6))
                                 for k, x in v.aggressivita.items()),
            'opt': round(o.opt(), 6),
            'curva': dict((r, [round(y, 8) for y in c2])
                          for r, c2 in v.curva.items()),
        },
        'giocatori': gio,
        'limiti': limiti,
    }


def main():
    uscita = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        BASE, 'pubblicazione', 'attesi.json')
    # I dati sono quelli veri, l'asta no: questo script ne gioca una finta
    # dall'inizio alla fine, e farlo sul file dell'asta vera vorrebbe dire
    # cancellare quella di chi sta giocando.
    with dbmod.asta_di_servizio() as con:
        return _dump(con, uscita)


def _dump(con, uscita):
    reg = regmod.carica()
    st = StatoAsta(con, reg)
    st.inizializza(NOMI[1:], mio_nome=NOMI[0])
    v = Valutatore(con, reg, st)
    o = Ottimizzatore(v)
    c = Consigliere(v, o)

    rng = random.Random(20260909)
    fuori = {'nomi': NOMI, 'tappe': []}
    fatti_finora = []
    for k, quante in enumerate(TAPPE):
        da_fare = quante - len(fatti_finora)
        if da_fare > 0:
            nuovi = scegli_acquisti(v, st, da_fare, rng)
            fatti_finora += nuovi
            v = Valutatore(con, reg, st)
        o = Ottimizzatore(v)
        c = Consigliere(v, o)
        print('  tappa %d: %d acquisti registrati' % (k, len(st.acquisti())))
        fuori['tappe'].append({
            'acquisti': list(fatti_finora),
            'dati': istantanea(v, o, c, st),
        })

    # Le due scene costruite: ognuna riparte da un'asta vuota, perche' quello
    # che deve essere riproducibile e' la **situazione**, non la strada per
    # arrivarci.
    for k, scena in enumerate([scena_portieri_miei, scena_difesa_scoperta]):
        st2 = StatoAsta(con, reg)
        st2.inizializza(NOMI[1:], mio_nome=NOMI[0])
        v2 = Valutatore(con, reg, st2)
        acquisti = scena(v2, st2)
        v2 = Valutatore(con, reg, st2)
        o2 = Ottimizzatore(v2)
        c2 = Consigliere(v2, o2)
        print('  scena %s: %d acquisti, fase %s'
              % (scena.__name__, len(acquisti), c2.fase()))
        fuori['tappe'].append({
            'acquisti': acquisti,
            'dati': istantanea(v2, o2, c2, st2),
        })

    cartella = os.path.dirname(uscita)
    if cartella and not os.path.isdir(cartella):
        os.makedirs(cartella)
    # --- e adesso gli stessi conti con altri regolamenti -----------------
    #
    # Ad asta vuota, perche' quello che si sta verificando qui non e' la
    # strategia ma la **scala**: rimpiazzo, curva dei prezzi, budget per
    # reparto e limiti nascono tutti dal numero di squadre e dal monte crediti.
    fuori['regolamenti'] = []
    for modifiche in REGOLAMENTI:
        reg2 = regmod.Regole(regmod.applica(regmod.carica()._d, modifiche))
        st2 = StatoAsta(con, reg2)
        st2.inizializza(NOMI[1:reg2.partecipanti], mio_nome=NOMI[0])
        v2 = Valutatore(con, reg2, st2)
        o2 = Ottimizzatore(v2)
        c2 = Consigliere(v2, o2)
        print('  regolamento %s: rimpiazzo P %.3f, opt %.1f'
              % (modifiche or 'quello del file', v2.rimpiazzo_fm['P'], o2.opt()))
        fuori['regolamenti'].append({
            'modifiche': modifiche,
            'nomi': NOMI[:reg2.partecipanti],
            'dati': istantanea(v2, o2, c2, st2),
        })

    with io.open(uscita, 'w', encoding='utf-8') as f:
        json.dump(fuori, f, ensure_ascii=False, separators=(',', ':'))
    print('scritto %s (%.0f KB)' % (uscita, os.path.getsize(uscita) / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
