# -*- coding: utf-8 -*-
"""Quanto deve pesare il bonus di chi chiude una coppia.

Separando il prezzo del piano da quello mostrato si guadagnano diciassette
punti di stagione, ma si perde una proprieta' che serviva: comprato il
titolare, il limite sul socio non sale piu' cosi' spesso. La domanda e' se si
riprende alzando il bonus &mdash; che e' il posto giusto dove metterla,
perche' e' li' che il motore rappresenta il valore di chiudere la maglia.

Due misure per ogni peso: la proprieta' (su quante coppie il socio sale) e
l'esito (punti di stagione e giornate a rischio di restare in dieci).
"""
import multiprocessing, os, statistics, sys

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

PESI = (1.0, 2.0, 3.0)


def proprieta(peso):
    """Su venticinque coppie: comprato il titolare, il socio sale o scende?"""
    import ottimizzatore, percorsi, shutil, tempfile
    ottimizzatore.PESO_COPPIA = peso
    import db as dbmod, regole as regmod
    from asta import StatoAsta, ErroreAsta
    from valutazione import Valutatore
    from ottimizzatore import Ottimizzatore
    cartella = tempfile.mkdtemp()
    dst = os.path.join(cartella, 'f.db')
    shutil.copyfile(percorsi.DB_FILE, dst)
    con = dbmod.connetti(dst)
    reg = regmod.carica()
    st = StatoAsta(con, reg)
    st.inizializza(['A', 'B', 'C', 'D', 'E', 'F', 'G'], mio_nome='Io')
    v0 = Valutatore(con, reg, st)
    coppie = []
    for x in v0.g.values():
        for c in v0.compagni_di_maglia(x.id):
            if (c.get('copertura_buchi', 0) >= 0.8
                    and c['ruolo_nella_coppia'] == 'titolare'):
                coppie.append((x.id, c['altro']))
    su = giu = 0
    for a, b in coppie[:25]:
        st = StatoAsta(con, reg)
        st.inizializza(['A', 'B', 'C', 'D', 'E', 'F', 'G'], mio_nome='Io')
        v = Valutatore(con, reg, st)
        o = Ottimizzatore(v)
        prima = o.max_bid(v.g[b])[0]
        try:
            st.registra(a, 1, max(1, int(round(v.prezzo_chiusura(v.g[a]) or 1))))
        except ErroreAsta:
            continue
        v.aggiorna()
        dopo = Ottimizzatore(v).max_bid(v.g[b])[0]
        if dopo > prima:
            su += 1
        elif dopo < prima:
            giu += 1
    con.close()
    shutil.rmtree(cartella, ignore_errors=True)
    return su, giu, len(coppie[:25])


def _asta(argomenti):
    seme, peso = argomenti
    import ottimizzatore
    ottimizzatore.PESO_COPPIA = peso
    import cento_aste as cento
    e = cento.gioca(seme, 'mercato')
    altri = [p for n, p in e['punti'].items() if n != cento.NOMI[0]]
    return peso, seme, e['punti'][cento.NOMI[0]], max(altri), e['rischio']


def main():
    quante = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    semi = [9000 + 19 * i for i in range(quante)]
    n = max(1, min(6, (os.cpu_count() or 2) - 1))
    with multiprocessing.Pool(n) as pool:
        righe = pool.map(_asta, [(s, p) for p in PESI for s in semi])
    per = {}
    for peso, seme, mio, primo, risc in righe:
        per.setdefault(peso, []).append((mio, primo, risc))
    print('%-8s %14s %10s %9s %10s'
          % ('bonus', 'il socio sale', 'vinte', 'punti', 'in dieci'))
    for peso in PESI:
        su, giu, tot = proprieta(peso)
        lista = per.get(peso) or []
        print('%-8.1f %6d su %-5d %6d/%-3d %9.0f %10.1f'
              % (peso, su, tot, sum(1 for a, b, _ in lista if a >= b),
                 len(lista), statistics.median([a for a, _, _ in lista]),
                 38 * statistics.median([r for _, _, r in lista])))


if __name__ == '__main__':
    main()
