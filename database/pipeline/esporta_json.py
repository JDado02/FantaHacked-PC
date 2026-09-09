# -*- coding: utf-8 -*-
"""Gli stessi dati, in JSON, per chi non ha SQLite: cioe' il telefono.

Il file `dati.db` va benissimo per il programma su PC, che SQLite ce l'ha
dentro. Un'applicazione che gira dentro una pagina non ce l'ha, e portarcelo
vorrebbe dire trascinarsi appresso mezzo megabyte di SQLite compilato in
WebAssembly per leggere seicento righe.

Quindi lo stesso pacchetto esce anche in JSON. Non e' una copia di tutto: sono
**solo le tabelle che servono mentre l'asta e' in corso**. Statistiche,
avanzate e calendario servono a *calcolare* le proiezioni, non a usarle, e le
proiezioni sono gia' calcolate qui dentro.

Il formato e' a colonne, non a oggetti: invece di ripetere seicento volte i
nomi dei campi, i nomi stanno una volta sola e sotto ci sono le righe. Sullo
stesso contenuto sono 180 KB invece di 420.
"""
import io, json, os, sqlite3, sys

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(os.path.dirname(QUI))
sys.path.insert(0, os.path.join(BASE, 'motore'))
import percorsi

# Quello che il motore legge davvero mentre si gioca. Ricavato dalle query di
# `valutazione`, `strategia` e `ottimizzatore`, non a memoria.
TABELLE = {
    'giocatori': ['id', 'nome', 'nome_completo', 'squadra', 'ruolo', 'qi', 'qa',
                  'fvm', 'eta', 'nuovo_acquisto', 'attivo'],
    'proiezioni': ['id', 'presenze_attese', 'mv_attesa', 'fantamedia_attesa',
                   'punti_attesi', 'metodo', 'affidabilita', 'titolarita',
                   'posto_reparto', 'in_reparto', 'grado', 'certezza',
                   'fuori_lista', 'gol_attesi', 'assist_attesi', 'gs_attesi',
                   'imbattuto_attese', 'minuti_attesi'],
    'contesto': ['id', 'rigorista', 'fonte_rigorista', 'stato',
                 'rientro_stimato', 'ballottaggio_con', 'calci_piazzati'],
    'gerarchie': ['id', 'titolarita', 'accordo', 'presenze_web', 'fonti',
                  'ballottaggio_con', 'ballottaggio_pct', 'rigorista', 'stato',
                  'rientro_stimato', 'partite_saltate', 'fuori_lista'],
    'prezzi_asta': ['id', 'prezzo_medio_per_1000'],
    'accoppiate': ['id_titolare', 'id_vice', 'squadra', 'ruolo', 'tipo',
                   'titolarita_titolare', 'titolarita_vice', 'presenze_titolare',
                   'presenze_vice', 'giornate_coperte', 'copertura',
                   'peso_fonti', 'fonti', 'nota'],
    'squadre': ['squadra', 'promossa', 'gf_prec', 'gs_prec'],
}


def esporta(dati=None, destinazione=None):
    dati = dati or percorsi.DATI_FILE
    con = sqlite3.connect(dati)
    con.row_factory = sqlite3.Row
    fuori = {}
    for tabella, campi in TABELLE.items():
        try:
            righe = con.execute('SELECT %s FROM %s' % (','.join(campi), tabella)).fetchall()
        except sqlite3.OperationalError:
            continue
        fuori[tabella] = {'campi': campi,
                          'righe': [[r[c] for c in campi] for r in righe]}
    meta = dict((r['chiave'], r['valore'])
                for r in con.execute('SELECT chiave, valore FROM meta'))
    con.close()
    fuori['meta'] = meta

    # Le regole della lega viaggiano insieme, e non per comodita': le
    # proiezioni dipendono da loro, e l'applicazione per telefono non sa
    # rifarle. Con un regolamento diverso da quello che ha prodotto questi
    # numeri, mostrerebbe cifre sbagliate senza modo di accorgersene.
    import json as _json
    try:
        with io.open(os.path.join(os.path.dirname(percorsi.DATI_FILE),
                                  'regole_lega.json'), encoding='utf-8') as f:
            fuori['regole'] = _json.load(f)
    except Exception:
        pass

    if destinazione:
        cartella = os.path.dirname(destinazione)
        if cartella and not os.path.isdir(cartella):
            os.makedirs(cartella)
        # `separators` senza spazi: su seicento righe sono trentamila caratteri
        # in meno, e nessuno legge questo file a occhio.
        with io.open(destinazione, 'w', encoding='utf-8') as f:
            json.dump(fuori, f, ensure_ascii=False, separators=(',', ':'))
    return fuori


if __name__ == '__main__':
    fuori = esporta(destinazione=sys.argv[1] if len(sys.argv) > 1 else None)
    for t in sorted(fuori):
        if t == 'meta':
            continue
        print('  %-14s %4d righe x %2d campi'
              % (t, len(fuori[t]['righe']), len(fuori[t]['campi'])))
    print('  meta          %s' % fuori['meta'])
