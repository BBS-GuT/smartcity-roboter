# Systemlast messen (fuer logs/system.log): Wer braucht die Rechenzeit, ist der Speicher voll, wird der Jetson heiss?
# Nur Lesen aus /proc und /sys, kein psutil noetig. Kostet ca. 1-2 ms pro Messung.
#
# Hintergrund (20.10.): In einer Messfahrt kamen Lagesensor, Raeder, LiDAR und KI-Befehle ueber 50-mal gleichzeitig
# 1-2,3 s lang nicht an. Das ist kein einzelnes Programm, sondern der ganze Rechner. Diese Messung zeigt, wer schuld ist.
import os
import time


class Systemlast:
    def __init__(self, wurzel='/', kerne=None):
        self.proc = os.path.join(wurzel, 'proc')
        self.sys = os.path.join(wurzel, 'sys')
        self.alt_cpu = None            # (gesamt, leerlauf, iowait)
        self.alt_prozesse = {}         # pid -> Rechenzeit (Ticks)
        self.alt_threads = {}          # (pid, tid) -> Rechenzeit (Ticks), nur fuer das staerkste Programm
        self.namen = {}
        self.kerne = kerne or os.cpu_count() or 1

    def _lies(self, *pfad):
        try:
            with open(os.path.join(*pfad)) as f:
                return f.read()
        except OSError:
            return None

    def _cpu(self):
        zeile = (self._lies(self.proc, 'stat') or '').split('\n')[0].split()
        werte = [int(x) for x in zeile[1:]] if zeile and zeile[0] == 'cpu' else []
        if len(werte) < 5:
            return None
        return sum(werte), werte[3], werte[4]

    def _name(self, pid):
        if pid not in self.namen:
            roh = self._lies(self.proc, pid, 'cmdline') or ''
            teile = [t for t in roh.split('\0') if t]
            # bei python3 das Skript zeigen (zentrale.py statt python3)
            wichtig = next((os.path.basename(t) for t in teile[1:] if t.endswith('.py')), None)
            self.namen[pid] = wichtig or (os.path.basename(teile[0]) if teile else
                                          (self._lies(self.proc, pid, 'comm') or '?').strip())
        return self.namen[pid]

    def _prozesse(self):
        aus = {}
        try:
            pids = [p for p in os.listdir(self.proc) if p.isdigit()]
        except OSError:
            return aus
        for pid in pids:
            st = self._lies(self.proc, pid, 'stat')
            if not st:
                continue
            felder = st[st.rfind(')') + 2:].split()       # Name kann Leerzeichen enthalten
            try:
                aus[pid] = int(felder[11]) + int(felder[12])    # utime + stime
            except (IndexError, ValueError):
                pass
        return aus

    def _threads(self, pid, je_kern):
        """Welche Threads im staerksten Programm rechnen? [(Name, Prozent), ...] (erste Messung: leer).
        Viele Threads um 100 % bei wenig Arbeit = aktiv wartende Mathe-Bibliothek (OpenBLAS/OpenMP)."""
        basis = os.path.join(self.proc, pid, 'task')
        try:
            tids = os.listdir(basis)
        except OSError:
            return []
        neu, aus = {k: v for k, v in self.alt_threads.items() if k[0] != pid}, []
        for tid in tids:
            st = self._lies(basis, tid, 'stat')
            if not st:
                continue
            felder = st[st.rfind(')') + 2:].split()
            try:
                t = int(felder[11]) + int(felder[12])
            except (IndexError, ValueError):
                continue
            neu[(pid, tid)] = t
            if (pid, tid) in self.alt_threads:
                prozent = 100.0 * (t - self.alt_threads[(pid, tid)]) / je_kern
                if prozent >= 10:
                    name = (self._lies(basis, tid, 'comm') or '?').strip()
                    aus.append((name, round(prozent)))
        self.alt_threads = neu
        return sorted(aus, key=lambda x: -x[1])[:6]

    def _speicher(self):
        m = {}
        for zeile in (self._lies(self.proc, 'meminfo') or '').splitlines():
            teile = zeile.split()
            if len(teile) >= 2:
                m[teile[0].rstrip(':')] = int(teile[1])      # kB
        if 'MemTotal' not in m:
            return None
        frei = m.get('MemAvailable', m.get('MemFree', 0))
        swap = m.get('SwapTotal', 0) - m.get('SwapFree', 0)
        return {'ram_belegt_mb': round((m['MemTotal'] - frei) / 1024), 'ram_gesamt_mb': round(m['MemTotal'] / 1024),
                'swap_mb': round(swap / 1024)}

    def _temperatur(self):
        hoechste = None
        basis = os.path.join(self.sys, 'class', 'thermal')
        try:
            zonen = [z for z in os.listdir(basis) if z.startswith('thermal_zone')]
        except OSError:
            return None
        for z in zonen:
            t = self._lies(basis, z, 'temp')
            try:
                c = int(t) / 1000.0
            except (TypeError, ValueError):
                continue
            if -40 < c < 150:
                hoechste = c if hoechste is None else max(hoechste, c)
        return hoechste

    def _gpu(self):
        for pfad in (('devices', 'gpu.0', 'load'), ('devices', 'platform', 'gpu.0', 'load'),
                     ('devices', 'platform', '17000000.ga10b', 'load'), ('devices', 'platform', '17000000.gv11b', 'load')):
            t = self._lies(self.sys, *pfad)
            if t and t.strip().isdigit():
                return int(t) / 10.0          # Jetson: Promille
        return None

    def messen(self, top=5):
        """Rueckgabe: dict cpu_prozent, iowait_prozent, last1, ram/swap, temperatur, gpu_prozent,
        top [(name, Prozent eines Kerns), ...]. Erste Messung: Prozentwerte None (Vergleich fehlt)."""
        aus = {'zeit': time.time()}
        cpu, prozesse = self._cpu(), self._prozesse()
        if cpu and self.alt_cpu:
            d_ges = cpu[0] - self.alt_cpu[0]
            if d_ges > 0:
                aus['cpu_prozent'] = round(100.0 * (1 - (cpu[1] - self.alt_cpu[1] + cpu[2] - self.alt_cpu[2]) / d_ges), 1)
                aus['iowait_prozent'] = round(100.0 * (cpu[2] - self.alt_cpu[2]) / d_ges, 1)
                je_kern = d_ges / self.kerne  # Ticks, die ein Kern in dieser Zeit hatte
                diff = sorted(((t - self.alt_prozesse[p], p) for p, t in prozesse.items() if p in self.alt_prozesse),
                              reverse=True)[:top]
                aus['top'] = [(self._name(p), round(100.0 * d / je_kern)) for d, p in diff if d > 0]
                if diff:
                    threads = self._threads(diff[0][1], je_kern)    # immer mitmessen (Vergleich naechstes Mal)
                    if 100.0 * diff[0][0] / je_kern > 120:
                        aus['threads'] = threads
        self.alt_cpu, self.alt_prozesse = cpu, prozesse
        for pid in list(self.namen):
            if pid not in prozesse:
                del self.namen[pid]
        last = (self._lies(self.proc, 'loadavg') or '').split()
        aus['last1'] = float(last[0]) if last else None
        aus.update(self._speicher() or {})
        aus['temperatur'] = self._temperatur()
        aus['gpu_prozent'] = self._gpu()
        return aus


