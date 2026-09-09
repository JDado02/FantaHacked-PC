# -*- coding: utf-8 -*-
"""Cinque aste giocate dal posto di Davide, col motore che decide per lui.

Il motore usa quello vero: `Ottimizzatore.max_bid` a ogni chiamata, ricalcolato
dopo ogni assegnazione, esattamente come farebbe il programma in asta. Gli
avversari sono umani: pagano intorno al prezzo giusto ma sbagliano, quasi
sempre in eccesso, e ognuno ha il suo carattere sui reparti.

Regola d'asta: vince chi offre di piu' e paga la seconda offerta piu' un
credito, che e' come finisce davvero un rilancio.
"""
import math, os, random, shutil, sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, 'motore'))
import percorsi, db as dbmod, regole as regmod
from asta import StatoAsta, ErroreAsta
from valutazione import Valutatore
from ottimizzatore import Ottimizzatore
from strategia import Consigliere

SCR = os.path.dirname(os.path.abspath(__file__))
RUOLI = ('P', 'D', 'C', 'A')
NOMI = ['Davide', 'Jacopo', 'Windser', 'Luca', 'Viane', 'Giorgio', 'Fede', 'Canzia']

# Quanto sbaglia un umano, per ruolo: mediana del moltiplicatore e dispersione.
# Sbilanciati verso l'alto, perche' in asta si sbaglia pagando troppo.
RUMORE = {'P': (1.05, 0.16), 'D': (1.06, 0.22),
          'C': (1.10, 0.26), 'A': (1.22, 0.32)}
CONCENTRAZIONE = 26.0     # quanto si somigliano i caratteri delle otto squadre


def dirichlet(rng, alpha):
    campioni = [rng.gammavariate(a, 1.0) for a in alpha]
    tot = sum(campioni) or 1.0
    return [c / tot for c in campioni]


def caratteri(rng, reg):
    """A ognuno la sua idea di come vanno divisi i crediti fra i reparti."""
    base = [reg.quota_budget[r] for r in RUOLI]
    fuori = {}
    for nome in NOMI[1:]:
        quote = dirichlet(rng, [max(0.4, q * CONCENTRAZIONE) for q in base])
        fuori[nome] = dict(zip(RUOLI, quote))
    return fuori


def offerta_umana(rng, x, ruolo, carattere, crediti, liquidita, slot_ruolo,
                  slot_totali, speso_ruolo, reg):
    """Fin dove si spinge un avversario su quel giocatore.

    Parte dal prezzo che quel giocatore varrebbe in una stanza normale, lo
    piega col carattere di chi offre e con l'errore umano, e lo taglia con i
    crediti che ha davvero: nessuno puo' offrire piu' di quanto gli resta
    tenendo un credito per ogni slot ancora scoperto.
    """
    if slot_ruolo <= 0 or liquidita < 1:
        return 0
    base = x.prezzo_base or 1.0
    # Il carattere sposta il prezzo in proporzione a quanto quel presidente
    # tiene a quel reparto rispetto alla media della lega.
    inclinazione = carattere[ruolo] / max(1e-6, reg.quota_budget[ruolo])
    mu, sigma = RUMORE[ruolo]
    errore = rng.lognormvariate(math.log(mu), sigma)
    # Ogni tanto due si intestardiscono e il prezzo esplode.
    if rng.random() < (0.05 if ruolo == 'A' else 0.02):
        errore *= rng.uniform(1.4, 2.0)
    valore = base * (0.45 + 0.55 * inclinazione) * errore
    # Non si svena: quello che ha destinato al reparto meno quello che ci ha
    # gia' speso, diviso per gli slot che gli restano li' dentro, per tre.
    tetto_reparto = max(1.0, carattere[ruolo] * reg.crediti - speso_ruolo)
    valore = min(valore, tetto_reparto * 3.0 / max(1, slot_ruolo))
    return int(max(0, min(round(valore), liquidita)))


