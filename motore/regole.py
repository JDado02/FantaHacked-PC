# -*- coding: utf-8 -*-
"""Lettura e validazione di regole_lega.json.

Le regole entrano ovunque nel motore: un valore sbagliato qui falsa ogni
prezzo consigliato. Per questo vengono validate all'avvio, non usate a fiducia.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import percorsi

GIORNATE = 38


class Regole(object):

    def __init__(self, d):
        self._d = d
        self.partecipanti     = int(d['partecipanti'])
        self.crediti          = int(d['crediti_iniziali'])
        r = d['rosa']
        self.slot = {'P': int(r['portieri']), 'D': int(r['difensori']),
                     'C': int(r['centrocampisti']), 'A': int(r['attaccanti'])}
        self.slot_totali = sum(self.slot.values())
        self.sostituzioni = int(d.get('sostituzioni', 0))

        b = d['bonus_malus']
        self.gol_ruolo = {'P': float(b['gol_portiere']), 'D': float(b['gol_difensore']),
                          'C': float(b['gol_centrocampista']), 'A': float(b['gol_attaccante'])}
        self.v_assist      = float(b['assist'])
        self.v_gol_subito  = float(b['gol_subito'])
        self.v_rig_parato  = float(b['rigore_parato'])
        self.v_rig_segnato = float(b.get('rigore_segnato', b['gol_attaccante']))
        self.v_rig_sbagl   = float(b['rigore_sbagliato'])
        self.v_autogol     = float(b['autogol'])
        self.v_amm         = float(b['ammonizione'])
        self.v_esp         = float(b['espulsione'])

        # --- come si spendono i crediti in questa lega ------------------
        # Non e' un parametro del gioco: e' una previsione sul comportamento
        # della stanza, e serve a stimare quanto costera' ogni giocatore. Il
        # valore di un giocatore e il suo prezzo sono due cose diverse, e
        # confonderle e' l'errore che porta a farsi una rosa di buoni affari
        # inutili.
        m = d.get('mercato', {})
        rip = m.get('ripartizione_budget') or {}
        grezza = {'P': float(rip.get('portieri', 9)),
                  'D': float(rip.get('difensori', 16)),
                  'C': float(rip.get('centrocampisti', 28)),
                  'A': float(rip.get('attaccanti', 47))}
        somma = sum(grezza.values()) or 1.0
        self.quota_budget = dict((r, grezza[r] / somma) for r in ('P', 'D', 'C', 'A'))
        # Due ripartizioni, non una. Quella qui sopra e' il **piano**: con che
        # forma si vuole uscire dall'asta. Questa e' la **previsione** su come
        # spende la stanza, e serve a un'altra domanda: quanto costera'.
        #
        # Tenerle insieme costava da entrambe le parti. Misurata sui 200
        # prezzi davvero pagati in una lega vera, la ripartizione del piano
        # (7/12/21/60) sbagliava del 50% in crediti e sistematicamente: gli
        # attaccanti sopravvalutati del 31%, i difensori sottovalutati del
        # 34%. Con la ripartizione osservata (8/18/28/46) l'errore scende al
        # 37% e la distorsione per reparto sparisce. Ma usarla anche per
        # pianificare fa **giocare peggio**: cento aste dicono 91 vittorie
        # invece di 98. E' lo stesso motivo per cui esiste `prezzo_piano`:
        # il numero da mostrare e il numero con cui decidere non coincidono.
        rip_m = m.get('ripartizione_mercato') or rip
        grezza_m = {'P': float(rip_m.get('portieri', grezza['P'])),
                    'D': float(rip_m.get('difensori', grezza['D'])),
                    'C': float(rip_m.get('centrocampisti', grezza['C'])),
                    'A': float(rip_m.get('attaccanti', grezza['A']))}
        somma_m = sum(grezza_m.values()) or 1.0
        self.quota_mercato = dict((r, grezza_m[r] / somma_m)
                                  for r in ('P', 'D', 'C', 'A'))
        self.impara_mercato = bool(m.get('impara_dall_asta', True))
        self.fiducia_mercato = min(1.0, max(0.0,
                                            float(m.get('fiducia_nel_mercato', 0.5))))
        self.portieri_pacchetto = bool(m.get('portieri_a_pacchetto', False))
        # Quanto del proprio budget tenere comunque da parte per ogni reparto.
        ris = m.get('riserva_minima_per_ruolo') or {}
        self.riserva_ruolo = {
            'P': max(0.0, float(ris.get('portieri', 0))) / 100.0,
            'D': max(0.0, float(ris.get('difensori', 0))) / 100.0,
            'C': max(0.0, float(ris.get('centrocampisti', 0))) / 100.0,
            'A': max(0.0, float(ris.get('attaccanti', 0))) / 100.0}

        pi = d.get('portiere_imbattuto', {})
        self.imbattuto_attivo = bool(pi.get('attivo', False))
        self.imbattuto_bonus  = float(pi.get('bonus', 0))

        md = d.get('modificatore_difesa', {})
        self.mod_dif_attivo = bool(md.get('attivo', False))
        self.mod_dif_scala  = sorted(
            [(float(x['media_minima']), float(x['bonus'])) for x in md.get('scala', [])],
            key=lambda t: t[0])
        # Quanti giocatori entrano nel calcolo del modificatore.
        # "portiere + 3 migliori difensori" -> 1 portiere, 3 difensori.
        testo = str(md.get('componenti', '')).lower()
        self.mod_dif_n_por = 1 if 'portiere' in testo else 0
        self.mod_dif_n_dif = 3
        for tok in testo.replace('+', ' ').split():
            if tok.isdigit():
                self.mod_dif_n_dif = int(tok)
                break

        # I modificatori non attivi non incidono: nessuna scala da leggere.
        self.mod_cen_attivo = bool(d.get('modificatore_centrocampo', {}).get('attivo', False))
        self.mod_att_attivo = bool(d.get('modificatore_attacco', {}).get('attivo', False))
        self.mod_fair_attivo = bool(d.get('modificatore_fairplay', {}).get('attivo', False))

        self._valida()

    # ---------------------------------------------------------------- derivati
    @property
    def crediti_totali(self):
        return self.partecipanti * self.crediti

    @property
    def slot_lega(self):
        return self.partecipanti * self.slot_totali

    def slot_lega_ruolo(self, ruolo):
        """Quanti giocatori di quel ruolo verranno assegnati in tutta la lega.

        E' il numero che fissa il livello di rimpiazzo.
        """
        return self.partecipanti * self.slot[ruolo]

    @property
    def crediti_per_slot(self):
        return float(self.crediti_totali) / self.slot_lega

    # ---------------------------------------------------------------- validita'
    def _valida(self):
        e = []
        if not 2 <= self.partecipanti <= 20:
            e.append('partecipanti fuori scala: %d' % self.partecipanti)
        if self.crediti < self.slot_totali:
            e.append('crediti (%d) inferiori agli slot di rosa (%d): impossibile '
                     'riempire la rosa' % (self.crediti, self.slot_totali))
        for r, n in self.slot.items():
            if n < 1:
                e.append('slot %s non valido: %d' % (r, n))
        if self.mod_dif_attivo and not self.mod_dif_scala:
            e.append('modificatore di difesa attivo ma scala vuota')
        if self.mod_dif_attivo:
            bonus = [b for _, b in self.mod_dif_scala]
            if bonus != sorted(bonus):
                e.append('la scala del modificatore di difesa non e\' crescente')
        for r, q in self.quota_budget.items():
            if not 0.005 <= q <= 0.9:
                e.append("la quota di budget per %s e' fuori scala: %.1f%%"
                         % (r, 100 * q))
        if sum(self.riserva_ruolo.values()) > 1.0:
            e.append("le riserve minime per ruolo sommano a piu' del 100%%: %.0f%%"
                     % (100 * sum(self.riserva_ruolo.values())))
        if self.portieri_pacchetto and self.slot['P'] < 2:
            e.append('portieri a pacchetto ma la rosa ha meno di 2 portieri')
        for nome, attivo in (('centrocampo', self.mod_cen_attivo),
                             ('attacco', self.mod_att_attivo),
                             ('fairplay', self.mod_fair_attivo)):
            if attivo and not self._d.get('modificatore_' + nome, {}).get('scala'):
                e.append('modificatore di %s attivo ma scala vuota' % nome)
        if e:
            raise ValueError('regole_lega.json non valido:\n  - ' + '\n  - '.join(e))

    def bonus_modificatore(self, media):
        """Bonus a gradini per una data media dei voti difensivi."""
        b = 0.0
        for soglia, valore in self.mod_dif_scala:
            if media >= soglia:
                b = valore
        return b

    def riassunto(self):
        return (
            "Lega: %d squadre x %d crediti = %d crediti totali\n"
            "Rosa: %dP %dD %dC %dA = %d slot  ->  %d giocatori assegnati\n"
            "Mercato: %.1f crediti per slot\n"
            "Spesa attesa per ruolo: %s\n"
            "Modificatore difesa: %s%s"
        ) % (self.partecipanti, self.crediti, self.crediti_totali,
             self.slot['P'], self.slot['D'], self.slot['C'], self.slot['A'],
             self.slot_totali, self.slot_lega, self.crediti_per_slot,
             ' '.join('%s %.0f%%' % (r, 100 * self.quota_budget[r])
                      for r in ('P', 'D', 'C', 'A')),
             'attivo' if self.mod_dif_attivo else 'non attivo',
             (' (%d portiere + %d difensori, scala %s)' % (
                 self.mod_dif_n_por, self.mod_dif_n_dif,
                 ' '.join('>=%g:+%g' % t for t in self.mod_dif_scala)))
             if self.mod_dif_attivo else '')


def carica(percorso=None):
    if percorso is None:
        percorso = os.path.join(percorsi.DATABASE, 'regole_lega.json')
    with open(percorso, encoding='utf-8') as f:
        return Regole(json.load(f))


if __name__ == '__main__':
    print(carica().riassunto())
