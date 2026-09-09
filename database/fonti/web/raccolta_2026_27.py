# -*- coding: utf-8 -*-
"""Raccolta dal web delle informazioni che il database non aveva: chi gioca.

Il database di partenza sapeva tutto del passato (minuti, xG, voti di tre
stagioni) e niente del presente: la colonna `titolarita` era vuota, i rigoristi
erano dedotti dai rigori calciati l'anno prima &mdash; cioe' spesso in un'altra
squadra &mdash; e di ballottaggi non c'era traccia. Sono esattamente le cose
che decidono un'asta, e nessuna si ricava dalle statistiche.

Qui stanno **le estrazioni grezze**, una per fonte, cosi' come sono state
lette dalle pagine il 3 settembre 2026. Non sono un'opinione del programma:
sono cinque guide indipendenti, trascritte com'erano. Il consenso fra loro lo
calcola `database/pipeline/consenso.py`, che e' il posto giusto perche' li'
si vede anche **quanto** sono d'accordo, ed e' quel numero a diventare la
certezza mostrata in asta.

Perche' cinque e non una: le guide si contraddicono, e non poco. Sull'attacco
del Bologna una dice Piccoli e un'altra Dovbyk; sul Como una dice Kean e
un'altra Douvikas. Prendere una fonte sola vuol dire ereditarne gli errori
senza accorgersene; prenderne cinque vuol dire sapere **dove** il dubbio c'e'
davvero, e quello e' precisamente cio' che serve sapere quando si rilancia.

Uso:  python raccolta_2026_27.py     riscrive i CSV normalizzati qui accanto
"""
import csv, os, re

QUI = os.path.dirname(os.path.abspath(__file__))

DATA_RACCOLTA = '2026-09-03'

FONTI = {
    'fantacalcio.it': {
        'url': 'https://www.fantacalcio.it/probabili-formazioni-serie-a',
        'tipo': 'probabili formazioni della giornata, con percentuali di ballottaggio',
        'peso': 2.0,   # e' la piu' vicina al campo: e' la formazione di domani
        'nota': 'giornata 3; tre partite non erano nella pagina letta',
    },
    'fantacalcio-online': {
        'url': 'https://www.fantacalcio-online.com/it/consigli-fantacalcio/'
               'formazioni-tipo-serie-a-2026-2027',
        'tipo': 'consenso dichiarato di dieci guide, con percentuali',
        'peso': 1.5,
        'nota': 'riporta solo le maglie su cui le guide si esprimono',
    },
    'sosfanta': {
        'url': 'https://www.sosfanta.com/asta-fantacalcio/'
               'seriea-tutte-formazioni-tipo-fantacalcio-2026-2027-asta-consigli-chi-prendere/',
        'tipo': 'formazioni tipo per l\'asta, con le alternative',
        'peso': 1.0, 'nota': '',
    },
    'calciodangolo': {
        'url': 'https://calciodangolo.com/'
               'fantacalcio-come-giocherebbero-oggi-formazioni-tipo-serie-a-2026-2027/',
        'tipo': 'formazioni tipo "come giocherebbero oggi"',
        'peso': 1.0, 'nota': '',
    },
    'fantamaster': {
        'url': 'https://www.fantamaster.it/'
               'probabili-formazioni-seriea-2026-2027-moduli-titolari-ballottaggi/',
        'tipo': 'probabili formazioni con i ballottaggi aperti',
        'peso': 1.0, 'nota': '',
    },
    'fantamaster-g3': {
        'url': 'https://www.fantamaster.it/probabili-formazioni-3-giornata-'
               'seriea-2026-2027-titolari-ballottaggi-ultime-dai-campi/',
        'tipo': 'probabili formazioni della giornata',
        'peso': 2.0,
        'nota': 'copre le sei squadre che mancavano nella pagina di fantacalcio.it',
    },
    'fantacalcio.it-infortuni': {
        'url': 'https://www.fantacalcio.it/infortunati-serie-a',
        'tipo': 'infortunati e indisponibili', 'peso': 1.0, 'nota': '',
    },
    'goal.com': {
        'url': 'https://www.goal.com/it/liste/fantacalcio-rigoristi-serie-a-2026-2027-'
               'tiratori-e-gerarchie-dal-dischetto-delle-20-squadre-del-campionato/'
               'bltdebca56c3bd91419',
        'tipo': 'gerarchie dal dischetto', 'peso': 1.0, 'nota': '',
    },
    'fantamaster-rigori': {
        'url': 'https://www.fantamaster.it/'
               'rigoristi-seriea-fantacalcio-2026-2027-gerarchie-20-squadre/',
        'tipo': 'gerarchie dal dischetto', 'peso': 1.0, 'nota': '',
    },
}


# ===================================================== formazioni titolari
# Una riga per squadra: (squadra, modulo, 'undici separato da virgole').
# Trascritte verbatim: i nomi si abbinano al listone dopo, e chi non si
# abbina finisce nelle lacune invece di essere aggiustato a mano.

