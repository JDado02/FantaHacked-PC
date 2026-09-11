# -*- coding: utf-8 -*-
"""Tenere aggiornato il file dei dati, e le proiezioni che ne discendono.

Due lavori distinti, che pero' si tengono per mano.

**Scaricare.** I dati dei giocatori stanno online in un unico file da mezzo
mega. All'avvio il programma chiede solo il `manifest.json` &mdash; due
kilobyte &mdash; e se la data e' la stessa che ha gia' non scarica niente.
Se la rete non c'e', o e' lenta, o risponde male, **non succede niente**: si
parte con i dati che ci sono e si scrive a schermo di quando sono. Un
assistente d'asta che non si apre perche' il wifi della stanza fa i capricci
sarebbe peggio di uno con i dati di tre giorni prima.

**Ricalcolare.** Le proiezioni non sono un dato, sono un conto: dipendono dal
listone *e* dal regolamento della tua lega. Un gol di difensore che vale 3
invece di 4, il modificatore acceso invece che spento, e i punti attesi di
tutti cambiano. Quindi il file scaricato porta con se' la firma del
regolamento con cui e' stato calcolato: se non e' la tua, le proiezioni si
rifanno qui, in due secondi, prima che il programma apra bocca.

Serviva comunque, anche senza niente da scaricare: fino a ieri chi correggeva
`regole_lega.json` continuava a vedere le proiezioni di prima, senza che
niente glielo dicesse.
"""
import gzip, hashlib, io, json, os, shutil, sqlite3, sys, tempfile, urllib.error, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import percorsi

# Dove stanno i dati pubblicati: due file nel ramo principale di un repository
# pubblico. L'indirizzo e' fisso e non cambia mai da una pubblicazione
# all'altra, che e' l'unica cosa che conta per chi lo deve leggere.
#
# Si era pensato alle release invece che ai file nel repository, per non
# lasciare una copia intera nella cronologia a ogni aggiornamento. Ma il
# pacchetto compresso sono 185 KB: anche pubblicandolo ogni settimana per una
# stagione intera restano sotto i dieci mega, mentre le release avrebbero
# richiesto uno strumento in piu' (`gh`) su ogni computer da cui si pubblica.
# Fra i due difetti, quello che pesa meno e' lo spazio.
#
# GitHub tiene questi file in cache per cinque minuti: dopo aver pubblicato,
# un programma acceso in quel momento puo' vedere ancora i dati di prima.
ORIGINE = os.environ.get('FANTAHACKED_ORIGINE') or (
    'https://raw.githubusercontent.com/JDado02/DBFantaHacked/main')

MANIFEST = 'manifest.json'
PACCHETTO = 'dati.db.gz'

# Quanto si aspetta la rete. Corto apposta: e' un di piu', non un requisito.
ATTESA_MANIFEST = 6
ATTESA_PACCHETTO = 60


# --------------------------------------------------------- firma del regolamento
def firma_regole(percorso=None):
    """L'impronta del regolamento **scritto sul disco**.

    Il calcolo vero sta in `regole.impronta`: qui resta solo la lettura del
    file, per chi non ha gia' in mano un oggetto `Regole`.
    """
    percorso = percorso or os.path.join(percorsi.DATABASE, 'regole_lega.json')
    try:
        with io.open(percorso, encoding='utf-8') as f:
            d = json.load(f)
    except Exception:
        return ''
    import regole as regmod
    return regmod.impronta(d)


def _meta(con, chiave):
    try:
        r = con.execute('SELECT valore FROM dati.meta WHERE chiave = ?',
                        (chiave,)).fetchone()
        return r['valore'] if r else ''
    except sqlite3.OperationalError:
        return ''


def _scrivi_meta(con, chiave, valore):
    try:
        con.execute('INSERT OR REPLACE INTO dati.meta (chiave, valore) VALUES (?,?)',
                    (chiave, valore))
        con.commit()
    except sqlite3.OperationalError:
        pass


def segna_firma_regole(con, reg):
    """Registra su quale regolamento sono calcolate le proiezioni che ci sono.

    Serve a chi le ricalcola per conto suo &mdash; database vuoto, prima
    installazione &mdash; per non farle rifare da capo al primo controllo.
    """
    _scrivi_meta(con, 'regole_firma', reg.firma if reg is not None
                 else firma_regole())


def assicura_proiezioni(con, reg=None, verboso=False):
    """Se le proiezioni non sono le tue, le rifa'. Restituisce True se ha lavorato.

    L'impronta viene dalle regole **in uso**, non dal file: da quando squadre,
    crediti e modificatore si scelgono dalla schermata iniziale, le due cose
    possono differire, e quella che conta e' la prima.
    """
    attesa = reg.firma if reg is not None else firma_regole()
    try:
        quante = con.execute('SELECT COUNT(*) FROM proiezioni').fetchone()[0]
    except sqlite3.OperationalError:
        return False
    if quante and _meta(con, 'regole_firma') == attesa:
        return False
    import proiezioni as proimod
    import regole as regmod
    proimod.esegui(con, reg or regmod.carica())
    _scrivi_meta(con, 'regole_firma', attesa)
    if verboso:
        print('proiezioni ricalcolate sul tuo regolamento')
    return True


# ------------------------------------------------------------------ scaricare
class Esito(object):
    """Com'e' andata: serve alla pagina per dire una frase onesta."""

    def __init__(self, stato, messaggio='', data_locale='', data_remota=''):
        self.stato = stato            # aggiornato | gia_aggiornato | offline | errore | spento
        self.messaggio = messaggio
        self.data_locale = data_locale
        self.data_remota = data_remota

    def __repr__(self):
        return 'Esito(%s, %r)' % (self.stato, self.messaggio)


