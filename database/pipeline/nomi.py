# -*- coding: utf-8 -*-
"""Normalizzazione e abbinamento nomi fra listone Fantacalcio e fonti statistiche.

Regola guida: un abbinamento sbagliato e' peggio di un abbinamento mancato.
Ogni match produce un metodo e una confidenza; i casi dubbi restano non abbinati.
"""
import re, unicodedata

# Caratteri che NFKD non scompone e che ricorrono nei nomi del calcio europeo.
TRANSLIT = {
    'ø':'o', 'Ø':'o', 'å':'a', 'Å':'a', 'æ':'ae', 'Æ':'ae', 'œ':'oe', 'Œ':'oe',
    'ß':'ss', 'đ':'d', 'Đ':'d', 'ð':'d', 'Ð':'d', 'ł':'l', 'Ł':'l',
    'ı':'i', 'İ':'i', 'þ':'th', 'Þ':'th', 'ŋ':'n',
}

def strip_accents(s: str) -> str:
    s = ''.join(TRANSLIT.get(ch, ch) for ch in str(s))
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()

def norm(s: str) -> str:
    """Forma canonica: minuscolo, senza accenti, apostrofi e trattini come spazi."""
    s = strip_accents(s).lower()
    s = s.replace("'", ' ').replace('\u2019', ' ').replace('-', ' ').replace('.', ' ')
    return re.sub(r'\s+', ' ', s).strip()

def variants(s: str) -> set:
    """Varianti equivalenti di un nome: con spazi, senza apostrofi, tutto attaccato.

    Copre i casi reali: N'Dicka/Ndicka, Del Prato/Delprato, Hojlund/Hojlund.
    """
    base = norm(s)
    out = {base, base.replace(' ', '')}
    noap = re.sub(r'\s+', '', strip_accents(s).lower().replace("'", '').replace('.', ''))
    out.add(noap)
    return {v for v in out if v}

# 'Pellegrini Lo.'  'Pessina Mas.'  'Ederson D.S.'  'Martinez Jo.'
_SUFFISSO = re.compile(r'^(.*?)\s+((?:[A-Z][a-z]{0,2}\.)|(?:[A-Z]\.){1,3})$')

def split_fanta(nome: str):
    """Separa cognome e prefisso del nome proprio usato per disambiguare.

    'Pellegrini Lo.' -> ('pellegrini', 'lo')
    'N'Dicka'        -> ('n dicka',   None)
    """
    raw = str(nome).strip()
    m = _SUFFISSO.match(raw)
    if m:
        cognome = m.group(1)
        iniziali = re.sub(r'[^A-Za-z]', '', m.group(2)).lower()
        return cognome, iniziali
    return raw, None

def chiavi_understat(nome_completo: str) -> set:
    """Chiavi sotto cui indicizzare un giocatore della fonte statistica.

    Include cognome semplice, cognomi composti (2 e 3 token) e nome completo,
    ciascuno in tutte le sue varianti ortografiche.
    """
    toks = norm(nome_completo).split()
    if not toks:
        return set()
    candidati = {toks[-1], ' '.join(toks)}
    if len(toks) >= 2: candidati.add(' '.join(toks[-2:]))
    if len(toks) >= 3: candidati.add(' '.join(toks[-3:]))
    chiavi = set()
    for c in candidati:
        chiavi |= variants(c)
    return chiavi

def combacia_iniziale(nome_completo: str, iniziali: str) -> bool:
    """'Jo.' deve corrispondere a Josep; 'D.S.' a Ederson De Souza."""
    if not iniziali:
        return True
    toks = norm(nome_completo).split()
    if not toks:
        return False
    if toks[0].startswith(iniziali):
        return True
    # iniziali multiple: una lettera per token ('D.S.' -> De Souza)
    if len(iniziali) > 1 and len(toks) >= len(iniziali):
        if all(toks[i].startswith(iniziali[i]) for i in range(len(iniziali))):
            return True
    return False
