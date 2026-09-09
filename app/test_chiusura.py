# -*- coding: utf-8 -*-
"""Collaudo di avvio e spegnimento: il programma deve comportarsi come un'app.

Si avvia con un doppio clic e si chiude chiudendo la finestra. Niente processi
che restano accesi senza che si vedano, niente pulsanti speciali da ricordarsi.

Queste verifiche hanno bisogno di avviare e spegnere il programma per intero,
quindi vogliono la macchina libera: **nessun'altra istanza in esecuzione**,
altrimenti il lucchetto le fa uscire subito (che e' il comportamento giusto,
ed e' verificato in test_app.py).

Uso:  python test_chiusura.py
"""
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

QUI = os.path.dirname(os.path.abspath(__file__))
PORTA = 8730
BASE = 'http://127.0.0.1:%d' % PORTA

ok = fail = 0


def verifica(descrizione, condizione, dettaglio=''):
    global ok, fail
    if condizione:
        ok += 1
        print('  OK   %s' % descrizione)
    else:
        fail += 1
        print('  FAIL %s   %s' % (descrizione, dettaglio))


def risponde(secondi=3):
    try:
        with urllib.request.urlopen(BASE + '/api/ping', timeout=secondi):
            return True
    except Exception:
        return False


def attendi_avvio(processo, secondi=60):
    scadenza = time.time() + secondi
    while time.time() < scadenza:
        if processo.poll() is not None:
            # Se e' uscito da solo, il motivo lo ha scritto: mostrarlo evita
            # di dover indovinare perche' una verifica e' rossa.
            try:
                testo = (processo.stdout.read() or b'').decode('utf-8', 'replace')
                print("       (il programma e' uscito: %s)"
                      % ' | '.join(testo.split())[:200])
            except Exception:
                pass
            return False
        if risponde(2):
            return True
        time.sleep(0.5)
    return False


def attendi_spegnimento(processo, secondi=45):
    scadenza = time.time() + secondi
    while time.time() < scadenza:
        if processo.poll() is not None:
            return True
        time.sleep(0.5)
    return False


def indizio_pagina_aperta():
    """Perche' il motore non si e' spento: quasi sempre una pagina di troppo.

    Il programma resta acceso finche' qualcuno sta usando l'interfaccia, ed e'
    giusto cosi'. Ma una scheda dimenticata su 127.0.0.1:8730 &mdash; in un
    browser qualunque, aperta magari mezz'ora prima su un motore poi morto
    &mdash; si riaggancia da sola al server appena la porta torna viva, e da
    quel momento tiene in piedi ogni prova di spegnimento. Sono due ore di
    caccia a un difetto che non c'era: meglio dirlo.
    """
    return ('il processo e\' rimasto acceso. Se c\'e\' una scheda aperta su '
            '%s in un browser qualsiasi, e\' lei a tenerlo vivo: chiudila e '
            'riprova.' % BASE)


