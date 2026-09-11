/* ==========================================================================
   FantaHacked — interfaccia

   Un solo stato locale (`S`), ridisegnato per intero a ogni cambiamento. In
   un'asta dal vivo gli aggiornamenti sono pochi (uno per giocatore venduto) e
   la correttezza conta molto piu' della finezza: ridisegnare tutto elimina in
   partenza la classe di bug in cui la schermata mostra crediti che non
   esistono piu'.
   Non esce da qui. Ogni `fetch` di questo file punta a `/api/...`, cioe' al
   server che gira sul computer di chi sta giocando; la pagina dichiara in
   `index.html` una politica dei contenuti che le vieta di caricare qualunque
   cosa da un'altra origine. L'unica cosa che viaggia in rete la scarica il
   programma, non questa pagina: i dati dei giocatori, una volta al giorno.
   ========================================================================== */

'use strict';

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

const RUOLI = ['P', 'D', 'C', 'A'];
const NOME_RUOLO = { P: 'Portieri', D: 'Difensori', C: 'Centrocampisti', A: 'Attaccanti' };
// Il singolare serve dove il numero e' uno: "in campo va 1 portiere",
// non "vanno 1 portieri". E' la prima riga del pannello, e una frase
// sgrammaticata li' fa sembrare approssimativo anche il conto sotto.
const NOME_SINGOLARE = { P: 'portiere', D: 'difensore',
                         C: 'centrocampista', A: 'attaccante' };

const S = {
  stato: null,        // riepilogo dal server
  scheda: null,       // giocatore attualmente sotto esame
  vista: 'rosa',      // colonna di destra
  filtroListone: null,
  soloTitolari: false, // listone: nasconde chi non gioca con certezza
  acquirente: null,   // presidente selezionato nel modulo di assegnazione
  evidenziato: -1,    // riga selezionata coi tasti nei risultati di ricerca
  risultati: [],
  rosaVista: null,    // presidente di cui si sta guardando la rosa
  turnoVisto: null,   // per accorgersi di quando passa a me
};

/* ------------------------------------------------------------------ rete */

/* Due famiglie di errori, che vanno dette all'utente in due modi diversi.
 *
 *   - il motore risponde e dice di no  ->  e' un messaggio, si mostra dov'e'
 *     stata fatta l'azione ("slot gia' pieni", "prezzo minimo 1");
 *   - il motore non risponde affatto   ->  il programma non e' piu' in
 *     esecuzione, e l'unica cosa sensata e' dirlo e riagganciarsi da soli.
 *
 * `fetch` per il secondo caso lancia un TypeError con scritto "Failed to
 * fetch", che a schermo non vuol dire niente per chi sta facendo un'asta. */
class ErroreCollegamento extends Error {}

async function api(percorso, opzioni) {
  let r;
  try {
    r = await fetch(percorso, opzioni);
  } catch (e) {
    perdutoIlCollegamento();
    throw new ErroreCollegamento('Il programma non risponde più.');
  }
  let dati = null;
  try { dati = await r.json(); } catch (e) { /* corpo vuoto */ }
  if (!r.ok) throw new Error((dati && dati.errore) || ('errore ' + r.status));
  collegamentoVivo();
  return dati;
}

const get  = (p) => api(p);
const post = (p, corpo) => api(p, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(corpo || {}),
});

/* ------------------------------------------------- collegamento al motore */

let timerRiaggancio = null;

function perdutoIlCollegamento() {
  if ($('#disconnesso').hidden === false) return;
  $('#disconnesso').hidden = false;
  $('#spia').className = 'spia rotta';
  if (!timerRiaggancio) timerRiaggancio = setInterval(riprovaCollegamento, 2000);
}

function collegamentoVivo() {
  if ($('#disconnesso').hidden) return;
  $('#disconnesso').hidden = true;
  $('#spia').className = 'spia';
  clearInterval(timerRiaggancio);
  timerRiaggancio = null;
}

async function riprovaCollegamento() {
  try {
    const r = await fetch('/api/ping', { cache: 'no-store' });
    if (!r.ok) return;
  } catch (e) { return; }
  // Il motore e' tornato: si rilegge lo stato dal database, che e' la
  // sorgente di verita', e si ridisegna. I nomi eventualmente gia' scritti
  // nella schermata iniziale restano dove sono.
  clearInterval(timerRiaggancio);
  timerRiaggancio = null;
  try {
    const st = await get('/api/stato');
    if (!interfacciaAvviata) {
      // Il motore non c'era gia' al primo caricamento: qui si monta ora.
      avviaInterfaccia(st);
    } else {
      S.stato = st;
      if (st.iniziata && !$('#app').hidden) disegna();
    }
  } catch (e) { return; }
  $('#disconnesso').hidden = true;
  $('#spia').className = 'spia';
  brindisi('Collegamento ripristinato.');
}

/* --------------------------------------------------------------- utilita' */

const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

let timerBrindisi = null;
function brindisi(testo, male) {
  const b = $('#brindisi');
  b.textContent = testo;
  b.className = 'brindisi' + (male ? ' male' : '');
  b.hidden = false;
  clearTimeout(timerBrindisi);
  timerBrindisi = setTimeout(() => { b.hidden = true; }, male ? 5200 : 2800);
}

const tag = (r) => `<span class="tag-ruolo ${r}">${r}</span>`;

/* Il grado di titolarita'. E' l'informazione che separa un'alternativa vera
 * da una trappola: una fantamedia alta su otto presenze non vale niente, e
 * senza questa etichetta le due cose sullo schermo si somigliano. */
const ETICHETTA_GRADO = {
  titolare: 'Titolare', ballottaggio: 'Ballottaggio',
  rotazione: 'Rotazione', riserva: 'Riserva', ignoto: '?',
};

const SPIEGA_GRADO = {
  titolare: 'Gioca quasi sempre.',
  ballottaggio: "Si gioca il posto: le presenze non sono garantite.",
  rotazione: 'Entra a rotazione: poche presenze.',
  riserva: 'Riserva: in campo lo vedi poco.',
};

/* Chi non e' iscritto alla lista di serie A non puo' giocare: e' l'unico
   cartellino che conta piu' di qualunque statistica accanto, e va visto senza
   dover aprire la scheda. */
function fuoriLista(d) {
  return d && d.fuori_lista
    ? '<span class="cartellino fuori-lista" title="Non &egrave; iscritto alla lista di serie A: non pu&ograve; scendere in campo">FUORI LISTA</span>'
    : '';
}

function grado(g, compatto) {
  if (!g || !g.grado || g.grado === 'ignoto') return '';
  const dubbio = g.grado === 'titolare' && !g.sicuro ? ' incerto' : '';
  const testo = compatto && g.grado === 'ballottaggio' ? 'Ballott.'
    : (ETICHETTA_GRADO[g.grado] || g.grado);
  const spiega = g.testo || SPIEGA_GRADO[g.grado] || '';
  return `<span class="grado ${esc(g.grado)}${dubbio}"
    title="${esc(spiega)}${dubbio ? ' Il punto interrogativo vuol dire che il posto non e\' saldo.' : ''}">${esc(testo)}${
      dubbio ? '?' : ''}</span>`;
}

/* Ha comprato sopra o sotto quello che quei giocatori valgono. Due presidenti
 * con gli stessi crediti residui non sono nella stessa posizione se uno ha in
 * rosa centoventi crediti di roba e l'altro centottanta: e' la differenza fra
 * chi sta facendo affari e chi si sta rovinando l'asta senza accorgersene. */
const SEGNO_BILANCIO = { positivo: 'in positivo', negativo: 'in negativo',
                         pari: 'in pari', niente: '' };
const SEGNO_MIO = { positivo: 'dentro i tuoi limiti',
                    negativo: 'sopra i tuoi limiti',
                    pari: 'sui tuoi limiti', niente: '' };

function bilancioBlocco(b) {
  if (!b || b.verso === 'niente') return '';
  const s = b.scarto;
  // Sulla mia rosa la cifra grande e' il margine sui limiti, non lo scarto dal
  // mercato: e' quella che risponde a "ho sbagliato qualcosa?".
  const mio = b.margine != null;
  const cifra = mio ? b.margine : -s;
  return `
    <div class="bilancio ${b.verso}">
      <div class="bilancio-testa">
        <span class="bilancio-verso">${
          (mio ? SEGNO_MIO : SEGNO_BILANCIO)[b.verso]}</span>
        <span class="bilancio-cifra">${cifra > 0 ? '+' : ''}${cifra}</span>
      </div>
      <div class="bilancio-barre">
        <span>speso <b>${b.speso}</b></span>
        ${mio ? `<span>i tuoi limiti <b>${b.limiti}</b></span>` : ''}
        <span>vale sul mercato <b>${b.atteso}</b></span>
      </div>
      <p class="nota piccola">${esc(b.testo)}</p>
    </div>`;
}

/* Sui MIEI acquisti il metro giusto non e' il mercato ma il limite che il
 * motore dava quando l'ho chiamato. Un giocatore fuori scala vale, per una rosa
 * che se lo puo' permettere, molto piu' di quanto la stanza media paghi quel
 * ruolo: il motore puo' dire "fino a 144" su uno che chiude a 63, e pagarlo 100
 * e' un ottimo affare pur essendo 37 sopra il prezzo di mercato. Segnarlo in
 * rosso sarebbe dargli dell'errore quando errore non e'. */
function scartoMio(x) {
  if (x.oltre_limite == null || !x.limite) return scarto(x);
  const sopra = x.oltre_limite > 0;
  const quanto = Math.abs(x.oltre_limite);
  return `<span class="scarto ${sopra ? 'sopra' : 'sotto'}"
    title="Il motore dava fino a ${x.limite} quando l'hai chiamato, e l'hai pagato ${x.prezzo}: ${
      sopra ? `${quanto} sopra il tuo limite` : `${quanto} sotto il tuo limite`}. Sul mercato ne sarebbe costati ${x.atteso}."
    >${sopra ? '+' : '−'}${quanto}</span>`;
}

/* Lo scarto sul singolo acquisto: quanto ha pagato in piu' o in meno di quanto
 * quel giocatore sarebbe costato in una stanza normale. E' il metro con cui si
 * guardano gli AVVERSARI, perche' del loro limite personale non so niente. */
function scarto(x) {
  if (x.scarto == null || !x.atteso) return '';
  if (Math.abs(x.scarto) < 2) return '<span class="scarto pari">=</span>';
  const su = x.scarto > 0;
  return `<span class="scarto ${su ? 'sopra' : 'sotto'}"
    title="Prezzo atteso ${x.atteso}: ${su ? 'pagato' : 'preso'} ${Math.abs(x.scarto)} crediti ${su ? 'in piu' : 'in meno'}"
    >${su ? '+' : ''}${x.scarto}</span>`;
}

const rigore = (g) => (g && g.rigorista === 1)
  ? '<span class="rigorista" title="Rigorista designato">R</span>' : '';

/* ============================================================== AVVIO */

