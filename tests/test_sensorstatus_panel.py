"""Diagnose trennt Empfang, Datenannahme und unbekannte Raumabdeckung."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'lib'))
import sensorstatus


class SensorstatusTest(unittest.TestCase):
    def test_missing_and_stale_channels_are_individual(self):
        s = sensorstatus.lidar_status({'/scan0': (8, {}, None, 9.9)},
                                     ['/scan0', '/scan1'], 10, 10)
        self.assertFalse(s['daten_ok'])
        self.assertTrue(s['kanaele'][0]['empfang'])
        self.assertIn('letzter Scan', s['kanaele'][0]['ablehnungsgrund'])
        self.assertFalse(s['kanaele'][1]['empfang'])

    def test_fresh_reception_does_not_hide_bad_timestamp(self):
        s = sensorstatus.lidar_status({'s': (10, {}, None, 11)}, ['s'], 10, 10)
        self.assertFalse(s['daten_ok'])
        self.assertFalse(s['kanaele'][0]['zeit_ok'])
        self.assertIn('Zukunft', s['kanaele'][0]['ablehnungsgrund'])

    def test_ki_and_lf_preserve_rejection_without_hardware_guess(self):
        for layout, entry in [('lf', (10, None, 'Frame falsch', 10)),
                              ('ki', (10, None, None, 'Frame falsch', 10, None))]:
            k = sensorstatus.lidar_status({'s': entry}, ['s'], 10, 10, layout=layout)['kanaele'][0]
            self.assertEqual(k['ablehnungsgrund'], 'Frame falsch')
            self.assertIsNone(k['qualitaet_ok'])

    def test_valid_data_needs_no_spatial_coverage(self):
        s = sensorstatus.lidar_status({'s': (10, {}, None, 10)}, ['s'], 10, 10)
        self.assertTrue(s['daten_ok'])
        json.dumps(s, allow_nan=False)

    @unittest.skipUnless(shutil.which('node'), 'Node fuer Browserfunktionsprobe erforderlich')
    def test_panel_null_and_real_hold_diagnostics(self):
        html = (ROOT / 'panel/index.html').read_text(encoding='utf-8')
        funcs = html[html.index('function lidarAnzeige('):html.index('function zeigeDashboard()')]
        script = funcs + """
const assert = require('assert');
assert(!lidarAnzeige({lidar:null,lidar_abdeckung:'unbekannt'})[0].includes('fehlt'));
assert(lidarAnzeige({lidar:null,lidar_status:{daten_ok:true}})[0].includes('gültig'));
assert.equal(lidarAnzeige({lidar:99,lidar_status:{daten_ok:false}})[1], 'rot');
const rows = sensorDiagnoseZeilen({lf:{status:'STOPP Zeitfehler'},ki:{grund:'Klotz',lidar_status:{kanaele:[{topic:'/scan1',empfang:true,aufnahme_alter_s:2,ablehnungsgrund:'Aufnahme alt'}]}}});
assert(rows.some(r => r[1] === 'STOPP Zeitfehler'));
assert(rows.some(r => r[1] === 'Klotz'));
assert(rows.some(r => r[1].includes('Aufnahme alt')));
const ki = {aktion:'fahren',grund:'frei'};
const lf = {betrieb_angefordert:true,betrieb_freigegeben:false,bereit:false,status:'Warte auf /scan1'};
let a = betriebAnzeige({fahren:false,ki,lf});
assert.equal(a.titel, 'START WARTET'); assert.equal(a.grund, lf.status);
a = betriebAnzeige({fahren:false,ki,lf:{...lf,bereit:true}});
assert.equal(a.titel, 'START WARTET');
a = betriebAnzeige({fahren:false,ki,lf:{...lf,betrieb_angefordert:false,status:'STOPP Bedienung'}});
assert.equal(a.titel, 'GESTOPPT'); assert.equal(a.grund, 'STOPP Bedienung');
a = betriebAnzeige({fahren:false,ki,lf:{...lf,freigabeweg_ausgefallen:true,status:'Lease abgelaufen'}});
assert.equal(a.titel, 'FREIGABEWEG AUSGEFALLEN'); assert.equal(a.grund, 'Lease abgelaufen');
const aktiv = {...lf,betrieb_freigegeben:true,bereit:true,status:'Linie bereit',bewegung:{gueltig:true,linear:0,quer:0,angular:0}};
a = betriebAnzeige({fahren:true,ki:{aktion:'stopp',grund:'Klotz'},lf:aktiv});
assert.equal(a.titel, 'BETRIEB AKTIV · HALT'); assert.equal(a.grund, 'Klotz');
a = betriebAnzeige({fahren:true,ki,lf:aktiv});
assert.equal(a.titel, 'FREI');
a = betriebAnzeige({fahren:false,ki,lf:null});
assert.equal(a.titel, 'BETRIEBSSTATUS UNBEKANNT');
"""
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()
