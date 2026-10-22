#!/usr/bin/env python3
"""Streckenabsprache (Issue #120): frisch / alt / fehlend / Konflikt und Negativkontrolle (nie gesperrte Ausfahrt).

Reine Logik, deterministische Uhr und Auswahl. Kein ROS, kein Geraet, keine Funkverbindung.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from streckenabsprache import (  # noqa: E402
    Claim, ClaimTable, choose_exit, section, claim_from_state,
    MAX_AGE_S, RECENT_WINDOW_S,
)


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


def first(options):
    """Deterministischer Ersatz fuer random.choice."""
    return options[0]


A, B, C = section(1, 2), section(1, 3), section(1, 4)
ALLOWED = [A, B, C]


class Tests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.table = ClaimTable(own_id=5, clock=self.clock)

    def test_fehlend_waehlt_wie_bisher(self):
        self.assertEqual(choose_exit(ALLOWED, self.table, first), A)

    def test_frisch_meidet_besetzten_abschnitt(self):
        self.table.on_message(Claim(2, current=A, next_=None))
        self.assertEqual(choose_exit(ALLOWED, self.table, first), B)

    def test_alt_wird_ignoriert(self):
        self.table.on_message(Claim(2, current=A, next_=None))
        self.clock.t += MAX_AGE_S + 0.1
        self.assertEqual(choose_exit(ALLOWED, self.table, first), A)

    def test_konflikt_kleinere_nummer_behaelt(self):
        self.table.on_message(Claim(2, current=C, next_=A))  # 2 < 5
        self.assertEqual(choose_exit(ALLOWED, self.table, first), B)

    def test_konflikt_groessere_nummer_weicht(self):
        self.table.on_message(Claim(9, current=C, next_=A))  # 9 > 5
        self.assertEqual(choose_exit(ALLOWED, self.table, first), A)

    def test_kuerzlich_befahren_wird_nachrangig(self):
        self.table.on_message(Claim(2, current=A, next_=None))
        self.clock.t += MAX_AGE_S + 0.1  # Meldung alt, Besuch noch "kuerzlich"
        self.table.on_message(Claim(3, current=C, next_=None))  # frisch
        self.assertEqual(choose_exit(ALLOWED, self.table, first), B)
        self.clock.t += RECENT_WINDOW_S
        self.table.on_message(Claim(3, current=C, next_=None))
        self.assertEqual(choose_exit(ALLOWED, self.table, first), A)

    def test_negativ_nie_gesperrte_ausfahrt(self):
        """Fremdmeldung 'Abschnitt frei' darf nichts erlauben."""
        gesperrt = section(1, 99)
        self.table.on_message(Claim(2, current=C, next_=None))
        for _ in range(20):
            self.assertIn(choose_exit(ALLOWED, self.table), ALLOWED)
            self.assertNotEqual(choose_exit(ALLOWED, self.table), gesperrt)

    def test_alle_besetzt_blockiert_nicht(self):
        for rid, sec in ((1, A), (2, B), (3, C)):
            self.table.on_message(Claim(rid, current=sec, next_=None))
        self.assertIn(choose_exit(ALLOWED, self.table, first), ALLOWED)

    def test_leere_liste(self):
        self.assertIsNone(choose_exit([], self.table, first))

    def test_eigene_meldung_wird_ignoriert(self):
        self.table.on_message(Claim(5, current=A, next_=None))
        self.assertEqual(choose_exit(ALLOWED, self.table, first), A)

    def test_doppelte_oder_alte_seq_wird_verworfen(self):
        self.table.on_message(Claim("RM02", A, None, "boot-1", 10))
        self.table.on_message(Claim("RM02", C, None, "boot-1", 9))
        self.assertEqual(choose_exit(ALLOWED, self.table, first), B)  # A besetzt

    def test_neuer_boot_setzt_seq_zurueck(self):
        self.table.on_message(Claim("RM02", A, None, "boot-1", 10))
        self.table.on_message(Claim("RM02", C, None, "boot-2", 1))
        # C ist jetzt besetzt (neuer Start wird akzeptiert), A war nur kuerzlich
        # befahren (Strafe 1) -> B ist die beste Ausfahrt
        self.assertEqual(choose_exit(ALLOWED, self.table, first), B)

    def test_claim_aus_zustandsdatensatz(self):
        state = {"robot_id": "RM02", "boot_id": "boot-1", "seq": 3,
                 "route": {"section": "S1", "node": "K1", "selected_exit": "links",
                           "localization_status": "valid"}}
        c = claim_from_state(state, lambda node, ex: node + "/" + ex)
        self.assertEqual((c.current, c.next_), ("S1", "K1/links"))
        state["route"]["localization_status"] = "unknown"
        self.assertIsNone(claim_from_state(state))

    def test_ausfahrten_werden_in_abschnitte_uebersetzt(self):
        mapping = {"links": "S_a", "rechts": "S_b"}
        self.table.on_message(Claim("RM02", "S_a", None))
        wahl = choose_exit(["links", "rechts"], self.table, first, node="K1",
                           exit_to_section=lambda n, e: mapping[e])
        self.assertEqual(wahl, "rechts")


if __name__ == "__main__":
    unittest.main(verbosity=2)