/* I nomi delle squadre restano nel browser mentre si scrivono, cosi' ricaricare
 * la pagina non li perde. Ma la memoria vera e' quella del programma: il
 * browser lega quello che salva all'indirizzo, e l'indirizzo cambia porta a
 * ogni avvio se quella di prima e' occupata &mdash; per lui e' un altro sito, e
 * i nomi sparivano senza che si capisse perche'. Quelli che arrivano dal
 * server hanno la precedenza. */
const CHIAVE_NOMI = 'fantahacked.nomi';

function ricordaNomi() {
  try {
    localStorage.setItem(CHIAVE_NOMI,
      JSON.stringify($$('#form-nuova input').map((c) => c.value)));
  } catch (e) { /* navigazione privata: si fa senza */ }
}

function nomiRicordati() {
  try { return JSON.parse(localStorage.getItem(CHIAVE_NOMI)) || []; }
  catch (e) { return []; }
}

/* ---------------------------------------------------- il regolamento

 * Quattro cose si scelgono da qui, e nessuna delle quattro e' cosmetica.
 * Quante squadre siamo decide **quanti giocatori verranno assegnati**, cioe'
 * il livello di rimpiazzo, cioe' quanto vale ogni giocatore; quanti crediti
 * abbiamo decide la scala dei prezzi; il modificatore sposta il valore fra
 * reparti; e i portieri a pacchetto cambiano il reparto in una scelta sola.
 * Il motore rifa' i conti dall'inizio a ogni cambiamento, sui dati aggiornati.
 *
 * I comandi stanno nell'HTML e non vengono mai ridisegnati: un `innerHTML` a
 * ogni modifica toglierebbe il fuoco dal campo mentre lo si sta usando, e con
 * le frecce di un campo numerico si perderebbe al primo clic. Qui si
 * riscrivono solo i valori. */

function aggiornaImpostazioni(stato) {
  const imp = stato.impostazioni;
  const sq = $('#reg-squadre'), cr = $('#reg-crediti'), md = $('#reg-mod');
  sq.min = imp.min_partecipanti; sq.max = imp.max_partecipanti;
  cr.min = imp.min_crediti;      cr.max = imp.max_crediti;
  sq.value = imp.partecipanti;
  cr.value = imp.crediti;
  md.checked = imp.modificatore;
  $('#reg-mod-testo').textContent = imp.modificatore ? 'attivo' : 'spento';
  $('#reg-mod').closest('.leva').classList.toggle('accesa', imp.modificatore);
  $('#reg-mod-nota').textContent = imp.modificatore
    ? 'Modificatore difesa · ' + imp.mod_componenti
    : 'Modificatore difesa';

  const pac = $('#reg-pacchetto');
  pac.checked = imp.pacchetto;
  $('#reg-pacchetto-testo').textContent = imp.pacchetto ? 'sì' : 'no';
  pac.closest('.leva').classList.toggle('accesa', imp.pacchetto);
  // Non e' una comodita' di registrazione: cambia il reparto. A pacchetto i
  // portieri sono **otto scelte su venti squadre**, e chi prende il titolare
  // ha chiuso il reparto; senza, sono ventiquattro giocatori da comprare uno
  // per uno, e il secondo portiere e' una decisione vera. Il motore conta i
  // due casi in modo diverso, quindi va detto cosa si sta scegliendo.
  $('#reg-pacchetto-nota').innerHTML = imp.pacchetto
    ? `Chi si aggiudica il portiere titolare di una squadra di serie A prende
       anche il secondo e il terzo <b>a 1 credito</b>: il programma li registra
       da solo. Il reparto diventa una chiamata sola, non tre.`
    : `Ogni portiere si compra per conto suo, come gli altri ruoli: il
       programma non assegna niente in automatico e i ${imp.slot.P} portieri
       sono ${imp.slot.P} scelte separate.`;
  $('#reg-rosa').textContent =
    `${imp.slot.P}-${imp.slot.D}-${imp.slot.C}-${imp.slot.A}`;
  $('#reg-monte').textContent = imp.crediti_totali;
  $('#titolo-squadre').textContent = 'Le ' + PAROLA_NUMERO(imp.partecipanti) + ' squadre';

  // Un'asta gia' cominciata si gioca con le regole con cui e' cominciata.
  // Se i numeri qui sopra non sono piu' quelli, bisogna dirlo: altrimenti si
  // cambia il budget, si preme "Riprendi", e si passa la serata a leggere
  // prezzi calcolati su un'altra lega.
  const avviso = $('#avvio-avviso');
  avviso.hidden = !imp.diverse_dall_asta;
  if (imp.diverse_dall_asta) {
    const in_corso = stato.regole;
    avviso.innerHTML = `L&rsquo;asta gi&agrave; in corso continua con le sue regole
      (${in_corso.partecipanti} squadre, ${in_corso.crediti} crediti,
      modificatore ${in_corso.modificatore ? 'attivo' : 'spento'}, portieri
      ${in_corso.portieri_pacchetto ? 'a pacchetto' : 'uno per uno'}).
      Questi numeri valgono per la <b>prossima</b>: premi <b>Nuova asta</b> per usarli.`;
  }
}

const PAROLA_NUMERO = (n) => ({
  2: 'due', 3: 'tre', 4: 'quattro', 5: 'cinque', 6: 'sei', 7: 'sette',
  8: 'otto', 9: 'nove', 10: 'dieci', 11: 'undici', 12: 'dodici',
  13: 'tredici', 14: 'quattordici', 15: 'quindici', 16: 'sedici',
  17: 'diciassette', 18: 'diciotto', 19: 'diciannove', 20: 'venti',
}[n] || n);

/* I nomi gia' scritti a mano non si perdono quando cambia il numero di
 * squadre: si passano di mano al ridisegno. Quelli che arrivano dal server
 * riempiono solo le caselle nuove. */
function disegnaNomiSquadre(stato, correnti) {
  const n = stato.impostazioni.partecipanti;
  const dalServer = stato.nomi_predefiniti || [];
  const salvati = nomiRicordati();
  const form = $('#form-nuova');
  form.classList.toggle('fitta', n > 12);
  form.innerHTML = Array.from({ length: n }, (_, i) => `
    <div class="campo${i === 0 ? ' mio' : ''}">
      <label for="sq${i}">${i === 0 ? 'La tua squadra' : 'Avversario ' + i}</label>
      <input id="sq${i}" type="text" maxlength="24"
             placeholder="${i === 0 ? 'Il tuo nome' : 'Squadra ' + i}">
    </div>`).join('');
  $$('#form-nuova input').forEach((c, i) => {
    const valore = (correnti && correnti[i]) || dalServer[i] || salvati[i];
    if (valore) c.value = valore;
    c.addEventListener('input', ricordaNomi);
  });
  ricordaNomi();
}

function mostraAvvio(stato) {
  aggiornaImpostazioni(stato);
  disegnaNomiSquadre(stato);
  $('#btn-riprendi').hidden = !stato.iniziata;
  $('#avvio').hidden = false;
  $('#app').hidden = true;
  setTimeout(() => $('#sq0').focus(), 60);
}

/* Salvataggio del regolamento. Il server puo' correggere quello che arriva
 * (venti squadre e' il massimo, i crediti non possono stare sotto il numero di
 * slot): la risposta e' la verita', e i campi si riallineano a lei. */
let salvandoRegole = null;

async function salvaRegole() {
  const err = $('#avvio-errore');
  const corpo = {
    partecipanti: parseInt($('#reg-squadre').value, 10),
    crediti: parseInt($('#reg-crediti').value, 10),
    modificatore: $('#reg-mod').checked,
    pacchetto: $('#reg-pacchetto').checked,
  };
  if (!Number.isFinite(corpo.partecipanti) || !Number.isFinite(corpo.crediti)) {
    return;                       // campo svuotato a meta' digitazione
  }
  const correnti = $$('#form-nuova input').map((c) => c.value);
  $('#avvio-regole').classList.add('in-corso');
  try {
    salvandoRegole = post('/api/regole', corpo);
    S.stato = await salvandoRegole;
    err.hidden = true;
    aggiornaImpostazioni(S.stato);
    disegnaNomiSquadre(S.stato, correnti);
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
    // Il valore rifiutato non puo' restare li' a farsi credere: accanto al
    // motivo del rifiuto tornano i numeri che valgono davvero.
    if (S.stato && S.stato.impostazioni) aggiornaImpostazioni(S.stato);
  } finally {
    salvandoRegole = null;
    $('#avvio-regole').classList.remove('in-corso');
  }
}

async function nuovaAsta() {
  // Cliccando "Nuova asta" con il cursore ancora dentro i crediti, il campo
  // perde il fuoco e parte il salvataggio del regolamento: l'asta deve nascere
  // **dopo** che quel salvataggio e' finito, o nascerebbe con i numeri vecchi.
  if (salvandoRegole) { try { await salvandoRegole; } catch (e) { /* gia' detto */ } }
  const campi = $$('#form-nuova input');
  const nomi = campi.map((c, i) => c.value.trim() || (i === 0 ? 'Io' : 'Squadra ' + i));
  const err = $('#avvio-errore');
  const doppioni = nomi.filter((x, i) => nomi.indexOf(x) !== i);
  if (doppioni.length) {
    err.textContent = 'Ci sono due squadre con lo stesso nome: ' + doppioni[0];
    err.hidden = false;
    return;
  }
  err.hidden = true;
  $('#btn-nuova').disabled = true;
  try {
    S.stato = await post('/api/nuova', { mio_nome: nomi[0], avversari: nomi.slice(1) });
    $('#avvio').hidden = true;
    $('#app').hidden = false;
    disegna();
    $('#cerca').focus();
  } catch (e) {
    err.textContent = e.message; err.hidden = false;
  } finally {
    $('#btn-nuova').disabled = false;
  }
}

/* ============================================================ DISEGNO */

function disegna() {
  const st = S.stato;
  if (!st || !st.iniziata) return;

  // ---- barra superiore
  $('#fase-nome').textContent = st.fase_nome;
  $('#fase-residui').textContent = st.fase
    ? `${st.mercato.residui_ruolo[st.fase]} ancora da assegnare`
    : '';

  const turno = st.presidenti.find((p) => p.id === st.turno);
  $('#turno-nome').textContent = turno ? turno.nome : '—';
  $('.turno').classList.toggle('mio', !!(turno && turno.io));

  S.turnoVisto = st.turno;

  $('#m-lega').textContent = st.mercato.crediti_lega;
  const infl = st.mercato.inflazione;
  $('#m-inflazione').textContent = infl > 1.03 ? `prezzi in salita ×${infl.toFixed(2)}`
    : infl < 0.97 ? `si compra a sconto ×${infl.toFixed(2)}` : 'in linea';
  $('#m-miei').textContent = st.io.crediti;
  $('#m-slot').textContent = `${st.io.slot_residui} slot • max ${st.io.liquidita}`;

  disegnaSquadre();
  disegnaDestra();
}

