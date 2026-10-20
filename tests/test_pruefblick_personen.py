#!/usr/bin/env python3
"""#79: Personen-/Tier-/Fahrzeughalt vor den Pruefblick-Armbewegungen der Kontrolle (auch beim Wiederholen).

Die Kontrolle haelt nur vor NEUEN Arm-/Fahrbewegungen (Pruefblick anfahren, naechster Versuch). Zuschauen geht
weiter; ist der Weg frei, endet sie wie bisher (eine Person neben der Strasse haelt nicht 30 s lang auf).

Echter Entscheider, natuerliche Phasen, reiner Planerstub; kein ROS, kein Geraet.
"""
import unittest

from raeum_lauf import AKTEURE, PRUEF_POSEN, Lauf, bewegt

PRUEF_OBJ = {'vor': 0.18, 'seite': 0.02, 'breite': 0.045, 'hoehe': 0.045, 'quelle': 'tiefe',
             'blick': 'pruef', 'blick_winkel': PRUEF_POSEN['pruefblick']}


class Welt:
    """Hindernis 18 cm voraus: nur im Pruefblick sichtbar. bleibt=True: liegt nach dem Greifen noch da."""

    def __init__(self, bleibt):
        self.lauf, self.bleibt = Lauf(PRUEF_POSEN), bleibt
        self.pose, self.gegriffen = 'fahrstellung', False

    def schritt(self, **kw):
        da = self.bleibt or not self.gegriffen
        b = self.lauf.schritt(lidar=0.18 if da else float('inf'),
                              objekt=PRUEF_OBJ if da and self.pose == 'pruefblick' else None, **kw)
        a = b['arm']
        if isinstance(a, dict) and a.get('pose'):
            self.pose = a['pose']
        elif a == 'fahrstellung':
            self.pose = 'fahrstellung'
        elif isinstance(a, dict) and a.get('winkel'):
            self.pose = 'bewegt'
            self.gegriffen = self.gegriffen or a['winkel'][5] == 130
        return b

    def bis_kontrolle(self):
        for _ in range(400):
            self.schritt()
            if self.lauf.phase() == 'kontrolle':
                return
        raise AssertionError('kontrolle nicht regulaer erreicht')


class PruefblickPersonen(unittest.TestCase):
    def test_freier_gegenfall(self):
        w = Welt(bleibt=False)
        posen, b = [], None
        for _ in range(400):
            b = w.schritt()
            if isinstance(b['arm'], dict) and b['arm'].get('pose'):
                posen.append(b['arm']['pose'])
            if b['aktion'] == 'fahren':
                break
        self.assertEqual(b['aktion'], 'fahren')
        self.assertGreaterEqual(posen.count('pruefblick'), 2)      # messen und kontrollieren im Pruefblick

    def halt_pruefen(self, bleibt, akteur, im_weg, k):
        w = Welt(bleibt)
        w.bis_kontrolle()
        for _ in range(k):
            w.schritt()
        phase = w.lauf.phase()
        if phase != 'kontrolle':
            return None                          # Kontrolle schon vorbei (frei weiter oder neuer Versuch)
        b = w.schritt(akteur=akteur, im_weg=im_weg)
        self.assertFalse(bewegt(b), f'{phase}+{k}: {b}')
        gesehen = w.lauf.t
        while w.lauf.t + 0.1 < gesehen + 2.0 - 1e-6:          # bestehendes Zwei-Sekunden-Wartefenster
            b = w.schritt()
            self.assertIsNone(b['arm'], f'{phase}+{k}, {w.lauf.t - gesehen:.1f} s danach: {b}')
            if bleibt or k == 0:      # liegt noch da (naechster Versuch) bzw. Pruefblick noch nicht angefahren
                self.assertFalse(bewegt(b), f'{phase}+{k}, {w.lauf.t - gesehen:.1f} s danach: {b}')
        return w

    def test_akteur_beim_eintritt_und_in_jedem_kontrollbild(self):
        for bleibt in (False, True):            # True: Wiederholungsweg (liegt noch da -> neuer Pruefblick)
            for akteur in AKTEURE:
                for im_weg in (True, False):
                    for k in range(0, 45, 1 if akteur == 'Person' else 4):
                        with self.subTest(bleibt=bleibt, akteur=akteur, im_weg=im_weg, k=k):
                            self.halt_pruefen(bleibt, akteur, im_weg, k)

    def test_nach_freipruefung_regulaer_weiter(self):
        w = self.halt_pruefen(False, 'Person', True, 0)
        posen, b = [], None
        for _ in range(200):
            b = w.schritt()
            if isinstance(b['arm'], dict) and b['arm'].get('pose'):
                posen.append(b['arm']['pose'])
            if b['aktion'] == 'fahren':
                break
        self.assertIn('pruefblick', posen)
        self.assertEqual(b['aktion'], 'fahren')

    def test_akteur_bleibt_30s_kein_arm_danach_halt_bis_start(self):
        w = Welt(bleibt=False)
        w.bis_kontrolle()
        start = w.lauf.t
        while w.lauf.t - start < 35.0:
            b = w.schritt(akteur='Person', im_weg=False)
            self.assertFalse(bewegt(b), f'{w.lauf.t - start:.1f} s: {b}')
        self.assertIsNone(w.lauf.e.ablauf)
        self.assertTrue(any('bleibt in Sicht' in t for _, t, _ in w.lauf.e.ereignisse))
        aktionen = [w.schritt()['aktion'] for _ in range(100)]
        self.assertNotIn('fahren', aktionen)          # aufgegeben: wartet auf STOPP + START
        w.lauf.e.kommando(w.lauf.t, 'start')
        aktionen = [w.schritt()['aktion'] for _ in range(100)]
        self.assertIn('fahren', aktionen)

    def test_wiederholung_nach_freipruefung(self):
        w = Welt(bleibt=True)
        w.bis_kontrolle()
        versuch = w.lauf.e.ablauf.versuch
        for _ in range(200):
            w.schritt()
            a = w.lauf.e.ablauf
            if a is None or a.versuch > versuch:
                break
        self.assertIsNotNone(w.lauf.e.ablauf)
        self.assertEqual(w.lauf.e.ablauf.versuch, versuch + 1)
        self.assertEqual(w.lauf.e.ablauf.phase, 'pruefblick')


if __name__ == '__main__':
    unittest.main(verbosity=2)
