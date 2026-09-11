# -*- coding: utf-8 -*-
"""Il marchio di FantaHacked, disegnato invece che disegnato a mano.

Il segno e' la tesi del programma, non un ornamento: **tre rilanci che salgono
e una riga che li ferma.** La riga e' ambra perche' e' l'unico colore che nel
programma vuol dire "questo e' il numero che decide"; le barre sono grigio
azzurro come tutto il resto dell'interfaccia. A sedici pixel restano leggibili
tre tacche e un taglio, che e' quanto serve per riconoscere una scheda nella
barra delle applicazioni.

Perche' generato da uno script: le stesse proporzioni servono in sette misure
(dai 16 px della barra ai 512 dell'icona Android), e ridisegnarle a mano vuol
dire sette marchi leggermente diversi. Qui la geometria e' scritta una volta in
una griglia da 100, e ogni misura e' la stessa figura scalata.

Uso:  python build/marchio.py        riscrive icone e SVG
"""
import os

from PIL import Image, ImageDraw

QUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(QUI)

# --- la geometria, in una griglia da 100 ---------------------------------
FONDO = (23, 30, 40, 255)          # --rilievo: si stacca anche su una barra scura
BARRA = (143, 163, 184, 255)       # grigio azzurro dell'interfaccia
AMBRA = (245, 182, 63, 255)        # --ambra: il limite

RAGGIO = 22.0                      # angoli del quadrato, in centesimi
BASE_Y = 79.0                      # dove poggiano le barre
LARGA = 14.0                       # larghezza di una barra
PASSO = 23.0                       # da una barra all'altra
PRIMA_X = 20.0
ALTEZZE = (20.0, 34.0, 48.0)       # i tre rilanci
LINEA_Y = 25.0                     # il muro: il terzo si ferma appena sotto
LINEA_SPESSA = 6.5
LINEA_DA, LINEA_A = 11.0, 89.0


def disegna(lato, sfondo=True):
    """Il marchio a `lato` pixel. Disegnato in grande e ridotto: gli angoli
    arrotondati e i bordi delle barre restano puliti anche a 16 px."""
    su = 8 if lato <= 64 else 4
    n = lato * su
    k = n / 100.0
    img = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if sfondo:
        d.rounded_rectangle([0, 0, n - 1, n - 1], radius=RAGGIO * k, fill=FONDO)

    raggio_barra = LARGA * k / 2.6
    for i, alt in enumerate(ALTEZZE):
        x0 = (PRIMA_X + i * PASSO) * k
        x1 = x0 + LARGA * k
        y1 = BASE_Y * k
        y0 = (BASE_Y - alt) * k
        d.rounded_rectangle([x0, y0, x1, y1], radius=raggio_barra, fill=BARRA)

    mezzo = LINEA_SPESSA * k / 2.0
    d.rounded_rectangle([LINEA_DA * k, LINEA_Y * k - mezzo,
                         LINEA_A * k, LINEA_Y * k + mezzo],
                        radius=mezzo, fill=AMBRA)
    return img.resize((lato, lato), Image.LANCZOS)


SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"
     role="img" aria-label="FantaHacked">
  <title>FantaHacked</title>
  <!-- Tre rilanci che salgono, e la riga che li ferma. -->
  %(sfondo)s
  <g fill="%(barra)s">
%(barre)s
  </g>
  <rect x="%(lda)s" y="%(ly)s" width="%(llarga)s" height="%(lsp)s"
        rx="%(lr)s" fill="%(ambra)s"/>