function disegnaSquadre() {
  const st = S.stato;
  $('#squadre').innerHTML = st.presidenti.map((p) => {
    const quota = Math.max(0, Math.min(1, p.crediti / st.regole.crediti));
    const pallini = RUOLI.map((r) => {
      const tot = st.regole.slot[r], usati = p.slot[r];
      const p_ = Array.from({ length: tot }, (_, i) =>
        `<i class="pallino${i < usati ? ' pieno' : ''}"></i>`).join('');
      return `<span class="gruppo-pallini"><b>${r}</b>${p_}</span>`;
    }).join('');
    return `
      <div class="squadra${p.io ? ' io' : ''}${p.id === st.turno ? ' turno' : ''}${
        st.fase && !p.attivo_nel_ruolo ? ' esclusa' : ''}"
           data-presidente="${p.id}"
           title="${esc(p.nome)} — può offrire fino a ${p.liquidita}">
        <div class="squadra-testa">
          <span class="squadra-nome">${esc(p.nome)}${
            p.id === st.turno ? '<span class="badge-turno">chiama</span>' : ''}</span>
          <button class="occhio" data-rosa="${p.id}"
                  title="Apri la rosa di ${esc(p.nome)} per vederla o correggerla">rosa</button>
          ${p.bilancio && p.bilancio.verso !== 'niente' && p.bilancio.verso !== 'pari'
            ? `<span class="scarto ${p.bilancio.verso === 'negativo' ? 'sopra' : 'sotto'}"
                     title="${esc(p.bilancio.testo)}"
               >${(() => {
                 // Sulla mia riga il numero e' il margine sui limiti; su quella
                 // degli altri lo scarto dal mercato, che e' l'unico che ho.
                 const n = p.bilancio.margine != null
                   ? p.bilancio.margine : -p.bilancio.scarto;
                 return (n > 0 ? '+' : '') + n;
               })()}</span>` : ''}
          <span class="squadra-crediti">${p.crediti}</span>
        </div>
        <div class="squadra-barra"><i style="width:${(quota * 100).toFixed(1)}%"></i></div>
        <div class="pallini">${pallini}</div>
      </div>`;
  }).join('');
}

/* ------------------------------------------------------ colonna destra */

function disegnaDestra() {
  $$('.scheda-tab').forEach((b) => b.classList.toggle('attiva', b.dataset.vista === S.vista));
  $('#vista-rosa').hidden = S.vista !== 'rosa';
  $('#vista-listone').hidden = S.vista !== 'listone';
  $('#vista-avversario').hidden = S.vista !== 'avversario';
  if (S.vista === 'rosa') disegnaRosa();
  if (S.vista === 'listone') caricaListone();
  if (S.vista === 'avversario') caricaRosaAvversario();
  // I consigli non sono piu' una scheda fra le altre: stanno al centro e si
  // ricalcolano sempre, perche' sono la cosa che si guarda quando non si sta
  // guardando nient'altro.
  caricaConsiglio();
}

/* I pannelli si ricalcolano sul server e arrivano quando arrivano. Se nel
 * frattempo l'asta e' andata avanti, la risposta vecchia non deve poter
 * sovrascrivere quella nuova: ogni richiesta si porta dietro il proprio
 * numero, e vince solo l'ultima.
 *
 * **Il numero e' per pannello, non uno solo per tutti.** Con un contatore
 * unico bastava che partissero due richieste diverse perche' la seconda
 * annullasse la prima: da quando i consigli si ricalcolano a ogni ridisegno,
 * aprire il listone lo lasciava **bianco** &mdash; la sua risposta arrivava
 * gia' scaduta, invalidata da una richiesta che riguardava un altro pannello.
 * La domanda giusta non e' "e' la richiesta piu' recente", e' "e' la piu'
 * recente **per questo pannello**". */
const nRichiesta = {};
function apriRichiesta(pannello) {
  nRichiesta[pannello] = (nRichiesta[pannello] || 0) + 1;
  return { pannello: pannello, n: nRichiesta[pannello] };
}
const ancoraValida = (t) => nRichiesta[t.pannello] === t.n;

async function caricaRosaAvversario() {
  const box = $('#vista-avversario');
  const p = S.stato.presidenti.find((x) => x.id === S.rosaVista);
  if (!p) { S.vista = 'rosa'; disegnaDestra(); return; }
  let rosa;
  try { rosa = await get('/api/rosa?presidente=' + p.id); }
  catch (e) { box.innerHTML = `<div class="errore">${esc(e.message)}</div>`; return; }
  const reparti = RUOLI.map((r) => {
    const presi = rosa[r] || [];
    const spesa = presi.reduce((a, x) => a + x.prezzo, 0);
    return `
      <div class="reparto ${r}">
        <div class="reparto-testa">
          <span class="reparto-nome">${NOME_RUOLO[r]}</span>
          <span class="reparto-conta">${presi.length}/${S.stato.regole.slot[r]} · ${spesa} cr</span>
        </div>
        ${presi.length ? presi.map((x) => `
          <div class="giocatore-riga">
            <span class="cresce">${esc(x.nome)}
              ${grado({ grado: x.grado, sicuro: x.sicuro }, true)}${rigore(x)}</span>
            ${scarto(x)}<span class="prezzo">${x.prezzo}</span>
            <button class="togli" data-annulla="${x.id}"
                    title="Annulla questo acquisto">&times;</button>
          </div>`).join('')
        : '<p class="nota piccola">Ancora niente.</p>'}
      </div>`;
  }).join('');
  box.innerHTML = `
    <button class="torna" data-vista="rosa">&larr; torna alla tua rosa</button>
    <p class="nota piccola" style="margin-bottom:8px">Se hai sbagliato a
       registrare un acquisto di ${esc(p.nome)}, toglilo con la crocetta e
       rifallo: tutti i prezzi si ricalcolano da soli.</p>
    <div class="riquadro">
      <div class="riquadro-titolo">Rosa di ${esc(p.nome)}</div>
      <div class="riga-lista"><span class="cresce">Crediti liberi</span>
        <span class="cifra">${p.crediti}</span></div>
      <div class="riga-lista"><span class="cresce">Offerta massima possibile</span>
        <span class="cifra">${p.liquidita}</span></div>
      <div class="riga-lista"><span class="cresce">Slot da riempire</span>
        <span class="cifra">${p.residui}</span></div>
    </div>
    ${bilancioBlocco(rosa.bilancio)}
    <p class="nota piccola" style="margin:-2px 0 10px">Il <b>+n</b> rosso accanto
       a un acquisto &egrave; quanto ha pagato in pi&ugrave; del prezzo atteso;
       il <b>&minus;n</b> verde quanto ha risparmiato. Il prezzo atteso &egrave;
       quello calibrato sulla spesa reale per reparto, non il valore a punti.</p>
    ${reparti}`;
}

function disegnaRosa() {
  const st = S.stato, io = st.io;
  const reparti = RUOLI.map((r) => {
    const presi = io.rosa[r] || [];
    const totale = st.regole.slot[r];
    const spesa = presi.reduce((a, x) => a + x.prezzo, 0);
    const righe = presi.map((x) => `
      <div class="giocatore-riga">
        <span class="cresce" title="${esc(x.squadra)} — fantamedia attesa ${x.fm} su ${x.presenze} presenze">${esc(x.nome)}
          ${grado({ grado: x.grado, sicuro: x.sicuro }, true)}${rigore(x)}</span>
        ${scartoMio(x)}<span class="prezzo">${x.prezzo}</span>
        <button class="togli" data-annulla="${x.id}" title="Annulla questo acquisto">&times;</button>
      </div>`).join('');
    const vuoti = Array.from({ length: totale - presi.length }, () =>
      '<div class="giocatore-riga"><span class="cresce vuoto-slot">— libero —</span></div>').join('');
    const nota = (r === 'P' && st.regole.portieri_pacchetto && presi.length > 1)
      ? `<p class="nota piccola">Le riserve arrivate col titolare si possono
           togliere con la crocetta e sostituire con un altro portiere, al
           prezzo che decidi tu: cercalo e registralo come una chiamata
           normale.</p>` : '';
    return `
      <div class="reparto ${r}">
        <div class="reparto-testa">
          <span class="reparto-nome">${NOME_RUOLO[r]}</span>
          <span class="reparto-conta">${presi.length}/${totale} · ${spesa} cr</span>
        </div>
        ${righe}${vuoti}${nota}
      </div>`;
  }).join('');

  const mod = st.regole.modificatore ? `
    <div class="riquadro">
      <div class="riquadro-titolo">Modificatore di difesa</div>
      <div class="riga-lista">
        <span class="cresce">Media attesa (${esc(st.regole.mod_componenti)})</span>
        <span class="cifra">${io.media_difesa.toFixed(2)}</span>
      </div>
      <div class="riga-lista">
        <span class="cresce">Bonus atteso a giornata</span>
        <span class="cifra">+${io.bonus_modificatore.toFixed(2)}</span>
      </div>
      <p class="nota piccola">Gli slot di difesa non ancora comprati contano al
         livello medio di mercato: il numero si aggiorna man mano che li riempi.</p>
    </div>` : '';

  $('#vista-rosa').innerHTML = `
    <div class="riquadro">
      <div class="riquadro-titolo">Budget</div>
      <div class="riga-lista"><span class="cresce">Crediti liberi</span>
        <span class="cifra">${io.crediti}</span></div>
      <div class="riga-lista"><span class="cresce">Offerta massima possibile</span>
        <span class="cifra">${io.liquidita}</span></div>
      <div class="riga-lista"><span class="cresce">Slot da riempire</span>
        <span class="cifra">${io.slot_residui}</span></div>
      <div id="piano"></div>
    </div>
    ${bilancioBlocco(io.rosa.bilancio)}
    <details class="spiega"><summary>come si legge</summary>
      <div class="spiega-corpo">Il numero accanto a ogni acquisto &egrave;
        quanto sei stato <b>sotto o sopra il limite che il motore ti dava in
        quel momento</b>, non il prezzo di mercato: su un giocatore fuori
        scala i due numeri non coincidono, e l&rsquo;unico che dice se hai
        sbagliato &egrave; il primo.</div></details>
    <div id="equilibrio"></div>
    ${mod}
    ${reparti}
    <div class="riquadro">
      <div class="riquadro-titolo">Ultimi assegnati</div>
      <p class="nota piccola" style="margin-bottom:6px">Sbagliato a registrare?
         Togli l'acquisto con la crocetta, di chiunque sia.</p>
      ${st.ultimi.length ? st.ultimi.map((u) => `
        <div class="riga-lista">
          <span class="cresce">${tag(u.ruolo)} ${esc(u.nome)}</span>
          <span class="fioco">${esc(u.presidente)}</span>
          <span class="cifra">${u.prezzo}</span>
          <button class="togli" data-annulla="${u.id}"
                  title="Annulla questo acquisto">&times;</button>
        </div>`).join('') : '<p class="nota piccola">Nessuno, per ora.</p>'}
    </div>`;
  caricaPiano();
  caricaEquilibrio();
}

