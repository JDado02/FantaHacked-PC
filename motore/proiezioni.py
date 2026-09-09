# -*- coding: utf-8 -*-
"""Da statistiche storiche a punti fantacalcio attesi sulla stagione.

E' il modulo che determina la qualita' di tutto il resto: il motore d'asta
calcola prezzi corretti per i punti che gli vengono dati. Se i punti sono
sbagliati, i prezzi sono precisi e inutili.

Impostazione:
  - media pesata delle ultime stagioni, con peso maggiore alla piu' recente
  - regressione verso la media di ruolo, tanto piu' forte quanto meno campione
  - i gol si stimano dagli xG, non dai gol: i gol sono rumorosi, gli xG molto meno
  - i rigori si contano a parte, perche' npxG li esclude per costruzione
  - chi non ha storico di Serie A viene imputato dalla quotazione, e marcato

Nessun parametro e' cablato a mano: le medie di ruolo, i tassi e le regressioni
sono calibrati sul database a ogni esecuzione.

Uso:  python proiezioni.py
"""
import math, os, sqlite3, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db as dbmod
import regole as regmod
import titolarita as titmod

GIORNATE = 38
MINUTI_STAGIONE = GIORNATE * 90

# Peso delle stagioni. Il rendimento recente conta di piu', ma non e' tutto.
PESO_RENDIMENTO = {'2025-26': 1.00, '2024-25': 0.55, '2023-24': 0.30}
# Per il minutaggio la memoria e' piu' corta: i ruoli in rosa cambiano in fretta.
PESO_MINUTAGGIO = {'2025-26': 1.00, '2024-25': 0.35, '2023-24': 0.15}

# Forza della regressione verso la media di ruolo, espressa in minuti di prior.
# 900 minuti = dieci partite intere: sotto quella soglia la stima e' dominata
# dalla media di ruolo, sopra dal rendimento individuale.
K_MV    = 900.0
K_TASSI = 700.0
K_QUOTA = 600.0

RUOLI = ('P', 'D', 'C', 'A')


