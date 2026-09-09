# -*- coding: utf-8 -*-
"""I prezzi attesi devono sempre sommare ai crediti che restano in gioco.

E' la proprieta' che rende `prezzo_atteso` una previsione e non un'opinione:
se la lega ha ancora 3834 crediti da spendere e i giocatori ancora da vendere,
sommati, ne valgono 3720, la differenza sono centoquattordici crediti che
qualcuno spendera' e che il motore non ha assegnato a nessuno.

`test_motore.py` la controlla a inizio asta, dove tiene. Questa la segue
**durante** l'asta, che e' dove `ispeziona.py` l'ha vista rompersi.
"""
import os, random, shutil, sys, tempfile

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(QUI), 'motore'))

RUOLI = ('P', 'D', 'C', 'A')


def prova(peso):
    import valutazione
    valutazione.PESO_CURVA = peso
    import percorsi, db as dbmod, regole as regmod
    from asta import StatoAsta, ErroreAsta
    cartella = tempfile.mkdtemp()
    dst = os.path.join(cartella, 'f.db')
    shutil.copyfile(percorsi.DB_FILE, dst)
    con = dbmod.connetti(dst)
    reg = regmod.carica()
    st = StatoAsta(con, reg)
    st.inizializza(['A', 'B', 'C', 'D', 'E', 'F', 'G'], mio_nome='Io')
    v = valutazione.Valutatore(con, reg, st)
    rng = random.Random(3)
    print('  curva %.1f' % peso)
    tappe = (0, 25, 60, 100, 150)
    fatte = 0
    for meta in tappe:
        tentativi = 0
        while fatte < meta and tentativi < 400:
            tentativi += 1
            ruolo = RUOLI[fatte % 4]
            liberi = [x for x in v.disponibili(ruolo)
                      if not (reg.portieri_pacchetto and ruolo == 'P'
                              and not x.titolare_por)]
            if not liberi:
                continue
            x = rng.choice(liberi[:30])
            presidente = 1 + (fatte % reg.partecipanti)
            prezzo = max(1, min(st.liquidita(presidente),
                                int(v.prezzo_chiusura(x) or 1)))
            try:
                st.registra(x.id, presidente, prezzo)
                fatte = len(st.venduti())
            except ErroreAsta:
                v.g.pop(x.id, None)
        v.aggiorna()
        somma = sum(x.prezzo_atteso for r in RUOLI for x in v.candidati[r])
        candidati = sum(len(v.candidati[r]) for r in RUOLI)
        slot = sum(st.slot_residui_ruolo(r) for r in RUOLI)
        print('    dopo %3d vendite: prezzi %7.0f   crediti %5d   scarto %+6.0f'
              '   (candidati %d, slot da assegnare %d)'
              % (len(st.venduti()), somma, v.crediti_residui,
                 somma - v.crediti_residui, candidati, slot))
    con.close()
    shutil.rmtree(cartella, ignore_errors=True)


if __name__ == '__main__':
    prova(float(sys.argv[1]) if len(sys.argv) > 1 else 0.6)