/* Che squadra sto costruendo. Si ricalcola a ogni acquisto, mio o altrui:
 * quando un avversario porta via un difensore cambia chi resta sul mercato,
 * e quindi cambia cosa mi manca. */
/* Quante giornate rischi di restare in dieci. E' l'unico numero del pannello
 * che non dice quanto la rosa rende, ma quante volte riesci a metterla in
 * campo: una fantamedia alta prodotta da cinque presenze in rosa c'e', in
 * campo no, e la differenza si vede solo a dicembre se nessuno la misura. */
function rischioBlocco(r) {
  if (!r) return '';
  const q = r.quota;
  const classe = q >= 0.16 ? 'stop' : q >= 0.08 ? 'attenzione' : 'ok';
  const NOME_STRETTO = { P: 'in porta', D: 'in difesa',
                         C: 'a centrocampo', A: 'in attacco' };
  const stretto = r.reparto_stretto && r.reparto_stretto.ruolo;
  return `
    <div class="riquadro">
      <div class="riquadro-titolo">Rischio di restare in dieci</div>
      <div class="riga-lista">
        <span class="cresce">Giornate in cui non schieri undici</span>
        <span class="cifra ${classe}">${r.giornate}<span class="fioco"> su 38</span></span>
      </div>
      <div class="riga-lista">
        <span class="cresce">Disponibili a giornata</span>
        <span class="fioco">${RUOLI.map((x) =>
          `${x} ${r.disponibili[x]}`).join(' · ')}</span>
      </div>
      <p class="nota piccola">Conta anche gli slot che ti restano, riempiti con
         giocatori normali del reparto: risponde a <b>se completi la rosa
         cos&igrave; come stai andando</b>, non a &ldquo;se l&rsquo;asta finisse
         adesso&rdquo;. I portieri della stessa squadra contano per uno: quella
         maglia prende voto comunque.${stretto
           ? ` Oggi il reparto pi&ugrave; stretto &egrave; quello
               <b>${NOME_STRETTO[stretto]}</b>.` : ''}</p>
    </div>`;
}

async function caricaEquilibrio() {
  const box = $('#equilibrio');
  if (!box) return;
  try {
    const q = await get('/api/equilibrio');
    const u = q.undici;
    const campo = RUOLI.map((r) => {
      const voci = u.giocatori.filter((g) => g.ruolo === r);
      if (!voci.length) return '';
      return `<div class="linea">
        ${voci.map((g) => g.vuoto
          ? '<span class="maglia vuota">—</span>'
          : `<span class="maglia ${g.grado}" title="${esc(g.nome)} (${esc(g.squadra)}) — fantamedia ${g.fm} su ${g.presenze} presenze">
               ${esc(g.nome)}<b>${g.fm.toFixed(2)}</b></span>`).join('')}
      </div>`;
    }).join('');

    const copertura = RUOLI.map((r) => {
      const c = q.copertura[r];
      return `<div class="riga-lista">
        <span class="cresce">${tag(r)} ${NOME_RUOLO[r]}</span>
        <span class="fioco">${c.in_rosa}/${c.slot} in rosa</span>
        <span class="cifra ${c.scoperte ? 'attenzione' : 'ok'}"
              title="Titolari sicuri fra quelli che schiereresti">
          ${Math.min(c.titolari_sicuri, c.nell_undici)}/${c.nell_undici}</span>
      </div>`;
    }).join('');

    box.innerHTML = `
      <div class="riquadro">
        <div class="riquadro-titolo">La squadra che stai costruendo</div>
        <div class="undici-testa">
          <span class="modulo">${esc(u.modulo)}</span>
          <span class="cresce nota piccola">${u.caselle_vuote
            ? `${u.caselle_vuote} caselle ancora da riempire`
            : 'undici completo'}</span>
          <span class="cifra grande">${u.punti_giornata}</span>
        </div>
        <p class="nota piccola" style="margin:-4px 0 8px">Fantamedie
           dell&rsquo;undici migliore che riesci a schierare${
           u.bonus_difesa ? `, col modificatore (+${u.bonus_difesa})` : ''}.</p>
        <div class="formazione">${campo}</div>
      </div>
      ${rischioBlocco(q.rischio)}
      <div class="riquadro">
        <div class="riquadro-titolo">Caselle coperte da un titolare sicuro</div>
        ${copertura}
        <div class="riga-lista"><span class="cresce">Rigoristi in rosa</span>
          <span class="cifra ${q.rigoristi.length ? 'ok' : ''}">${q.rigoristi.length}</span></div>
        ${q.rigoristi.length ? `<p class="nota piccola">${
          q.rigoristi.map((g) => esc(g.nome)).join(', ')}</p>` : ''}
        ${q.concentrazione.length && q.concentrazione[0].quanti > 2
          ? `<p class="nota piccola">Pi&ugrave; presenti: ${q.concentrazione
              .map((c) => `${esc(c.squadra)} ${c.quanti}`).join(' · ')}</p>` : ''}
      </div>
      ${q.avvisi.map((a) => `<div class="avviso">${esc(a.testo)}</div>`).join('')}`;
  } catch (e) {
    box.innerHTML = '';
  }
}

async function caricaPiano() {
  const box = $('#piano');
  if (!box) return;
  try {
    const p = await get('/api/piano');
    const tot = Math.max(1, p.crediti);
    const barre = RUOLI.map((r) => {
      const c = (p.per_ruolo[r] || {}).crediti || 0;
      return `<i class="${r}" style="width:${(100 * c / tot).toFixed(1)}%"></i>`;
    }).join('');
    const leg = RUOLI.map((r) => {
      const d = p.per_ruolo[r] || {};
      const ris = (p.riserva || {})[r] || 0;
      return `<span title="${ris ? ris + ' crediti accantonati per questo reparto' : ''}">
                <b>${r}</b> ${d.crediti || 0}<span style="opacity:.6">/${d.slot || 0}</span>${
                ris ? '<span style="opacity:.55"> &middot; min ' + ris + '</span>' : ''}</span>`;
    }).join('');
    // I crediti non spesi valgono zero a fine asta: se il piano ne lascia
    // indietro molti, vuol dire che si puo' alzare la mira.
    const avanzo = p.avanzo || 0;
    const soglia = Math.max(15, Math.round(0.06 * Math.max(1, p.crediti)));
    box.innerHTML = `
      <p class="nota piccola" style="margin-top:10px">Come conviene distribuire
         quello che ti resta, ai prezzi di adesso:</p>
      <div class="barra-piano">${barre}</div>
      <div class="legenda-piano">${leg}</div>
      ${avanzo > soglia ? `
        <div class="avviso" style="margin-top:10px;font-size:12px">
          Cosi&#768; ti <b>avanzerebbero ${avanzo} crediti</b>, che a fine asta
          valgono zero. Puoi permetterti di alzare la mira su qualcuno.
        </div>` : ''}`;
  } catch (e) { box.innerHTML = ''; }
}

/* Il pannello "chi chiamare".
 *
 * Quattro sezioni, e ognuna risponde a una domanda diversa. Prima c'erano solo
 * i giocatori che superavano il vaglio del prezzo massimo, e con i portieri a
 * pacchetto quel vaglio lo supera una persona sola: restava un nome a schermo,
 * e siccome i primi portieri si equivalgono a due punti di distanza bastava un
 * acquisto altrui per farlo cambiare. Adesso il reparto si vede intero, in
 * fila per quanto sposta la rosa, con accanto il numero che spiega perche' uno
 * sta sopra l'altro. */
/* Quante caselle della formazione riempie il reparto che hai in mano.
 *
 * Non e' "quanti giocatori ho": e' quanti ne prendono voto la domenica. Otto
 * difensori che giocano meta' campionato coprono meno di quattro che giocano
 * sempre, e finora quella differenza non si vedeva da nessuna parte &mdash;
 * la si scopriva a stagione iniziata, schierando in dieci. */
function coperturaBarra(cop, ruolo) {
  if (!cop || !cop.servono) return '';
  const quota = Math.max(0, Math.min(1, cop.coperti / cop.servono));
  const stato = cop.mancano >= 1.5 ? 'male' : cop.mancano >= 0.5 ? 'cosi' : 'bene';
  const nome = cop.servono === 1
    ? NOME_SINGOLARE[ruolo] : NOME_RUOLO[ruolo].toLowerCase();
  return `
    <div class="copertura ${stato}"
         title="Ogni giocatore prende voto in una giornata qualunque con la probabilita' delle sue presenze attese. Questa e' la media delle caselle che riesci a riempire fra i ${esc(nome)} titolari, contando anche la panchina.">
      <span class="cop-testa">In campo ogni giornata</span>
      <span class="cop-barra"><i style="width:${Math.round(100 * quota)}%"></i></span>
      <span class="cop-cifra">${cop.coperti.toFixed(1)}<span class="fioco"> / ${
        cop.servono} ${esc(nome)}</span></span>
    </div>`;
}