# --------------------------------------------------------------- calibrazione
class Calibrazione(object):
    """Medie di ruolo e tassi di lega, ricavati dal database."""

    def __init__(self, con):
        self.con = con
        self.mv_ruolo = {}
        self.npxg90 = {}
        self.xa90 = {}
        self.amm90 = {}
        self.esp90 = {}
        self.min_per_pg = {}
        self.fit_minuti = {}   # ruolo -> (a, b) per minuti ~ a + b*ln(qi)
        self.fit_mv = {}
        self._medie_ruolo()
        self._tassi()
        self._rigori()
        self._assist_su_xa()
        self._difese()
        self._fit_quotazione()

    def _q(self, sql, *a):
        return self.con.execute(sql, a).fetchall()

    def _medie_ruolo(self):
        for r in self._q("""SELECT g.ruolo, AVG(s.mv) mv,
                                   SUM(s.minuti)*1.0/SUM(s.pg) mpg
                            FROM statistiche s JOIN giocatori g USING(id)
                            WHERE s.minuti >= 900 AND s.mv IS NOT NULL AND s.pg > 0
                            GROUP BY g.ruolo"""):
            self.mv_ruolo[r['ruolo']] = r['mv']
            self.min_per_pg[r['ruolo']] = r['mpg']
        for r in self._q("""SELECT g.ruolo,
                                   SUM(s.amm)*90.0/SUM(s.minuti) a90,
                                   SUM(s.esp)*90.0/SUM(s.minuti) e90
                            FROM statistiche s JOIN giocatori g USING(id)
                            WHERE s.minuti >= 900 GROUP BY g.ruolo"""):
            self.amm90[r['ruolo']] = r['a90'] or 0.0
            self.esp90[r['ruolo']] = r['e90'] or 0.0

    def _tassi(self):
        for r in self._q("""SELECT g.ruolo,
                                   SUM(a.npxg)*90.0/SUM(a.minuti) n90,
                                   SUM(a.xa)*90.0/SUM(a.minuti)   x90
                            FROM avanzate a JOIN giocatori g USING(id)
                            WHERE a.minuti >= 900 GROUP BY g.ruolo"""):
            self.npxg90[r['ruolo']] = r['n90'] or 0.0
            self.xa90[r['ruolo']] = r['x90'] or 0.0
        for ruolo in RUOLI:
            self.npxg90.setdefault(ruolo, 0.0)
            self.xa90.setdefault(ruolo, 0.0)

    def _rigori(self):
        r = self._q("""SELECT SUM(rc) rc, SUM(rpiu) rp FROM statistiche
                       WHERE stagione = ?""", '2025-26')[0]
        self.rigori_per_squadra = (r['rc'] or 0) / 20.0
        self.conversione_rigori = (r['rp'] or 0) / float(r['rc']) if r['rc'] else 0.75

    def _assist_su_xa(self):
        """Gli assist del fantacalcio non coincidono con gli xA: si calibra il rapporto."""
        r = self._q("""SELECT SUM(s.ass) a, SUM(v.xa) x
                       FROM statistiche s JOIN avanzate v ON v.id = s.id
                            AND v.stagione = s.stagione
                       WHERE s.minuti >= 900""")[0]
        self.assist_su_xa = (r['a'] / r['x']) if (r['a'] and r['x']) else 1.0

    def _difese(self):
        """Gol subiti per 90' di ogni squadra. Le neopromosse prendono un prior prudente."""
        self.gs90_squadra = {}
        vals = []
        for r in self._q("""SELECT squadra, gf_prec, gs_prec, promossa FROM squadre"""):
            # gs_prec a zero non significa "difesa perfetta": significa che di
            # quella squadra non abbiamo la stagione. Va trattato come ignoto,
            # altrimenti il suo portiere risulterebbe imbattibile.
            if r['promossa'] or not r['gs_prec']:
                continue
            v = r['gs_prec'] / float(GIORNATE)
            self.gs90_squadra[r['squadra']] = v
            vals.append(v)
        # Prior per le neopromosse: il peggior quartile delle difese di Serie A.
        vals.sort()
        prior = vals[int(len(vals) * 0.85)] if vals else 1.5
        self.gs90_neopromosse = prior
        for r in self._q("SELECT squadra, promossa FROM squadre"):
            if r['squadra'] not in self.gs90_squadra:
                self.gs90_squadra[r['squadra']] = prior

    def _fit_quotazione(self):
        """Regressione minuti/mv sulla quotazione, per imputare chi non ha storico."""
        for ruolo in RUOLI:
            rows = self._q("""SELECT g.qi, s.minuti, s.mv
                              FROM giocatori g JOIN statistiche s USING(id)
                              WHERE s.stagione = ? AND g.ruolo = ? AND g.qi > 0
                                AND s.minuti IS NOT NULL AND s.mv IS NOT NULL""",
                           '2025-26', ruolo)
            if len(rows) < 8:
                self.fit_minuti[ruolo] = (MINUTI_STAGIONE * 0.4, 0.0)
                self.fit_mv[ruolo] = (self.mv_ruolo.get(ruolo, 6.0), 0.0)
                continue
            xs = [math.log(r['qi']) for r in rows]
            self.fit_minuti[ruolo] = _retta(xs, [r['minuti'] for r in rows])
            self.fit_mv[ruolo] = _retta(xs, [r['mv'] for r in rows])

    def gs90(self, squadra):
        return self.gs90_squadra.get(squadra, self.gs90_neopromosse)


