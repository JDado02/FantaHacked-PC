# -*- coding: utf-8 -*-
"""Server locale dell'assistente d'asta.

Gira solo su 127.0.0.1: nessuna porta esposta alla rete, nessun dato che esce
dal computer. L'interfaccia e' una pagina web servita da qui, cosi' la grafica
puo' essere curata davvero senza portarsi dietro un framework desktop.

Avvio:  python server.py        (o doppio clic su "Avvia FantaHacked.vbs")
"""
import datetime, json, mimetypes, os, socket, sys, threading, time, traceback, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

def _radice():
    """La cartella del progetto, sia da sorgente sia da .exe."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE = _radice()
sys.path.insert(0, os.path.join(BASE, 'motore'))
if getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.join(getattr(sys, '_MEIPASS', BASE), 'motore'))

import percorsi

# L'interfaccia viaggia dentro l'eseguibile, ma una copia sul disco accanto
# vince: cosi' ci si lavora senza ricostruire l'exe a ogni riga.
WEB = percorsi.risorsa('app', 'web')
import db as dbmod
import regole as regmod
import proiezioni as prmod
import aggiornamento as aggmod
from asta import StatoAsta, ErroreAsta
from valutazione import Valutatore
from ottimizzatore import Ottimizzatore
from strategia import Consigliere
from equilibrio import Equilibrio

PORTA_PREFERITA = 8730
RUOLI = ('P', 'D', 'C', 'A')
NOME_RUOLO = {'P': 'Portieri', 'D': 'Difensori',
              'C': 'Centrocampisti', 'A': 'Attaccanti'}


# ============================================================== sessione
# Dove restano i nomi delle squadre fra un'asta e l'altra. Sta accanto al
# database e non nel browser: l'interfaccia gira su una porta che puo' cambiare
# a ogni avvio, e per il browser una porta diversa e' un sito diverso: quello
# che si era scritto nei campi spariva senza motivo apparente.
# La variabile d'ambiente serve al collaudo: le prove aprono e chiudono decine
# di aste con nomi finti, e senza una destinazione separata cancellerebbero
# proprio i nomi veri che questo file esiste per non far ridigitare.
PREFERENZE = (os.environ.get('FANTAHACKED_PREFERENZE')
              or os.path.join(BASE, 'motore', 'preferenze.json'))


def leggi_preferenze():
    try:
        with open(PREFERENZE, encoding='utf-8') as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def scrivi_preferenze(d):
    """Salva senza mai far fallire una richiesta: sono comodita', non dati."""
    try:
        with open(PREFERENZE, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


class Sessione(object):
    """Tutto lo stato vivo, dietro un lucchetto.

    Il browser puo' mandare piu' richieste insieme; il motore non e' pensato
    per essere toccato da due thread alla volta, e SQLite nemmeno. Un lucchetto
    solo e' piu' che sufficiente: le operazioni durano decine di millisecondi.
    """

    def __init__(self):
        self.lock = threading.RLock()
        # Prima di aprire il database si guarda se online ce n'e' uno piu'
        # recente. Se la rete non c'e' non succede niente: si va avanti con
        # quello che c'e', e la pagina dira' di quando sono i dati. Un
        # assistente d'asta che non parte perche' il wifi della stanza fa i
        # capricci sarebbe peggio di uno con i dati di tre giorni prima.
        self.aggiornamento = aggmod.aggiorna(
            attivo=not os.environ.get('FANTAHACKED_NIENTE_RETE'))
        self.con = dbmod.connetti(check_same_thread=False)
        self.reg = regmod.carica()
        # Le proiezioni si rifanno quando non ci sono, e anche quando ci sono
        # ma sono di una versione del motore che non calcolava ancora la
        # gerarchia di reparto: un database vecchio non deve far girare il
        # programma senza sapere chi gioca.
        vuote = self.con.execute(
            'SELECT COUNT(*) FROM proiezioni').fetchone()[0] == 0
        senza_gerarchia = self.con.execute(
            'SELECT COUNT(*) FROM proiezioni WHERE grado IS NOT NULL'
        ).fetchone()[0] == 0
        if vuote or senza_gerarchia:
            prmod.esegui(self.con, self.reg)
        else:
            # E si rifanno anche quando il regolamento e' cambiato: le
            # proiezioni ne dipendono, e fino a ieri chi correggeva
            # `regole_lega.json` continuava a vedere i numeri di prima senza
            # che niente glielo dicesse. Vale pure per i dati appena
            # scaricati, che arrivano calcolati sul regolamento standard.
            aggmod.assicura_proiezioni(self.con, self.reg)
        self.stato = StatoAsta(self.con, self.reg)
        self.v = self.o = self.c = self.e = None
        self.versione = 0
        self._consiglio = None
        if self.stato.esiste():
            self._monta()

    # --------------------------------------------------------------- ciclo
    def _monta(self):
        self.v = Valutatore(self.con, self.reg, self.stato)
        self.o = Ottimizzatore(self.v)
        self.c = Consigliere(self.v, self.o)
        self.e = Equilibrio(self.v, self.o)
        self.versione += 1
        self._consiglio = None

    def _ricalcola(self):
        self.c.aggiorna()
        self.versione += 1
        self._consiglio = None

    def pronta(self):
        return self.c is not None

    # ------------------------------------------------------------- comandi
    MAX_NOME = 24

    def _nome(self, testo, riserva):
        """Un nome di squadra deve stare in una riga.

        Il limite c'e' gia' nel campo di testo dell'interfaccia, ma il server
        non puo' fidarsi di quello: basta una richiesta fatta a mano, o un
        incolla che porta dentro mezzo documento, e la barra in alto si sfonda.
        """
        pulito = ' '.join(str(testo or '').split())
        return pulito[:self.MAX_NOME] or riserva

    def nomi_predefiniti(self):
        """I nomi con cui si riapre il modulo della nuova asta.

        In ordine: quelli salvati l'ultima volta; se non ci sono, quelli
        dell'asta che e' gia' nel database. Restano modificabili &mdash; sono
        un riempimento, non un vincolo &mdash; ma non vanno ridigitati ogni
        anno, e soprattutto non spariscono riavviando il programma.
        """
        salvati = leggi_preferenze().get('squadre')
        if isinstance(salvati, list) and salvati:
            return [str(n) for n in salvati][:self.reg.partecipanti]
        try:
            righe = self.stato.presidenti()
        except Exception:
            return []
        if not righe:
            return []
        mio = [p['nome'] for p in righe if p['io']]
        altri = [p['nome'] for p in righe if not p['io']]
        return (mio + altri)[:self.reg.partecipanti]

    def nuova(self, mio_nome, avversari):
        with self.lock:
            nomi = [self._nome(n, '') for n in (avversari or [])]
            nomi = [n for n in nomi if n]
            mio = self._nome(mio_nome, 'La mia squadra')
            self.stato.inizializza(nomi, mio_nome=mio)
            pref = leggi_preferenze()
            pref['squadre'] = [mio] + nomi
            scrivi_preferenze(pref)
            self._monta()
            return self.riepilogo()

    def rinomina(self, nomi):
        """Cambia i nomi delle squadre ad asta gia' cominciata.

        Serve perche' sbagliare a digitarli non deve costare l'asta. Finora
        l'unico modo di correggere un nome era "nuova asta", che cancella
        tutti gli acquisti gia' registrati: un errore di battitura al primo
        campo e si ricomincia da capo. Il caso vero e' stato peggiore &mdash;
        il collaudo aveva sovrascritto i nomi salvati, e l'asta e' partita con
        otto nomi finti gia' dentro.

        Cambia solo l'etichetta: gli identificativi, i crediti e gli acquisti
        restano dove sono. E i nuovi nomi diventano anche i predefiniti della
        prossima asta, che e' l'unica ragione per cui erano sbagliati.
        """
        with self.lock:
            righe = self.stato.presidenti()
            if len(nomi) != len(righe):
                raise ErroreAsta('servono %d nomi, ne sono arrivati %d'
                                 % (len(righe), len(nomi)))
            puliti = [self._nome(n, r['nome']) for n, r in zip(nomi, righe)]
            if len(set(puliti)) != len(puliti):
                raise ErroreAsta('ci sono due squadre con lo stesso nome')
            for r, nuovo in zip(righe, puliti):
                self.stato.con.execute(
                    'UPDATE presidenti SET nome = ? WHERE id = ?', (nuovo, r['id']))
            self.stato.con.commit()
            pref = leggi_preferenze()
            pref['squadre'] = puliti
            scrivi_preferenze(pref)
            self._monta()
            return self.riepilogo()

    def acquisto(self, giocatore_id, presidente_id, prezzo):
        with self.lock:
            giocatore_id = int(giocatore_id)
            presidente_id = int(presidente_id)
            # Il limite si legge **prima** di registrare: un istante dopo lo
            # slot e' occupato e il numero non esiste piu'. E' quello che
            # permettera' di dire, guardando la rosa a fine asta, se un
            # acquisto era un errore o solo un giocatore fuori scala pagato
            # sopra la media di mercato: due cose diversissime.
            limite = self._limite_ora(giocatore_id, presidente_id)
            self.stato.registra(giocatore_id, presidente_id, int(prezzo),
                                limite=limite)
            extra = self._segui_pacchetto(giocatore_id, presidente_id)
            self._ricalcola()
            r = self.riepilogo()
            r['pacchetto'] = extra
            return r

    def _limite_ora(self, giocatore_id, presidente_id):
        """Il mio prezzo massimo su quel giocatore, adesso.

        Solo per i miei acquisti: di quello che vale un giocatore **per la rosa
        di un avversario** non so niente, e inventarlo sarebbe peggio che
        lasciarlo vuoto.
        """
        try:
            if presidente_id != self.stato.io()['id']:
                return None
            x = self.v.g.get(giocatore_id)
            if x is None:
                return None
            return int(self.o.max_bid(x)[0])
        except Exception:
            return None

    def _segui_pacchetto(self, giocatore_id, presidente_id):
        """Chi prende il portiere titolare prende anche le sue riserve a 1.

        E' una regola di questa lega, e vale per tutti: quando la applica un
        avversario, i suoi slot da portiere si chiudono di colpo e non puo'
        piu' contendere nessun altro portiere. Registrarlo subito e' quello che
        tiene onesto il calcolo di chi puo' ancora rilanciare.
        """
        if not self.reg.portieri_pacchetto:
            return []
        presi = []
        for rid in self.v.riserve_di(giocatore_id):
            if rid in self.stato.venduti():
                continue
            if self.stato.slot_residui(presidente_id, 'P') <= 0:
                break
            try:
                self.stato.registra(rid, presidente_id, 1)
            except ErroreAsta:
                break
            x = self.v.g.get(rid)
            presi.append({'id': rid, 'nome': x.nome if x else str(rid)})
        return presi

    def annulla(self, giocatore_id=None):
        with self.lock:
            if giocatore_id:
                giocatore_id = int(giocatore_id)
                proprietario = self._proprietario(giocatore_id)
                self.stato.annulla(giocatore_id)
                # Annullare il titolare deve portarsi via anche le riserve
                # arrivate in dote: lasciarle in rosa falserebbe gli slot.
                if self.reg.portieri_pacchetto and proprietario is not None:
                    for rid in self.v.riserve_di(giocatore_id):
                        if self._proprietario(rid) == proprietario:
                            try:
                                self.stato.annulla(rid)
                            except ErroreAsta:
                                pass
            else:
                self.stato.annulla_ultimo()
            self._ricalcola()
            return self.riepilogo()

    def _proprietario(self, giocatore_id):
        r = self.con.execute('SELECT presidente_id FROM acquisti WHERE giocatore_id=?',
                             (int(giocatore_id),)).fetchone()
        return r['presidente_id'] if r else None

    def turno(self, presidente_id):
        with self.lock:
            self.stato.imposta_turno(int(presidente_id))
            self._consiglio = None
            return self.riepilogo()

    def avanza(self):
        with self.lock:
            self.stato.avanza_turno()
            self._consiglio = None
            return self.riepilogo()

    # ------------------------------------------------------------- letture
    def _dati(self):
        """Di quando sono i dati, e com'e' andato il controllo online."""
        e = self.aggiornamento
        return {'generato_il': dbmod.dati_generati_il(self.con),
                'aggiornamento': e.stato,
                'nota': e.messaggio}

    def riepilogo(self):
        """Lo stato che l'interfaccia ridisegna a ogni cambiamento."""
        with self.lock:
            if not self.pronta():
                return {'iniziata': False, 'regole': self._regole(),
                        'nomi_predefiniti': self.nomi_predefiniti(),
                        'dati': self._dati()}
            v, o, st = self.v, self.o, self.stato
            fase = self.c.fase()
            presidenti = []
            for p in st.presidenti():
                presidenti.append({
                    'id': p['id'], 'nome': p['nome'], 'io': bool(p['io']),
                    'crediti': p['crediti'],
                    'liquidita': st.liquidita(p['id']),
                    'slot': {'P': p['n_p'], 'D': p['n_d'], 'C': p['n_c'], 'A': p['n_a']},
                    'residui': st.slot_residui(p['id']),
                    'attivo_nel_ruolo': (fase is not None
                                         and st.slot_residui(p['id'], fase) > 0),
                    'bilancio': self._bilancio_di(p['id']),
                })
            return {
                'iniziata': True,
                'versione': self.versione,
                'dati': self._dati(),
                'regole': self._regole(),
                'nomi_predefiniti': self.nomi_predefiniti(),
                'fase': fase,
                'fase_nome': NOME_RUOLO.get(fase, 'Asta conclusa'),
                'turno': st.turno(),
                'presidenti': presidenti,
                'mercato': {
                    'crediti_lega': v.crediti_residui,
                    'slot_lega': v.slot_residui,
                    'inflazione': round(v.inflazione, 3),
                    'rimpiazzo': dict((r, round(v.rimpiazzo_fm[r], 2)) for r in RUOLI),
                    'residui_ruolo': dict((r, st.slot_residui_ruolo(r)) for r in RUOLI),
                },
                'io': self._io(),
                'ultimi': self._ultimi(8),
            }

    def _bilancio_mio(self, speso, atteso, mia):
        """Il verdetto sulla mia asta: sopra o sotto i limiti che il motore dava.

        Ha senso solo se i limiti ci sono. Su un'asta cominciata prima che il
        programma li salvasse non ci sono, e allora si torna al metro di
        mercato, che e' meno preciso ma non e' inventato.
        """
        con_limite = [x for r in RUOLI for x in mia.get(r, [])
                      if x.get('limite')]
        if not con_limite:
            return None
        speso_l = sum(x['prezzo'] for x in con_limite)
        limiti = sum(x['limite'] for x in con_limite)
        margine = limiti - speso_l
        sopra = [x for x in con_limite if x['oltre_limite'] > 0]
        scarto = speso - atteso
        base = {'speso': speso, 'atteso': atteso, 'scarto': scarto,
                'quota': round(100.0 * scarto / atteso) if atteso else 0,
                'limiti': limiti, 'margine': margine,
                'sopra_limite': len(sopra)}
        if sopra:
            nomi = ', '.join(x['nome'] for x in sopra[:3])
            base.update({
                'verso': 'negativo',
                'testo': ('Hai pagato sopra il tuo limite su %d acquisti (%s): '
                          'sono %d crediti che non rendono. Sul resto sei '
                          'rientrato.'
                          % (len(sopra), nomi,
                             sum(x['oltre_limite'] for x in sopra)))})
        elif margine > 0:
            base.update({
                'verso': 'positivo',
                'testo': ("Tutti dentro il limite che il motore dava al momento "
                          "della chiamata, con %d crediti di margine in totale. "
                          "Hai speso %d per giocatori che sul mercato ne valgono "
                          "%d: la differenza non e' uno spreco, e' quello che "
                          "valgono in piu' per la tua rosa."
                          % (margine, speso, atteso))})
        else:
            base.update({
                'verso': 'pari',
                'testo': ('Sei esattamente sui limiti che il motore dava: nessun '
                          'errore, ma nemmeno margine.')})
        return base

    def _bilancio_di(self, presidente_id):
        # Sulla mia riga vale lo stesso metro del pannello della mia rosa: i
        # limiti del motore, non il prezzo di mercato. Vederli discordare
        # &mdash; rosso nella colonna, verde nel pannello &mdash; sarebbe il
        # modo piu' rapido di non fidarsi di nessuno dei due.
        if presidente_id == self.stato.io()['id']:
            return self.rosa(presidente_id)['bilancio']
        speso = atteso = 0
        for a in self.stato.acquisti():
            if a['presidente_id'] != presidente_id:
                continue
            x = self.v.g.get(a['giocatore_id'])
            speso += a['prezzo']
            if x is not None:
                atteso += int(round(x.prezzo_base or x.prezzo_atteso
                                    or x.prezzo_mercato or 1))
        return self._bilancio(speso, atteso)

    def _regole(self):
        r = self.reg
        return {
            'partecipanti': r.partecipanti, 'crediti': r.crediti,
            'slot': r.slot, 'slot_totali': r.slot_totali,
            'crediti_totali': r.crediti_totali,
            'modificatore': r.mod_dif_attivo,
            'mod_componenti': '%d portiere + %d difensori' % (r.mod_dif_n_por,
                                                              r.mod_dif_n_dif),
            'mod_scala': [{'soglia': s, 'bonus': b} for s, b in r.mod_dif_scala],
            'sostituzioni': r.sostituzioni,
            'quota_budget': dict((k, round(100 * v)) for k, v in r.quota_budget.items()),
            'riserva_ruolo': dict((k, round(100 * v)) for k, v in r.riserva_ruolo.items()),
            'fiducia_mercato': r.fiducia_mercato,
            'portieri_pacchetto': r.portieri_pacchetto,
        }

    def _io(self):
        st, o = self.stato, self.o
        me = st.io()
        return {
            'id': me['id'], 'nome': me['nome'],
            'crediti': me['crediti'], 'liquidita': st.liquidita(me['id']),
            'serve': o.serve, 'slot_residui': o.slot_residui,
            'media_difesa': round(o.media_difesa, 2),
            'bonus_modificatore': round(
                o.mod.punti_stagione(o.media_difesa) / 38.0, 2) if o.mod.attivo else 0,
            'rosa': self.rosa(me['id']),
        }

    def rosa(self, presidente_id):
        presidente_id = int(presidente_id)
        if self.con.execute('SELECT 1 FROM presidenti WHERE id=?',
                            (presidente_id,)).fetchone() is None:
            raise ErroreAsta('presidente %s inesistente' % presidente_id)
        out = dict((r, []) for r in RUOLI)
        speso = atteso_tot = 0
        for a in self.stato.acquisti():
            if a['presidente_id'] != presidente_id:
                continue
            x = self.v.g.get(a['giocatore_id'])
            # Quanto AVREBBE dovuto costare **in una stanza normale**, non
            # quanto costerebbe adesso. La differenza non e' sottile: il prezzo
            # del momento divide i crediti che restano fra gli slot che
            # restano, e quando l'ultimo portiere della lega e' assegnato
            # scende a un credito per tutti. Con quel metro chiunque avesse
            # pagato quaranta il suo portiere risultava in perdita di
            # trentanove: non era un giudizio sull'asta, era il metro che si
            # accorciava. `prezzo_base` invece e' calcolato una volta sola, sul
            # listone e sul budget interi, e non si muove piu'.
            atteso = int(round(x.prezzo_base or x.prezzo_atteso
                               or x.prezzo_mercato or 1)) if x else None
            speso += a['prezzo']
            if atteso:
                atteso_tot += atteso
            limite = a['limite'] if 'limite' in a.keys() else None
            out[a['ruolo']].append({
                'id': a['giocatore_id'], 'nome': a['nome'], 'squadra': a['squadra'],
                'prezzo': a['prezzo'],
                # Due metri diversi, e servono a due domande diverse.
                # `scarto` dice se ha pagato sopra il mercato; `oltre_limite`
                # dice se ha pagato sopra quanto quel giocatore valeva **per la
                # sua rosa**, che e' l'unico modo di chiamarlo errore.
                'limite': limite,
                'oltre_limite': (a['prezzo'] - limite) if limite else None,
                'mv': round(x.mv, 2) if x else None,
                'fm': round(x.fm, 2) if x else None,
                'mercato': int(round(x.prezzo_mercato)) if x else None,
                'atteso': atteso,
                'scarto': (a['prezzo'] - atteso) if atteso else None,
                'grado': (x.grado or 'ignoto') if x else None,
                'sicuro': bool(x.sicuro) if x else False,
                'presenze': int(round(x.presenze)) if x else None,
                'rigorista': int(x.rigorista or 0) if x else 0,
            })
        for r in RUOLI:
            out[r].sort(key=lambda d: -d['prezzo'])
        out['bilancio'] = self._bilancio(
            speso, atteso_tot, out if presidente_id == self.stato.io()['id'] else None)
        return out

    def _bilancio(self, speso, atteso, mia=None):
        """Ha comprato sopra o sotto quello che quei giocatori valgono.

        E' il modo piu' rapido di capire chi in quella stanza sta facendo
        un'asta cara e chi sta facendo affari: due presidenti con gli stessi
        crediti residui non sono nella stessa posizione se uno ha in rosa
        centoventi crediti di roba e l'altro centottanta.

        Il metro e' `prezzo_base`: quanto quel giocatore sarebbe costato in
        una stanza normale, calcolato sul listone e sul budget interi una volta
        sola. Non e' il valore a punti (che sui portieri e' fuori scala) e non
        e' il prezzo del momento (che a reparto esaurito crolla a un credito e
        farebbe risultare tutti in perdita).

        **Per la mia rosa la domanda pero' e' un'altra**, e va tenuta separata.
        Un giocatore fuori scala vale, per una rosa che se lo puo' permettere,
        molto piu' di quanto la stanza media paghi quel ruolo: il motore puo'
        dire "fino a 144" su uno che il mercato chiude a 63, e pagarlo 100 e'
        un ottimo affare pur essendo 37 sopra il prezzo di mercato. Chiamarli
        "crediti buttati" sarebbe falso. Sui miei acquisti il verdetto si basa
        percio' sul **limite salvato al momento della chiamata**; lo scarto dal
        mercato resta, ma come informazione, non come accusa.
        """
        if mia is not None:
            verdetto = self._bilancio_mio(speso, atteso, mia)
            if verdetto is not None:
                return verdetto
        scarto = speso - atteso
        if atteso <= 0:
            return {'speso': speso, 'atteso': atteso, 'scarto': 0,
                    'verso': 'niente', 'testo': 'Non ha ancora comprato niente.'}
        quota = scarto / float(atteso)
        if scarto <= -3 and quota <= -0.05:
            verso = 'positivo'
            testo = ('Sta facendo affari: ha speso %d crediti per una rosa che '
                     'ne vale %d. Sono %d crediti guadagnati.'
                     % (speso, atteso, -scarto))
        elif scarto >= 3 and quota >= 0.05:
            verso = 'negativo'
            testo = ('Sta pagando caro: %d crediti per una rosa che ne vale '
                     '%d. Sono %d crediti buttati, e alla fine gli mancheranno.'
                     % (speso, atteso, scarto))
        else:
            verso = 'pari'
            testo = ('In pari: %d crediti spesi per una rosa che ne vale %d.'
                     % (speso, atteso))
        return {'speso': speso, 'atteso': atteso, 'scarto': scarto,
                'quota': round(100 * quota), 'verso': verso, 'testo': testo}

    def _ultimi(self, quanti):
        righe = self.stato.acquisti()[-quanti:]
        nomi = dict((p['id'], p['nome']) for p in self.stato.presidenti())
        righe.reverse()
        return [{'id': a['giocatore_id'], 'nome': a['nome'], 'ruolo': a['ruolo'],
                 'squadra': a['squadra'], 'prezzo': a['prezzo'],
                 'presidente': nomi.get(a['presidente_id'], '?'),
                 'mio': a['presidente_id'] == self.stato.io()['id']}
                for a in righe]

    # --------------------------------------------------------- interrogazioni
    def cerca(self, testo, limite=12):
        with self.lock:
            t = (testo or '').strip().lower()
            if not t:
                return []
            venduti = self.stato.venduti()
            trovati = []
            for x in self.v.g.values():
                nome = x.nome.lower()
                if t in nome:
                    trovati.append((0 if nome.startswith(t) else 1, x))
            trovati.sort(key=lambda t_: (t_[0], -t_[1].vor))
            out = []
            for _, x in trovati[:limite]:
                preso = x.id in venduti
                out.append({'id': x.id, 'nome': x.nome, 'squadra': x.squadra,
                            'ruolo': x.ruolo, 'qi': x.qi,
                            'mercato': int(round(x.prezzo_atteso
                                                 or x.prezzo_mercato or 1)),
                            'grado': x.grado or 'ignoto',
                            'sicuro': bool(x.sicuro),
                            'fuori_lista': bool(x.fuori_lista),
                            'venduto': preso})
            return out

    def scheda(self, giocatore_id):
        with self.lock:
            x = self.v.g.get(int(giocatore_id))
            if x is None:
                raise ErroreAsta('giocatore inesistente')
            d = self.c.scheda(x)
            if x.id in self.stato.venduti():
                a = [r for r in self.stato.acquisti()
                     if r['giocatore_id'] == x.id][0]
                nomi = dict((p['id'], p['nome']) for p in self.stato.presidenti())
                d['gia_venduto'] = {'a': nomi.get(a['presidente_id'], '?'),
                                    'prezzo': a['prezzo']}
            return d

    def consiglio(self):
        with self.lock:
            if self._consiglio is None:
                self._consiglio = self.c.consiglio()
            return self._consiglio

    def equilibrio(self):
        """Che squadra sto costruendo: undici, coperture, rischi."""
        with self.lock:
            return self.e.quadro()

    def piano(self):
        with self.lock:
            p = self.o.piano()
            return {'crediti': p.get('crediti', 0),
                    'per_ruolo': p.get('per_ruolo', {}),
                    'spesa_prevista': p.get('spesa_prevista', 0),
                    'avanzo': p.get('avanzo', 0),
                    'riserva': dict(self.o.riserva),
                    'surplus': self.o.surplus,
                    'profondita': dict((r, [round(w, 2) for w in self.o.pesi[r]])
                                       for r in RUOLI)}

    def listone(self, ruolo=None, testo='', quanti=60, ordine='costa',
                solo_titolari=False):
        with self.lock:
            v = self.v
            venduti = self.stato.venduti()
            t = (testo or '').strip().lower()
            righe = []
            for x in v.g.values():
                if ruolo and x.ruolo != ruolo:
                    continue
                if t and t not in x.nome.lower() and t not in x.squadra.lower():
                    continue
                if solo_titolari and not x.sicuro:
                    continue
                righe.append(x)
            # 'costa' e' la colonna che si vede a schermo: la chiusura attesa,
            # cioe' quanto ci vorra' davvero per portarlo via viste le rose e i
            # crediti di adesso. Ordinare per 'prezzo' (il prezzo atteso) dava
            # una lista che non seguiva la colonna sotto gli occhi.
            chiave = {'costa': lambda x: -v.prezzo_chiusura(x),
                      'prezzo': lambda x: -(x.prezzo_atteso or 0),
                      'valore': lambda x: -(x.prezzo_mercato or 0),
                      'nome': lambda x: x.nome.lower(),
                      'mv': lambda x: -(x.mv or 0),
                      'presenze': lambda x: -(x.presenze or 0),
                      'quota': lambda x: -(x.qi or 0)}.get(ordine)
            righe.sort(key=chiave or (lambda x: -v.prezzo_chiusura(x)))
            nomi = dict((p['id'], p['nome']) for p in self.stato.presidenti())
            comprati = dict((a['giocatore_id'], a) for a in self.stato.acquisti())
            out = []
            for x in righe[:quanti]:
                a = comprati.get(x.id)
                out.append({
                    'id': x.id, 'nome': x.nome, 'squadra': x.squadra,
                    'ruolo': x.ruolo, 'qi': x.qi, 'mv': round(x.mv, 2),
                    'fm': round(x.fm, 2), 'presenze': int(round(x.presenze)),
                    # Due numeri diversi, e vanno tenuti distinti: quanto vale
                    # per la lega secondo il modello, e quanto costera' davvero.
                    # Confonderli e' il modo piu' rapido di pagare troppo.
                    'valore': int(round(x.prezzo_mercato or 1)),
                    'mercato': int(round(x.prezzo_atteso or x.prezzo_mercato or 1)),
                    'chiusura': int(round(v.prezzo_chiusura(x))),
                    'riferimento': int(round(x.prezzo_riferimento or 0)),
                    'gerarchia': Consigliere.gerarchia(x),
                    'stima': x.metodo != 'storico',
                    'fuori_lista': bool(x.fuori_lista),
                    'venduto': x.id in venduti,
                    'a_chi': nomi.get(a['presidente_id']) if a else None,
                    'pagato': a['prezzo'] if a else None,
                })
            return {'righe': out, 'totale': len(righe)}


def _intero(valore, nome, predefinito=None, minimo=None, massimo=None):
    """Legge un parametro numerico e lo rifiuta con parole comprensibili.

    Senza questo passaggio un parametro sbagliato usciva come 500 con dentro
    il messaggio di Python ("invalid literal for int()"), che a chi usa il
    programma non dice niente e sembra un guasto.
    """
    if valore is None or valore == '':
        if predefinito is not None:
            return predefinito
        raise ErroreAsta("manca il parametro '%s'" % nome)
    try:
        n = int(str(valore).strip())
    except (TypeError, ValueError):
        raise ErroreAsta("'%s' deve essere un numero intero, non %r" % (nome, valore))
    if minimo is not None and n < minimo:
        n = minimo
    if massimo is not None and n > massimo:
        n = massimo
    return n


def _prezzo(valore):
    """Un prezzo d'asta e' un numero intero di crediti.

    Se arriva un decimale si arrotonda invece di troncare: 3.7 crediti deve
    diventare 4, non 3. Troncare falserebbe i conti della cassa in silenzio,
    che e' il difetto peggiore che possa avere un registro d'asta.
    """
    if isinstance(valore, bool) or valore is None:
        raise ErroreAsta('manca il prezzo')
    if isinstance(valore, float):
        return int(round(valore))
    return _intero(valore, 'prezzo')


def _registra_errore():
    """Un errore imprevisto va lasciato per iscritto.

    Da .exe non c'e' una console dove guardare: senza un file, l'unica traccia
    di un guasto sarebbe il messaggio a schermo, che sparisce al primo clic.
    """
    testo = traceback.format_exc()
    try:
        with open(os.path.join(BASE, 'errori.log'), 'a', encoding='utf-8') as f:
            f.write('\n===== %s =====\n%s'
                    % (datetime.datetime.now().isoformat(timespec='seconds'), testo))
    except Exception:
        pass
    try:
        sys.stderr.write(testo)
    except Exception:
        pass


def _semplifica(x):
    """numpy restituisce int32/float64: JSON non li conosce, ma hanno .item()."""
    if hasattr(x, 'item'):
        return x.item()
    raise TypeError('non serializzabile: %r' % (type(x),))


# ============================================================== instradamento
class Gestore(BaseHTTPRequestHandler):
    server_version = 'FantaHacked'
    sessione = None
    ultimo_contatto = None    # quando l'interfaccia si e' fatta sentire
    congedo = None            # quando ha detto che si stava chiudendo
    spegni = None

    def log_message(self, *a):        # niente rumore sulla console
        pass

    def handle_one_request(self):
        # Qualunque richiesta e' un segno di vita, e annulla un congedo
        # annunciato: un ricaricamento della pagina passa di qui.
        Gestore.ultimo_contatto = time.time()
        Gestore.congedo = None
        BaseHTTPRequestHandler.handle_one_request(self)

    # ------------------------------------------------------------- risposte
    def _json(self, dati, codice=200):
        corpo = json.dumps(dati, ensure_ascii=False,
                           default=_semplifica).encode('utf-8')
        self.send_response(codice)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(corpo)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(corpo)

    def _file(self, richiesto):
        """Serve un file, ma solo se sta davvero dentro app/web.

        Il controllo va fatto sul percorso risolto, non sul testo dell'URL.
        Su Windows `os.path.join` butta via la cartella di partenza appena il
        secondo pezzo contiene una lettera di unita': con "/C:/Windows/..." si
        finiva a servire file di sistema. Confrontare i percorsi reali chiude
        anche le varianti con link simbolici e codifiche strane.
        """
        radice = os.path.realpath(WEB)
        percorso = os.path.realpath(os.path.join(radice, richiesto))
        if os.path.commonpath([radice, percorso]) != radice:
            self.send_error(403)
            return
        if not os.path.isfile(percorso):
            self.send_error(404)
            return
        tipo = mimetypes.guess_type(percorso)[0] or 'application/octet-stream'
        if tipo.startswith('text/') or tipo in ('application/javascript',):
            tipo += '; charset=utf-8'
        with open(percorso, 'rb') as f:
            corpo = f.read()
        self.send_response(200)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(corpo)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(corpo)

    # --------------------------------------------------------------- verbi
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        uno = lambda k, d=None: (q.get(k) or [d])[0]
        s = self.sessione
        try:
            if u.path.startswith('/api/'):
                if not s.pronta() and u.path not in ('/api/stato', '/api/ping'):
                    return self._json({'errore': 'asta non iniziata'}, 409)
                if u.path == '/api/ping':
                    # Il database **e i nomi delle squadre** si dichiarano.
                    # Serve al collaudo: le prove aprono e chiudono decine di
                    # aste con nomi finti, e se per sbaglio parlassero con
                    # un'istanza gia' accesa sui file veri cancellerebbero
                    # l'asta e sovrascriverebbero i nomi con "Bea, Chiara,
                    # Dario..." E' successo tutte e due le volte. Ora possono
                    # accorgersene e fermarsi prima di toccare niente.
                    return self._json({'app': 'FantaHacked',
                                       'database': percorsi.DB_FILE,
                                       'dati': percorsi.DATI_FILE,
                                       'preferenze': PREFERENZE})
                if u.path == '/api/stato':
                    return self._json(s.riepilogo())
                if u.path == '/api/cerca':
                    return self._json(s.cerca(uno('q', ''),
                                              _intero(uno('n'), 'n', 12, 1, 60)))
                if u.path == '/api/scheda':
                    return self._json(s.scheda(_intero(uno('id'), 'id')))
                if u.path == '/api/consiglio':
                    return self._json(s.consiglio())
                if u.path == '/api/piano':
                    return self._json(s.piano())
                if u.path == '/api/equilibrio':
                    return self._json(s.equilibrio())
                if u.path == '/api/rosa':
                    return self._json(s.rosa(_intero(uno('presidente'),
                                                     'presidente')))
                if u.path == '/api/listone':
                    return self._json(s.listone(
                        uno('ruolo'), uno('q', ''),
                        _intero(uno('n'), 'n', 60, 1, 600),
                        uno('ordine', 'costa'),
                        uno('titolari', '') in ('1', 'si', 'true')))
                return self._json({'errore': 'endpoint sconosciuto'}, 404)
            percorso = u.path.lstrip('/') or 'index.html'
            return self._file(percorso.replace('/', os.sep))
        except ErroreAsta as e:
            self._json({'errore': str(e)}, 400)
        except Exception as e:                                # pragma: no cover
            _registra_errore()
            self._json({'errore': '%s: %s' % (type(e).__name__, e)}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        s = self.sessione
        try:
            n = int(self.headers.get('Content-Length') or 0)
            if n > 1 << 20:
                return self._json({'errore': 'richiesta troppo grande'}, 413)
            grezzo = self.rfile.read(n).decode('utf-8') if n else ''
            try:
                dati = json.loads(grezzo) if grezzo else {}
            except ValueError:
                return self._json({'errore': 'il corpo della richiesta non e\' '
                                             'JSON valido'}, 400)
            if not isinstance(dati, dict):
                return self._json({'errore': 'il corpo deve essere un oggetto'}, 400)
            if u.path == '/api/congedo':
                # Deve funzionare anche prima che l'asta sia iniziata: la
                # pagina puo' essere chiusa dalla schermata di configurazione.
                Gestore.congedo = time.time()
                return self._json({'ok': True})
            if u.path == '/api/nuova':
                avversari = dati.get('avversari')
                if avversari is not None and not isinstance(avversari, list):
                    return self._json({'errore': "'avversari' deve essere un elenco"},
                                      400)
                return self._json(s.nuova(dati.get('mio_nome'), avversari or []))
            if not s.pronta():
                return self._json({'errore': 'asta non iniziata'}, 409)
            if u.path == '/api/rinomina':
                nomi = dati.get('nomi')
                if not isinstance(nomi, list):
                    return self._json({'errore': "'nomi' deve essere un elenco"}, 400)
                return self._json(s.rinomina(nomi))
            if u.path == '/api/acquisto':
                return self._json(s.acquisto(
                    _intero(dati.get('id'), 'id'),
                    _intero(dati.get('presidente'), 'presidente'),
                    _prezzo(dati.get('prezzo'))))
            if u.path == '/api/annulla':
                ident = dati.get('id')
                return self._json(s.annulla(
                    _intero(ident, 'id') if ident is not None else None))
            if u.path == '/api/turno':
                return self._json(s.turno(_intero(dati.get('presidente'),
                                                  'presidente')))
            if u.path == '/api/avanza':
                return self._json(s.avanza())
            if u.path == '/api/spegni':
                self._json({'ok': True})
                threading.Timer(0.4, self.server.shutdown).start()
                return
            return self._json({'errore': 'endpoint sconosciuto'}, 404)
        except ErroreAsta as e:
            self._json({'errore': str(e)}, 400)
        except KeyError as e:
            self._json({'errore': 'manca il campo %s' % e}, 400)
        except Exception as e:                                # pragma: no cover
            _registra_errore()
            self._json({'errore': '%s: %s' % (type(e).__name__, e)}, 500)


# ==================================================================== avvio
FILE_LUCCHETTO = 'fanta.lock'
FILE_PORTA = 'fanta.porta'


class Lucchetto(object):
    """Garantisce un solo FantaHacked alla volta sullo stesso database.

    Due processi che scrivono sullo stesso file SQLite durante un'asta dal
    vivo significa crediti sbagliati e giocatori assegnati due volte: e' il
    guasto peggiore che questo programma possa avere, ed e' facilissimo da
    provocare, basta fare doppio clic due volte perche' il primo avvio ci
    mette una decina di secondi e sembra che non stia succedendo niente.

    Il controllo non puo' basarsi sull'interrogare la porta: durante quei dieci
    secondi il primo processo non risponde ancora. Serve un lucchetto preso dal
    sistema operativo prima di toccare qualsiasi cosa, che viene rilasciato da
    solo anche se il programma finisce male.
    """

    def __init__(self, cartella):
        self.percorso = os.path.join(cartella, FILE_LUCCHETTO)
        self.percorso_porta = os.path.join(cartella, FILE_PORTA)
        self.f = None

    def acquisisci(self):
        try:
            self.f = open(self.percorso, 'a+b')
        except OSError:
            return True          # cartella di sola lettura: si prosegue
        try:
            if os.name == 'nt':
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            self.f = None
            return False
        return True

    def scrivi_porta(self, porta):
        try:
            with open(self.percorso_porta, 'w', encoding='utf-8') as f:
                f.write(str(porta))
        except OSError:
            pass

    def leggi_porta(self):
        try:
            with open(self.percorso_porta, encoding='utf-8') as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def rilascia(self):
        if not self.f:
            return
        try:
            if os.name == 'nt':
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        self.f.close()
        self.f = None
        try:
            os.remove(self.percorso_porta)
        except OSError:
            pass


def risponde(porta):
    """Vero se su quella porta c'e' davvero l'interfaccia di FantaHacked."""
    import urllib.request
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/api/ping' % porta,
                                    timeout=2.0) as r:
            return json.loads(r.read().decode('utf-8')).get('app') == 'FantaHacked'
    except Exception:
        return False


def porta_libera(preferita=PORTA_PREFERITA):
    for p in range(preferita, preferita + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', p)) != 0:
                return p
    return 0


# ------------------------------------------------------- finestra dell'app
def _browser_applicazione():
    """Un browser capace di aprire una finestra senza barre e schede.

    Edge c'e' su ogni Windows 11, e in modalita' `--app` da una finestra che
    e' a tutti gli effetti quella di un programma: icona sua nella barra delle
    applicazioni, niente indirizzo, niente schede.
    """
    nomi = [('Microsoft', 'Edge', 'Application', 'msedge.exe'),
            ('Google', 'Chrome', 'Application', 'chrome.exe'),
            ('BraveSoftware', 'Brave-Browser', 'Application', 'brave.exe')]
    basi = [os.environ.get(v) for v in
            ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA')]
    for base in basi:
        if not base:
            continue
        for pezzi in nomi:
            p = os.path.join(base, *pezzi)
            if os.path.isfile(p):
                return p
    import shutil
    for nome in ('msedge', 'chrome', 'chromium', 'chromium-browser'):
        p = shutil.which(nome)
        if p:
            return p
    return None


def _cartella_finestra():
    """Dove il browser tiene il profilo della finestra dell'app.

    Va fuori dalla cartella del progetto: e' roba del browser, non dati
    dell'asta, e non deve sporcare quello che l'utente vede.
    """
    base = (os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'))
    return os.path.join(base, 'FantaHacked', 'finestra')


def _dimentica_sessione(profilo):
    """Cancella le finestre che il browser vorrebbe riaprire all'avvio.

    Senza questo, alla seconda esecuzione Edge ripristina la finestra della
    volta prima: se ne aprono due, quella vecchia mostra una pagina scaduta, e
    chiudendo l'una il programma non si spegne perche' l'altra e' ancora li'.
    """
    import shutil
    for pezzi in (('Default', 'Sessions'), ('Default', 'Session Storage')):
        try:
            shutil.rmtree(os.path.join(profilo, *pezzi), ignore_errors=True)
        except Exception:
            pass


def apri_finestra(url):
    """Apre l'interfaccia in una finestra sua. Restituisce il processo.

    Il profilo dedicato serve a due cose: la finestra non finisce dentro il
    browser che l'utente ha gia' aperto, e quando la si chiude il processo
    finisce davvero, che e' il segnale con cui il programma capisce di doversi
    spegnere.
    """
    exe = _browser_applicazione()
    if not exe:
        return None
    import subprocess
    profilo = _cartella_finestra()
    try:
        os.makedirs(profilo, exist_ok=True)
    except OSError:
        pass
    _dimentica_sessione(profilo)
    argomenti = [
        exe,
        '--app=' + url,
        '--user-data-dir=' + profilo,
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-background-timer-throttling',
        '--window-size=1440,900',
    ]
    try:
        return subprocess.Popen(argomenti)
    except OSError:
        return None


def _porta_dell_altro(lucchetto, attesa=25.0):
    """Aspetta che l'istanza gia' avviata dica su che porta sta rispondendo.

    Il secondo doppio clic arriva spesso mentre il primo sta ancora caricando:
    invece di dire "e' gia' aperto" e lasciare l'utente davanti a niente, si
    aspetta che sia pronto e gli si apre la finestra.
    """
    scadenza = time.time() + attesa
    while time.time() < scadenza:
        porta = lucchetto.leggi_porta()
        if porta and risponde(porta):
            return porta
        time.sleep(0.7)
    return None


def _segui_finestra(processo, httpd):
    """Aspetta che la finestra venga chiusa, poi spegne tutto.

    Con una cautela: il processo che abbiamo lanciato non e' sempre quello che
    tiene la finestra. Il browser puo' passarla a un'altra sua istanza e
    uscire subito, e spegnere in quel momento chiuderebbe il programma un
    istante dopo averlo aperto. Percio' prima di spegnere si guarda se
    qualcuno sta ancora parlando con noi: se una pagina e' viva, la finestra
    c'e' ancora, e a dire quando non ci sara' piu' ci pensera' il congedo.
    """
    try:
        processo.wait()
    except Exception:
        return
    time.sleep(6.0)
    # Da qui in poi non si smette di guardare: se il browser ha passato la
    # finestra a un altro processo, l'unico segnale che resta e' la pagina che
    # continua a farsi viva. Quando smette, la finestra e' stata chiusa.
    # La pagina batte ogni dieci secondi: mezzo minuto di silenzio sono tre
    # battiti mancati, abbastanza per non spegnersi a un singhiozzo.
    while True:
        ultimo = Gestore.ultimo_contatto
        if ultimo is None or time.time() - ultimo > 30.0:
            print('Finestra chiusa: spengo il motore.')
            httpd.shutdown()
            return
        time.sleep(3.0)


# Quanto il programma sopravvive senza sentire piu' la pagina. Deve essere
# largo: un browser che mette in pausa le schede in secondo piano puo' saltare
# qualche battito, e spegnersi mentre l'utente sta facendo l'asta sarebbe
# molto peggio che restare acceso qualche minuto di troppo.
ATTESA_SENZA_PAGINA = 180.0

# Con una finestra dedicata il silenzio non e' un buon segnale di chiusura:
# la finestra c'e', e a dire quando sparisce ci pensa il congedo. Questo e'
# solo l'ultimo paracadute, per il caso in cui il browser muoia di schianto.
ATTESA_FINESTRA = 600.0


def _sentinella_pagina(httpd, scadenza=None):
    """Spegne il programma quando l'interfaccia non da' piu' segno di vita.

    Serve solo quando non si e' potuta aprire una finestra dedicata: in quel
    caso l'unico modo di sapere che l'utente ha finito e' che la pagina smetta
    di farsi sentire. La pagina avvisa anche esplicitamente quando viene
    chiusa, cosi' nel caso normale lo spegnimento e' immediato.
    """
    while True:
        time.sleep(3.0)
        ultimo = Gestore.ultimo_contatto
        if ultimo is None:
            continue                      # nessuno si e' ancora collegato
        if Gestore.congedo and time.time() - Gestore.congedo > 12.0:
            # La pagina ha detto che si stava chiudendo e non e' tornata:
            # un semplice ricaricamento si sarebbe rifatto vivo subito.
            print('Interfaccia chiusa: spengo il motore.')
            httpd.shutdown()
            return
        limite = ATTESA_SENZA_PAGINA if scadenza is None else scadenza
        if time.time() - ultimo > limite:
            print('Nessuna interfaccia collegata: spengo il motore.')
            httpd.shutdown()
            return


def main(apri=True, forza_sistema=False):
    print("FantaHacked - assistente d'asta")

    # Prima di tutto il lucchetto: se c'e' gia' un'istanza non si deve nemmeno
    # aprire il database.
    # Il lucchetto sta accanto al database che protegge, non in una cartella
    # fissa. Serve a due cose diverse che sono la stessa cosa: due istanze non
    # devono poter scrivere sullo stesso file, e **il collaudo, che gira su una
    # copia usa e getta, non deve litigare con l'istanza dell'utente per il
    # lucchetto e la porta**. Prima le prove si prendevano la porta 8730 o
    # niente: se il programma era aperto uscivano senza fare nulla, ed era
    # quello il caso in cui, per due volte, hanno cancellato l'asta vera.
    lucchetto = Lucchetto(os.path.dirname(os.path.abspath(percorsi.DB_FILE)))
    if not lucchetto.acquisisci():
        porta = _porta_dell_altro(lucchetto)
        if porta:
            url = 'http://127.0.0.1:%d/' % porta
            print('FantaHacked era gia\' avviato: apro %s' % url)
            if apri:
                # Anche la seconda finestra dev'essere una finestra
                # dell'applicazione, non una scheda del browser. Qui si
                # ripiegava su `webbrowser.open`, e chi faceva doppio clic
                # mentre il programma era gia' acceso - anche solo perche' la
                # finestra era finita dietro le altre - se lo ritrovava aperto
                # dentro il browser, con barra degli indirizzi e schede.
                # Sembrava che il programma cambiasse forma a caso.
                if apri_finestra(url) is None:
                    webbrowser.open(url)
        else:
            _avvisa('FantaHacked risulta gia\' in esecuzione.\n\n'
                    'Se non lo vedi da nessuna parte, chiudilo dalla Gestione '
                    'attivita\' (processo FantaHacked.exe) e riprova.')
        return

    try:
        print('Preparazione del motore...')
        Gestore.sessione = Sessione()
        porta = porta_libera()
        httpd = ThreadingHTTPServer(('127.0.0.1', porta), Gestore)
        porta = httpd.server_address[1]
        lucchetto.scrivi_porta(porta)
        url = 'http://127.0.0.1:%d/' % porta
        Gestore.spegni = lambda: threading.Thread(
            target=httpd.shutdown, daemon=True).start()
        print('Pronto. Interfaccia su %s' % url)

        if forza_sistema and not apri:
            # Solo per il collaudo: la sentinella senza aprire nessuna finestra.
            threading.Thread(target=_sentinella_pagina,
                             args=(httpd,), daemon=True).start()
        if apri:
            finestra = None if forza_sistema else apri_finestra(url)
            if finestra is not None:
                # La finestra E' il programma: quando l'utente la chiude, il
                # motore si spegne con lei. Nessun processo che resta acceso
                # senza che si veda, nessun pulsante speciale da ricordarsi.
                print('Finestra aperta. Chiudila per uscire dal programma.')
                threading.Thread(target=_segui_finestra,
                                 args=(finestra, httpd), daemon=True).start()
                # Doppia rete: se il browser si sdoppia in piu' processi e il
                # controllo sul processo perde il filo, e' la pagina stessa a
                # dire quando non c'e' piu'. Senza scadenza a tempo, pero':
                # con una finestra aperta non si spegne mai a orologio.
                threading.Thread(target=_sentinella_pagina,
                                 args=(httpd, ATTESA_FINESTRA), daemon=True).start()
            else:
                # Nessun browser adatto: si ripiega su quello di sistema, e
                # allora e' la pagina stessa a dire quando non c'e' piu'.
                print('Apro nel browser predefinito.')
                threading.Timer(0.6, lambda: webbrowser.open(url)).start()
                threading.Thread(target=_sentinella_pagina,
                                 args=(httpd,), daemon=True).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nChiusura.')
    finally:
        lucchetto.rilascia()


def _avvisa(testo):
    """Un messaggio all'utente, anche quando non c'e' una console."""
    print(testo)
    if getattr(sys, 'frozen', False):
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, testo, 'FantaHacked', 0x40)
        except Exception:
            pass


def avvio_protetto():
    """Da .exe non c'e' console: un errore all'avvio sarebbe invisibile.

    Viene scritto accanto all'eseguibile, dove l'utente puo' trovarlo, e
    mostrato in una finestra di sistema se ce n'e' una disponibile.
    """
    try:
        main(apri='--no-browser' not in sys.argv,
         forza_sistema='--browser-di-sistema' in sys.argv)
    except Exception:
        testo = traceback.format_exc()
        percorso = os.path.join(BASE, 'errore-avvio.log')
        try:
            with open(percorso, 'w', encoding='utf-8') as f:
                f.write(testo)
        except Exception:
            pass
        if getattr(sys, 'frozen', False):
            try:
                import ctypes
                ctypes.windll.user32.MessageBoxW(
                    None,
                    "FantaHacked non e' riuscito ad avviarsi.\n\n"
                    + testo.strip().splitlines()[-1]
                    + "\n\nIl dettaglio completo e' in errore-avvio.log",
                    'FantaHacked', 0x10)
            except Exception:
                pass
        else:
            print(testo)
        raise SystemExit(1)


if __name__ == '__main__':
    avvio_protetto()