async function caricaConsiglio() {
  const box = $('#vista-consiglio');
  const mio = apriRichiesta('consiglio');
  // Il "sto calcolando" solo la prima volta: durante l'asta il pannello si
  // rifa' a ogni acquisto, e svuotarlo ogni volta lo farebbe lampeggiare.
  if (!box.firstChild) box.innerHTML = '<p class="nota">Sto calcolando…</p>';
  else box.classList.add('in-aggiornamento');
  try {
    const c = await get('/api/consiglio');
    if (!ancoraValida(mio)) return;
    box.classList.remove('in-aggiornamento');
    if (!c.fase) {
      box.innerHTML = `${coppieBlocco(c.coppie)}
        <p class="nota">Asta conclusa.</p>`;
      return;
    }
    // Il verdetto va scritto su ogni riga: e' lo stesso che comparira'
    // aprendo la scheda, e vederlo qui toglie ogni ambiguita' su cosa
    // significhi trovarsi in una lista o nell'altra.
    const CLASSE = { OCCASIONE: 'ottimo', PRENDILO: 'ottimo',
                     'AL PREZZO GIUSTO': 'attenzione', 'DA UN CREDITO': 'attenzione' };
    /* Le liste possono riguardare un reparto **diverso** da quello che si sta
       chiamando: quando i miei slot in questo sono pieni non posso piu'
       offrire, e il motore manda avanti il prossimo. Tutti i testi vanno
       scritti sul reparto elencato, non sulla fase. */
    const ruoloElenco = c.anticipo || c.fase;
    const reparto = NOME_RUOLO[ruoloElenco].toLowerCase();
    /* Il reparto regge la formazione, o mancano ancora giocatori che scendono
       in campo tutte le domeniche? Finche' manca qualcuno, ogni riga deve dire
       da che parte sta: e' l'informazione che separa un affare da un buco. */
    const scoperto = !!(c.copertura && c.copertura.mancano >= 0.5);

    const voce = (d, cat, i) => `
      <button class="consiglio-voce ${cat}" data-giocatore="${d.id}">
        <div class="consiglio-testa">
          <span class="consiglio-nome">${cat === 'top'
            ? `<span class="posto">${i + 1}</span>` : ''}${esc(d.nome)}
            <span class="fioco">${esc(d.squadra)}</span>${
            d.divergenza && d.divergenza.verso === 'sopra'
              ? `<span class="dubbio" title="${esc(d.divergenza.testo)}">?</span>` : ''}</span>
          <span class="consiglio-cifra ${d.max_bid > 0 && cat !== 'svuota' && cat !== 'evitare' ? '' : 'stimata'}"
                title="${d.max_bid > 0 && cat !== 'svuota' && cat !== 'evitare'
                  ? 'Il massimo che puoi offrire senza peggiorare la rosa finale'
                  : cat === 'svuota'
                  ? 'Il tetto oltre il quale non spingere: se gli altri si fermano te lo ritrovi in rosa, e sotto questa cifra almeno non ci rimetti'
                  : 'Quanto dovrebbe chiudere. Il tuo limite qui e 0: per quello slot il motore ha una prima scelta, e questo lo prendi solo se quella vola via.'}"
            >${d.max_bid > 0 && cat !== 'svuota' && cat !== 'evitare'
              ? d.max_bid
              : cat === 'svuota' ? d.tetto_sicuro : '~' + d.chiusura}</span>
        </div>
        <div class="consiglio-riga2">
          <span class="esito ${CLASSE[d.verdetto] || 'stop'}">${esc(d.verdetto)}</span>
          ${grado(d.gerarchia, true)}${rigore(d.gerarchia)}
          ${d.categoria === 'coppia'
            ? '<span class="tag-coppia">chiude una coppia</span>' : ''}
          ${scoperto && !d.titolare_pieno
            ? `<span class="tag-panchina" title="Con ${d.presenze} presenze attese su 38 non copre un posto fisso: va bene come quinto o sesto, non come titolare. In questo reparto te ne mancano ancora.">da panchina</span>` : ''}
          ${d.categoria === 'copertura'
            ? `<span class="tag-copre" title="E' qui perche' copre una casella della formazione, non perche' sia un affare: ${d.presenze} presenze attese, e costa quanto chi ne gioca la meta'.">copre un posto</span>` : ''}
          ${cat !== 'svuota' && d.convenienza != null
            ? `<span class="utilita ${d.convenienza >= 0 ? '' : 'meno'}"
                     title="Punti di stagione che rende in ${d.convenienza >= 0 ? 'piu' : 'meno'}' di quello che quei crediti comprano fra i ${esc(reparto)}. E' il numero che decide in quale sezione finisce."
               >${d.convenienza >= 0 ? '+' : ''}${d.convenienza}</span>` : ''}
          ${cat !== 'svuota' && d.resa != null
            ? `<span class="resa" title="Punti di stagione che aggiunge alla tua rosa, nel primo slot libero del reparto">${Math.round(d.resa)} pt</span>`
            : ''}
        </div>
        <div class="consiglio-perche">${esc(d.perche || d.frase || '')}</div>
      </button>`;

    /* Le spiegazioni lunghe stavano **sopra** la lista, aperte. Sono scritte
       bene e servono la prima volta; alla ventesima chiamata sono sei righe
       fra te e il nome che stai cercando, e in asta non le legge nessuno.
       Ora si aprono se le vuoi. */
    /* La chiave con cui il motore spiega perche' una sezione e' vuota non e'
       il nome della categoria delle singole voci: "evitare" contiene voci di
       categoria "evitare", ma "alternative" ne contiene di categoria
       "alternativa" e "svuotare" di categoria "svuota". */
    const cat0 = (c) => ({ alternativa: 'alternative', svuota: 'svuotare' }[c] || c);

    const spiegazione = (testo) => `
      <details class="spiega"><summary>come si legge</summary>
        <div class="spiega-corpo">${testo}</div></details>`;

    const sezione = (titolo, colonna, spiega, lista, cat, vuoto) => `
      <div class="reparto-testa" style="margin-top:18px">
        <span class="reparto-nome">${titolo}</span>
        <span class="reparto-conta">${colonna}</span></div>
      ${spiegazione(spiega)}
      ${lista && lista.length
        ? `<div class="lista-voci">${lista.map((d, i) => voce(d, cat, i)).join('')}</div>`
        : `<p class="sezione-vuota">${esc((c.vuoti || {})[cat0(cat)] || vuoto)}</p>`}`;

    box.innerHTML = `
      <!-- Il titolo "Si chiamano portieri" c'e' gia' in alto a sinistra,
           grande, insieme a quanti ne restano. Ripeterlo qui costava una
           quarantina di pixel in cima alla colonna piu' preziosa per non
           aggiungere niente: resta l'indicazione, che e' la sola cosa che
           quel riquadro aveva da dire. -->
      <div class="titolo-centro">Chi chiamare</div>
      <div class="riquadro indicazione-strip">
        <p class="indicazione">${esc(c.indicazione)}</p>
        ${coperturaBarra(c.copertura, ruoloElenco)}
        ${c.scarsita ? `<div class="avviso" style="margin-top:10px;font-size:12px">
          ${esc(c.scarsita)}</div>` : ''}
      </div>

      ${c.anticipo ? `<div class="anticipo-strip">
        <span class="anticipo-tag">in anticipo</span>
        Qui sotto ci sono i <b>${esc(NOME_RUOLO[c.anticipo].toLowerCase())}</b>,
        non i ${esc(NOME_RUOLO[c.fase].toLowerCase())}: nel reparto che si sta
        chiamando hai gi&agrave; gli slot pieni e non puoi rilanciare.
        Servono a scegliere gli obiettivi &mdash; i prezzi si assestano quando
        toccher&agrave; a questo reparto.</div>` : ''}

      ${coppieBlocco(c.coppie, c.fase)}

      <div class="reparto-testa"><span class="reparto-nome">Top acquisti</span>
        <span class="reparto-conta">max che puoi offrire</span></div>
      ${spiegazione(`Tutti i ${esc(reparto)}
         che a quel prezzo rendono pi&ugrave; di quanto costano, dal migliore
         in gi&ugrave;. L&rsquo;ordine &egrave; per <b>quanto spostano la tua
         rosa</b>, non per quanto costano poco: il <b>+n</b> verde &egrave;
         un&rsquo;altra cosa, sono i punti che rende in pi&ugrave; della media
         del reparto a parit&agrave; di crediti. Le cifre valgono <b>una alla
         volta</b>: lo slot &egrave; uno, il motore ha una prima scelta, e per
         tutti gli altri il tuo limite &egrave; calcolato <i>ammesso che il
         primo te lo lascino</i> &mdash; per questo dal secondo in gi&ugrave;
         leggi <b>RIPIEGO</b>. Se fra il primo e il secondo ci sono due punti,
         vuol dire che si equivalgono: guarda il prezzo e prendi quello che
         costa meno.`)}
      ${c.top.length
        ? `<div class="lista-voci">${c.top.map((d, i) => voce(d, d.categoria === 'obbligato' ? 'obbligato' : 'top', i)).join('')}</div>`
        : `<p class="nota piccola">Nessuno: ai prezzi di adesso in questo
             reparto costano tutti pi&ugrave; di quanto renderebbero. Guarda le
             alternative qui sotto.</p>`}

      ${sezione('Da evitare', 'chiusura attesa',
        `Le trappole vere: costano abbastanza da far male e rendono meno di quello
         che quei crediti comprano fra gli altri ${esc(reparto)}. Sono in ordine
         di pericolo &mdash; prima quelli su cui la stanza spender&agrave;
         davvero &mdash; non di bruttezza.`,
        c.evitare, 'evitare', 'Niente da segnalare in questo reparto.')}

      ${sezione('Alternative', 'max che puoi offrire',
        `N&eacute; affari n&eacute; trappole: costano quello che valgono. &Egrave;
         il piano B da tenere pronto se i primi volano oltre il tuo limite, e
         ci stanno tutti nei ${c.budget_ruolo} crediti destinati al reparto.
         Vengono prima i <b>titolari veri</b>: se devi riempire uno slot in
         fretta, l&rsquo;ultima cosa che ti serve &egrave; una fantamedia alta
         di uno che gioca otto partite.`,
        c.alternative, 'alternativa', 'Nessuno in questa fascia di prezzo.')}

      ${sezione('Da far pagare agli altri', 'chiusura attesa',
        `Nessuno di questi &egrave; fra i tuoi obiettivi, e costano abbastanza da
         far male a chi se li prende: chiamarli brucia crediti agli avversari
         prima che tocchi ai giocatori che vuoi tu. La cifra &egrave; il
         <b>tetto oltre cui non spingere</b>, non la chiusura attesa: sopra
         quella, se gli altri si fermano, te lo ritrovi in rosa a un prezzo che
         non volevi pagare. Compaiono solo quando almeno <b>due</b> avversari
         possono superare il tetto: con uno solo, se passa la mano
         &egrave; tuo.`,
        c.svuotare, 'svuota',
        'Niente da svuotare: nessuno ha ancora abbastanza crediti.')}

      <p class="nota piccola" style="margin-top:14px">Valutati i
         <b>${c.valutati}</b> ${esc(reparto)} pi&ugrave; utili dei
         ${c.liberi_nel_ruolo} ancora liberi. Pi&ugrave; in basso ci sono solo
         riempitivi da un credito, e li trovi nel listone.</p>`;
  } catch (e) {
    if (!ancoraValida(mio)) return;
    box.classList.remove('in-aggiornamento');
    box.innerHTML = `<div class="errore">${esc(e.message)}</div>`;
  }
}

/* Le maglie di cui possiedo gia' meta'. Sta in cima e non dentro la classifica
 * apposta: se ho comprato uno dei due che si giocano il posto, il secondo mi
 * copre le giornate in cui il primo non gioca e costa una frazione, ma solo se
 * me ne accorgo prima che se lo prenda qualcun altro. */
function coppieBlocco(coppie, fase) {
  if (!coppie || !coppie.length) return '';
  const righe = coppie.map((c) => `
    <button class="consiglio-voce coppia" data-giocatore="${c.id}">
      <div class="consiglio-testa">
        <span class="consiglio-nome">${tag(c.ruolo)}${esc(c.nome)}
          <span class="fioco">${esc(c.squadra)}</span></span>
        <span class="consiglio-cifra">${c.slot_liberi > 0 ? c.max_bid : '~' + c.chiusura}</span>
      </div>
      <div class="consiglio-riga2">
        <span class="tag-coppia">${c.tipo === 'ballottaggio' ? 'Ballottaggio' : 'Suo vice'}
          con ${esc(c.con)}</span>
        <span class="utilita" title="Copre ${Math.round(c.giornate_coperte)} delle ${Math.round(c.buchi)} giornate che ${esc(c.con)} salta">${Math.round(c.copertura_buchi * 100)}% dei buchi</span>
        ${c.slot_liberi > 0 ? '' : '<span class="esito stop">REPARTO PIENO</span>'}
      </div>
      <div class="consiglio-perche">${esc(c.perche)}</div>
    </button>`).join('');
  return `
    <div class="reparto-testa"><span class="reparto-nome">Coppie da chiudere</span>
      <span class="reparto-conta">${coppie.length}</span></div>
    <p class="nota piccola" style="margin-bottom:8px">Hai gi&agrave; met&agrave;
       di queste maglie. La percentuale &egrave; <b>quanti dei buchi del tuo
       giocatore questo riempie davvero</b>: non quante giornate coprono in due,
       che &egrave; alta comunque se il primo &egrave; titolare e non
       distinguerebbe niente. Il secondo costa una frazione perch&eacute; il
       mercato paga chi &egrave; sicuro, non chi &egrave; complementare, ed
       &egrave; l&igrave; che sta l&rsquo;affare. Restano qui finch&eacute; non
       li prendi tu o non li prende qualcun altro.</p>
    ${righe}`;
}