def gioca(seme, verboso=False):
    rng = random.Random(seme)
    dst = os.path.join(SCR, 'sim_%d.db' % seme)
    shutil.copyfile(percorsi.DB_FILE, dst)
    con = dbmod.connetti(dst)
    reg = regmod.carica()
    st = StatoAsta(con, reg)
    st.inizializza(NOMI[1:], mio_nome=NOMI[0])
    v = Valutatore(con, reg, st)
    o = Ottimizzatore(v)
    c = Consigliere(v, o)
    carattere = caratteri(rng, reg)
    per_id = dict((p['nome'], p['id']) for p in st.presidenti())
    io_id = st.io()['id']
    speso = dict((n, dict((r, 0) for r in RUOLI)) for n in NOMI)

    def stato_di(nome):
        pid = per_id[nome]
        return pid, st.crediti(pid), st.liquidita(pid)

    while True:
        fase = c.fase()
        if fase is None:
            break
        liberi = [x for x in v.disponibili(fase)
                  if not (reg.portieri_pacchetto and fase == 'P'
                          and not x.titolare_por)]
        if not liberi:
            break
        # Chi chiama sceglie fra i primi della lista, non sempre il primo: in
        # una stanza vera l'ordine delle chiamate non e' una classifica.
        finestra = sorted(liberi, key=lambda y: -(y.prezzo_base or 0))[:8]
        x = rng.choice(finestra)

        offerte = []
        for nome in NOMI[1:]:
            pid, crediti, liq = stato_di(nome)
            if st.slot_residui(pid, fase) <= 0:
                continue
            off = offerta_umana(rng, x, fase, carattere[nome], crediti, liq,
                                st.slot_residui(pid, fase), st.slot_residui(pid),
                                speso[nome][fase], reg)
            if off >= 1:
                offerte.append((off, nome))

        mio = 0
        if st.slot_residui(io_id, fase) > 0:
            limite, _ = o.max_bid(x)
            mio = int(limite)
        if mio >= 1:
            offerte.append((mio, NOMI[0]))
        if not offerte:
            # Nessuno lo vuole: resta fuori, ma il ciclo deve avanzare.
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
        try:
            st.registra(x.id, pid, prezzo)
        except ErroreAsta:
            v.g.pop(x.id, None)
            continue
        speso[vincitore][fase] += prezzo
        # Regola della lega: col titolare arrivano le sue riserve a 1.
        if reg.portieri_pacchetto and fase == 'P':
            for rid in v.riserve_di(x.id):
                if rid in st.venduti():
                    continue
                if st.slot_residui(pid, 'P') <= 0:
                    break
                try:
                    st.registra(rid, pid, 1)
                    speso[vincitore]['P'] += 1
                except ErroreAsta:
                    pass
        c.aggiorna()
        if verboso:
            print('  %-20s -> %-8s %3d' % (x.nome, vincitore, prezzo))

    rose = {}
    for nome in NOMI:
        pid = per_id[nome]
        rosa = dict((r, []) for r in RUOLI)
        for a in st.acquisti():
            if a['presidente_id'] != pid:
                continue
            g = v.g.get(a['giocatore_id'])
            rosa[a['ruolo']].append({
                'nome': a['nome'], 'squadra': a['squadra'], 'prezzo': a['prezzo'],
                'fm': round(g.fm, 2) if g else None,
                'presenze': int(round(g.presenze)) if g else None,
                'punti': round(g.presenze * g.fm) if g else 0,
                'base': int(round(g.prezzo_base)) if g else 1,
                'grado': (g.grado or '?') if g else '?',
            })
        for r in RUOLI:
            rosa[r].sort(key=lambda d: -d['prezzo'])
        rose[nome] = rosa
    con.close()
    try:
        os.remove(dst)
    except OSError:
        pass
    return rose


def undici_atteso(rosa):
    """Punti di stagione dei titolari: 1 portiere, 4 difensori, 4 c, 2 a."""
    quanti = {'P': 1, 'D': 4, 'C': 4, 'A': 2}
    tot = 0.0
    for r in RUOLI:
        migliori = sorted(rosa[r], key=lambda d: -(d['punti'] or 0))[:quanti[r]]
        tot += sum(d['punti'] or 0 for d in migliori)
    return tot


if __name__ == '__main__':
    semi = [101, 202, 303, 404, 505]
    tutte = []
    for i, seme in enumerate(semi, start=1):
        rose = gioca(seme)
        tutte.append(rose)
        mia = rose['Davide']
        spesa = dict((r, sum(d['prezzo'] for d in mia[r])) for r in RUOLI)
        print('\n' + '=' * 72)
        print('ASTA %d   spesa  P %d / D %d / C %d / A %d   totale %d'
              % (i, spesa['P'], spesa['D'], spesa['C'], spesa['A'],
                 sum(spesa.values())))
        for r in RUOLI:
            print('  %s' % {'P': 'PORTIERI', 'D': 'DIFENSORI',
                            'C': 'CENTROCAMPISTI', 'A': 'ATTACCANTI'}[r])
            for d in mia[r]:
                print('     %-22s %-12s %3d cr  (valeva %3d)  fm %.2f su %2d  %s'
                      % (d['nome'], d['squadra'], d['prezzo'], d['base'],
                         d['fm'] or 0, d['presenze'] or 0, d['grado']))
        classifica = sorted(((undici_atteso(rose[n]), n) for n in NOMI),
                            reverse=True)
        print('  --- undici titolare atteso, punti di stagione ---')
        for posto, (punti, n) in enumerate(classifica, start=1):
            print('     %d. %-10s %6.0f%s' % (posto, n, punti,
                                              '   <-- tu' if n == 'Davide' else ''))
