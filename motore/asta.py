# -*- coding: utf-8 -*-
"""Stato dell'asta: chi ha comprato cosa, a che prezzo, con quanti crediti residui.

Il registro degli acquisti e' la sorgente unica di verita': crediti e slot non
vengono mai memorizzati, si ricavano sempre dal registro. Cosi' l'annullamento
e' esatto per costruzione e non puo' lasciare lo stato incoerente.
"""
import datetime, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RUOLI = ('P', 'D', 'C', 'A')


class ErroreAsta(Exception):
    pass


class StatoAsta(object):

    def __init__(self, con, regole):
        self.con = con
        self.reg = regole

    # ------------------------------------------------------------ creazione
    def inizializza(self, nomi=None, mio_nome='Io'):
        """Crea l'asta e i presidenti. Cancella un'eventuale asta precedente."""
        import json
        c = self.con
        c.execute('DELETE FROM acquisti')
        c.execute('DELETE FROM presidenti')
        c.execute('DELETE FROM asta')
        c.execute("DELETE FROM sqlite_sequence WHERE name='acquisti'")
        c.execute('INSERT INTO asta (id, creata_il, partecipanti, crediti_iniziali,'
                  ' regole_json, turno) VALUES (1,?,?,?,?,1)',
                  (datetime.datetime.now().isoformat(timespec='seconds'),
                   self.reg.partecipanti, self.reg.crediti,
                   json.dumps(self.reg._d, ensure_ascii=False)))
        nomi = list(nomi or [])
        while len(nomi) < self.reg.partecipanti - 1:
            nomi.append('Avversario %d' % (len(nomi) + 1))
        nomi = nomi[:self.reg.partecipanti - 1]
        c.execute('INSERT INTO presidenti (id, nome, io) VALUES (1,?,1)', (mio_nome,))
        for i, n in enumerate(nomi, start=2):
            c.execute('INSERT INTO presidenti (id, nome, io) VALUES (?,?,0)', (i, n))
        c.commit()
        return self

    def esiste(self):
        """C'e' un'asta **utilizzabile**, non solo una riga in tabella.

        La riga `asta` da sola non basta: un'inizializzazione interrotta a
        meta' &mdash; il programma chiuso nel momento sbagliato, un errore su
        disco &mdash; lascia l'asta senza presidenti, e allora `io()` alza
        un'eccezione. Chi la chiama e' `Sessione.__init__`, cioe' l'avvio:
        il risultato era il programma che moriva prima di aprire la finestra,
        con una traccia di stack e nessun modo di ricominciare se non
        cancellando il database a mano.

        Un'asta senza presidenti non e' un'asta a meta': e' un'asta che non
        c'e', e la risposta giusta e' la schermata di partenza.
        """
        if self.con.execute('SELECT 1 FROM asta WHERE id=1').fetchone() is None:
            return False
        return self.con.execute(
            'SELECT 1 FROM presidenti WHERE io = 1').fetchone() is not None

    # ---------------------------------------------------------------- turno
    def turno(self):
        """Di chi e' il turno di chiamare. Lo decide l'utente, non il software:
        l'ordine reale di una stanza non e' sempre quello nominale."""
        r = self.con.execute('SELECT turno FROM asta WHERE id=1').fetchone()
        return r['turno'] if r else None

    def imposta_turno(self, presidente_id):
        if self.con.execute('SELECT 1 FROM presidenti WHERE id=?',
                            (presidente_id,)).fetchone() is None:
            raise ErroreAsta('presidente %s inesistente' % presidente_id)
        self.con.execute('UPDATE asta SET turno=? WHERE id=1', (presidente_id,))
        self.con.commit()

    def avanza_turno(self):
        """Passa al presidente successivo in ordine di numero, a giro."""
        ids = [r['id'] for r in self.con.execute(
            'SELECT id FROM presidenti ORDER BY id')]
        if not ids:
            return None
        corrente = self.turno()
        i = ids.index(corrente) if corrente in ids else -1
        prossimo = ids[(i + 1) % len(ids)]
        self.imposta_turno(prossimo)
        return prossimo

    # -------------------------------------------------------------- lettura
    def presidenti(self):
        return [dict(r) for r in self.con.execute(
            'SELECT * FROM v_presidenti ORDER BY io DESC, id')]

    def io(self):
        r = self.con.execute('SELECT * FROM v_presidenti WHERE io = 1').fetchone()
        if r is None:
            raise ErroreAsta("asta non inizializzata: chiama inizializza()")
        return dict(r)

    def acquisti(self):
        return [dict(r) for r in self.con.execute(
            """SELECT a.*, g.nome, g.squadra FROM acquisti a
               JOIN giocatori g ON g.id = a.giocatore_id ORDER BY a.seq""")]

    def venduti(self):
        return set(r[0] for r in self.con.execute('SELECT giocatore_id FROM acquisti'))

    # --------------------------------------------------------------- conteggi
    def slot_usati(self, presidente_id, ruolo):
        return self.con.execute(
            'SELECT COUNT(*) FROM acquisti WHERE presidente_id=? AND ruolo=?',
            (presidente_id, ruolo)).fetchone()[0]

    def slot_residui(self, presidente_id, ruolo=None):
        if ruolo:
            return self.reg.slot[ruolo] - self.slot_usati(presidente_id, ruolo)
        return sum(self.slot_residui(presidente_id, r) for r in RUOLI)

    def crediti(self, presidente_id):
        speso = self.con.execute(
            'SELECT COALESCE(SUM(prezzo),0) FROM acquisti WHERE presidente_id=?',
            (presidente_id,)).fetchone()[0]
        return self.reg.crediti - speso

    def liquidita(self, presidente_id):
        """Massimo che puo' offrire ora restando in grado di riempire la rosa.

        Deve tenere almeno 1 credito per ogni slot che restera' da coprire
        dopo questo acquisto.
        """
        residui = self.slot_residui(presidente_id)
        if residui <= 0:
            return 0
        return max(0, self.crediti(presidente_id) - (residui - 1))

    # ------------------------------------------------------- stato aggregato
    @property
    def crediti_residui_lega(self):
        speso = self.con.execute('SELECT COALESCE(SUM(prezzo),0) FROM acquisti').fetchone()[0]
        return self.reg.crediti_totali - speso

    @property
    def slot_residui_lega(self):
        return self.reg.slot_lega - self.con.execute(
            'SELECT COUNT(*) FROM acquisti').fetchone()[0]

    def speso_ruolo(self, ruolo):
        """Crediti gia' bruciati dalla lega su quel reparto."""
        return self.con.execute(
            'SELECT COALESCE(SUM(prezzo),0) FROM acquisti WHERE ruolo=?',
            (ruolo,)).fetchone()[0]

    def slot_residui_ruolo(self, ruolo):
        assegnati = self.con.execute(
            'SELECT COUNT(*) FROM acquisti WHERE ruolo=?', (ruolo,)).fetchone()[0]
        return self.reg.slot_lega_ruolo(ruolo) - assegnati

    # ------------------------------------------------------------- scrittura
    def registra(self, giocatore_id, presidente_id, prezzo, limite=None):
        g = self.con.execute('SELECT id, nome, ruolo FROM giocatori WHERE id=?',
                             (giocatore_id,)).fetchone()
        if g is None:
            raise ErroreAsta('giocatore %s inesistente' % giocatore_id)
        if self.con.execute('SELECT 1 FROM acquisti WHERE giocatore_id=?',
                            (giocatore_id,)).fetchone():
            raise ErroreAsta('%s risulta gia\' acquistato' % g['nome'])
        if self.con.execute('SELECT 1 FROM presidenti WHERE id=?',
                            (presidente_id,)).fetchone() is None:
            raise ErroreAsta('presidente %s inesistente' % presidente_id)
        prezzo = int(prezzo)
        if prezzo < 1:
            raise ErroreAsta('il prezzo minimo e\' 1')
        if self.slot_residui(presidente_id, g['ruolo']) <= 0:
            raise ErroreAsta('slot %s gia\' pieni per quel presidente' % g['ruolo'])
        residui_dopo = self.slot_residui(presidente_id) - 1
        if self.crediti(presidente_id) - prezzo < residui_dopo:
            raise ErroreAsta(
                'con %d crediti non potrebbe piu\' riempire i %d slot rimanenti'
                % (self.crediti(presidente_id) - prezzo, residui_dopo))
        # `limite` e' il prezzo massimo che il motore dava a quel giocatore un
        # istante prima della chiamata. Si salva perche' e' l'unico modo di
        # giudicare poi la decisione con le informazioni che c'erano allora: il
        # limite di adesso e' un altro numero, calcolato su una rosa e su un
        # budget che nel frattempo sono cambiati.
        self.con.execute(
            'INSERT INTO acquisti (giocatore_id, presidente_id, prezzo, ruolo,'
            ' istante, limite) VALUES (?,?,?,?,?,?)',
            (giocatore_id, presidente_id, prezzo, g['ruolo'],
             datetime.datetime.now().isoformat(timespec='seconds'),
             int(limite) if limite is not None else None))
        self.con.commit()

    def annulla_ultimo(self):
        r = self.con.execute('SELECT seq, giocatore_id FROM acquisti'
                             ' ORDER BY seq DESC LIMIT 1').fetchone()
        if r is None:
            raise ErroreAsta('nessun acquisto da annullare')
        self.con.execute('DELETE FROM acquisti WHERE seq=?', (r['seq'],))
        self.con.commit()
        return r['giocatore_id']

    def annulla(self, giocatore_id):
        n = self.con.execute('DELETE FROM acquisti WHERE giocatore_id=?',
                             (giocatore_id,)).rowcount
        self.con.commit()
        if not n:
            raise ErroreAsta('quel giocatore non risulta acquistato')

    # ------------------------------------------------------------- riassunto
    def riassunto(self):
        r = ['%-16s %8s %5s %5s %5s %5s %6s' %
             ('presidente', 'crediti', 'P', 'D', 'C', 'A', 'slot')]
        for p in self.presidenti():
            r.append('%-16s %8d %5s %5s %5s %5s %6d' % (
                (p['nome'] + (' *' if p['io'] else ''))[:16], p['crediti'],
                '%d/%d' % (p['n_p'], self.reg.slot['P']),
                '%d/%d' % (p['n_d'], self.reg.slot['D']),
                '%d/%d' % (p['n_c'], self.reg.slot['C']),
                '%d/%d' % (p['n_a'], self.reg.slot['A']),
                self.slot_residui(p['id'])))
        r.append('lega: %d crediti residui, %d slot da riempire'
                 % (self.crediti_residui_lega, self.slot_residui_lega))
        return '\n'.join(r)