def _retta(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    b = (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den) if den else 0.0
    return (my - b * mx, b)


def _shrink(somma_valore, somma_peso, prior, k):
    """Media regressa verso il prior. `somma_peso` e' in minuti."""
    return (somma_valore + prior * k) / (somma_peso + k)


# ---------------------------------------------------------------- proiezione
class Proiettore(object):

    def __init__(self, con, reg, cal=None):
        self.con = con
        self.reg = reg
        self.cal = cal or Calibrazione(con)

    def _rigoristi(self):
        """Chi tira i rigori **quest'anno**, non chi li tirava l'anno scorso.

        E' una differenza che vale punti veri. Il dato di partenza era dedotto
        dai rigori calciati nella stagione precedente: dopo un mercato dice
        che i rigori del Napoli li tira chi adesso gioca altrove, e che il
        nuovo rigorista non ne tira nessuno. Sei o sette gol a stagione
        assegnati alla persona sbagliata.
        """
        try:
            righe = self.con.execute(
                'SELECT id, rigorista FROM gerarchie WHERE rigorista IS NOT NULL'
            ).fetchall()
        except Exception:
            return {}
        return dict((r['id'], r['rigorista']) for r in righe if r['rigorista'])

    def _dati(self):
        """Un dizionario id -> {anagrafica, stagioni, contesto}."""
        g = {}
        for r in self.con.execute("SELECT * FROM giocatori"):
            g[r['id']] = {'id': r['id'], 'nome': r['nome'], 'ruolo': r['ruolo'],
                          'squadra': r['squadra'], 'qi': r['qi'] or 1,
                          'st': {}, 'av': {}, 'ctx': {}}
        for r in self.con.execute("SELECT * FROM statistiche"):
            if r['id'] in g:
                g[r['id']]['st'][r['stagione']] = dict(r)
        for r in self.con.execute("SELECT * FROM avanzate"):
            if r['id'] in g:
                g[r['id']]['av'][r['stagione']] = dict(r)
        for r in self.con.execute("SELECT * FROM contesto"):
            if r['id'] in g:
                g[r['id']]['ctx'] = dict(r)
        return g

    def proietta_tutti(self):
        self.rigoristi = self._rigoristi()
        return [self.proietta(p) for p in self._dati().values()]

    # ------------------------------------------------------------------ core
    def proietta(self, p):
        cal, reg, ruolo = self.cal, self.reg, p['ruolo']

        # --- minutaggio atteso -------------------------------------------
        sm = sw = 0.0
        for stag, peso in PESO_MINUTAGGIO.items():
            m = (p['st'].get(stag) or {}).get('minuti')
            if m is None:
                m = (p['av'].get(stag) or {}).get('minuti')
            if m is not None:
                sm += peso * m
                sw += peso * MINUTI_STAGIONE

        a, b = cal.fit_minuti[ruolo]
        minuti_da_quota = max(0.0, min(MINUTI_STAGIONE, a + b * math.log(max(p['qi'], 1))))
        if sw > 0:
            quota_storica = sm / sw
            # La quotazione porta l'informazione sul ruolo previsto quest'anno,
            # lo storico porta quella sul rendimento passato: si combinano.
            peso_storico = min(1.0, sw / (sw + K_QUOTA * 1.0))
            minuti = (peso_storico * quota_storica * MINUTI_STAGIONE
                      + (1 - peso_storico) * minuti_da_quota)
            metodo = 'storico'
        else:
            minuti = minuti_da_quota
            metodo = 'imputato_da_quotazione'
        minuti = max(0.0, min(float(MINUTI_STAGIONE), minuti))

        # --- minuti pesati: quanto campione c'e' davvero ------------------
        # Denominatori separati per fonte. Le statistiche coprono 2 stagioni,
        # i dati avanzati 3: usare un denominatore unico diluirebbe la media
        # voto con minuti per cui il voto non esiste.
        peso_st = peso_av = 0.0
        for stag, peso in PESO_RENDIMENTO.items():
            s, v = p['st'].get(stag), p['av'].get(stag)
            if s and s.get('minuti'):
                peso_st += peso * s['minuti']
            if v and v.get('minuti'):
                peso_av += peso * v['minuti']
        peso_min = max(peso_st, peso_av)

        # --- media voto ---------------------------------------------------
        num = 0.0
        for stag, peso in PESO_RENDIMENTO.items():
            s = p['st'].get(stag)
            if s and s.get('mv') is not None and s.get('minuti'):
                num += peso * s['minuti'] * s['mv']
        if peso_st > 0:
            mv = _shrink(num, peso_st, cal.mv_ruolo.get(ruolo, 6.0), K_MV)
        else:
            am, bm = cal.fit_mv[ruolo]
            mv = am + bm * math.log(max(p['qi'], 1))
        mv = max(4.5, min(7.5, mv))

        # --- presenze -----------------------------------------------------
        mpg = cal.min_per_pg.get(ruolo, 85.0)
        pg_num = pg_den = 0.0
        for stag, peso in PESO_RENDIMENTO.items():
            s = p['st'].get(stag)
            if s and s.get('pg') and s.get('minuti'):
                pg_num += peso * s['minuti']
                pg_den += peso * s['pg']
        mpg_pers = (pg_num / pg_den) if pg_den else mpg
        mpg_eff = _shrink(mpg_pers * peso_st, peso_st, mpg, K_MV)
        presenze = min(float(GIORNATE), minuti / max(mpg_eff, 20.0))

        # --- tassi offensivi ---------------------------------------------
        npxg = xa = 0.0
        for stag, peso in PESO_RENDIMENTO.items():
            v = p['av'].get(stag)
            if v and v.get('minuti'):
                npxg += peso * (v.get('npxg') or 0.0)
                xa += peso * (v.get('xa') or 0.0)
        npxg90 = _shrink(npxg * 90.0, peso_av, cal.npxg90.get(ruolo, 0.0), K_TASSI)
        xa90 = _shrink(xa * 90.0, peso_av, cal.xa90.get(ruolo, 0.0), K_TASSI)

        novanta = minuti / 90.0
        gol_azione = npxg90 * novanta
        assist = xa90 * novanta * cal.assist_su_xa

        # --- rigori --------------------------------------------------------
        # La gerarchia dal dischetto letta dal web batte quella dedotta dai
        # rigori dell'anno scorso: sa dove gioca adesso, e chi tira adesso.
        rig = getattr(self, 'rigoristi', {}).get(p['id'])
        if rig is None:
            rig = p['ctx'].get('rigorista')
        quota_gioco = minuti / float(MINUTI_STAGIONE)
        if rig == 1:
            rigori = cal.rigori_per_squadra * 0.85 * quota_gioco
        elif rig == 2:
            rigori = cal.rigori_per_squadra * 0.25 * quota_gioco
        else:
            rigori = 0.0
        rig_segnati = rigori * cal.conversione_rigori
        rig_sbagliati = rigori - rig_segnati

        # --- cartellini -----------------------------------------------------
        amm_num = esp_num = 0.0
        for stag, peso in PESO_RENDIMENTO.items():
            s = p['st'].get(stag)
            if s and s.get('minuti'):
                amm_num += peso * (s.get('amm') or 0)
                esp_num += peso * (s.get('esp') or 0)
        amm90 = _shrink(amm_num * 90.0, peso_st, cal.amm90.get(ruolo, 0.15), K_TASSI)
        esp90 = _shrink(esp_num * 90.0, peso_st, cal.esp90.get(ruolo, 0.01), K_TASSI)
        amm = amm90 * novanta
        esp = esp90 * novanta

        # --- specifiche portiere --------------------------------------------
        gs = rp = imbattuto = 0.0
        if ruolo == 'P':
            gs90 = self.cal.gs90(p['squadra'])
            gs = gs90 * novanta
            # Probabilita' di non subire gol: Poisson con media gs90.
            if reg.imbattuto_attivo:
                imbattuto = presenze * math.exp(-gs90)
            rp_num = 0.0
            for stag, peso in PESO_RENDIMENTO.items():
                s = p['st'].get(stag)
                if s and s.get('minuti'):
                    rp_num += peso * (s.get('rp') or 0)
            rp = _shrink(rp_num * 90.0, peso_st, 0.02, K_TASSI) * novanta

        # --- bonus totali ----------------------------------------------------
        bonus = (gol_azione * reg.gol_ruolo[ruolo]
                 + rig_segnati * reg.v_rig_segnato
                 + rig_sbagliati * reg.v_rig_sbagl
                 + assist * reg.v_assist
                 + amm * reg.v_amm
                 + esp * reg.v_esp
                 + gs * reg.v_gol_subito
                 + rp * reg.v_rig_parato
                 + imbattuto * (reg.imbattuto_bonus if reg.imbattuto_attivo else 0.0))
        bpp = bonus / presenze if presenze > 0.5 else 0.0
        fantamedia = mv + bpp
        punti = presenze * fantamedia

        affidabilita = min(1.0, peso_min / 2400.0)
        return {
            'id': p['id'], 'minuti_attesi': round(minuti, 1),
            'presenze_attese': round(presenze, 2), 'mv_attesa': round(mv, 3),
            'gol_attesi': round(gol_azione + rig_segnati, 2),
            'assist_attesi': round(assist, 2), 'amm_attese': round(amm, 2),
            'esp_attese': round(esp, 3), 'gs_attesi': round(gs, 2),
            'rp_attesi': round(rp, 3), 'imbattuto_attese': round(imbattuto, 2),
            'bonus_per_partita': round(bpp, 4),
            'fantamedia_attesa': round(fantamedia, 3),
            'punti_attesi': round(punti, 2),
            'metodo': metodo, 'affidabilita': round(affidabilita, 3),
        }


# Quanto pesa il consenso delle guide rispetto allo storico del giocatore.
# Alto per chi le guide nominano: sanno in quale squadra e in quale ruolo
# gioca **adesso**, che e' precisamente cio' che nessuna statistica del
# passato puo' sapere dopo un mercato.
#
# Il peso non e' uno solo, cresce con l'accordo fra le fonti, e la ragione si
# vede meglio su un caso vero. Josep Martinez ha giocato cinque partite in due
# stagioni, da secondo portiere; quest'anno tutte e quattro le guide lo danno
# titolare dell'Inter. Con un peso fisso a 0.65 il programma gli assegnava
# ventisei presenze: una media fra "gioca sempre" e "ha giocato cinque volte",
# che pero' non descrive nessuno dei due mondi possibili. Lo storico non ha
# **nessuna** informazione da aggiungere sul fatto che oggi sia il titolare:
# e' esattamente la cosa che non puo' sapere. Quando le fonti sono unanimi il
# loro numero deve prendersi tutto; quando si dividono, lo storico torna a
# contare, perche' li' l'incertezza e' vera.
# Non 1.0 nemmeno quando sono tutte d'accordo: un decimo resta allo storico,
# perche' anche le guide sbagliano e perche' chi si e' rotto tre volte in due
# anni ha buone probabilita' di rompersi ancora, e quello le guide di agosto
# non lo dicono. Un decimo non ribalta niente, ma tiene una differenza fra il
# titolare di ferro e il titolare di cristallo.
PESO_WEB = 0.65
PESO_WEB_UNANIME = 0.90


def _peso_web(accordo):
    """Da 0.65 (fonti divise a meta') a 0.90 (fonti tutte d'accordo)."""
    a = min(1.0, max(0.0, accordo if accordo is not None else 0.0))
    return PESO_WEB + (PESO_WEB_UNANIME - PESO_WEB) * a


def applica_consenso(con, righe):
    """Corregge le presenze attese con quello che dicono le guide di quest'anno.

    Le statistiche sanno quanto ha giocato uno l'anno scorso; le guide sanno
    se quest'anno e' titolare. Sono due informazioni diverse e servono
    entrambe: chi ha fatto trentaquattro presenze in una squadra e adesso ne
    ha davanti due nella nuova non ne fara' trentaquattro, e nessun modello
    statistico puo' accorgersene.

    La regola non e' simmetrica, ed e' voluto: **le guide possono abbassare
    chiunque, ma possono alzare solo chi nominano.** Il silenzio delle guide
    su un giocatore e' un indizio che non gioca, non una prova che giochi; e
    tirare su le presenze di un fondo-rosa solo perche' la media dei
    non-titolari e' tredici partite sarebbe il modo piu' rapido di rimettere
    in circolo proprio le trappole che si volevano evitare.

    E il peso delle guide **cresce con quanto sono d'accordo fra loro**: se
    tutte danno titolare uno che l'anno scorso ha fatto il secondo, lo storico
    non ha niente da dire e non deve trascinare giu' il numero. Se si dividono,
    torna a contare, perche' li' l'incertezza e' vera.

    Gli infortuni in corso sono gia' dentro `presenze_web`: le giornate che il
    giocatore salta da oggi al rientro stimato le conta il calendario.
    """
    try:
        web = dict((r['id'], dict(r)) for r in con.execute(
            'SELECT id, presenze_web, accordo, fonti, partite_saltate,'
            ' fuori_lista FROM gerarchie'))
    except Exception:
        return righe                      # database senza gerarchie: si tira dritto
    if not web:
        return righe

    for r in righe:
        g = web.get(r['id'])
        if not g:
            continue
        # **Fuori dalla lista di serie A non e' una presenza bassa: e' zero.**
        # Non si mescola con niente e non passa dai pesi: chi non e' iscritto
        # non puo' scendere in campo, e ogni numero che ne discende - punti,
        # gol, media - va azzerato con lui. Se la lista viene corretta in
        # corsa, si rifa' la raccolta e torna dentro.
        if g.get('fuori_lista'):
            r['fuori_lista'] = 1
            r['presenze_attese'] = 0.0
            r['minuti_attesi'] = 0.0
            r['punti_attesi'] = 0.0
            r['titolarita'] = 0.0
            for campo in ('gol_attesi', 'assist_attesi', 'amm_attese',
                          'esp_attese', 'gs_attesi', 'rp_attesi',
                          'imbattuto_attese'):
                r[campo] = 0.0
            continue
        if g['presenze_web'] is None:
            continue
        prima = r['presenze_attese'] or 0.0
        if prima <= 0:
            continue
        citato = (g['fonti'] or 0) > 0
        # Chi le guide non nominano non guadagna nulla dall'accordo: il peso
        # resta quello base, e comunque puo' solo scendere.
        peso = _peso_web(g['accordo']) if citato else PESO_WEB
        mescolata = peso * g['presenze_web'] + (1 - peso) * prima
        dopo = mescolata if citato else min(prima, mescolata)
        if abs(dopo - prima) < 0.05:
            continue
        k = max(0.0, dopo / prima)
        r['presenze_attese'] = round(dopo, 2)
        r['minuti_attesi'] = round((r['minuti_attesi'] or 0.0) * k, 1)
        # La fantamedia e' un tasso e non si tocca: cambia quante volte
        # scende in campo, non come rende quando ci scende.
        r['punti_attesi'] = round(r['presenze_attese']
                                  * (r['fantamedia_attesa'] or 0.0), 2)
        for campo in ('gol_attesi', 'assist_attesi', 'amm_attese', 'esp_attese',
                      'gs_attesi', 'rp_attesi', 'imbattuto_attese'):
            r[campo] = round((r[campo] or 0.0) * k, 3)
    return righe


def applica_gerarchia(con, righe):
    """Ridistribuisce i minuti dentro ogni reparto e ne annota la gerarchia.

    Le proiezioni individuali non si parlano fra loro: ognuna guarda lo storico
    del suo giocatore e non sa che nella sua squadra, in quel ruolo, ce ne sono
    altri nove a cui il modello ha promesso gli stessi minuti. Sommando reparto
    per reparto si scopre che a qualche squadra si stanno assegnando meta'
    stagione in piu' di quanta ne esista.

    Il taglio non cambia **come rende** un giocatore, solo **quanto gioca**:
    media voto e fantamedia restano intatte, scendono minuti, presenze e punti
    di stagione. E' esattamente la distinzione che serve a non farsi ingannare
    da una fantamedia alta prodotta da sette partite.
    """
    per_id = dict((r['id'], r) for r in righe)
    dati = []
    for r in con.execute("""SELECT g.id, g.squadra, g.ruolo,
                                   COALESCE(g.nuovo_acquisto, 0) nuovo,
                                   ge.titolarita, ge.accordo, ge.fonti,
                                   pa.prezzo_medio_per_1000 mercato
                            FROM giocatori g
                            LEFT JOIN gerarchie ge ON ge.id = g.id
                            LEFT JOIN prezzi_asta pa ON pa.id = g.id
                            WHERE g.attivo = 1"""):
        p = per_id.get(r['id'])
        if p is None:
            continue
        dati.append({'id': r['id'], 'squadra': r['squadra'], 'ruolo': r['ruolo'],
                     'minuti': p['minuti_attesi'] or 0.0,
                     'presenze': p['presenze_attese'] or 0.0,
                     'affidabilita': p['affidabilita'] or 0.0,
                     'mercato': r['mercato'] or 0.0,
                     'titolarita_web': r['titolarita'],
                     'accordo': r['accordo'], 'fonti_web': r['fonti'],
                     'nuovo': bool(r['nuovo'])})
    posizioni = titmod.calcola(dati)

    for r in righe:
        pos = posizioni.get(r['id'])
        if pos is None:
            r.update({'titolarita': None, 'posto_reparto': None,
                      'in_reparto': None, 'grado': None, 'certezza': None})
            continue
        prima = r['minuti_attesi'] or 0.0
        if prima > 0 and pos.minuti < prima - 1e-6:
            k = pos.minuti / prima
            r['minuti_attesi'] = round(pos.minuti, 1)
            r['presenze_attese'] = round(pos.presenze, 2)
            # La fantamedia e' un tasso: non si tocca. I punti di stagione
            # sono un volume, e seguono le presenze.
            r['punti_attesi'] = round(r['presenze_attese']
                                      * (r['fantamedia_attesa'] or 0.0), 2)
            for campo in ('gol_attesi', 'assist_attesi', 'amm_attese',
                          'esp_attese', 'gs_attesi', 'rp_attesi',
                          'imbattuto_attese'):
                r[campo] = round((r[campo] or 0.0) * k, 3)
        r['titolarita'] = round(pos.quota, 3)
        r['posto_reparto'] = pos.posto
        r['in_reparto'] = pos.in_reparto
        r['grado'] = pos.grado
        r['certezza'] = pos.certezza
    return righe


def salva(con, righe):
    con.execute('DELETE FROM proiezioni')
    campi = ['id', 'minuti_attesi', 'presenze_attese', 'mv_attesa', 'gol_attesi',
             'assist_attesi', 'amm_attese', 'esp_attese', 'gs_attesi', 'rp_attesi',
             'imbattuto_attese', 'bonus_per_partita', 'fantamedia_attesa',
             'punti_attesi', 'metodo', 'affidabilita',
             'titolarita', 'posto_reparto', 'in_reparto', 'grado', 'certezza',
             'fuori_lista']
    con.executemany(
        'INSERT INTO proiezioni (%s) VALUES (%s)' % (','.join(campi), ','.join('?' * len(campi))),
        [tuple(r.get(c) for c in campi) for r in righe])
    con.commit()


def esegui(con=None, reg=None):
    con = con or dbmod.connetti()
    reg = reg or regmod.carica()
    p = Proiettore(con, reg)
    # Prima quello che dicono le guide di quest'anno, poi il controllo che i
    # minuti di ogni reparto stiano dentro quelli che esistono. In quest'ordine:
    # la seconda correzione deve lavorare su numeri gia' aggiornati al mercato.
    righe = applica_gerarchia(con, applica_consenso(con, p.proietta_tutti()))
    salva(con, righe)
    return p.cal, righe


if __name__ == '__main__':
    con = dbmod.connetti()
    reg = regmod.carica()
    cal, righe = esegui(con, reg)

    print('Calibrazione dal database')
    print('  media voto di ruolo   : %s' % {k: round(v, 3) for k, v in cal.mv_ruolo.items()})
    print('  npxG/90 di ruolo      : %s' % {k: round(v, 4) for k, v in cal.npxg90.items()})
    print('  xA/90 di ruolo        : %s' % {k: round(v, 4) for k, v in cal.xa90.items()})
    print('  assist reali / xA     : %.3f' % cal.assist_su_xa)
    print('  rigori per squadra    : %.2f   conversione %.3f'
          % (cal.rigori_per_squadra, cal.conversione_rigori))
    print('  gol subiti/90 neoprom.: %.3f' % cal.gs90_neopromosse)

    n_imp = sum(1 for r in righe if r['metodo'] != 'storico')
    print('\nProiezioni: %d giocatori  (%d imputati da quotazione, %.1f%%)'
          % (len(righe), n_imp, 100.0 * n_imp / len(righe)))

    ruoli = dict((r['id'], r['ruolo']) for r in con.execute('SELECT id, ruolo FROM giocatori'))
    nomi = dict((r['id'], r['nome']) for r in con.execute('SELECT id, nome FROM giocatori'))
    sq = dict((r['id'], r['squadra']) for r in con.execute('SELECT id, squadra FROM giocatori'))
    for ruolo in RUOLI:
        top = sorted([r for r in righe if ruoli[r['id']] == ruolo],
                     key=lambda x: -x['punti_attesi'])[:8]
        print('\n  -- %s : primi 8 per punti attesi --' % ruolo)
        print('     %-20s %-11s %6s %6s %6s %6s %6s  %s'
              % ('nome', 'squadra', 'pres', 'mv', 'fm', 'punti', 'affid', 'metodo'))
        for r in top:
            print('     %-20s %-11s %6.1f %6.2f %6.2f %6.0f %6.2f  %s'
                  % (nomi[r['id']][:20], sq[r['id']][:11], r['presenze_attese'],
                     r['mv_attesa'], r['fantamedia_attesa'], r['punti_attesi'],
                     r['affidabilita'], r['metodo']))
    con.close()
