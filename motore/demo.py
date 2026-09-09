# -*- coding: utf-8 -*-
"""Dimostrazione del motore: listone valutato, poi una chiamata in asta live.

Uso:  python demo.py
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db as dbmod, regole as regmod, proiezioni as prmod
from asta import StatoAsta
from valutazione import Valutatore

AVVERSARI = ['Bea', 'Chiara', 'Dario', 'Elena', 'Fabio', 'Gaia', 'Hugo']


def riga(x, rif=True):
    return ('   %-20s %-11s %5d %7.0f %7.1f %7.1f  %6.1f  %s'
            % (x.nome[:20], x.squadra[:11], x.qi, x.punti, x.vor,
               x.prezzo_mercato, x.prezzo_riferimento,
               '' if x.metodo == 'storico' else 'stima da quotazione'))


def intestazione():
    return ('   %-20s %-11s %5s %7s %7s %7s  %6s'
            % ('nome', 'squadra', 'qt', 'punti', 'VOR', 'prezzo', 'rifer.'))


def main():
    con = dbmod.connetti()
    reg = regmod.carica()
    if con.execute('SELECT COUNT(*) FROM proiezioni').fetchone()[0] == 0:
        prmod.esegui(con, reg)

    stato = StatoAsta(con, reg).inizializza(AVVERSARI, mio_nome='Davide')
    v = Valutatore(con, reg, stato)

    print('=' * 78)
    print(reg.riassunto())
    print('=' * 78)
    print('\n' + v.riassunto())

    print('\n\nPREZZI CONSIGLIATI A INIZIO ASTA')
    print('("rifer." = prezzo medio storicamente pagato, riportato al budget della lega)')
    for ruolo, quanti in (('P', 6), ('D', 8), ('C', 8), ('A', 8)):
        print('\n  -- %s --' % ruolo)
        print(intestazione())
        for x in v.disponibili(ruolo, quanti):
            print(riga(x))

    # ------------------------------------------------------------------ live
    print('\n\n' + '=' * 78)
    print("SIMULAZIONE: la stanza parte forte sugli attaccanti")
    print('=' * 78)
    spesi = []
    for pid, g in zip(range(2, 9), v.disponibili('A')[:7]):
        prezzo = int(round(g.prezzo_mercato * 1.35))
        stato.registra(g.id, pid, prezzo)
        spesi.append((g.nome, prezzo, g.prezzo_mercato))
    v.aggiorna()
    print('\n  Sette attaccanti venduti il 35%% sopra il prezzo consigliato:')
    for n, p, m in spesi:
        print('    %-20s pagato %3d   (mercato %.0f)' % (n, p, m))
    print('\n' + v.riassunto())

    print('\n\n  Effetto sul resto del listone:')
    print(intestazione())
    for ruolo in ('D', 'C', 'A'):
        x = v.disponibili(ruolo, 1)[0]
        print(riga(x))

    # -------------------------------------------------------- scheda giocatore
    print('\n\n' + '=' * 78)
    print('SCHEDA DI UNA CHIAMATA')
    print('=' * 78)
    for ruolo in ('D', 'A'):
        x = v.disponibili(ruolo, 1)[0]
        conc = v.concorrenti(x)
        chiusura = v.prezzo_chiusura(x)
        io = stato.io()
        print('\n  %s  (%s, %s)  quotazione %d' % (x.nome, ruolo, x.squadra, x.qi))
        print('    punti attesi %.0f   VOR %.1f   affidabilita %.2f  [%s]'
              % (x.punti, x.vor, x.affidabilita, x.metodo))
        print('    prezzo di mercato ora .... %6.0f' % x.prezzo_mercato)
        print('    chiusura attesa .......... %6.0f' % chiusura)
        print('    tua liquidita massima .... %6d' % stato.liquidita(io['id']))
        print('    concorrenti ancora in gioco (%d):' % len(conc))
        for c in conc[:4]:
            print('      %-10s crediti %3d, puo\' arrivare a %3d'
                  % (c['nome'], c['crediti'], c['liquidita']))
        alt = [y for y in v.disponibili(ruolo, 6) if y.id != x.id][:3]
        print('    se lo perdi:')
        for y in alt:
            perc = 100.0 * y.punti / x.punti if x.punti else 0
            print('      %-18s %5.0f (%.0f%% dei punti) a %.0f crediti'
                  % (y.nome[:18], y.punti, perc, y.prezzo_mercato))

    stato.inizializza(AVVERSARI, mio_nome='Davide')
    con.close()


if __name__ == '__main__':
    main()