async function caricaListone() {
  const box = $('#vista-listone');
  const filtri = ['tutti', ...RUOLI].map((r) => `
    <button class="filtro${(S.filtroListone || 'tutti') === r ? ' attiva' : ''}"
            data-filtro="${r}">${r === 'tutti' ? 'Tutti' : r}</button>`).join('')
    + `<button class="filtro${S.soloTitolari ? ' attiva' : ''}" data-titolari="1"
               title="Nasconde chi non e' titolare con ragionevole certezza"
       >solo titolari</button>`;
  // Le intestazioni ordinano. La colonna sotto gli occhi e quella con cui la
  // lista e' in fila devono essere la stessa: prima il listone si ordinava per
  // prezzo atteso mentre mostrava la chiusura, e le due cose non coincidono.
  const ordine = S.ordineListone || 'costa';
  const col = (chiave, etichetta, extra) => `
    <button class="col ordina${extra || ''}${ordine === chiave ? ' attiva' : ''}"
            data-ordine="${chiave}"
            title="Ordina per ${esc(etichetta)}, dal piu&#768; alto">${etichetta}${
      ordine === chiave ? '<i class="freccia">▾</i>' : ''}</button>`;
  const testa = `
    <div class="listone-filtri">${filtri}</div>
    <div class="listone-intestazione">
      <button class="cresce ordina${ordine === 'nome' ? ' attiva' : ''}"
              data-ordine="nome" title="Ordina per nome">giocatore</button>
      ${col('presenze', 'pres')}
      ${col('valore', 'vale')}
      ${col('costa', 'costa', ' forte')}
    </div>`;
  const mio = apriRichiesta('listone');
  try {
    const p = new URLSearchParams({ n: '80', ordine });
    if (S.filtroListone && S.filtroListone !== 'tutti') p.set('ruolo', S.filtroListone);
    if (S.soloTitolari) p.set('titolari', '1');
    const l = await get('/api/listone?' + p.toString());
    if (!ancoraValida(mio)) return;
    box.innerHTML = testa + `
      ${l.righe.map((x) => `
        <div class="riga-lista cliccabile listone-riga" data-giocatore="${x.id}">
          <span class="cresce" style="${x.venduto ? 'opacity:.45' : ''}">
            ${tag(x.ruolo)} ${esc(x.nome)}
            <span class="fioco">${esc(x.squadra)}</span>
            ${grado(x.gerarchia, true)}${rigore(x.gerarchia)}${fuoriLista(x)}</span>
          ${x.venduto
            ? `<span class="fioco venduto-a">${esc(x.a_chi)}</span>
               <span class="cifra forte">${x.pagato}</span>`
            : `<span class="col">${x.presenze}</span>
               <span class="col">${x.valore}</span>
               <span class="col forte">${x.chiusura}</span>`}
        </div>`).join('')}
      <p class="nota piccola" style="margin-top:10px">
        <b>vale</b> &egrave; quanto varrebbe se in questa lega si pagasse a punti;
        <b>costa</b> &egrave; quanto ci vorr&agrave; davvero per portarlo via,
        viste le rose e i crediti di adesso. Sono numeri diversi apposta:
        la differenza fra i due &egrave; l&rsquo;affare. <b>pres</b> sono le
        presenze attese su 38. Le intestazioni sono cliccabili: si ordina per
        quella colonna, dal pi&ugrave; alto al pi&ugrave; basso.</p>`;
  } catch (e) {
    if (!ancoraValida(mio)) return;
    box.innerHTML = testa + `<div class="errore">${esc(e.message)}</div>`;
  }
}

/* ============================================================== CERCA */

let timerCerca = null;
function alDigitare() {
  clearTimeout(timerCerca);
  timerCerca = setTimeout(cerca, 130);
}

async function cerca() {
  const t = $('#cerca').value.trim();
  const box = $('#risultati');
  if (t.length < 2) {
    box.hidden = true;
    S.risultati = [];
    // Svuotare il campo e' il gesto con cui si dice "con questo ho finito":
    // la scheda si chiude e tornano i consigli. Vale anche per la crocetta
    // del campo di ricerca, che e' del browser e non passa da Escape.
    if (!t && S.scheda) { S.scheda = null; disegnaScheda(); }
    return;
  }
  try {
    S.risultati = await get('/api/cerca?n=10&q=' + encodeURIComponent(t));
  } catch (e) { return; }
  S.evidenziato = S.risultati.length ? 0 : -1;
  if (!S.risultati.length) {
    box.innerHTML = '<div class="risultato"><span class="risultato-squadra">Nessun giocatore con questo nome.</span></div>';
    box.hidden = false;
    return;
  }
  disegnaRisultati();
  box.hidden = false;
}

function disegnaRisultati() {
  $('#risultati').innerHTML = S.risultati.map((x, i) => `
    <div class="risultato${x.venduto ? ' venduto' : ''}${i === S.evidenziato ? ' evidenziato' : ''}"
         data-giocatore="${x.id}">
      ${tag(x.ruolo)}
      <span class="risultato-nome">${esc(x.nome)}</span>
      <span class="risultato-squadra">${esc(x.squadra)}</span>
      <span class="risultato-prezzo">${x.venduto ? 'venduto' : x.mercato}</span>
    </div>`).join('');
}

function chiudiRisultati() {
  $('#risultati').hidden = true;
  S.evidenziato = -1;
}

/* ============================================================= SCHEDA */

async function apriGiocatore(id) {
  chiudiRisultati();
  try {
    S.scheda = await get('/api/scheda?id=' + id);
  } catch (e) { brindisi(e.message, true); return; }
  S.acquirente = S.stato.turno;
  disegnaScheda();
  // Il fuoco va tolto dal campo di ricerca, altrimenti i tasti 1-8 finiscono
  // dentro la casella invece di scegliere chi si e' aggiudicato il giocatore.
  if (document.activeElement && document.activeElement.blur) {
    document.activeElement.blur();
  }
}

/* Un acquisto sposta ogni prezzo dell'asta, compreso quello del giocatore che
 * si sta guardando: chi resta sul mercato e' cambiato, e con lui il livello di
 * rimpiazzo e i crediti di chi puo' rilanciare. Lasciare a schermo la scheda
 * di prima vorrebbe dire rilanciare su un numero vecchio. */
async function aggiornaScheda() {
  const d = S.scheda;
  if (!d) return;
  try {
    S.scheda = await get('/api/scheda?id=' + d.id);
  } catch (e) { return; }
  disegnaScheda(true);
}