TITOLARI = {

'fantacalcio.it': [
 ('Genoa', '3-4-2-1', 'Bijlow, Marcandalli, Ostigard, Vasquez, Ellertsson, Frendrup, Sow, Mitaj, Baldanzi, Vitinha O., Colombo'),
 ('Como', '4-2-3-1', 'Butez, Couto, Chalobah T., Ramon, Valle, Da Cunha, Perrone, Diao, Paz N., Baturina, Kean'),
 ('Fiorentina', '4-3-2-1', 'De Gea, Jimenez A., Dragusin, Viery, Valdepenas, Ndour, Oulai, Atta, Mastantuono, Njie, Pellegrino M.'),
 ('Torino', '3-4-2-1', 'Perri, Comuzzo, Coco, Comert, Belghali, Gineitis, Fitz-Jim, Cacciamani, Adams C., Vlasic, Simeone'),
 ('Inter', '3-5-2', 'Martinez Jo., Bisseck, Akanji, Bastoni, Diouf, Barella, Calhanoglu, Zielinski, Dimarco, Martinez L., Esposito F.P.'),
 ('Napoli', '4-3-3', 'Meret, Di Lorenzo, Rrahmani, Marin R., Spinazzola, Zambo Anguissa, Lobotka, De Bruyne, Politano, Hojlund, Santos A.'),
 ('Roma', '3-4-2-1', 'Svilar, Mancini, Ghilardi, Hermoso, Molina N., Kone M., Cristante, Wesley, Dybala, Mora, Malen'),
 ('Atalanta', '4-3-3', 'Carnesecchi, Bellanova, Kossounou, Scalvini, Bernasconi, Samardzic, Gaetano, Ederson D.S., De Ketelaere, Scamacca, Rowe'),
 ('Frosinone', '4-2-3-1', 'Palmisani, Oyono A., Calvani, Monterisi, Bracaglia, Masini, Calo, Fini, Schmid, Kvernadze, Raimondo'),
 ('Venezia', '3-5-2', 'Stankovic F., Schingtienne, Bella-Kotchap, Halhal, Mazzocchi, Perez K., Busio, Basic, Haps, Yeboah J., Adams A.'),
 ('Parma', '3-5-2', 'Corvi, Delprato, Troilo, Diego Carlos, Britschgi, Bernabe, Keita M., Ordonez C., Valeri, Romero D., Toure E.'),
 ('Monza', '3-4-2-1', 'Tornqvist, Ziolkowski, Lucchesi, Carboni A., Birindelli, Akinsanmiro, Folorunsho, Mangas, Colpani, Ngonge, Cutrone'),
 ('Bologna', '4-3-3', 'Skorupski, Zortea, Heggem, Theate, Miranda J., Odgaard, Ferguson, Pobega, Bernardeschi, Piccoli, Cambiaghi'),
 ('Sassuolo', '4-3-3', 'Muric, Van Der Brempt, Idzes, Leysen F., Doig, Adzic, Matic, Bakola, Berardi, Bowie, Lauriente'),
],

'fantamaster-g3': [
 ('Juventus', '4-2-3-1', 'Vicario, Kalulu, Bremer, Lucumi, Celik, Douglas Luiz, Locatelli, Conceicao, Nico Gonzalez, Boga, Kolo Muani'),
 ('Milan', '3-4-2-1', 'Maignan, Gila, De Winter, Pavlovic, Chukwueze, Musah, Modric, Bartesaghi, Rabiot, Cisse, Goncalo Ramos'),
 ('Cagliari', '4-3-3', 'Caprile, Ze Pedro, Deiola, Rodriguez, Obert, Adopo, Winks, Romano, Maldini, Mendy, Fazzini'),
 ('Lecce', '3-5-2', 'Falcone, Tiago Gabriel, Gaspar, Siebert, Veiga, Coulibaly, Ilic, Gorter, Gallo, Pierotti, Stulic'),
 ('Udinese', '3-4-2-1', 'Okoye, Abankwah, Kabasele, Solet, Vojvoda, Piotrowski, Karlstrom, Kamara, Unai Gomez, Ekkelenkamp, Davis'),
 ('Lazio', '4-3-3', 'Mandas, Floriani Mussolini, Doekhi, Provstgaard, Nuno Tavares, Taylor, Belahyane, Frattesi, Gudmundsson, Pinamonti, Zaccagni'),
],

'sosfanta': [
 ('Atalanta', '4-3-3', 'Carnesecchi, Zappacosta, Kristensen, Scalvini, Bernasconi, Kessie, Gaetano, Ederson, De Ketelaere, Scamacca, Rowe'),
 ('Bologna', '4-3-3', 'Skorupski, Zortea, Heggem, Theate, Miranda, Pobega, Moro, Odgaard, Orsolini, Dovbyk, Cambiaghi'),
 ('Cagliari', '4-3-3', 'Caprile, Ze Pedro, Mina, Rodriguez, Obert, Adopo, Winks, Romano, Maldini, Kevin Carlos, Fazzini'),
 ('Como', '4-2-3-1', 'Butez, Couto, Ramon, Chalobah, Valle, Perrone, Da Cunha, Baturina, Paz, Diao, Douvikas'),
 ('Fiorentina', '4-3-3', 'De Gea, Jimenez, Dragusin, Viery, Valdepenas, Atta, Oulai, Ndour, Mastantuono, Beto, Pedro Goncalves'),
 ('Frosinone', '4-2-3-1', 'Palmisani, Tchato, Calvani, Monterisi, Bracaglia, Calo, Grillitsch, Kvernadze, Schmid, Ghedjemis, Raimondo'),
 ('Genoa', '3-4-2-1', 'Bijlow, Marcandalli, Ostigard, Vasquez, Drameh, Sow, Frendrup, Mitaj, Baldanzi, El Shaarawy, Colombo'),
 ('Inter', '3-5-2', 'Martinez, Akanji, Stones, Bastoni, Diouf, Barella, Calhanoglu, Jones, Dimarco, Martinez L., Thuram'),
 ('Juventus', '4-2-3-1', 'Vicario, Kalulu, Bremer, Lucumi, Celik, Douglas Luiz, Locatelli, Conceicao, Mckennie, Yildiz, Kolo Muani'),
 ('Lazio', '4-3-3', 'Mandas, Marusic, Provstgaard, Tavares, Rovella, Frattesi, Taylor, Isaksen, Pinamonti, Zaccagni, Motta'),
 ('Lecce', '4-3-3', 'Falcone, Veiga, Tiago Gabriel, Gaspar, Gallo, Coulibaly, Ilic, Gorter, Pierotti, Geubbels, Monteiro'),
 # 'Dybala' nella fonte originale: e' un errore della pagina (gioca alla
 # Roma, non al Milan, ed e' infatti nella formazione Roma qui sotto). Tolto
 # invece di abbinarlo per non inquinare la squadra sbagliata.
 ('Milan', '3-4-2-1', 'Maignan, Gila, De Winter, Pavlovic, Chukwueze, Rabiot, Modric, Moreira, Pulisic, Ramos'),
 ('Monza', '3-4-2-1', 'Tornqvist, Goglichidze, Ziolkowski, Carboni, Toure, Folorunsho, Pessina, Mangas, Colpani, Cutrone, Varela'),
 ('Napoli', '4-3-3', 'Meret, Di Lorenzo, Rrahmani, Badiashile, Spinazzola, De Bruyne, Lobotka, Mctominay, Politano, Hojlund, Santos'),
 ('Parma', '4-3-3', 'Corvi, Delprato, Troilo, Diego Carlos, Valeri, Bernabe, Keita, Fabbian, Lontani, Romero, Toure'),
 ('Roma', '4-3-3', 'Svilar, Mancini, N\'dicka, Hermoso, Molina, Cristante, Kone, Wesley, Dybala, Mora, Malen'),
 ('Sassuolo', '4-2-3-1', 'Muric, Van Der Brempt, Idzes, Leysen, Obrador, Matic, Bakola, Berardi, Thorstvedt, Lauriente, Esposito'),
 ('Torino', '3-4-2-1', 'Perri, Comuzzo, Coco, Rodriguez, Belghali, Mandragora, Fitz-Jim, Cacciamani, Casadei, Vlasic, Simeone'),
 ('Udinese', '3-4-2-1', 'Okoye, Abankwah, Kabasele, Solet, Vojvoda, Piotrowski, Karlstrom, Kamara, Zaniolo, Ekkelenkamp, Davis'),
 ('Venezia', '3-5-2', 'Stankovic, Schingtienne, Bella-Kotchap, Juan Jesus, Mazzocchi, Sohm, Busio, Basic, Haps, Adams, Yeboah'),
],

'calciodangolo': [
 ('Atalanta', '4-3-3', 'Carnesecchi, Bellanova, Kristensen, Scalvini, Zalewski, Kessie, Gaetano, Ederson, De Ketelaere, Scamacca, Rowe'),
 ('Bologna', '4-2-3-1', 'Skorupski, Zortea, Heggem, Theate, Miranda, Amondarain, Ferguson, Orsolini, Bernardeschi, Cambiaghi, Dovbyk'),
 ('Cagliari', '4-3-2-1', 'Caprile, Ze Pedro, Mina, Rodriguez, Obert, Adopo, Romano, Winks, Maldini, Fazzini, Kevin Carlos'),
 ('Como', '4-2-3-1', 'Butez, Couto, Ramon, Chalobah, Valle, Perrone, Da Cunha, Diao, Paz, Baturina, Kean'),
 ('Fiorentina', '4-3-2-1', 'De Gea, Jimenez, Dragusin, Viery, Valdepenas, Ndour, Oulai, Atta, Mastantuono, Goncalves, Pellegrino'),
 ('Frosinone', '4-3-3', 'Palmisani, Tchato, Monterisi, Calvani, Terzic, Grillitsch, Calo, Masini, Schmid, Bobcek, Kvernadze'),
 ('Genoa', '3-4-2-1', 'Bijlow, Marcandalli, Ostigard, Vasquez, Drameh, Frendrup, Sow, Mitaj, Baldanzi, Vitinha, Colombo'),
 ('Inter', '3-5-2', 'Martinez Jo., Akanji, Stones, Bastoni, Spence, Barella, Calhanoglu, Jones, Dimarco, Thuram, Martinez L.'),
 ('Juventus', '4-2-3-1', 'Vicario, Kalulu, Bremer, Lucumi, Celik, Locatelli, Sarr, Conceicao, Woltemade, Yildiz, Kolo Muani'),
 ('Lazio', '4-3-3', 'Motta, Marusic, Doekhi, Sutalo, Pedraza, Frattesi, Rovella, Taylor, Isaksen, Pinamonti, Zaccagni'),
 ('Lecce', '4-3-3', 'Falcone, Veiga, Gaspar, Tiago Gabriel, Gallo, Coulibaly, Ilic, Ngom, Pierotti, Geubbels, Monteiro'),
 ('Milan', '3-4-2-1', 'Maignan, Gila, Gabbia, Pavlovic, Chukwueze, Modric, Rabiot, Estupinan, Hutchinson, Pulisic, Ramos'),
 ('Monza', '3-4-2-1', 'Tornqvist, Ziolkowski, Goglichidze, Carboni, Birindelli, Pessina, Folorunsho, Mangas, Ngonge, Zeballos, Varela'),
 ('Napoli', '4-3-3', 'Meret, Di Lorenzo, Rrahmani, Badiashile, Spinazzola, Anguissa, Lobotka, McTominay, Politano, Hojlund, Santos'),
 ('Parma', '4-3-3', 'Corvi, Delprato, Troilo, Diego Carlos, Valeri, Bernabe, Keita, Fabbian, Almqvist, Romero, Toure'),
 ('Roma', '3-4-2-1', 'Svilar, Mancini, N\'dicka, Hermoso, Molina, Cristante, Kone, Wesley, Dybala, Mora, Malen'),
 # 'Pinamonti' nella fonte originale: e' un errore della pagina (gioca alla
 # Lazio, non al Sassuolo). Tolto per la stessa ragione di sopra.
 ('Sassuolo', '4-3-3', 'Muric, Van Der Brempt, Walukiewicz, Idzes, Obrador, Bakola, Matic, Adzic, Berardi, Lauriente'),
 ('Torino', '3-4-2-1', 'Perri, Coco, Comert, Comuzzo, Belghali, Fitz-Jim, Mandragora, Fortini, Vlasic, Casadei, Simeone'),
 ('Udinese', '3-5-2', 'Okoye, Bertola, Kabasele, Solet, Vojvoda, Ekkelenkamp, Karlstrom, Piotrowski, Kamara, Zaniolo, Davis'),
 ('Venezia', '3-5-2', 'Stankovic, Schingtienne, Bella-Kotchap, Juan Jesus, Hainaut, Basic, Perez, Sohm, Correia, Adams, Yeboah'),
],

'fantamaster': [
 ('Atalanta', '4-3-3', 'Carnesecchi, Zappacosta, Kristensen, Scalvini, Bernasconi, Ederson, Gaetano, Kessie, De Ketelaere, Scamacca, Raspadori'),
 ('Bologna', '4-3-3', 'Skorupski, Zortea, Theate, Heggem, Miranda, Ferguson, Amondarain, Bernardeschi, Orsolini, Piccoli, Cambiaghi'),
 ('Cagliari', '4-3-2-1', 'Caprile, Sugawara, Mina, Rodriguez, Obert, Adopo, Winks, Romano, Fazzini, Maldini, Kevin Carlos'),
 ('Como', '4-2-3-1', 'Butez, Couto, Ramon, Chalobah, Valle, Milla, Da Cunha, Diao, Paz, Baturina, Kean'),
 ('Fiorentina', '4-3-2-1', 'De Gea, Jimenez, Dragusin, Pongracic, Valdepenas, Atta, Fagioli, Ndour, Mastantuono, Goncalves, Pellegrino'),
 ('Frosinone', '4-2-3-1', 'Palmisani, Oyono, Calvani, Monterisi, Bracaglia, Calo, Masini, Fini, Schmid, Raimondo, Kvernadze'),
 ('Genoa', '3-4-2-1', 'Bijlow, Marcandalli, Ostigard, Vasquez, Drameh, Frendrup, Sow, Ellertsson, Baldanzi, Vitinha, Colombo'),
 ('Inter', '3-5-2', 'Martinez, Bisseck, Akanji, Bastoni, Spence, Barella, Calhanoglu, Zielinski, Dimarco, Martinez L., Thuram'),
 ('Juventus', '4-2-3-1', 'Vicario, Kalulu, Bremer, Lucumi, Celik, Locatelli, Douglas Luiz, Conceicao, McKennie, Boga, Kolo Muani'),
 ('Lazio', '4-3-3', 'Mandas, Marusic, Sutalo, Provstgaard, Nuno Tavares, Frattesi, Rovella, Taylor, Gudmundsson, Pinamonti, Zaccagni'),
 ('Lecce', '4-2-3-1', 'Falcone, Veiga, Gaspar, Tiago Gabriel, Gallo, Ilic, Coulibaly, Pierotti, Gorter, N\'dri, Stulic'),
 ('Milan', '3-4-2-1', 'Maignan, Gila, Gabbia, Pavlovic, Chukwueze, Modric, Musah, Bartesaghi, Rabiot, Pulisic, Ramos'),
 ('Monza', '3-4-2-1', 'Tornqvist, Kouadio, Ziolkowski, Carboni, Birindelli, Folorunsho, Mout, Mangas, Colpani, Cutrone, Varela'),
 ('Napoli', '4-3-3', 'Meret, Di Lorenzo, Rrahmani, Badiashile, Spinazzola, Anguissa, Lobotka, McTominay, Politano, Hojlund, Santos'),
 ('Parma', '4-3-2-1', 'Corvi, Delprato, Troilo, Diego Carlos, Valeri, Bernabe, Keita, Fabbian, Toure, Lontani, Romero'),
 ('Roma', '3-4-2-1', 'Svilar, Mancini, N\'dicka, Hermoso, Molina, Cristante, Kone, Wesley, Mora, Dybala, Malen'),
 ('Sassuolo', '4-3-3', 'Muric, Van Der Brempt, Leysen, Idzes, Doig, Bakola, Matic, Adzic, Berardi, Bowie, Lauriente'),
 ('Torino', '3-4-2-1', 'Perri, Comuzzo, Comert, Coco, Belghali, Mandragora, Fitz-Jim, Cacciamani, Vlasic, Casadei, Simeone'),
 ('Udinese', '3-5-2', 'Okoye, Abankwah, Kabasele, Solet, Vojvoda, Ekkelenkamp, Karlstrom, Piotrowski, Kamara, Zaniolo, Davis'),
 ('Venezia', '3-5-2', 'Stankovic, Bella-Kotchap, Schingtienne, Juan Jesus, Mazzocchi, Basic, Busio, Sohm, Haps, Adams, Yeboah'),
],

}