def _leggi(url, attesa):
    req = urllib.request.Request(url, headers={'User-Agent': 'FantaHacked'})
    with urllib.request.urlopen(req, timeout=attesa) as r:
        return r.read()


def manifest_remoto(origine=None, attesa=ATTESA_MANIFEST):
    """Il manifest pubblicato. Torna (manifest, motivo): uno dei due e' None.

    Il motivo serve perche' i due modi di fallire vogliono due frasi diverse:
    *non c'e' ancora niente pubblicato* e *questo computer non arriva a
    internet* si assomigliano solo dal punto di vista del codice.
    """
    origine = origine or ORIGINE
    try:
        return json.loads(_leggi(origine.rstrip('/') + '/' + MANIFEST, attesa)
                          .decode('utf-8')), None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, 'nessun pacchetto pubblicato a quell indirizzo'
        return None, 'il sito ha risposto %s' % e.code
    except Exception:
        return None, 'nessuna risposta da internet'


def scarica(destinazione=None, origine=None, attesa=ATTESA_PACCHETTO, atteso=None):
    """Scarica il pacchetto e lo mette al posto giusto, tutto o niente.

    Scrive prima un file a fianco, lo verifica, e solo allora lo sposta. Se
    salta la corrente a meta' download, quello che c'era resta dov'era.
    """
    destinazione = destinazione or percorsi.DATI_FILE
    origine = origine or ORIGINE
    grezzo = _leggi(origine.rstrip('/') + '/' + PACCHETTO, attesa)
    if atteso:
        visto = hashlib.sha256(grezzo).hexdigest()
        if visto != atteso:
            raise ValueError('il file scaricato non corrisponde alla sua firma')
    corpo = gzip.decompress(grezzo)

    cartella = os.path.dirname(destinazione) or '.'
    if not os.path.isdir(cartella):
        os.makedirs(cartella)
    fd, tmp = tempfile.mkstemp(suffix='.db', dir=cartella)
    os.close(fd)
    try:
        with io.open(tmp, 'wb') as f:
            f.write(corpo)
        # Aprirlo prima di fidarsene: un file troncato passa il controllo della
        # firma solo se la firma manca, ma non passa mai una query.
        prova = sqlite3.connect(tmp)
        n = prova.execute('SELECT COUNT(*) FROM giocatori').fetchone()[0]
        prova.close()
        if n < 100:
            raise ValueError('il file scaricato contiene solo %d giocatori' % n)
        # Su Windows un file aperto non si puo' sostituire. Capita quando un
        # altro FantaHacked e' acceso sugli stessi dati: e' una situazione
        # normale, e va detta in modo che si capisca cosa fare.
        try:
            if os.path.exists(destinazione):
                os.replace(destinazione, destinazione + '.precedente')
            os.replace(tmp, destinazione)
        except OSError as e:
            raise OSError('i dati sono aperti da un altro programma: chiudi '
                          'FantaHacked e riprova (%s)' % e)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return destinazione


def aggiorna(dati=None, origine=None, attivo=True):
    """Il giro completo da fare all'avvio, prima di aprire il database.

    Non solleva mai: qualunque cosa vada storta, il programma deve partire.
    """
    dati = dati or percorsi.DATI_FILE
    locale = _versione_locale(dati)
    if not attivo:
        return Esito('spento', data_locale=locale)

    m, motivo = manifest_remoto(origine)
    if m is None:
        return Esito('offline', motivo, locale)
    remota = m.get('generato_il') or ''
    if os.path.exists(dati) and remota and remota <= locale:
        return Esito('gia_aggiornato', '', locale, remota)
    try:
        scarica(dati, origine, atteso=m.get('sha256'))
        _segna_installato(dati, remota)
    except Exception as e:
        return Esito('errore', str(e), locale, remota)
    return Esito('aggiornato', '', remota, remota)


def _versione_locale(dati):
    """Quale pacchetto e' stato installato, non che data dichiarano i dati.

    Sembra la stessa cosa e non lo e'. Se il manifest dicesse una data e il
    file ne contenesse un'altra - una svista di chi pubblica - confrontare la
    data *dentro* il file farebbe riscaricare lo stesso pacchetto a ogni
    avvio, per sempre, senza che nessuno se ne accorga: ogni volta mezzo mega,
    e ogni volta lo stesso risultato. Quello che conta e' cos'ho gia' preso.
    """
    if not os.path.exists(dati):
        return ''
    try:
        c = sqlite3.connect(dati)
        r = c.execute("SELECT chiave, valore FROM meta"
                      " WHERE chiave IN ('installato','generato_il')").fetchall()
        c.close()
    except Exception:
        return ''
    d = dict(r)
    return d.get('installato') or d.get('generato_il') or ''


def _segna_installato(dati, versione):
    """Annota nel file quale pacchetto e'. Se non riesce, pazienza: si riscarica."""
    if not versione:
        return
    try:
        c = sqlite3.connect(dati)
        c.execute('INSERT OR REPLACE INTO meta (chiave, valore) VALUES (?,?)',
                  ('installato', versione))
        c.commit()
        c.close()
    except Exception:
        pass


if __name__ == '__main__':
    import regole as regmod
    import db as dbmod
    e = aggiorna()
    print('aggiornamento: %s %s' % (e.stato, e.messaggio))
    print('  dati locali del %s, pubblicati del %s'
          % (e.data_locale or '-', e.data_remota or '-'))
    con = dbmod.connetti()
    if assicura_proiezioni(con, regmod.carica(), verboso=True):
        print('  (erano state calcolate con un altro regolamento)')
    else:
        print('  proiezioni gia\' allineate al regolamento')
    con.close()
