# -*- coding: utf-8 -*-
"""La stagione: quale si gioca, quali sono finite, a che punto siamo.

Prima queste informazioni erano scritte a mano in cinque posti diversi -
`'2025-26'` in `proiezioni.py`, la data di lettura in `consenso.py`, le
stagioni in `build.py` - e aggiornarle a ogni campionato voleva dire
ricordarsi di tutti e cinque. Dimenticarne uno non da' errori: da' numeri
calcolati su una stagione sbagliata, che e' peggio.

Adesso stanno qui, e basta cambiare questo file.

**A campionato iniziato** la stagione in corso entra anche lei nei conti, ma
con un'avvertenza che vale per tutto il resto: di una stagione cominciata da
cinque giornate i minuti disponibili sono cinque partite, non trentotto.
Contarla come intera direbbe che chi le ha giocate tutte e cinque ha fatto
un settimo di stagione, cioe' che e' una riserva.
"""
import csv, datetime, os

GIORNATE = 38
MINUTI_PARTITA = 90

# La stagione che si gioca, e quelle concluse dalla piu' recente.
CORRENTE = '2026-27'
CONCLUSE = ['2025-26', '2024-25', '2023-24']
ULTIMA_CONCLUSA = CONCLUSE[0]

# Quanto conta, minuto per minuto, il rendimento di ogni stagione. La
# stagione in corso pesa di piu' dell'ultima conclusa: e' la squadra di
# adesso, l'allenatore di adesso, il ruolo di adesso. Siccome i minuti
# giocati sono pochi, il suo peso complessivo resta comunque piccolo finche'
# le giornate non si accumulano: la regressione verso la media la tiene a
# bada da sola.
PESO_RENDIMENTO = {CORRENTE: 2.00, '2025-26': 1.00, '2024-25': 0.55,
                   '2023-24': 0.30}
# Per il minutaggio la memoria e' piu' corta, e la stagione in corso conta
# ancora di piu': chi gioca adesso e' la domanda.
PESO_MINUTAGGIO = {CORRENTE: 2.00, '2025-26': 1.00, '2024-25': 0.35,
                   '2023-24': 0.15}

# **Chi gioca adesso lo dice la stagione in corso.** Con un peso per minuto
# fisso, cinque giornate erano 450 minuti contro i 3420 dell'anno scorso: anche
# a peso doppio valevano un quarto di una stagione, e il modello continuava a
# credere piu' all'allenatore dell'anno prima che a quello di adesso. Il peso
# della stagione in corso si misura invece **sull'intera stagione**: da quando
# si gioca, conta una volta e mezza l'ultima conclusa, qualunque sia il numero
# di giornate. Il campione per la regressione resta quello vero (vedi
# `proiezioni._campione`): cinque partite non diventano quaranta, pesano solo
# di piu' nella media.
PESO_CORRENTE_IN_STAGIONI = 1.5


def data_riferimento(fonti_csv=None):
    """Il giorno a cui si riferiscono i dati: quello dell'ultima lettura.

    Serve a contare le giornate gia' giocate e quelle che un infortunato
    saltera' da qui in avanti. Si prende dalla data di lettura degli
    infortuni in `fonti.csv`, che e' la lettura piu' volatile; la variabile
    d'ambiente `FANTAHACKED_OGGI` la sovrascrive, e senza nessuna delle due
    vale oggi.
    """
    forzata = os.environ.get('FANTAHACKED_OGGI')
    if forzata:
        return forzata
    if fonti_csv and os.path.exists(fonti_csv):
        with open(fonti_csv, encoding='utf-8', newline='') as f:
            date = [r.get('letta_il') or '' for r in csv.DictReader(f)
                    if 'infortuni' in (r.get('fonte') or '')]
        date = [d for d in date if d]
        if date:
            return max(date)
    return datetime.date.today().isoformat()


def giornate_giocate(calendario, oggi):
    """Quante giornate sono gia' state giocate a quella data.

    `calendario` e' un elenco di coppie (giornata, data). Una giornata conta
    come giocata quando tutte le sue partite stanno prima di `oggi`.
    """
    ultima = {}
    for giornata, data in calendario:
        if not data:
            continue
        g = int(giornata)
        ultima[g] = max(ultima.get(g, ''), str(data)[:10])
    return sum(1 for d in ultima.values() if d < oggi)


def peso_minutaggio(stag, giocate):
    """Il peso, per minuto disponibile, di una stagione nel minutaggio atteso."""
    base = PESO_MINUTAGGIO.get(stag, 0.0)
    if stag == CORRENTE and giocate > 0:
        return max(base, PESO_CORRENTE_IN_STAGIONI * GIORNATE / float(giocate))
    return base


def minuti_disponibili(stagione, giocate):
    """I minuti che una stagione ha messo a disposizione di un giocatore."""
    if stagione == CORRENTE:
        return max(0, giocate) * MINUTI_PARTITA
    return GIORNATE * MINUTI_PARTITA