# ====================================================== ballottaggi aperti
# (fonte, squadra, giocatore_a, giocatore_b, pct_a, pct_b)
# Il ballottaggio e' la forma piu' pura di coppia complementare: due giocatori
# per una maglia sola. Quando gioca l'uno non gioca l'altro, e se li prendi
# tutti e due quella maglia e' tua comunque.

BALLOTTAGGI = [
 ('fantacalcio.it', 'Genoa', 'Vitinha O.', 'Osmajic', 60, 40),
 ('fantacalcio.it', 'Como', 'Couto', 'Smolcic I.', 60, 40),
 ('fantacalcio.it', 'Como', 'Valle', 'Kaiki', 60, 40),
 ('fantacalcio.it', 'Como', 'Kean', 'Douvikas', 55, 45),
 ('fantacalcio.it', 'Fiorentina', 'Jimenez A.', 'Joao Mario', 55, 45),
 ('fantacalcio.it', 'Fiorentina', 'Viery', 'Ranieri L.', 55, 45),
 ('fantacalcio.it', 'Fiorentina', 'Njie', 'Gnonto', 60, 40),
 ('fantacalcio.it', 'Torino', 'Gineitis', 'Mandragora', 55, 45),
 ('fantacalcio.it', 'Torino', 'Cacciamani', 'Fortini', 60, 40),
 ('fantacalcio.it', 'Torino', 'Adams C.', 'Oristanio', 60, 40),
 ('fantacalcio.it', 'Inter', 'Zielinski', 'Jones C.', 60, 40),
 ('fantacalcio.it', 'Inter', 'Esposito F.P.', 'Thuram', 55, 45),
 ('fantacalcio.it', 'Napoli', 'Marin R.', 'Beukema', 60, 40),
 ('fantacalcio.it', 'Napoli', 'Spinazzola', 'Olivera', 60, 40),
 ('fantacalcio.it', 'Roma', 'Molina N.', 'Lulli', 55, 45),
 ('fantacalcio.it', 'Roma', 'Mora', 'Soule', 60, 40),
 ('fantacalcio.it', 'Atalanta', 'Bellanova', 'Zappacosta', 60, 40),
 ('fantacalcio.it', 'Atalanta', 'Samardzic', 'Pasalic', 55, 45),
 ('fantacalcio.it', 'Atalanta', 'Scamacca', 'Krstovic', 60, 40),
 ('fantacalcio.it', 'Frosinone', 'Schmid', 'Cichella', 60, 40),
 ('fantacalcio.it', 'Venezia', 'Mazzocchi', 'Hainaut', 55, 45),
 ('fantacalcio.it', 'Venezia', 'Haps', 'Correia T.', 60, 40),
 ('fantacalcio.it', 'Parma', 'Romero D.', 'Lontani', 55, 45),
 ('fantacalcio.it', 'Monza', 'Ziolkowski', 'Kouadio', 60, 40),
 ('fantacalcio.it', 'Monza', 'Ngonge', 'Mout', 60, 40),

 ('fantacalcio-online', 'Atalanta', 'Rowe', 'Raspadori', 65, 40),
 ('fantacalcio-online', 'Atalanta', 'Kessie', 'Samardzic', 73, 29),
 ('fantacalcio-online', 'Atalanta', 'Kristensen', 'Kossounou', 74, 11),
 ('fantacalcio-online', 'Atalanta', 'Bernasconi', 'Kolasinac', 67, 10),
 ('fantacalcio-online', 'Bologna', 'Zortea', 'Holm', 62, 38),
 ('fantacalcio-online', 'Cagliari', 'Kevin Carlos', 'Nzola', 67, 17),
 ('fantacalcio-online', 'Como', 'Kean', 'Douvikas', 62, 46),
 ('fantacalcio-online', 'Como', 'Kaiki', 'Valle', 50, 42),
 ('fantacalcio-online', 'Fiorentina', 'Beto', 'Pellegrino', 58, 51),
 ('fantacalcio-online', 'Fiorentina', 'Oulai', 'Fagioli', 67, 38),
 ('fantacalcio-online', 'Fiorentina', 'Goncalves', 'Njie', 62, 38),
 ('fantacalcio-online', 'Genoa', 'Ellertsson', 'Mitaj', 77, 43),
 ('fantacalcio-online', 'Inter', 'Jones', 'Zielinski', 56, 42),
 ('fantacalcio-online', 'Inter', 'Akanji', 'Stones', 96, 69),
 ('fantacalcio-online', 'Lazio', 'Doekhi', 'Sutalo', 69, 61),
 ('fantacalcio-online', 'Lazio', 'Pinamonti', 'Isaksen', 85, 68),
 ('fantacalcio-online', 'Lecce', 'Monteiro', 'Fatah', 50, 19),
 ('fantacalcio-online', 'Milan', 'Pulisic', 'Saelemaekers', 92, 38),
 ('fantacalcio-online', 'Monza', 'Tornqvist', 'Thiam', 58, 42),
 ('fantacalcio-online', 'Monza', 'Ngonge', 'Colpani', 59, 44),
 ('fantacalcio-online', 'Napoli', 'Badiashile', 'Beukema', 68, 21),
 ('fantacalcio-online', 'Napoli', 'Anguissa', 'De Bruyne', 65, 58),
 ('fantacalcio-online', 'Napoli', 'Politano', 'Neres', 67, 10),
 ('fantacalcio-online', 'Parma', 'Corvi', 'Daffara', 58, 42),
 ('fantacalcio-online', 'Parma', 'Fabbian', 'Lontani', 56, 47),
 ('fantacalcio-online', 'Sassuolo', 'Adzic', 'Bakola', 74, 65),
 ('fantacalcio-online', 'Torino', 'Cacciamani', 'Belghali', 71, 52),
 ('fantacalcio-online', 'Torino', 'Casadei', 'Adams', 72, 18),
 ('fantacalcio-online', 'Udinese', 'Kabasele', 'Palma', 95, 41),
 ('fantacalcio-online', 'Udinese', 'Piotrowski', 'Miller', 61, 28),
 ('fantacalcio-online', 'Venezia', 'Correia', 'Hainaut', 72, 68),
 ('fantacalcio-online', 'Venezia', 'Sohm', 'Perez', 56, 54),

 ('fantamaster', 'Atalanta', 'Zappacosta', 'Bellanova', None, None),
 ('fantamaster', 'Atalanta', 'Kessie', 'Pasalic', None, None),
 ('fantamaster', 'Atalanta', 'Scamacca', 'Krstovic', None, None),
 ('fantamaster', 'Bologna', 'Zortea', 'Holm', None, None),
 ('fantamaster', 'Bologna', 'Amondarain', 'Pobega', None, None),
 ('fantamaster', 'Bologna', 'Piccoli', 'Dovbyk', None, None),
 ('fantamaster', 'Cagliari', 'Fazzini', 'Fadera', None, None),
 ('fantamaster', 'Cagliari', 'Kevin Carlos', 'Nzola', None, None),
 ('fantamaster', 'Como', 'Valle', 'Kaiki', None, None),
 ('fantamaster', 'Como', 'Kean', 'Douvikas', None, None),
 ('fantamaster', 'Fiorentina', 'Pongracic', 'Viery', None, None),
 ('fantamaster', 'Fiorentina', 'Fagioli', 'Oulai', None, None),
 ('fantamaster', 'Fiorentina', 'Pellegrino', 'Beto', None, None),
 ('fantamaster', 'Frosinone', 'Calo', 'Grillitsch', None, None),
 ('fantamaster', 'Frosinone', 'Fini', 'Zerbin', None, None),
 ('fantamaster', 'Genoa', 'Baldanzi', 'Traore', None, None),
 ('fantamaster', 'Genoa', 'Vitinha', 'El Shaarawy', None, None),
 ('fantamaster', 'Inter', 'Bisseck', 'Stones', None, None),
 ('fantamaster', 'Inter', 'Zielinski', 'Sucic', None, None),
 ('fantamaster', 'Inter', 'Thuram', 'Esposito F.P.', None, None),
 ('fantamaster', 'Juventus', 'Douglas Luiz', 'Sarr', None, None),
 ('fantamaster', 'Juventus', 'Kolo Muani', 'Woltemade', None, None),
 ('fantamaster', 'Lazio', 'Sutalo', 'Doekhi', None, None),
 ('fantamaster', 'Lazio', 'Nuno Tavares', 'Pedraza', None, None),
 ('fantamaster', 'Lecce', 'Coulibaly', 'Berisha', None, None),
 ('fantamaster', 'Lecce', 'Pierotti', 'Monteiro', None, None),
 ('fantamaster', 'Lecce', 'Stulic', 'Geubbels', None, None),
 ('fantamaster', 'Milan', 'Modric', 'Jashari', None, None),
 ('fantamaster', 'Milan', 'Rabiot', 'Saelemaekers', None, None),
 ('fantamaster', 'Monza', 'Colpani', 'Zeballos', None, None),
 ('fantamaster', 'Monza', 'Cutrone', 'Ngonge', None, None),
 ('fantamaster', 'Napoli', 'Anguissa', 'De Bruyne', None, None),
 ('fantamaster', 'Napoli', 'Santos', 'Neres', None, None),
 ('fantamaster', 'Parma', 'Romero', 'Elphege', None, None),
 ('fantamaster', 'Roma', 'Hermoso', 'Koulierakis', None, None),
 ('fantamaster', 'Roma', 'Molina', 'Lulli', None, None),
 ('fantamaster', 'Roma', 'Mora', 'Soule', None, None),
 ('fantamaster', 'Sassuolo', 'Adzic', 'Thorstvedt', None, None),
 ('fantamaster', 'Sassuolo', 'Bowie', 'Esposito', None, None),
 ('fantamaster', 'Torino', 'Mandragora', 'Braganca', None, None),
 ('fantamaster', 'Torino', 'Fitz-Jim', 'Gineitis', None, None),
 ('fantamaster', 'Torino', 'Casadei', 'Adams', None, None),
 ('fantamaster', 'Udinese', 'Piotrowski', 'Miller', None, None),
 ('fantamaster', 'Venezia', 'Mazzocchi', 'Hainaut', None, None),
 ('fantamaster', 'Venezia', 'Haps', 'Correia', None, None),

 ('fantamaster-g3', 'Juventus', 'Lucumi', 'Kelly', None, None),
 ('fantamaster-g3', 'Juventus', 'Boga', 'Alajbegovic', None, None),
 ('fantamaster-g3', 'Milan', 'Bartesaghi', 'Estupinan', None, None),
 ('fantamaster-g3', 'Milan', 'Rabiot', 'Loftus-Cheek', None, None),
 ('fantamaster-g3', 'Milan', 'Cisse', 'Saelemaekers', None, None),
 ('fantamaster-g3', 'Cagliari', 'Mendy', 'Kevin Carlos', None, None),
 ('fantamaster-g3', 'Cagliari', 'Fazzini', 'Fadera', None, None),
 ('fantamaster-g3', 'Lecce', 'Ilic', 'Ngom', None, None),
 ('fantamaster-g3', 'Lecce', 'Gorter', 'Maleh', None, None),
 ('fantamaster-g3', 'Lecce', 'Gallo', 'Ndaba', None, None),
 ('fantamaster-g3', 'Lecce', 'Pierotti', 'Monteiro', None, None),
 ('fantamaster-g3', 'Lazio', 'Floriani Mussolini', 'Lazzari', None, None),
 ('fantamaster-g3', 'Lazio', 'Gudmundsson', 'Isaksen', None, None),
 ('fantamaster-g3', 'Lazio', 'Gudmundsson', 'Cancellieri', None, None),
]