function disegnaScheda(mantieni) {
  const d = S.scheda;
  const box = $('#scheda');
  // Il prezzo gia' digitato e l'aggiudicatario gia' scelto non si perdono
  // quando la scheda si ridisegna da sola sotto le dita.
  const prezzoScritto = mantieni && $('#prezzo') ? $('#prezzo').value : null;
  const consigli = $('#vista-consiglio');
  if (!d) {
    box.className = 'scheda';
    box.innerHTML = '';
    if (consigli) consigli.hidden = false;
    return;
  }
  if (consigli) consigli.hidden = true;
  box.className = 'scheda viva';

  const st = S.stato;
  const stima = d.metodo !== 'storico';
  const venduto = d.gia_venduto;

  const avvisi = [];
  if (venduto) {
    avvisi.push(['grave', `Gia&#768; assegnato a <b>${esc(venduto.a)}</b> per
      <b>${venduto.prezzo}</b> crediti.`]);
  }
  if (d.divergenza) {
    avvisi.push([d.divergenza.verso === 'sopra' ? 'grave' : '', esc(d.divergenza.testo)]);
  }
  if (stima) {
    avvisi.push(['', `Non ha storico di Serie A: la stima viene dalla quotazione,
      non dai suoi numeri. Trattala con prudenza.`]);
  }
  // Una fantamedia alta prodotta da poche partite e' la trappola classica
  // dell'asta, e a schermo somiglia a un affare. Va detto prima del prezzo.
  const ge = d.gerarchia;
  if (!venduto && ge && ge.grado && ge.grado !== 'ignoto' && !ge.sicuro) {
    avvisi.push([ge.grado === 'riserva' || ge.grado === 'rotazione' ? 'grave' : '',
      `<b>${esc(ETICHETTA_GRADO[ge.grado])}.</b> ${esc(ge.testo)}
       La fantamedia di ${d.fantamedia.toFixed(2)} vale su
       ${d.presenze} presenze, non su 38.`]);
  }
  if (!venduto && d.pacchetto && d.pacchetto.length) {
    // Quanti slot chiude davvero, non quanti dovrebbe chiuderne. Qualche
    // squadra ha solo due portieri a listone, e dire "chiude tutto il reparto"
    // in quel caso e' falso: ci si ritrova con uno slot scoperto scoperto solo
    // dopo aver pagato.
    const chiusi = d.pacchetto.length + 1;
    const totale = st.regole.slot.P;
    avvisi.push([chiusi < totale ? 'attenzione' : '', `Regola della lega:
      prendendolo ti arrivano anche
      <b>${d.pacchetto.map((r) => esc(r.nome)).join('</b> e <b>')}</b>
      a 1 credito. ${chiusi >= totale
        ? `Questo prezzo chiude <b>tutto il reparto portieri</b>, non compra un
           giocatore solo.`
        : `Attenzione: il ${esc(d.squadra)} ha solo ${chiusi} portieri a
           listone, quindi questo prezzo chiude <b>${chiusi} slot su
           ${totale}</b>. Il terzo dovrai prenderlo a parte, da un'altra
           squadra.`}`]);
  }
  if (!venduto && d.chiude_coppia) {
    avvisi.push(['bonus', `Possiedi gi&agrave; <b>${esc(d.chiude_coppia.con)}</b>, che
      salta circa <b>${Math.round(d.chiude_coppia.buchi)}</b> giornate: questo ne
      copre il <b>${Math.round(d.chiude_coppia.copertura_buchi * 100)}%</b>. Il
      limite qui sopra include gi&agrave; <b>+${d.chiude_coppia.punti_extra}</b>
      punti stagione per questo.`]);
  }
  if (!venduto && d.stessa_squadra >= 3) {
    avvisi.push(['', `Hai gi&agrave; <b>${d.stessa_squadra}</b> giocatori
      del ${esc(d.squadra)}. Non &egrave; un errore, ma &egrave; varianza:
      quando quella squadra si inceppa si inceppa mezza rosa.`]);
  }
  if (!venduto && st.fase && d.ruolo !== st.fase) {
    avvisi.push(['', `Si stanno chiamando <b>${NOME_RUOLO[st.fase].toLowerCase()}</b>,
      questo &egrave; un ${NOME_RUOLO[d.ruolo].slice(0, -1).toLowerCase()}.
      Puoi registrarlo lo stesso, ma controlla di non aver sbagliato giocatore.`]);
  }

  const numeri = [
    ['Chiusura attesa', d.chiusura, 'quanto costera&#768; davvero'],
    ['Valore per la lega', d.mercato, 'quanto varrebbe se si pagasse a punti'],
    ['Pagato in passato', d.riferimento || '—', 'media delle aste storiche'],
    ['Fantamedia attesa', d.fantamedia.toFixed(2), `su ${d.presenze} presenze · mv ${d.mv.toFixed(2)}`],
    ['Presenze attese', d.presenze,
      ge && ge.quota != null ? `${Math.round(ge.quota * 100)}% della stagione` : 'su 38'],
  ];
  if (d.utilita > 0) {
    numeri.push(['Se lo prendi a ' + d.chiusura, '+' + d.utilita,
      'punti stagione in piu&#768; per la tua rosa']);
  }
  if (d.contributo_modificatore > 0) {
    numeri.push(['Modificatore', '+' + d.contributo_modificatore,
      'punti stagione che aggiunge alla tua difesa']);
  }

  const concorrenti = d.concorrenti.length ? d.concorrenti.map((c) => `
    <div class="riga-lista">
      <span class="cresce">${esc(c.nome)}</span>
      <span class="fioco">${c.crediti} cr</span>
      <span class="cifra">${c.liquidita}</span>
    </div>`).join('') : '<p class="nota piccola">Nessuno: o hanno il reparto pieno, o non hanno crediti.</p>';

  const ETICHETTA_COPPIA = { ballottaggio: 'Ballottaggio', vice: 'Suo vice' };
  const compagni = (d.compagni_di_maglia || []).map((c) => {
    const cifra = c.stato === 'mio' ? '<span class="fioco">gi&agrave; tuo</span>'
      : c.stato === 'avversario' ? `<span class="fioco">di ${esc(c.presidente)}</span>`
      : `<span class="cifra">${c.max_bid}</span>`;
    return `
    <div class="riga-lista${c.stato === 'libero' ? ' cliccabile' : ''}"
         ${c.stato === 'libero' ? `data-giocatore="${c.id}"` : ''}>
      <span class="cresce">${esc(c.nome)} <span class="fioco">${esc(c.squadra)}</span>
        <span class="tag-coppia">${ETICHETTA_COPPIA[c.tipo] || c.tipo}</span></span>
      <span class="fioco" title="Copre ${Math.round(c.buchi_coperti)} delle ${Math.round(c.buchi)} giornate in cui l'altro non gioca">copre ${Math.round(c.copertura_buchi * 100)}% dei buchi</span>
      ${cifra}
    </div>`;
  }).join('');

  const alternative = d.alternative.map((a) => `
    <div class="riga-lista cliccabile" data-giocatore="${a.id}">
      <span class="cresce">${esc(a.nome)} <span class="fioco">${esc(a.squadra)}</span>
        ${grado(a.gerarchia, true)}${rigore(a.gerarchia)}</span>
      ${a.quota_punti != null ? `<span class="fioco">${a.quota_punti}% dei punti</span>` : ''}
      <span class="cifra">${a.max_bid}</span>
    </div>`).join('');

  box.innerHTML = `
    <div class="scheda-testa">
      ${tag(d.ruolo)}
      <div>
        <div class="scheda-nome">${esc(d.nome)} ${grado(d.gerarchia)}${rigore(d.gerarchia)}${fuoriLista(d)}</div>
        <div class="scheda-sotto"><b>${esc(d.squadra)}</b> ·
          quotazione ${d.qi} · ${NOME_RUOLO[d.ruolo].slice(0, -1).toLowerCase()}
          ${stima ? ' · <b>stima da quotazione</b>' : ''}</div>
      </div>
      <!-- Aprire un giocatore dal listone lasciava senza via d'uscita: la
           scheda copre i consigli e il tasto Esc funzionava solo col cursore
           dentro il campo di ricerca, dove chi arriva dal listone non e' mai
           passato. Serviva una porta che si vede. -->
      <button id="btn-chiudi-scheda" class="chiudi-scheda"
              title="Torna ai consigli (Esc)">&times;<span>consigli</span></button>
    </div>

    <div class="verdetto ${d.colore}">
      <div class="verdetto-cifra">
        <div class="verdetto-numero">${d.max_bid || '—'}</div>
        <span class="verdetto-unita">${d.max_bid ? 'non oltre' : 'non comprare'}</span>
      </div>
      <div class="verdetto-testo">
        <div class="verdetto-parola">${esc(d.verdetto)}</div>
        <div class="verdetto-frase">${esc(d.frase)}</div>
      </div>
    </div>

    ${avvisi.map(([c, t]) => `<div class="avviso ${c}">${t}</div>`).join('')}

    <div class="numeri">
      ${numeri.map(([e, v, s]) => `
        <div class="numero"><span>${e}</span><b>${v}</b><small>${s}</small></div>`).join('')}
    </div>

    ${compagni ? `
    <div class="riquadro">
      <div class="riquadro-titolo">Chi copre la maglia quando non gioca lui</div>
      <p class="nota piccola" style="margin-bottom:8px">Quando l'uno non
         gioca gioca l'altro. Prendendoli entrambi quella maglia &egrave; tua
         quasi ogni giornata, e il secondo costa una frazione del primo:
         il mercato paga la certezza, non il complementare.</p>
      ${compagni}
    </div>` : ''}

    ${venduto ? '' : `
    <div class="assegna">
      <div class="assegna-titolo">Chi se l'&egrave; aggiudicato?</div>
      <div class="assegna-riga">
        ${st.presidenti.map((p, i) => {
          const pieno = p.slot[d.ruolo] >= st.regole.slot[d.ruolo];
          return `<button class="chi${p.io ? ' mio' : ''}${p.id === S.acquirente ? ' scelto' : ''}"
                    data-acquirente="${p.id}" ${pieno ? 'disabled title="reparto pieno"' : ''}>
                    <kbd>${i + 1}</kbd>${esc(p.nome)}</button>`;
        }).join('')}
      </div>
      <div class="assegna-prezzo">
        <input id="prezzo" type="number" min="1" value="${d.consigliato || d.chiusura || 1}"
               aria-label="Prezzo pagato">
        <button class="bottone" id="btn-assegna">Registra l'acquisto</button>
        <span class="nota piccola">Invio per confermare</span>
      </div>
    </div>`}

    <div class="blocchi">
      <div class="blocco">
        <h3>Chi pu&ograve; ancora rilanciare (${d.concorrenti.length})</h3>
        ${concorrenti}
      </div>
      <div class="blocco">
        <h3>Se lo perdi</h3>
        <p class="nota piccola" style="margin:-2px 0 6px">Prima i titolari
           sicuri: un ripiego che non gioca non &egrave; un ripiego.</p>
        ${alternative || '<p class="nota piccola">Nessuna alternativa nel ruolo.</p>'}
      </div>
    </div>`;

  if (prezzoScritto != null && $('#prezzo')) $('#prezzo').value = prezzoScritto;
}

/* --------------------------------------------------------- assegnazione */

async function registra() {
  const d = S.scheda;
  if (!d) return;
  const prezzo = parseInt($('#prezzo').value, 10);
  if (!S.acquirente) { brindisi('Scegli chi se l\'è aggiudicato.', true); return; }
  if (!(prezzo >= 1)) { brindisi('Il prezzo minimo è 1 credito.', true); return; }
  try {
    S.stato = await post('/api/acquisto',
      { id: d.id, presidente: S.acquirente, prezzo: prezzo });
    const chi = S.stato.presidenti.find((p) => p.id === S.acquirente);
    const extra = (S.stato.pacchetto || []).map((r) => r.nome);
    brindisi(`${d.nome} → ${chi.nome} per ${prezzo} crediti`
      + (extra.length ? `  ·  in dote anche ${extra.join(' e ')} a 1` : ''));
    S.scheda = null;
    disegnaScheda();
    disegna();
    $('#cerca').value = '';
    $('#cerca').focus();
  } catch (e) {
    brindisi(e.message, true);
  }
}

async function annulla(id) {
  try {
    S.stato = await post('/api/annulla', id ? { id: id } : {});
    brindisi('Acquisto annullato.');
    disegna();
    aggiornaScheda();
  } catch (e) { brindisi(e.message, true); }
}

/* ============================================================= EVENTI */


/* Correggere i nomi delle squadre senza rifare l'asta. Prima l'unica via era
   "nuova asta", che cancella tutti gli acquisti: un nome sbagliato costava la
   serata. */
function apriRinomina() {
  const f = $('#form-rinomina');
  if (!f.hidden) { f.hidden = true; return; }
  f.innerHTML = S.stato.presidenti.map((p, i) => `
    <label class="rinomina-riga">
      <span>${p.io ? 'tu' : i}</span>
      <input type="text" maxlength="24" data-presidente="${p.id}"
             value="${esc(p.nome)}">
    </label>`).join('') + `
    <div class="rinomina-azioni">
      <button id="btn-rinomina-ok" class="bottone minuscolo">Salva</button>
      <span id="rinomina-errore" class="errore" hidden></span>
    </div>`;
  f.hidden = false;
  f.querySelector('input').focus();
}

async function salvaRinomina() {
  const f = $('#form-rinomina');
  const err = $('#rinomina-errore');
  const nomi = $$('#form-rinomina input').map((c) => c.value.trim());
  try {
    S.stato = await post('/api/rinomina', { nomi });
    f.hidden = true;
    disegna();
  } catch (e) {
    err.textContent = e.message;
    err.hidden = false;
  }
}

/* Il regolamento si salva quando il campo si chiude (`change`, non `input`):
 * altrimenti si rifarebbero tutti i prezzi a ogni tasto, e digitando "500" si
 * passerebbe per una lega da 5 crediti e una da 50. */
document.addEventListener('change', (ev) => {
  if (ev.target.closest('#avvio-regole')) salvaRegole();
});

/* Riempie il reparto in corso per tutte le squadre. E' un attrezzo da
 * collaudo: serve ad arrivare in un secondo al punto dell'asta che si vuole
 * guardare, invece di registrare a mano quaranta acquisti ogni volta.
 *
 * Chiede conferma con i numeri davanti, perche' quello che fa non si annulla
 * in blocco: gli acquisti si tolgono uno alla volta. E dice quanto ci mettera'
 * &mdash; il motore rifa' tutti i conti dopo ogni assegnazione, che e' il
 * motivo per cui lo stato a cui si arriva e' uno stato vero e non una
 * scorciatoia. */
