# -*- coding: utf-8 -*-
"""Bonus atteso del modificatore di difesa.

Il regolamento definisce il bonus a gradini sulla media dei voti di portiere e
tre migliori difensori. Ma quella media si calcola **ogni giornata**, e i voti
oscillano: una squadra con media attesa 6.24 supera comunque la soglia di 6.25
in circa meta' delle giornate.

Percio' il bonus atteso NON e' `bonus(media_attesa)`: e' il valore atteso della
funzione a gradini rispetto al rumore giornaliero. Integrando, la funzione
diventa liscia e crescente, e ogni decimo di media voto acquista valore. E'
quello che rende calcolabile il valore marginale di un difensore.

Assunzione dichiarata: la deviazione standard di un singolo voto di Serie A e'
circa 0.65. La media di N voti indipendenti ha quindi sd 0.65/sqrt(N). Il dato
non e' ricavabile dal database, che contiene medie stagionali e non voti
partita per partita: e' una stima da letteratura, esposta come parametro.
"""
import math

SD_VOTO_SINGOLO = 0.65
GIORNATE = 38


def sd_media(n_giocatori):
    """Deviazione standard della media di n voti in una singola giornata."""
    return SD_VOTO_SINGOLO / math.sqrt(max(n_giocatori, 1))


def _phi(z):
    """Funzione di ripartizione della normale standard."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def bonus_atteso(media, scala, sd):
    """Valore atteso del bonus a gradini, dato il rumore giornaliero.

    scala: lista di (soglia, bonus) ordinata per soglia crescente.

    Si usa la forma incrementale: ogni scalino aggiunge (b_i - b_prec)
    moltiplicato per la probabilita' di superare la sua soglia.
    """
    if not scala or sd <= 0:
        b = 0.0
        for soglia, valore in scala:
            if media >= soglia:
                b = valore
        return b
    atteso = 0.0
    precedente = 0.0
    for soglia, valore in scala:
        p_supera = 1.0 - _phi((soglia - media) / sd)
        atteso += (valore - precedente) * p_supera
        precedente = valore
    return atteso


class Modificatore(object):
    """Calcolatore del contributo del modificatore di difesa, in punti stagione."""

    def __init__(self, regole):
        self.reg = regole
        self.attivo = regole.mod_dif_attivo
        self.n = regole.mod_dif_n_por + regole.mod_dif_n_dif
        self.sd = sd_media(self.n)
        self.scala = regole.mod_dif_scala

    def punti_stagione(self, media_voti):
        """Punti che il modificatore aggiunge in tutta la stagione."""
        if not self.attivo:
            return 0.0
        return GIORNATE * bonus_atteso(media_voti, self.scala, self.sd)

    def guadagno(self, media_base, media_nuova):
        """Punti guadagnati passando da una media difensiva all'altra."""
        return self.punti_stagione(media_nuova) - self.punti_stagione(media_base)

    def contributo_marginale(self, mv_giocatore, mv_sostituito, media_base):
        """Punti aggiunti sostituendo un componente della difesa con un altro.

        Il giocatore pesa 1/n sulla media, dove n e' il numero di componenti
        che entrano nel calcolo (portiere + difensori).
        """
        if not self.attivo:
            return 0.0
        delta = (mv_giocatore - mv_sostituito) / float(self.n)
        return self.guadagno(media_base, media_base + delta)


if __name__ == '__main__':
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import regole as regmod
    reg = regmod.carica()
    m = Modificatore(reg)
    print('Modificatore di difesa: %s' % ('attivo' if m.attivo else 'non attivo'))
    print('  componenti: %d  ->  sd della media giornaliera = %.3f' % (m.n, m.sd))
    print('  scala: %s\n' % ' '.join('>=%g:+%g' % t for t in m.scala))
    print('  %-14s %10s %10s %14s' % ('media attesa', 'a gradini', 'atteso', 'punti stagione'))
    for mu in (5.9, 6.0, 6.1, 6.2, 6.25, 6.3, 6.4, 6.5):
        print('  %-14.2f %10.2f %10.2f %14.0f'
              % (mu, reg.bonus_modificatore(mu),
                 bonus_atteso(mu, m.scala, m.sd), m.punti_stagione(mu)))
    print('\n  Valore di un difensore da 6.40 al posto di uno da 6.00,')
    print('  con difesa di partenza a 6.15: %+.1f punti stagione'
          % m.contributo_marginale(6.40, 6.00, 6.15))