# ============================================================== infortuni
# (squadra, giocatore, problema, rientro come lo scrive la fonte)
# Il dato piu' deperibile di tutti, e il piu' pesante in asta: una guida
# d'agosto mette Yildiz fra i titolari della Juventus, ed e' giusto; ma oggi
# Yildiz ha il quinto metatarso rotto e torna a fine novembre. Sono un terzo
# di stagione, e nessun modello statistico puo' saperlo.

INFORTUNI = [
 ('Atalanta', 'Sulemana K.', 'legamento del ginocchio', 'inizio ottobre'),
 ('Atalanta', 'Hien', 'operazione al flessore', 'inizio ottobre'),
 ('Atalanta', 'Kristensen T.', 'problema alla caviglia', 'da valutare'),
 ('Bologna', 'El Azzouzi O.', 'flessore', 'fine settembre'),
 ('Bologna', 'Orsolini', 'stiramento al flessore', 'fine settembre'),
 ('Cagliari', 'Mina', 'affaticamento al polpaccio', 'da valutare'),
 ('Cagliari', 'Trepy', 'recupero', 'da valutare'),
 ('Cagliari', 'Idrissi R.', 'recupero da crociato', 'fine ottobre'),
 ('Como', 'Addai', 'rottura del tendine d\'Achille', 'meta\' settembre'),
 ('Fiorentina', 'Parisi', 'recupero da crociato', 'novembre'),
 ('Genoa', 'Venturino', 'operazione al tendine rotuleo', 'fine settembre'),
 ('Juventus', 'Yildiz', 'frattura del quinto metatarso, operato', 'fine novembre'),
 ('Juventus', 'Ekhator', 'flessore', 'fine ottobre'),
 ('Juventus', 'Thuram K.', 'operazione femoro-rotulea', 'gennaio'),
 ('Juventus', 'McKennie', 'affaticamento muscolare', 'da valutare'),
 ('Juventus', 'Cabal', 'flessore', 'meta\' settembre'),
 ('Lazio', 'Patric', 'problema fisico', 'da valutare'),
 ('Lazio', 'Marusic', 'infortunio alla coscia', 'inizio ottobre'),
 ('Lazio', 'Cataldi', 'recupero da ernia', 'meta\' settembre'),
 ('Lazio', 'Rovella', 'infortunio al polpaccio', 'inizio ottobre'),
 ('Lazio', 'Dele-Bashiru', 'problema muscolare', 'meta\' settembre'),
 ('Lecce', 'Geubbels', 'distorsione alla caviglia', 'da valutare'),
 ('Monza', 'Ciurria', 'problemi fisici', 'da valutare'),
 ('Monza', 'Pessina', 'lussazione al ginocchio', 'inizio novembre'),
 ('Monza', 'Varela G.', 'stiramento agli adduttori', 'da valutare'),
 ('Napoli', 'Giovane', 'operazione per ernia', 'inizio ottobre'),
 ('Napoli', 'McTominay', 'ablazione per aritmia', 'inizio ottobre'),
 ('Napoli', 'Buongiorno', 'operazione al menisco', 'meta\' novembre'),
 ('Napoli', 'Marianucci', 'legamento del ginocchio', 'novembre'),
 ('Parma', 'Nicolussi Caviglia', 'coscia, operato', 'novembre'),
 ('Roma', 'N\'Dicka', 'fastidio agli adduttori', 'da valutare'),
 ('Sassuolo', 'Walukiewicz', 'contusione', 'meta\' settembre'),
 ('Sassuolo', 'Cande', 'recupero da crociato', 'meta\' settembre'),
 ('Sassuolo', 'Pieragnolo', 'recupero da crociato', 'ottobre'),
 ('Sassuolo', 'Boloca', 'problema al ginocchio', 'fine settembre'),
 ('Sassuolo', 'Kone I.', 'frattura di tibia e perone', 'dicembre'),
 ('Torino', 'Casadei', 'affaticamento muscolare', 'da valutare'),
 ('Udinese', 'Palma', 'stiramento agli adduttori', 'meta\' settembre'),
 ('Udinese', 'Zanoli', 'recupero da crociato', 'ottobre'),
 ('Udinese', 'Chakvetadze', 'frattura al metatarso', 'inizio settembre'),
 ('Udinese', 'Zaniolo', 'flessore', 'meta\' settembre'),
 ('Venezia', 'Moreno M.', 'problemi fisici', 'inizio settembre'),
 ('Venezia', 'Sverko', 'operazione all\'anca', 'fine ottobre'),
 ('Venezia', 'Franjic', 'infortunio', 'da valutare'),
 ('Venezia', 'Adorante', 'operazione alla schiena', 'ottobre'),
]