async function completaReparto() {
  const st = S.stato;
  if (!st || !st.fase) { brindisi("L'asta è già conclusa.", true); return; }
  const reparto = NOME_RUOLO[st.fase].toLowerCase();
  const restano = st.mercato.residui_ruolo[st.fase];
  const miei = st.regole.slot[st.fase] - (st.io.rosa[st.fase] || []).length;
  const messaggio = [
    `Completo i ${reparto} per tutte le squadre: ${restano} caselle da riempire`
      + (miei > 0
        ? `, ${miei} delle quali tue — prendo i primi della lista dei consigli,`
          + ' uno alla volta, coi conti rifatti dopo ognuno.'
        : ', tutte ad altre squadre.'),
    '',
    'Ci mette qualche secondo, e non si annulla in blocco: gli acquisti si',
    'tolgono uno alla volta.',
    '',
    'Procedo?',
  ].join('\n');
  if (!confirm(messaggio)) return;

  const b = $('#btn-completa');
  const prima = b.textContent;
  b.disabled = true;
  b.textContent = 'sto riempiendo…';
  try {
    S.stato = await post('/api/completa_reparto');
    const c = S.stato.completati || {};
    disegna();
    // Con i portieri a pacchetto le due cifre non coincidono, e dirlo evita
    // di far sembrare che ne abbia registrati meno di quelli annunciati.
    brindisi(`${NOME_RUOLO[c.ruolo].toLowerCase()} completati: ${c.caselle} caselle`
      + (c.caselle !== c.quanti ? ` in ${c.quanti} chiamate.` : ' riempite.'));
  } catch (e) {
    brindisi(e.message, true);
  } finally {
    b.disabled = false;
    b.textContent = prima;
  }
}

document.addEventListener('click', async (ev) => {
  const t = ev.target;

  const avvia = t.closest('#btn-nuova');
  if (avvia) { ev.preventDefault(); nuovaAsta(); return; }

  if (t.closest('#btn-ricomincia')) { mostraAvvio(S.stato); return; }

  if (t.closest('#btn-chiudi-scheda')) {
    ev.preventDefault();
    S.scheda = null;
    $('#cerca').value = '';
    chiudiRisultati();
    disegnaScheda();
    return;
  }

  if (t.closest('#btn-completa')) { ev.preventDefault(); completaReparto(); return; }

  if (t.closest('#btn-rinomina')) { ev.preventDefault(); apriRinomina(); return; }
  if (t.closest('#btn-rinomina-ok')) { ev.preventDefault(); salvaRinomina(); return; }

  if (t.closest('#btn-chiudi')) {
    if (!confirm("Chiudo FantaHacked? L'asta resta salvata e la ritrovi al prossimo avvio."))
      return;
    chiudendo = true;
    try { await post('/api/spegni', {}); } catch (e) { /* il motore sta gia' morendo */ }
    // Nella finestra dell'applicazione questo la chiude davvero. Nel browser
    // di sistema il permesso non c'e', e resta il messaggio qui sotto.
    window.close();
    document.body.innerHTML =
      `<div style="display:grid;place-items:center;height:100vh;text-align:center;
                   font-family:system-ui;color:#74889A">
         <div><p style="font-size:20px;color:#E8EFF5">FantaHacked &egrave; chiuso.</p>
         <p>L'asta &egrave; salvata: la ritrovi al prossimo avvio.<br>
            Puoi chiudere questa finestra.</p></div></div>`;
    return;
  }

  if (t.closest('#btn-riprendi')) {
    $('#avvio').hidden = true; $('#app').hidden = false; disegna(); $('#cerca').focus(); return;
  }

  const tab = t.closest('[data-vista]');
  if (tab) { S.vista = tab.dataset.vista; disegnaDestra(); return; }

  const filtro = t.closest('[data-filtro]');
  if (filtro) { S.filtroListone = filtro.dataset.filtro; caricaListone(); return; }

  const ordina = t.closest('[data-ordine]');
  if (ordina) { S.ordineListone = ordina.dataset.ordine; caricaListone(); return; }

  if (t.closest('[data-titolari]')) {
    S.soloTitolari = !S.soloTitolari;
    caricaListone();
    return;
  }

  const occhio = t.closest('[data-rosa]');
  if (occhio) {
    ev.stopPropagation();
    S.rosaVista = parseInt(occhio.dataset.rosa, 10);
    S.vista = 'avversario';
    disegnaDestra();
    return;
  }

  const squadra = t.closest('[data-presidente]');
  if (squadra) {
    const id = parseInt(squadra.dataset.presidente, 10);
    try { S.stato = await post('/api/turno', { presidente: id }); disegna(); }
    catch (e) { brindisi(e.message, true); }
    return;
  }

  if (t.closest('#btn-avanza')) {
    ev.stopPropagation();
    try { S.stato = await post('/api/avanza', {}); disegna(); }
    catch (e) { brindisi(e.message, true); }
    return;
  }

  const togli = t.closest('[data-annulla]');
  if (togli) { annulla(parseInt(togli.dataset.annulla, 10)); return; }

  const acq = t.closest('[data-acquirente]');
  if (acq) {
    S.acquirente = parseInt(acq.dataset.acquirente, 10);
    $$('[data-acquirente]').forEach((b) =>
      b.classList.toggle('scelto', parseInt(b.dataset.acquirente, 10) === S.acquirente));
    $('#prezzo').focus(); $('#prezzo').select();
    return;
  }

  if (t.closest('#btn-assegna')) { registra(); return; }

  const g = t.closest('[data-giocatore]');
  if (g) { apriGiocatore(parseInt(g.dataset.giocatore, 10)); return; }

  if (!t.closest('.cerca-guscio')) chiudiRisultati();
});

$('#cerca').addEventListener('input', alDigitare);

$('#cerca').addEventListener('keydown', (ev) => {
  if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
    if (!S.risultati.length) return;
    ev.preventDefault();
    S.evidenziato = (S.evidenziato + (ev.key === 'ArrowDown' ? 1 : -1) + S.risultati.length)
      % S.risultati.length;
    disegnaRisultati();
  } else if (ev.key === 'Enter') {
    ev.preventDefault();
    const x = S.risultati[S.evidenziato];
    if (x) apriGiocatore(x.id);
  } else if (ev.key === 'Escape') {
    // Escape svuota la ricerca **e chiude la scheda**. Da quando i consigli
    // stanno al centro, la scheda aperta li copre: senza una via di ritorno
    // l'unico modo di rivederli era registrare l'acquisto o cercare un altro
    // nome, cioe' due strade che passano da un'azione che non volevi fare.
    $('#cerca').value = '';
    chiudiRisultati();
    if (S.scheda) { S.scheda = null; disegnaScheda(); }
  }
});

document.addEventListener('keydown', (ev) => {
  const dentroCampo = /^(INPUT|TEXTAREA|SELECT)$/.test(ev.target.tagName);

  if (ev.key === '/' && !dentroCampo) {
    ev.preventDefault(); $('#cerca').focus(); $('#cerca').select(); return;
  }
  // Esc chiude la scheda da qualunque punto della pagina. Prima stava solo
  // sul campo di ricerca, e chi apriva un giocatore dal listone non aveva
  // nessun modo di tornare ai consigli.
  if (ev.key === 'Escape' && S.scheda) {
    ev.preventDefault();
    S.scheda = null;
    $('#cerca').value = '';
    chiudiRisultati();
    disegnaScheda();
    return;
  }
  if (ev.key === 'Enter' && ev.target.id === 'prezzo') { ev.preventDefault(); registra(); return; }
  // Invio dentro il regolamento **non** fa partire l'asta: conferma il numero
  // e basta. Premerlo dopo aver scritto i crediti e ritrovarsi dentro un'asta
  // creata con quelli vecchi era il modo piu' facile di sbagliare serata.
  if (ev.key === 'Enter' && ev.target.closest('#avvio-regole')) {
    ev.preventDefault(); ev.target.blur(); return;
  }
  if (ev.key === 'Enter' && ev.target.closest('#form-nuova')
      && $('#avvio').hidden === false) {
    ev.preventDefault(); nuovaAsta(); return;
  }
  // Cifre 1..8: scelgono chi si e' aggiudicato il giocatore sotto esame.
  if (!dentroCampo && S.scheda && /^[1-9]$/.test(ev.key)) {
    const i = parseInt(ev.key, 10) - 1;
    const p = S.stato.presidenti[i];
    if (p) {
      // Senza questo, la stessa cifra finisce anche dentro il campo prezzo
      // appena gli si da' il fuoco, e cancella il prezzo suggerito.
      ev.preventDefault();
      S.acquirente = p.id;
      $$('[data-acquirente]').forEach((b) =>
        b.classList.toggle('scelto', parseInt(b.dataset.acquirente, 10) === p.id));
      const inp = $('#prezzo'); if (inp) { inp.focus(); inp.select(); }
    }
  }
});

/* ------------------------------------------------------------- congedo */

/* Quando la pagina sparisce il motore deve poterlo sapere: altrimenti resta
 * acceso senza che si veda, ed e' esattamente il genere di stranezza che un
 * programma non deve avere. Un ricaricamento passa di qui allo stesso modo,
 * percio' il motore aspetta qualche secondo prima di spegnersi davvero: se la
 * pagina torna, l'annuncio viene annullato da solo. */
let chiudendo = false;

window.addEventListener('pagehide', () => {
  if (chiudendo) return;
  try { navigator.sendBeacon('/api/congedo', '{}'); } catch (e) { /* pazienza */ }
});

/* Tornando visibile la pagina si rifa' viva subito, senza aspettare il
 * battito: i browser rallentano i timer delle finestre in secondo piano. */
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    fetch('/api/ping', { cache: 'no-store' }).catch(() => {});
  }
});

/* =============================================================== BOOT */

let interfacciaAvviata = false;

function avviaInterfaccia(st) {
  S.stato = st;
  interfacciaAvviata = true;
  if (st.iniziata) {
    $('#avvio').hidden = true;
    $('#app').hidden = false;
    disegna();
    $('#cerca').focus();
  } else {
    mostraAvvio(st);
  }
}

/* Battito: se il programma muore mentre la pagina e' ferma, si deve vedere
 * subito, non al primo clic. In asta scoprirlo nel momento in cui serve
 * sarebbe il momento peggiore. */
setInterval(async () => {
  if (!$('#disconnesso').hidden) return;      // ci pensa gia' il riaggancio
  try {
    const r = await fetch('/api/ping', { cache: 'no-store' });
    if (r.ok) collegamentoVivo(); else perdutoIlCollegamento();
  } catch (e) { perdutoIlCollegamento(); }
}, 10000);

(async function boot() {
  try {
    avviaInterfaccia(await get('/api/stato'));
  } catch (e) {
    // Il pannello di riconnessione e' gia' comparso da solo se il motore non
    // risponde. Qui resta da coprire il caso di un errore diverso.
    if (!(e instanceof ErroreCollegamento)) {
      $('#avvio-errore').textContent = e.message;
      $('#avvio-errore').hidden = false;
      $('#avvio').hidden = false;
    }
  }
})();
