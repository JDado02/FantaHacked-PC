# -*- coding: utf-8 -*-
"""Ricostruisce il prezzo massimo dei miei acquisti gia' registrati.

Il limite del motore si salva insieme all'acquisto da quando esiste la colonna
`acquisti.limite`. Chi aveva un'asta gia' aperta prima non ce l'ha, e senza
quel numero la rosa non puo' dire se un acquisto e' stato un errore o solo un
giocatore fuori scala pagato sopra la media di mercato.

Qui si recupera rigiocando l'asta dall'inizio su una copia del database: prima
di ogni mio acquisto si chiede al motore quanto valeva quel giocatore in quel
momento, e il numero si riscrive nell'asta vera. Non si tocca nient'altro:
prezzi, presidenti e ordine restano quelli.

Uso:  python recupera_limiti.py
"""
import os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import percorsi
import db as dbmod
import regole as regmod
from asta import StatoAsta, ErroreAsta
from valutazione import Valutatore
from ottimizzatore import Ottimizzatore


def recupera(percorso=None, verboso=True):
    percorso = percorso or percorsi.DB_FILE
    vero = dbmod.connetti(percorso)
    righe = [dict(r) for r in vero.execute(
        'SELECT seq, giocatore_id, presidente_id, prezzo, limite'
        ' FROM acquisti ORDER BY seq')]
    io_riga = vero.execute('SELECT id FROM presidenti WHERE io=1').fetchone()
    if not righe or io_riga is None:
        if verboso:
            print('Nessun acquisto da recuperare.')
        return 0
    io_id = io_riga['id']
    da_fare = [r for r in righe if r['presidente_id'] == io_id
               and r['limite'] is None]
    if not da_fare:
        if verboso:
            print('I limiti ci sono gia\' tutti.')
        return 0

    # Si rigioca su una copia: il database vero non deve mai trovarsi a meta'
    # di una ricostruzione se qualcosa va storto.
    cartella = tempfile.mkdtemp(prefix='fantahacked_')
    copia = os.path.join(cartella, 'replay.db')
    shutil.copyfile(percorso, copia)
    con = dbmod.connetti(copia)
    con.execute('DELETE FROM acquisti')
    con.commit()
    reg = regmod.carica()
    st = StatoAsta(con, reg)
    v = Valutatore(con, reg, st)
    o = Ottimizzatore(v)

    trovati = {}
    for r in righe:
        limite = None
        if r['presidente_id'] == io_id:
            x = v.g.get(r['giocatore_id'])
            if x is not None:
                try:
                    limite = int(o.max_bid(x)[0])
                except Exception:
                    limite = None
            trovati[r['seq']] = limite
        try:
            st.registra(r['giocatore_id'], r['presidente_id'], r['prezzo'],
                        limite=limite)
        except ErroreAsta:
            # Un acquisto che oggi non sarebbe valido (rose cambiate a mano):
            # si salta, meglio un limite mancante che una ricostruzione falsa.
            continue
        v.aggiorna()
        o.aggiorna()
    con.close()
    shutil.rmtree(cartella, ignore_errors=True)

    scritti = 0
    for seq, limite in trovati.items():
        if limite is None:
            continue
        vero.execute('UPDATE acquisti SET limite=? WHERE seq=? AND limite IS NULL',
                     (limite, seq))
        scritti += vero.total_changes and 1 or 0
    vero.commit()
    if verboso:
        for r in vero.execute(
                'SELECT g.nome, a.prezzo, a.limite FROM acquisti a'
                ' JOIN giocatori g ON g.id=a.giocatore_id'
                ' WHERE a.presidente_id=? ORDER BY a.seq', (io_id,)):
            print('  %-20s pagato %3d   limite di allora %s'
                  % (r['nome'], r['prezzo'], r['limite']))
    return len(trovati)


if __name__ == '__main__':
    n = recupera()
    print('\nLimiti ricostruiti: %d' % n)