# Da come lo scrive la fonte a una data: serve per contare quante partite di
# quella squadra saltera' davvero, e il calendario ce l'abbiamo.
RIENTRI = {
    'da valutare':        '2026-09-17',
    'inizio settembre':   '2026-09-08',
    'meta\' settembre':   '2026-09-16',
    'fine settembre':     '2026-09-28',
    'inizio ottobre':     '2026-10-06',
    'ottobre':            '2026-10-15',
    'meta\' ottobre':     '2026-10-15',
    'fine ottobre':       '2026-10-28',
    'inizio novembre':    '2026-11-05',
    'novembre':           '2026-11-15',
    'meta\' novembre':    '2026-11-15',
    'fine novembre':      '2026-11-28',
    'dicembre':           '2026-12-15',
    'gennaio':            '2027-01-15',
}


# ============================================================== rigoristi
# (fonte, squadra, 'primo, secondo, terzo')

RIGORISTI = {
'goal.com': [
 ('Atalanta', 'Kessie, Scamacca, De Ketelaere'),
 ('Bologna', 'Orsolini, Dovbyk, Bernardeschi'),
 ('Cagliari', 'Nzola, Fazzini'),
 ('Como', 'Da Cunha, Paz, Douvikas'),
 ('Fiorentina', 'Mastantuono, Pedro Goncalves, Pellegrino'),
 ('Frosinone', 'Calo, Raimondo'),
 ('Genoa', 'Colombo, Messias, Vitinha'),
 ('Inter', 'Calhanoglu, Martinez L., Zielinski'),
 ('Juventus', 'Yildiz, Locatelli, Kolo Muani'),
 ('Lazio', 'Zaccagni, Gudmundsson, Pinamonti'),
 ('Lecce', 'Geubbels, Stulic'),
 ('Milan', 'Ramos, Pulisic'),
 ('Monza', 'Pessina, Cutrone, Varela'),
 ('Napoli', 'De Bruyne, Hojlund'),
 ('Parma', 'Toure, Bernabe'),
 ('Roma', 'Malen, Dybala, Soule'),
 ('Sassuolo', 'Berardi, Esposito'),
 ('Torino', 'Vlasic, Zapata, Simeone'),
 ('Udinese', 'Davis, Solet, Zaniolo'),
 ('Venezia', 'Busio, Adams'),
],
'fantamaster-rigori': [
 ('Atalanta', 'Kessie, Scamacca, Samardzic'),
 ('Bologna', 'Orsolini, Bernardeschi, Dovbyk'),
 ('Cagliari', 'Nzola, Mina, Maldini'),
 ('Como', 'Da Cunha, Kean, Douvikas'),
 ('Fiorentina', 'Goncalves, Mastantuono, Pellegrino'),
 ('Frosinone', 'Calo, Schmid, Raimondo'),
 ('Genoa', 'Colombo, Vitinha, Messias'),
 ('Inter', 'Calhanoglu, Zielinski, Martinez L.'),
 ('Juventus', 'Kolo Muani, Woltemade, Locatelli'),
 ('Lazio', 'Zaccagni, Taylor, Gudmundsson'),
 ('Lecce', 'Geubbels, Stulic, Pierotti'),
 ('Milan', 'Ramos, Pulisic, Modric'),
 ('Monza', 'Pessina, Cutrone, Varela'),
 ('Napoli', 'De Bruyne, Hojlund, Politano'),
 ('Parma', 'Bernabe, Toure, Elphege'),
 ('Roma', 'Malen, Dybala, Soule'),
 ('Sassuolo', 'Berardi, Esposito, Lauriente'),
 ('Torino', 'Vlasic, Mandragora, Simeone'),
 ('Udinese', 'Davis, Solet, Zaniolo'),
 ('Venezia', 'Busio, Adams, Adorante'),
],
}


