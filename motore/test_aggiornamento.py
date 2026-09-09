# -*- coding: utf-8 -*-
"""Verifiche sui due file e sull'aggiornamento dei dati.

Sono le prove che contano quando qualcosa va storto: la rete che non risponde,
un file scaricato a meta', un pacchetto piu' nuovo del programma. In tutti
questi casi la risposta giusta e' la stessa &mdash; **il programma parte lo
stesso** &mdash; e queste verifiche servono a non perderla per strada.

Uso:  python test_aggiornamento.py
"""
import gzip, hashlib, io, json, os, shutil, sqlite3, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)

superati = falliti = 0


def verifica(nome, condizione, dettaglio=''):
    global superati, falliti
    if condizione:
        superati += 1
        print('  OK   %s' % nome)
    else:
        falliti += 1
        print('  FAIL %s   %s' % (nome, dettaglio))


# --------------------------------------------------- un finto sito da cui scaricare
class Deposito(object):
    """Un server locale che serve manifest e pacchetto, e sa anche rompersi."""

    def __init__(self, file_dati, generato_il, guasto=None):
        corpo = io.open(file_dati, 'rb').read()
        self.pacchetto = gzip.compress(corpo, 6)
        self.manifest = json.dumps({
            'generato_il': generato_il, 'schema': 1, 'file': 'dati.db.gz',
            'sha256': hashlib.sha256(self.pacchetto).hexdigest(),
            'dimensione': len(self.pacchetto)}).encode('utf-8')
        self.guasto = guasto
        deposito = self

        class Gestore(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if deposito.guasto == 'errore':
                    self.send_response(500)
                    self.end_headers()
                    return
                if self.path.endswith('manifest.json'):
                    corpo = deposito.manifest
                elif self.path.endswith('dati.db.gz'):
                    corpo = deposito.pacchetto
                    if deposito.guasto == 'troncato':
                        corpo = corpo[:len(corpo) // 3]
                else:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Length', str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), Gestore)
        self.porta = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def origine(self):
        return 'http://127.0.0.1:%d' % self.porta

    def chiudi(self):
        self.httpd.shutdown()


def main():
    vero_db = os.path.join(QUI, 'asta.db')
    import percorsi
    vero_dati = percorsi.DATI_FILE
    if not os.path.exists(vero_dati):
        print('Manca %s: lancia prima  python db.py' % vero_dati)
        return 1

    prove = tempfile.mkdtemp(prefix='fantahacked_agg_')
    os.environ['FANTAHACKED_DB'] = os.path.join(prove, 'asta.db')
    os.environ['FANTAHACKED_DATI'] = os.path.join(prove, 'dati.db')
    for m in ('percorsi', 'db', 'aggiornamento'):
        sys.modules.pop(m, None)
    import percorsi                     # noqa: F811  (rilettura con l'ambiente nuovo)
    import db as dbmod
    import aggiornamento as aggmod
    shutil.copyfile(vero_dati, percorsi.DATI_FILE)

    print('\n[1] I due file stanno insieme')
    con = dbmod.connetti()
    n = con.execute('SELECT COUNT(*) FROM giocatori').fetchone()[0]
    verifica('i giocatori si leggono dal file dei dati', n > 500, '%d trovati' % n)
    con.execute("INSERT INTO asta (id, creata_il, partecipanti, crediti_iniziali,"
                " regole_json) VALUES (1,'2026-09-09',8,500,'{}')")
    con.execute("INSERT INTO presidenti (id, nome, io) VALUES (1,'Davide',1)")
    con.execute("INSERT INTO acquisti (giocatore_id, presidente_id, prezzo, ruolo,"
                " istante) VALUES (5585, 1, 184, 'A', '2026-09-09')")
    con.commit()
    r = con.execute('SELECT g.nome, a.prezzo FROM acquisti a'
                    ' JOIN giocatori g ON g.id = a.giocatore_id').fetchone()
    verifica('un acquisto si unisce al listone attraverso i due file',
             r and r['prezzo'] == 184, str(r and tuple(r)))
    verifica('la vista dei disponibili esclude chi e\' stato comprato',
             con.execute('SELECT COUNT(*) FROM v_disponibili').fetchone()[0] == n - 1)
    solo_dati = sqlite3.connect(percorsi.DATI_FILE)
    verifica('gli acquisti stanno nel file dell\'asta, non in quello dei dati',
             solo_dati.execute(
                 "SELECT COUNT(*) FROM sqlite_master WHERE name='acquisti'"
             ).fetchone()[0] == 0)
    # Chiudere sul serio: su Windows un file aperto non si puo' sostituire, e
    # una connessione dimenticata qui farebbe fallire l'aggiornamento piu'
    # sotto per un motivo che col codice non c'entra niente.
    solo_dati.close()
    con.close()

    print('\n[2] Sostituire i dati non tocca l\'asta')
    deposito = Deposito(vero_dati, '2099-01-01')
    esito = aggmod.aggiorna(percorsi.DATI_FILE, deposito.origine)
    verifica('scarica quando online e\' piu\' recente', esito.stato == 'aggiornato',
             repr(esito))
    con = dbmod.connetti()
    verifica('l\'acquisto registrato prima e\' ancora li\'',
             con.execute('SELECT COUNT(*) FROM acquisti').fetchone()[0] == 1)
    verifica('e i giocatori pure', con.execute(
        'SELECT COUNT(*) FROM giocatori').fetchone()[0] == n)
    con.close()

    print('\n[3] Se i dati sono gia\' quelli, non scarica')
    esito = aggmod.aggiorna(percorsi.DATI_FILE, deposito.origine)
    verifica('riconosce di essere gia\' aggiornato',
             esito.stato == 'gia_aggiornato', repr(esito))
    deposito.chiudi()

    print('\n[4] Quando la rete non c\'e\', si parte lo stesso')
    prima = os.path.getsize(percorsi.DATI_FILE)
    esito = aggmod.aggiorna(percorsi.DATI_FILE, 'http://127.0.0.1:9/inesistente')
    verifica('lo dice invece di piantarsi', esito.stato == 'offline', repr(esito))
    verifica('e i dati restano intatti',
             os.path.getsize(percorsi.DATI_FILE) == prima)
    con = dbmod.connetti()
    verifica('il programma continua a funzionare offline',
             con.execute('SELECT COUNT(*) FROM giocatori').fetchone()[0] == n)
    con.close()

    print('\n[5] Un pacchetto rotto non sostituisce quello buono')
    rotto = Deposito(vero_dati, '2099-06-01', guasto='troncato')
    esito = aggmod.aggiorna(percorsi.DATI_FILE, rotto.origine)
    verifica('lo rifiuta', esito.stato == 'errore', repr(esito))
    verifica('e i dati di prima sono ancora al loro posto',
             os.path.getsize(percorsi.DATI_FILE) == prima)
    con = dbmod.connetti()
    verifica('che infatti si aprono ancora',
             con.execute('SELECT COUNT(*) FROM giocatori').fetchone()[0] == n)
    con.close()
    rotto.chiudi()

    print('\n[6] Dati piu\' nuovi del programma: si rifiuta, non ci si rompe dentro')
    c = sqlite3.connect(percorsi.DATI_FILE)
    c.execute("INSERT OR REPLACE INTO meta (chiave, valore) VALUES ('schema','99')")
    c.commit(); c.close()
    try:
        dbmod.connetti().close()
        verifica('avvisa che serve un programma piu\' recente', False,
                 'ha aperto un file che non sa leggere')
    except dbmod.DatiTroppoNuovi as e:
        verifica('avvisa che serve un programma piu\' recente', True)
        verifica('e lo dice in italiano', 'aggiorna' in str(e).lower(), str(e))
    c = sqlite3.connect(percorsi.DATI_FILE)
    c.execute("INSERT OR REPLACE INTO meta (chiave, valore) VALUES ('schema','1')")
    c.commit(); c.close()

    print('\n[7] Cambiare il regolamento rifa\' le proiezioni')
    import regole as regmod
    con = dbmod.connetti()
    aggmod.assicura_proiezioni(con, regmod.carica())
    prima_punti = con.execute(
        'SELECT punti_attesi FROM proiezioni WHERE id = 5585').fetchone()[0]
    rifatte = aggmod.assicura_proiezioni(con, regmod.carica())
    verifica('a regolamento invariato non ricalcola', not rifatte)
    # Si cambia la firma memorizzata, che e' esattamente quello che succede
    # quando arriva un pacchetto calcolato sul regolamento standard e il tuo
    # e' un altro.
    c = sqlite3.connect(percorsi.DATI_FILE)
    c.execute("UPDATE meta SET valore='firma-diversa' WHERE chiave='regole_firma'")
    c.commit(); c.close()
    con.close()
    con = dbmod.connetti()
    rifatte = aggmod.assicura_proiezioni(con, regmod.carica())
    verifica('con una firma diversa ricalcola', rifatte)
    dopo = con.execute(
        'SELECT punti_attesi FROM proiezioni WHERE id = 5585').fetchone()[0]
    verifica('e i numeri tornano quelli del tuo regolamento',
             abs(dopo - prima_punti) < 0.01, '%s -> %s' % (prima_punti, dopo))
    con.close()

    print('\n[8] Il vecchio fanta.db si divide senza perdere l\'asta')
    vecchia_cartella = tempfile.mkdtemp(prefix='fantahacked_vecchio_')
    os.makedirs(os.path.join(vecchia_cartella, 'motore'))
    os.makedirs(os.path.join(vecchia_cartella, 'database'))
    unico = os.path.join(vecchia_cartella, 'motore', 'fanta.db')
    u = sqlite3.connect(unico)
    for schema in ('schema_dati.sql', 'schema_asta.sql'):
        with io.open(os.path.join(QUI, schema), encoding='utf-8') as f:
            u.executescript(f.read())
    u.execute("INSERT INTO squadre (squadra) VALUES ('Roma')")
    u.execute("INSERT INTO giocatori (id, nome, squadra, ruolo, qi)"
              " VALUES (5585,'Malen','Roma','A',34)")
    u.execute("INSERT INTO asta (id, creata_il, partecipanti, crediti_iniziali,"
              " regole_json) VALUES (1,'2026-09-09',8,500,'{}')")
    u.execute("INSERT INTO presidenti (id, nome, io) VALUES (1,'Davide',1)")
    u.execute("INSERT INTO acquisti (giocatore_id, presidente_id, prezzo, ruolo,"
              " istante, limite) VALUES (5585,1,184,'A','2026-09-09',205)")
    u.commit(); u.close()
    percorsi.VECCHIO_DB = unico
    nuovo_asta = os.path.join(vecchia_cartella, 'motore', 'asta.db')
    nuovi_dati = os.path.join(vecchia_cartella, 'database', 'dati.db')
    con = dbmod.connetti(nuovo_asta, nuovi_dati)
    verifica('l\'acquisto e\' passato nel file dell\'asta',
             con.execute('SELECT COUNT(*) FROM acquisti').fetchone()[0] == 1)
    verifica('col suo limite', con.execute(
        'SELECT limite FROM acquisti').fetchone()[0] == 205)
    verifica('il giocatore e\' passato nel file dei dati',
             con.execute('SELECT nome FROM giocatori').fetchone()[0] == 'Malen')
    verifica('il file di prima e\' stato messo da parte, non cancellato',
             os.path.exists(unico + '.prima-della-divisione'))
    con.close()
    shutil.rmtree(vecchia_cartella, ignore_errors=True)
    shutil.rmtree(prove, ignore_errors=True)

    print('\n%s   %d superati, %d falliti'
          % ('TUTTO OK' if not falliti else 'CI SONO ERRORI', superati, falliti))
    return 1 if falliti else 0


if __name__ == '__main__':
    sys.exit(main())