def zeile(m, zu_spaet=None):
    """Eine Logzeile. zu_spaet: so viele s kam die Messung zu spaet (= der Rechner hing)."""
    teile = [time.strftime('%H:%M:%S', time.localtime(m['zeit']))]
    if zu_spaet:
        teile.append(f'HING {zu_spaet:.1f}s')
    if m.get('cpu_prozent') is not None:
        teile.append(f"CPU {m['cpu_prozent']:.0f}% (IO-Warten {m['iowait_prozent']:.0f}%)")
    if m.get('last1') is not None:
        teile.append(f"Last {m['last1']:.1f}")
    if m.get('ram_gesamt_mb'):
        teile.append(f"RAM {m['ram_belegt_mb']}/{m['ram_gesamt_mb']} MB, Swap {m['swap_mb']} MB")
    if m.get('gpu_prozent') is not None:
        teile.append(f"GPU {m['gpu_prozent']:.0f}%")
    if m.get('temperatur') is not None:
        teile.append(f"{m['temperatur']:.0f} Grad")
    if m.get('top'):
        teile.append('| ' + ', '.join(f'{n} {p}%' for n, p in m['top']))
    if m.get('threads'):
        teile.append(f"| Threads von {m['top'][0][0]}: " + ', '.join(f'{n} {p}%' for n, p in m['threads']))
    return '  '.join(teile)