</svg>
'''


def _esa(c):
    return '#%02x%02x%02x' % c[:3]


def svg(con_sfondo=True):
    barre = []
    for i, alt in enumerate(ALTEZZE):
        barre.append(
            '    <rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f"/>'
            % (PRIMA_X + i * PASSO, BASE_Y - alt, LARGA, alt, LARGA / 2.6))
    sfondo = ('<rect width="100" height="100" rx="%.0f" fill="%s"/>'
              % (RAGGIO, _esa(FONDO))) if con_sfondo else ''
    return SVG % {
        'sfondo': sfondo,
        'barra': _esa(BARRA),
        'barre': '\n'.join(barre),
        'ambra': _esa(AMBRA),
        'lda': LINEA_DA,
        'ly': LINEA_Y - LINEA_SPESSA / 2,
        'llarga': LINEA_A - LINEA_DA,
        'lsp': LINEA_SPESSA,
        'lr': LINEA_SPESSA / 2,
    }


def _rett_arrotondato(x, y, w, h, r):
    """Un rettangolo arrotondato come dato di percorso: lo capiscono sia SVG
    sia il formato vettoriale di Android, che e' la stessa sintassi."""
    r = min(r, w / 2.0, h / 2.0)
    return ('M%.2f,%.2f h%.2f a%.2f,%.2f 0 0 1 %.2f,%.2f v%.2f '
            'a%.2f,%.2f 0 0 1 %.2f,%.2f h%.2f a%.2f,%.2f 0 0 1 %.2f,%.2f '
            'v%.2f a%.2f,%.2f 0 0 1 %.2f,%.2f Z'
            % (x + r, y, w - 2 * r, r, r, r, r, h - 2 * r,
               r, r, -r, r, -(w - 2 * r), r, r, -r, -r,
               -(h - 2 * r), r, r, r, -r))


VETTORE = '''<?xml version="1.0" encoding="utf-8"?>
<!-- Il marchio: tre rilanci che salgono e la riga che li ferma.
     Generato da build/marchio.py, la stessa geometria delle altre misure.
     Disegnato dentro il riquadro sicuro di 72dp su 108: fuori di li' il
     sistema ritaglia, e su certi telefoni gli angoli sparirebbero. -->
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
%(paths)s
</vector>
'''


def vettore_android():
    k, off = 0.68, 20.0
    m = lambda v: off + k * v                                    # noqa: E731
    fuori = []
    for i, alt in enumerate(ALTEZZE):
        fuori.append(
            '    <path android:fillColor="%s" android:pathData="%s" />'
            % (_esa(BARRA),
               _rett_arrotondato(m(PRIMA_X + i * PASSO), m(BASE_Y - alt),
                                 k * LARGA, k * alt, k * LARGA / 2.6)))
    fuori.append(
        '    <path android:fillColor="%s" android:pathData="%s" />'
        % (_esa(AMBRA),
           _rett_arrotondato(m(LINEA_DA), m(LINEA_Y - LINEA_SPESSA / 2),
                             k * (LINEA_A - LINEA_DA), k * LINEA_SPESSA,
                             k * LINEA_SPESSA / 2)))
    return VETTORE % {'paths': '\n'.join(fuori)}


def scrivi(dove_android=None):
    misure = [16, 24, 32, 48, 64, 128, 256]
    icone = [disegna(m) for m in misure]
    ico = os.path.join(BASE, 'app', 'fantahacked.ico')
    icone[-1].save(ico, format='ICO',
                   sizes=[(m, m) for m in misure])
    print('scritto', ico)

    for nome, dim in (('marchio-192.png', 192), ('marchio-512.png', 512)):
        p = os.path.join(BASE, 'app', 'web', nome)
        disegna(dim).save(p)
        print('scritto', p)

    # `newline='\n'` e non il predefinito: su Windows quello scriverebbe CRLF,
    # e questi file finiscono dentro il pacchetto che si scarica. Windows
    # Defender ha gia' segnalato una volta un file dell'interfaccia **nella
    # versione CRLF** e non in quella LF, a parita' di ogni altro byte: e'
    # `.gitattributes` a dire che qui dentro si scrive LF, e chi genera file
    # deve rispettarlo come tutti gli altri.
    p = os.path.join(BASE, 'app', 'web', 'marchio.svg')
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(svg())
    print('scritto', p)

    # Lo stesso marchio, senza sfondo: serve nell'intestazione, dove il fondo
    # ce l'ha gia' la pagina.
    p = os.path.join(BASE, 'app', 'web', 'marchio-piatto.svg')
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(svg(con_sfondo=False))
    print('scritto', p)

    if dove_android and os.path.isdir(dove_android):
        web = os.path.join(dove_android, 'web')
        for nome, dim in (('marchio-192.png', 192), ('marchio-512.png', 512)):
            disegna(dim).save(os.path.join(web, nome))
            print('scritto', os.path.join(web, nome))
        for nome, con in (('marchio.svg', True), ('marchio-piatto.svg', False)):
            with open(os.path.join(web, nome), 'w', encoding='utf-8',
                      newline='\n') as f:
                f.write(svg(con_sfondo=con))
            print('scritto', os.path.join(web, nome))
        # L'icona dell'applicazione Android: il sistema ci mette lui lo sfondo
        # e ritaglia il primo piano, quindi il segno va disegnato piu' piccolo
        # dentro il quadrato, se no i bordi vengono tagliati via.
        res = os.path.join(dove_android, 'app', 'src', 'main', 'res')
        for cartella, dim in (('mipmap-mdpi', 48), ('mipmap-hdpi', 72),
                              ('mipmap-xhdpi', 96), ('mipmap-xxhdpi', 144),
                              ('mipmap-xxxhdpi', 192)):
            d = os.path.join(res, cartella)
            if not os.path.isdir(d):
                os.makedirs(d)
            disegna(dim).save(os.path.join(d, 'ic_launcher.png'))
            disegna(dim).save(os.path.join(d, 'ic_launcher_round.png'))
        print('scritte le icone mipmap in', res)

        p = os.path.join(res, 'drawable', 'ic_launcher_foreground.xml')
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write(vettore_android())
        print('scritto', p)
        p = os.path.join(res, 'values', 'ic_launcher_background.xml')
        with open(p, 'w', encoding='utf-8', newline='\n') as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
                    '    <color name="ic_launcher_background">%s</color>\n'
                    '</resources>\n' % _esa(FONDO))
        print('scritto', p)


if __name__ == '__main__':
    import sys
    android = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(BASE), 'FantaHacked-Android')
    scrivi(android)