# =============================================================== scrittura
def _riga(s):
    return [x.strip() for x in s.split(',') if x.strip()]


def scrivi():
    percorsi = []

    p = os.path.join(QUI, 'formazioni_tipo.csv')
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['fonte', 'squadra', 'modulo', 'posto', 'giocatore'])
        for fonte, righe in TITOLARI.items():
            for squadra, modulo, undici in righe:
                for i, nome in enumerate(_riga(undici), start=1):
                    w.writerow([fonte, squadra, modulo, i, nome])
    percorsi.append(p)

    p = os.path.join(QUI, 'ballottaggi.csv')
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['fonte', 'squadra', 'giocatore_a', 'giocatore_b',
                    'pct_a', 'pct_b'])
        for r in BALLOTTAGGI:
            w.writerow([r[0], r[1], r[2], r[3],
                        '' if r[4] is None else r[4],
                        '' if r[5] is None else r[5]])
    percorsi.append(p)

    p = os.path.join(QUI, 'rigoristi.csv')
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['fonte', 'squadra', 'ordine', 'giocatore'])
        for fonte, righe in RIGORISTI.items():
            for squadra, elenco in righe:
                for i, nome in enumerate(_riga(elenco), start=1):
                    w.writerow([fonte, squadra, i, nome])
    percorsi.append(p)

    p = os.path.join(QUI, 'infortuni.csv')
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['squadra', 'giocatore', 'problema', 'rientro_testo',
                    'rientro_stimato'])
        for squadra, nome, problema, rientro in INFORTUNI:
            w.writerow([squadra, nome, problema, rientro,
                        RIENTRI.get(rientro, '')])
    percorsi.append(p)

    p = os.path.join(QUI, 'fonti.csv')
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['fonte', 'url', 'tipo', 'peso', 'letta_il', 'nota'])
        for nome, d in FONTI.items():
            w.writerow([nome, d['url'], d['tipo'], d['peso'],
                        DATA_RACCOLTA, d['nota']])
    percorsi.append(p)
    return percorsi


if __name__ == '__main__':
    for p in scrivi():
        n = sum(1 for _ in open(p, encoding='utf-8')) - 1
        print('  %-24s %4d righe' % (os.path.basename(p), n))
