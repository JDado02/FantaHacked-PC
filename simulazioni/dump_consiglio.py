# -*- coding: utf-8 -*-
"""Fotografa anche le liste dei consigli, non solo i numeri per giocatore.

`dump_equivalenza.py` confronta prezzi, limiti e verdetti: la matematica. Ma
quello che si guarda durante l'asta sono **le liste** &mdash; chi chiamare, su
chi ripiegare, chi far pagare agli altri &mdash; e quelle nascono da una
sequenza di ordinamenti, promozioni e deduplicazioni in cui e' facilissimo
sbagliare senza che nessun numero cambi.

Il caso che l'ha resa necessaria: nel motore JavaScript mancavano due righe in
fondo a `_svuota`, e la lista "da far pagare agli altri" usciva ordinata per
quanto converrebbe **comprarli** invece che per quanti crediti bruciano. Tutti
i numeri erano giusti; la lista diceva un'altra cosa.

Uso:  python dump_consiglio.py [file di uscita]
"""
import io, json, os, sys

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(QUI)
sys.path.insert(0, os.path.join(BASE, 'motore'))

import db as dbmod, regole as regmod
from asta import StatoAsta
from valutazione import Valutatore
from ottimizzatore import Ottimizzatore
from strategia import Consigliere


def riassunto(cons):
    """Solo quello che si vede: nomi, ordine, e i numeri accanto."""
    def voci(lista, extra=()):
        out = []
        for d in lista:
            v = {'id': d['id'], 'nome': d['nome'], 'verdetto': d['verdetto'],
                 'max_bid': d['max_bid'], 'chiusura': d['chiusura'],
                 'utilita': d['utilita'], 'categoria': d.get('categoria'),
                 # Da quando la fascia alta si ordina mettendo davanti chi
                 # scende in campo, questi due decidono **l'ordine**: se il
                 # telefono li calcolasse diversamente mostrerebbe gli stessi
                 # nomi in un'altra fila, che e' un difetto piu' subdolo di un
                 # numero sbagliato.
                 'titolare_pieno': d.get('titolare_pieno'),
                 'copre': d.get('copre')}
            for k in extra:
                v[k] = d.get(k)
            out.append(v)
        return out
    return {
        'fase': cons['fase'], 'serve': cons['serve'],
        'pressione': cons['pressione'],
        'indicazione': cons['indicazione'],
        'budget_ruolo': cons.get('budget_ruolo'),
        'copertura': cons.get('copertura'),
        'anticipo': cons.get('anticipo'),
        'anticipo_nome': cons.get('anticipo_nome'),
        'restano_nel_reparto': cons.get('restano_nel_reparto'),
        'valutati': cons.get('valutati'),
        'vuoti_testo': dict(cons.get('vuoti') or {}),
        'top': voci(cons['top']),
        'evitare': voci(cons['evitare']),
        'alternative': voci(cons['alternative']),
        'svuotare': voci(cons['svuotare'], ('brucia', 'contendenti', 'minacciosi')),
        'coppie': voci(cons['coppie'], ('con', 'copertura_buchi')),
        'vuoti': sorted(cons['vuoti'].keys()),
    }


def main():
    uscita = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        BASE, 'pubblicazione', 'attesi_consiglio.json')
    attesi = os.path.join(os.path.dirname(uscita), 'attesi.json')
    att = json.load(io.open(attesi, encoding='utf-8'))
    # Come sopra: i dati veri, l'asta usa e getta.
    with dbmod.asta_di_servizio() as con:
        return _dump(con, att, uscita)


def _dump(con, att, uscita):
    reg = regmod.carica()
    fuori = {'nomi': att['nomi'], 'tappe': []}
    for k, tappa in enumerate(att['tappe']):
        st = StatoAsta(con, reg)
        st.inizializza(att['nomi'][1:], mio_nome=att['nomi'][0])
        for g, p, pr in tappa['acquisti']:
            st.registra(g, p, pr, None)
        v = Valutatore(con, reg, st)
        o = Ottimizzatore(v)
        c = Consigliere(v, o)
        r = riassunto(c.consiglio())
        print('  tappa %d: fase %s, %d consigliati, %d alternative, %d da far pagare'
              % (k, r['fase'], len(r['top']), len(r['alternative']),
                 len(r['svuotare'])))
        fuori['tappe'].append(r)
    with io.open(uscita, 'w', encoding='utf-8') as f:
        json.dump(fuori, f, ensure_ascii=False, separators=(',', ':'))
    print('scritto %s (%.0f KB)' % (uscita, os.path.getsize(uscita) / 1024.0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