def avvia(*extra):
    return subprocess.Popen([sys.executable, os.path.join(QUI, 'server.py')]
                            + list(extra),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def chiudi_finestre():
    """Chiude le finestre dell'app rimaste aperte.

    Uccidere il server senza chiudere la sua finestra lascia un browser che
    continua a bussare sulla porta: si riaggancia al server della prova
    successiva e lo tiene vivo. E' il comportamento giusto del programma
    (una finestra aperta vuol dire che l'utente lo sta usando), ma falsa le
    verifiche se non si fa pulizia.
    """
    if os.name != 'nt':
        return
    subprocess.run(
        ['powershell', '-NoProfile', '-Command',
         "Get-CimInstance Win32_Process | Where-Object "
         "{ $_.CommandLine -like '*--app=http://127.0.0.1*' } | "
         "ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
         "-ErrorAction SilentlyContinue }"],
        capture_output=True, timeout=60)
    time.sleep(1.5)


def chiudi(processo):
    if processo.poll() is None:
        processo.kill()
        processo.wait(timeout=10)
    chiudi_finestre()


def main():
    if risponde(2):
        print('C\'e\' gia\' un FantaHacked in esecuzione: chiudilo e riprova.')
        return 1

    # -------------------------------------------------- finestra dedicata
    print('\n[1] La finestra E\' il programma')
    import server as srv
    browser = srv._browser_applicazione()
    verifica('sul computer c\'e\' un browser adatto a fare da finestra',
             browser is not None, 'nessuno fra Edge, Chrome e Brave')
    p = avvia()
    try:
        verifica('il programma parte', attendi_avvio(p))
        finestra = None
        if browser and os.name == 'nt':
            time.sleep(3)
            nome = os.path.basename(browser)
            righe = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 "Get-CimInstance Win32_Process -Filter \"Name='%s'\" | "
                 "Where-Object { $_.CommandLine -like '*--app=http://127.0.0.1*' } | "
                 "Select-Object -First 1 -ExpandProperty ProcessId" % nome],
                capture_output=True, text=True, timeout=40).stdout.strip()
            finestra = int(righe) if righe.isdigit() else None
            verifica('si apre una finestra dedicata, non una scheda del browser',
                     finestra is not None, righe[:60])
        if finestra:
            # Chiudere la finestra deve spegnere tutto: e' l'unico gesto che
            # l'utente deve conoscere.
            subprocess.run(['powershell', '-NoProfile', '-Command',
                            '(Get-Process -Id %d).CloseMainWindow()' % finestra],
                           capture_output=True, timeout=40)
            verifica('chiudendo la finestra il motore si spegne',
                     attendi_spegnimento(p), indizio_pagina_aperta())
            verifica('la porta viene liberata', not risponde(2))
    finally:
        chiudi(p)
        time.sleep(3)

    # ------------------------------------ la seconda volta, col profilo gia' li'
    print('\n[1b] Alla seconda esecuzione la finestra resta una sola')
    # Il browser, trovando un profilo gia' usato, vorrebbe riaprire la finestra
    # della volta prima: se ne aprirebbero due, quella vecchia con una pagina
    # scaduta, e chiudendo l'una il programma non si spegnerebbe.
    if browser and os.name == 'nt':
        p = avvia()
        try:
            verifica('riparte', attendi_avvio(p))
            time.sleep(3)
            nome = os.path.basename(browser)
            uscita = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 "@(Get-CimInstance Win32_Process -Filter \"Name='%s'\" | "
                 "Where-Object { $_.CommandLine -like '*--app=http://127.0.0.1*' }"
                 ").Count" % nome],
                capture_output=True, text=True, timeout=40).stdout.strip()
            verifica('si apre una finestra sola, non due', uscita == '1',
                     'finestre trovate: %s' % uscita)
        finally:
            chiudi(p)
            time.sleep(1)

    # ---------------------------------------------- ripiego senza finestra
    print('\n[2] Se non si puo\' aprire una finestra dedicata')
    p = avvia('--no-browser', '--browser-di-sistema')
    try:
        verifica('il programma parte lo stesso', attendi_avvio(p))

        # Un ricaricamento della pagina passa dal congedo e torna subito:
        # non deve spegnere niente.
        urllib.request.urlopen(urllib.request.Request(
            BASE + '/api/congedo', data=b'{}',
            headers={'Content-Type': 'application/json'}), timeout=10).read()
        time.sleep(2)
        urllib.request.urlopen(BASE + '/api/ping', timeout=10).read()
        time.sleep(18)
        verifica('un ricaricamento della pagina non spegne il programma',
                 p.poll() is None and risponde(3))

        # La pagina chiusa per davvero, invece, lo spegne.
        urllib.request.urlopen(urllib.request.Request(
            BASE + '/api/congedo', data=b'{}',
            headers={'Content-Type': 'application/json'}), timeout=10).read()
        verifica('chiudendo la pagina il motore si spegne',
                 attendi_spegnimento(p, 40), indizio_pagina_aperta())
    finally:
        chiudi(p)

    # ------------------------------------------------------- si riparte
    print('\n[3] Si riparte da capo')
    p = avvia('--no-browser')
    try:
        verifica('dopo uno spegnimento si puo\' riavviare', attendi_avvio(p))
        verifica('il lucchetto non e\' rimasto bloccato', risponde(3))
    finally:
        chiudi(p)
        time.sleep(1)

    print('\n%s   %d superati, %d falliti'
          % ('TUTTO OK' if not fail else 'CI SONO ERRORI', ok, fail))
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
