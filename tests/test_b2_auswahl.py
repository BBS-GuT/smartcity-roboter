"""Deterministische synthetische B2-Folgen, keine Geraete-/ROS-Abnahme."""
from dataclasses import replace
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from b2_auswahl import Auswahl, Bezug, Eingabe  # noqa: E402


B = Bezug('test-geraet', 'test-start', 'test-regel-v1', 'test-X', 'test-S',
          'test-1', True)


def bild(seq=1, **werte):
    basis = Eingabe(B, seq, float(seq), 1.0, geometrie=frozenset({'A', 'B', 'C'}),
                    erlaubt=frozenset({'A', 'C'}), einfahrtsfreigabe=True,
                    spur_bestaetigt=True, geometrie_vollstaendig=True)
    return replace(basis, **werte)


class Zufall:
    def __init__(self, wert=0.0):
        self.wert, self.zuege = wert, 0

    def random(self):
        self.zuege += 1
        return self.wert


def automat(**werte):
    return Auswahl(B.geraet, B.start, B.quelle, **dict(historie={}, **werte))


class Wegwahl(unittest.TestCase):
    def test_einzelausgang_ohne_zufall_und_verbotener_sichtbarer_arm(self):
        rng = Zufall()
        a = automat(zufall=rng)
        e = bild(erlaubt=frozenset({'C'}))
        self.assertEqual(a.schritt(e, 1).ausgang, 'C')
        self.assertEqual(rng.zuege, 0)

    def test_seed_und_zwei_getrennte_kreuzungsfolgen(self):
        def folge(seed):
            a, result = automat(zufall=random.Random(seed)), []
            for i in range(40):
                b = replace(B, anfahrt=f'test-{i}')
                seq = i * 3 + 1
                e = bild(seq, bezug=b)
                wahl = a.schritt(e, seq).ausgang
                self.assertIn(wahl, {'A', 'C'})
                result.append(wahl)
                ein = replace(bild(seq + 1, bezug=b), art='einfahrt',
                              ausgang=wahl, bestaetigt=True)
                self.assertEqual(a.schritt(ein, seq + 1).lage, 'raeumen')
                aus = replace(bild(seq + 2, bezug=b), art='abschluss',
                              ausgang=wahl, bestaetigt=True)
                self.assertEqual(a.schritt(aus, seq + 2).lage, 'abgeschlossen')
            self.assertEqual(sum(a.historie.values()), 40)
            return result
        self.assertEqual(folge(17), folge(17))

    def test_historie_gewichtet_und_kopiert(self):
        h = {(B.knoten, B.zufahrt, 'A'): 9}
        a = Auswahl(B.geraet, B.start, B.quelle, historie=h, zufall=Zufall(.2))
        h.clear()
        self.assertEqual(a.schritt(bild(), 1).ausgang, 'C')
        kopie = a.historie
        kopie.clear()
        self.assertEqual(a.historie[(B.knoten, B.zufahrt, 'A')], 9)
        self.assertEqual(automat(zufall=Zufall(.2)).schritt(bild(), 1).ausgang, 'A')

    def test_fehlende_und_ungueltige_historie_sind_nicht_leer(self):
        for h in (None, [], {('X', 'S', 'A'): -1}, {('X', 'S', 'A'): True},
                  {('X', 'S'): 1}):
            with self.subTest(h=h):
                a = Auswahl(B.geraet, B.start, B.quelle, historie=h)
                self.assertEqual(a.schritt(bild(), 1).grund, 'historie_unbekannt')

    def test_bezug_und_quelle(self):
        for feld in ('geraet', 'start', 'quelle'):
            a = automat()
            self.assertEqual(a.schritt(bild(bezug=replace(B, **{feld: 'fremd'})), 1).grund,
                             'quelle_unpassend')
        for feld in ('knoten', 'zufahrt', 'anfahrt'):
            self.assertEqual(automat().schritt(bild(bezug=replace(B, **{feld: ''})), 1).grund,
                             'bezug_ungueltig')
        self.assertEqual(automat().schritt(bild(bezug=replace(B, bestaetigt=False)), 1).grund,
                         'bezug_ungueltig')

    def test_zeit_und_sequenz(self):
        for werte in ({'aufnahme': float('nan')}, {'aufnahme': float('inf')},
                      {'aufnahme': 2}, {'gueltig_fuer': 0}, {'gueltig_fuer': -1},
                      {'sequenz': True}, {'sequenz': -1}):
            with self.subTest(werte=werte):
                self.assertEqual(automat().schritt(bild(**werte), 1).grund, 'zeit_ungueltig')
        self.assertEqual(automat().schritt(bild(), 2.01).grund, 'beobachtung_veraltet')
        a = automat()
        a.schritt(bild(2), 2)
        self.assertEqual(a.schritt(bild(1), 2).grund, 'sequenz_ruecklaeufig')
        self.assertEqual(a.schritt(bild(3, aufnahme=1.9), 2).grund, 'zeit_ruecklaeufig')
        self.assertEqual(a.schritt(bild(3), 1).grund, 'zeit_ungueltig')

    def test_unbekannt_leer_ungueltig(self):
        for werte, grund in (({'erlaubt': None}, 'erlaubnis_unbekannt'),
                             ({'erlaubt': frozenset()}, 'keine_erlaubte_ausfahrt'),
                             ({'erlaubt': frozenset({'D'})}, 'keine_erlaubte_ausfahrt'),
                             ({'erlaubt': {'A'}}, 'erlaubnis_ungueltig'),
                             ({'geometrie': {'A'}}, 'geometrie_ungueltig'),
                             ({'ueberweg': True}, 'ueberweg'),
                             ({'erkannt': False}, 'erkennung_fehlt')):
            with self.subTest(grund=grund):
                r = automat().schritt(bild(**werte), 1)
                self.assertEqual(r.grund, grund)
                self.assertIsNone(r.ausgang)

    def test_duplikate_verbrauchen_keine_frische_oder_zufall(self):
        rng, e = Zufall(), bild()
        a = automat(zufall=rng)
        r = a.schritt(e, 1)
        for _ in range(30):
            self.assertEqual(a.schritt(e, 1.2), r)
        self.assertEqual(rng.zuege, 1)
        self.assertEqual(a.schritt(e, 2.01).grund, 'beobachtung_veraltet')
        self.assertEqual(a.schritt(replace(e, aufnahme=2), 2.01).grund,
                         'duplikat_widerspruechlich')

    def test_luecke_verbot_zuordnung_wechseln_nicht_den_arm(self):
        rng, a = Zufall(), None
        a = automat(zufall=rng)
        self.assertEqual(a.schritt(bild(), 1).ausgang, 'A')
        fehler = [({'erkannt': False}, 'erkennung_fehlt'),
                  ({'geometrie': frozenset({'B', 'C'})}, 'ausgang_nicht_sichtbar'),
                  ({'erlaubt': frozenset({'C'})}, 'ausgang_verboten'),
                  ({'bezug': replace(B, anfahrt='andere')}, 'anfahrt_konflikt'),
                  ({'bezug': replace(B, zufahrt='andere')}, 'anfahrt_konflikt')]
        for seq, (werte, grund) in enumerate(fehler, 2):
            r = a.schritt(bild(seq, **werte), seq)
            self.assertEqual((r.grund, r.ausgang), (grund, 'A'))
        self.assertEqual(a.schritt(bild(7), 7).lage, 'gewaehlt')
        self.assertEqual(rng.zuege, 1)

    def test_einfahrt_rot_vorher_und_nachher(self):
        a = automat(zufall=Zufall())
        self.assertEqual(a.schritt(bild(einfahrtsfreigabe=False), 1).grund,
                         'einfahrt_gesperrt')
        a.schritt(bild(2), 2)
        self.assertEqual(a.schritt(bild(3, einfahrtsfreigabe=None), 3).grund,
                         'einfahrt_gesperrt')
        falsch = bild(4, art='einfahrt', ausgang='C', bestaetigt=True)
        self.assertEqual(a.schritt(falsch, 4).grund, 'einfahrt_unpassend')
        ein = bild(5, art='einfahrt', ausgang='A', bestaetigt=True)
        self.assertEqual(a.schritt(ein, 5).lage, 'raeumen')
        self.assertEqual(a.schritt(bild(6, einfahrtsfreigabe=False), 6).lage, 'raeumen')
        self.assertEqual(a.schritt(bild(7, einfahrtsfreigabe=None), 7).lage, 'raeumen')
        self.assertEqual(a.historie, {})

    def test_abschluss_nur_passend_frisch_nach_einfahrt_einmal(self):
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        self.assertEqual(a.schritt(bild(2, art='abschluss', ausgang='A', bestaetigt=True), 2).grund,
                         'abschluss_unpassend')
        a.schritt(bild(3, art='einfahrt', ausgang='A', bestaetigt=True), 3)
        for seq, werte in ((4, {'ausgang': 'C'}), (5, {'bestaetigt': False}),
                           (6, {'bezug': replace(B, anfahrt='falsch')})):
            r = a.schritt(replace(
                bild(seq, art='abschluss', ausgang='A', bestaetigt=True), **werte), seq)
            self.assertEqual(r.lage, 'halt')
            self.assertEqual(a.historie, {})
        aus = bild(7, art='abschluss', ausgang='A', bestaetigt=True)
        self.assertEqual(a.schritt(aus, 8.01).grund, 'beobachtung_veraltet')
        aus = bild(8, art='abschluss', ausgang='A', bestaetigt=True)
        self.assertEqual(a.schritt(aus, 8.1).lage, 'abgeschlossen')
        a.schritt(aus, 8.2)
        a.schritt(replace(aus, sequenz=9, aufnahme=9), 9)
        self.assertEqual(a.historie, {(B.knoten, B.zufahrt, 'A'): 1})
        self.assertEqual(a.schritt(bild(10), 10).grund, 'anfahrt_abgeschlossen')
        self.assertEqual(a.schritt(bild(11, bezug=replace(B, anfahrt='test-2')), 11).lage,
                         'gewaehlt')

    def test_schutzstopps_loeschen_keine_wahl_oder_raemfreigabe(self):
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        for seq, grund in enumerate(('STOPP', 'Hindernis', 'Pflichtdaten', 'Armschutz'), 2):
            r = a.schritt(bild(seq), seq, haltgruende=(grund,))
            self.assertEqual((r.lage, r.ausgang, r.grund), ('halt', 'A', 'schutzstopp'))
        a.schritt(bild(6, art='einfahrt', ausgang='A', bestaetigt=True), 6)
        self.assertEqual(a.schritt(bild(7), 7, haltgruende=('STOPP',)).lage, 'halt')
        self.assertEqual(a.schritt(bild(8, einfahrtsfreigabe=False), 8).lage, 'raeumen')

    def test_einfahrtereignis_ohne_wahl_oder_bestaetigung(self):
        e = bild(art='einfahrt', ausgang='A', bestaetigt=True)
        self.assertEqual(automat().schritt(e, 1).grund, 'einfahrt_unpassend')
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        self.assertEqual(a.schritt(replace(e, sequenz=2, aufnahme=2, bestaetigt=False), 2).grund,
                         'einfahrt_unpassend')
        self.assertEqual(a.schritt(replace(e, sequenz=3, aufnahme=3), 4.01).grund,
                         'beobachtung_veraltet')
        self.assertEqual(a.schritt(bild(5, einfahrtsfreigabe=False), 5).grund,
                         'einfahrt_gesperrt')

    def test_schilderverbot_und_sichtluecke_auch_beim_raeumen(self):
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        a.schritt(bild(2, art='einfahrt', ausgang='A', bestaetigt=True), 2)
        self.assertEqual(a.schritt(bild(3, erlaubt=frozenset({'C'})), 3).grund,
                         'ausgang_verboten')
        self.assertEqual(a.schritt(bild(4, erkannt=False, spur_bestaetigt=False), 4).grund,
                         'spur_unbestaetigt')
        self.assertEqual(a.schritt(bild(5, einfahrtsfreigabe=False), 5).lage, 'raeumen')

    def test_zufall_ungueltig_und_identitaet_pflicht(self):
        for wert in (-.01, 1, float('nan'), float('inf'), True):
            self.assertEqual(automat(zufall=Zufall(wert)).schritt(bild(), 1).grund,
                             'zufall_ungueltig')
        with self.assertRaises(ValueError):
            Auswahl('', B.start, B.quelle, historie={})

    def test_neustart_und_kartenwechsel_sind_keine_fortsetzung(self):
        a = Auswahl(B.geraet, 'neustart', B.quelle, historie={})
        self.assertEqual(a.schritt(bild(), 1).grund, 'quelle_unpassend')
        a = Auswahl(B.geraet, B.start, 'neue-karte', historie={})
        self.assertEqual(a.schritt(bild(), 1).grund, 'quelle_unpassend')
        a = automat()
        self.assertEqual(a.schritt(bild(art='abschluss', ausgang='A', bestaetigt=True), 1).grund,
                         'abschluss_unpassend')

    def test_duplikat_darf_unbekannte_erlaubnis_nicht_ersetzen(self):
        a = automat()
        e = bild(erlaubt=None)
        a.schritt(e, 1)
        self.assertEqual(a.schritt(replace(e, erlaubt=frozenset({'A'})), 1.1).grund,
                         'duplikat_widerspruechlich')
        self.assertEqual(a.schritt(bild(2), 2).lage, 'gewaehlt')

    def test_grosse_historienzaehler_unterlaufen_nicht_zu_null(self):
        h = {(B.knoten, B.zufahrt, a): 10 ** 1000 for a in ('A', 'C')}
        a = Auswahl(B.geraet, B.start, B.quelle, historie=h, zufall=Zufall(.25))
        self.assertEqual(a.schritt(bild(), 1).ausgang, 'A')
        self.assertEqual(automat().schritt(bild(aufnahme=10 ** 1000), 1).grund,
                         'zeit_ungueltig')

    def test_schutzstopp_vor_wahl_und_beim_abschluss(self):
        rng = Zufall()
        a = automat(zufall=rng)
        self.assertIsNone(a.schritt(bild(), 1, haltgruende=('STOPP',)).ausgang)
        self.assertEqual(rng.zuege, 0)
        a.schritt(bild(2), 2)
        a.schritt(bild(3, art='einfahrt', ausgang='A', bestaetigt=True), 3)
        aus = bild(4, art='abschluss', ausgang='A', bestaetigt=True)
        self.assertEqual(a.schritt(aus, 4, haltgruende=('Hindernis',)).grund, 'schutzstopp')
        self.assertEqual(a.historie, {})
        self.assertEqual(a.schritt(aus, 4.1).lage, 'abgeschlossen')
        self.assertEqual(sum(a.historie.values()), 1)

    def test_bezug_falscher_quelle_vergiftet_keine_lokale_sequenz(self):
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        fremd = bild(1000, aufnahme=2, bezug=replace(B, quelle='fremd'))
        self.assertEqual(a.schritt(fremd, 2).grund, 'quelle_unpassend')
        self.assertEqual(a.schritt(bild(3), 3).ausgang, 'A')

    def test_datenobjekte_unveraenderlich_und_keine_motorfreigabe(self):
        from dataclasses import FrozenInstanceError
        e = bild()
        with self.assertRaises(FrozenInstanceError):
            e.sequenz = 2
        r = automat().schritt(e, 1)
        with self.assertRaises(FrozenInstanceError):
            r.ausgang = 'verboten'
        self.assertEqual(set(vars(r)), {'lage', 'ausgang', 'grund'})

    def test_kreuzungsform_verschwindet_nach_einfahrt_spur_bleibt(self):
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        ohne_form = dict(erkannt=False, geometrie=frozenset(), spur_bestaetigt=True)
        self.assertEqual(a.schritt(bild(2, **ohne_form), 2).grund, 'erkennung_fehlt')
        self.assertEqual(a.schritt(bild(3, geometrie=frozenset({'C'})), 3).grund,
                         'ausgang_nicht_sichtbar')
        a.schritt(bild(4, art='einfahrt', ausgang='A', bestaetigt=True), 4)
        r = a.schritt(bild(5, einfahrtsfreigabe=False, **ohne_form), 5)
        self.assertEqual((r.lage, r.ausgang, r.grund), ('raeumen', 'A', None))
        self.assertEqual(a.historie, {})  # Formverlust ist keine Ausfahrt
        self.assertEqual(a.schritt(bild(6, geometrie=frozenset({'C'})), 6).lage, 'raeumen')
        self.assertEqual(a.schritt(bild(7, art='abschluss', ausgang='A', bestaetigt=True), 7).lage,
                         'abgeschlossen')

    def test_raeumen_braucht_echte_spur_und_schutzstopps_trotz_formverlust(self):
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        self.assertEqual(a.schritt(bild(2, art='einfahrt', ausgang='A', bestaetigt=True,
                                       spur_bestaetigt=False), 2).grund, 'einfahrt_unpassend')
        a.schritt(bild(3, art='einfahrt', ausgang='A', bestaetigt=True), 3)
        for seq, spur in ((4, False), (5, None)):
            self.assertEqual(a.schritt(bild(seq, erkannt=False, geometrie=frozenset(),
                                           spur_bestaetigt=spur), seq).grund, 'spur_unbestaetigt')
        e = bild(6, erkannt=False, geometrie=frozenset(), spur_bestaetigt=True)
        self.assertEqual(a.schritt(e, 6, haltgruende=('Hindernis',)).grund, 'schutzstopp')
        self.assertEqual(a.schritt(replace(e, sequenz=7, aufnahme=7), 7).lage, 'raeumen')
        self.assertEqual(a.historie, {})

    def test_teilmenge_vor_wahl_verbraucht_keinen_zufallszug(self):
        rng = Zufall(.75)
        a = automat(zufall=rng)
        teil = bild(geometrie=frozenset({'A'}), geometrie_vollstaendig=False)
        r = a.schritt(teil, 1)
        self.assertEqual((r.lage, r.ausgang, r.grund),
                         ('halt', None, 'geometrie_unvollstaendig'))
        self.assertEqual(a.schritt(teil, 1.2), r)
        self.assertEqual(a.schritt(bild(2, geometrie=frozenset({'A'})), 2).grund,
                         'geometrie_unvollstaendig')  # Widerspruch trotz True
        self.assertEqual(a.schritt(bild(3, geometrie_vollstaendig=False), 3).grund,
                         'geometrie_unvollstaendig')
        self.assertEqual(rng.zuege, 0)
        self.assertEqual(a.historie, {})
        self.assertEqual(a.schritt(bild(4), 4).ausgang, 'C')
        self.assertEqual(rng.zuege, 1)
        self.assertEqual(a.schritt(bild(5, geometrie_vollstaendig=False), 5).ausgang, 'C')
        self.assertEqual(rng.zuege, 1)  # nach Bindung keine neue Vollstaendigkeitswahl

    def test_ein_erlaubter_arm_braucht_ebenfalls_vollstaendigkeitsbeleg(self):
        a = automat()
        self.assertEqual(a.schritt(bild(erlaubt=frozenset({'A'}),
                                       geometrie_vollstaendig=False), 1).grund,
                         'geometrie_unvollstaendig')
        self.assertEqual(a.schritt(bild(2, erlaubt=frozenset({'A'})), 2).ausgang, 'A')

    def test_abschluss_ohne_spurnachweis_loest_bindung_nicht(self):
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        a.schritt(bild(2, art='einfahrt', ausgang='A', bestaetigt=True), 2)
        for seq, spur in ((3, False), (4, None)):
            r = a.schritt(bild(seq, art='abschluss', ausgang='A', bestaetigt=True,
                              spur_bestaetigt=spur), seq)
            self.assertEqual((r.lage, r.ausgang, r.grund), ('halt', 'A', 'spur_unbestaetigt'))
            self.assertEqual(a.historie, {})
        self.assertEqual(a.schritt(bild(5, bezug=replace(B, anfahrt='andere')), 5).grund,
                         'anfahrt_konflikt')
        self.assertEqual(a.schritt(bild(6, art='abschluss', ausgang='A', bestaetigt=True), 6).lage,
                         'abgeschlossen')
        self.assertEqual(sum(a.historie.values()), 1)

    def test_ungueltiger_zufallszug_sperrt_genau_diese_anfahrt(self):
        rng = Zufall(float('nan'))
        a = automat(zufall=rng)
        self.assertEqual(a.schritt(bild(), 1).grund, 'zufall_ungueltig')
        rng.wert = .75
        for seq in (2, 3):
            r = a.schritt(bild(seq), seq)
            self.assertEqual((r.lage, r.ausgang, r.grund), ('halt', None, 'zufall_ungueltig'))
        self.assertEqual(rng.zuege, 1)
        self.assertEqual(a.historie, {})
        neue = replace(B, anfahrt='neue-bestaetigte-anfahrt')
        self.assertEqual(a.schritt(bild(4, bezug=neue), 4).ausgang, 'C')
        self.assertEqual(rng.zuege, 2)

    def test_schutzstopp_merkt_neueste_sequenz_gegen_alte_einfahrt(self):
        a = automat(zufall=Zufall())
        a.schritt(bild(), 1)
        rot = bild(3, einfahrtsfreigabe=False)
        self.assertEqual(a.schritt(rot, 3, haltgruende=('Hindernis',)).grund, 'schutzstopp')
        alt = bild(2, art='einfahrt', ausgang='A', bestaetigt=True)
        self.assertEqual(a.schritt(alt, 3).grund, 'sequenz_ruecklaeufig')
        self.assertEqual(a.schritt(bild(4, einfahrtsfreigabe=False), 4).grund,
                         'einfahrt_gesperrt')
        self.assertEqual(a.historie, {})
        self.assertEqual(a.schritt(bild(5, art='einfahrt', ausgang='A', bestaetigt=True), 5).lage,
                         'raeumen')

    def test_schutzstopp_merkt_zeit_und_widerspruechliche_duplikate(self):
        a = automat()
        e = bild(3)
        a.schritt(e, 3, haltgruende=('STOPP',))
        self.assertEqual(a.schritt(bild(4, aufnahme=2.5), 3).grund, 'zeit_ruecklaeufig')
        self.assertEqual(a.schritt(replace(e, einfahrtsfreigabe=False), 3).grund,
                         'duplikat_widerspruechlich')
        self.assertEqual(a.schritt(e, 3.1).lage, 'gewaehlt')


if __name__ == '__main__':
    unittest.main()
