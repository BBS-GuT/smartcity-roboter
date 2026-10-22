#!/usr/bin/env python3
"""Transactionally install and optionally activate the MQTT desktop panel."""
import argparse, ast, json, math, os, re, shlex, shutil, signal, subprocess, sys, time
from datetime import datetime
from pathlib import Path
import urllib.request
import tempfile

BASE_URL = "http://10.0.12.100:8765/"
FILES = {"panel.py":"panel/panel.py", "panel_index.html":"panel/index.html",
         "mqtt_data.py":"panel/mqtt_data.py", "telemetry_detail.py":"panel/telemetry_detail.py",
         "robot_live_test.py":"mqtt/robot_live_test.py",
         "microros_agent_stable.sh":"scripts/microros_agent_stable.sh"}
MAX_SIZE = 2_000_000

def validate_file(relative, body):
    if not body or len(body) > MAX_SIZE or b"\0" in body:
        raise RuntimeError("Unerwartete Dateigroesse: " + relative)
    try: text = body.decode("utf-8")
    except UnicodeDecodeError as exc: raise RuntimeError("Keine UTF-8-Datei: " + relative) from exc
    if relative.endswith(".py"): ast.parse(text, filename=relative)
    elif relative.endswith(".html") and 'id="s-mqtt"' not in text: raise RuntimeError("MQTT-Ansicht fehlt")
    elif relative.endswith(".sh") and (not text.startswith("#!/") or "micro_ros_agent" not in text):
        raise RuntimeError("Ungueltiger micro-ROS-Agent-Wrapper")
    if relative.endswith('.sh'):
        with tempfile.TemporaryDirectory() as directory:
            staged = Path(directory) / 'check.sh'
            staged.write_bytes(body)
            subprocess.run(['bash', '-n', str(staged)], check=True, capture_output=True, text=True)

def download_all():
    result = {}
    for remote, relative in FILES.items():
        with urllib.request.urlopen(BASE_URL + remote, timeout=15) as response:
            body = response.read(MAX_SIZE + 1)
        validate_file(relative, body); result[relative] = body
    return result

def python_script(command, cwd):
    try: words = shlex.split(command)
    except ValueError: return None
    if not words: return None
    i = 0
    if Path(words[0]).name == "env":
        i = 1
        while i < len(words) and ("=" in words[i] or words[i].startswith("-")): i += 1
    if i >= len(words) or not re.fullmatch(r"python(?:3(?:\.\d+)?)?", Path(words[i]).name): return None
    i += 1
    while i < len(words):
        word = words[i]
        if word in ("-", "-c", "-m"): return None
        if word in ("-W", "-X"): i += 2; continue
        if word.startswith("-"): i += 1; continue
        path = Path(word)
        return (path if path.is_absolute() else Path(cwd)/path).resolve(strict=False)
    return None

def process_rows():
    out = subprocess.run(["ps","-eo","pid=,args="], check=True, text=True, capture_output=True).stdout
    return [(int(x[0]),x[1]) for line in out.splitlines() if len(x:=line.strip().split(None,1)) == 2 and x[0].isdigit()]

def process_script(pid, command):
    try: cwd = os.readlink(f"/proc/{pid}/cwd")
    except OSError: return None
    return python_script(command, cwd)

def hazardous_process(command):
    try: words = shlex.split(command)
    except ValueError: return False
    words = [x.replace("\\","/").rstrip("/") for x in words]
    return any(x == "line_follower.py" or x.endswith("/line_follower.py") or
               x == "ki/zentrale.py" or x.endswith("/ki/zentrale.py") for x in words)

def preflight(rows):
    bad = [pid for pid, cmd in rows if hazardous_process(cmd)]
    if bad: raise RuntimeError("Aktive Fahr-/KI-Prozesse; Abbruch (PID " + ",".join(map(str,bad)) + ")")

def install(repo, downloaded):
    backup = repo/"logs"/("panel-mqtt-backup-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    existed = {}
    try:
        backup.mkdir(parents=True)
        for relative in downloaded:
            target=repo/relative; existed[relative]=target.exists()
            if target.exists():
                saved=backup/relative; saved.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,saved)
        for relative,body in downloaded.items():
            target=repo/relative; target.parent.mkdir(parents=True,exist_ok=True)
            temp=target.with_name(target.name+".mqtt-new"); temp.write_bytes(body); os.replace(temp,target)
            if relative.endswith(".sh"): target.chmod(target.stat().st_mode|0o111)
    except Exception:
        for relative,old in existed.items():
            target,saved=repo/relative,backup/relative
            if old and saved.exists(): shutil.copy2(saved,target)
            elif not old and target.exists(): target.unlink()
        raise
    return backup

def stop_owned(repo, rows):
    targets={(repo/x).resolve() for x in ("panel/panel.py","mqtt/robot_live_test.py","panel/fenster.py")}
    pids=[p for p,c in rows if p != os.getpid() and process_script(p,c) in targets]
    for pid in pids:
        try: os.kill(pid,signal.SIGINT)
        except ProcessLookupError: pass
    deadline=time.monotonic()+20; remaining=set(pids)
    while remaining and time.monotonic()<deadline:
        for pid in list(remaining):
            try: os.kill(pid,0)
            except ProcessLookupError: remaining.remove(pid)
        if remaining: time.sleep(.2)
    if remaining: raise RuntimeError("Keine SIGINT-Beendigung: "+",".join(map(str,remaining)))

def status(timeout=1):
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/api/status",timeout=timeout) as response: return json.load(response)
    except Exception: return None

def activate(repo):
    stop_owned(repo,process_rows()); logs=repo/"logs"; logs.mkdir(exist_ok=True)
    env=os.environ.copy(); env.update(SMARTCITY_MQTT="1",MQTT_HOST="127.0.0.1",MQTT_PORT="1883")
    py=shutil.which("python3") or sys.executable
    with (logs/"panel-mqtt-activated.log").open("ab") as out:
        subprocess.Popen(['bash', '-c', 'source "$1" && exec "$2" "$3" --kein-netz --port 8080',
                          'panel-mqtt', str(repo/'scripts/env.sh'), py, str(repo/'panel/panel.py')],cwd=repo,env=env,
                         stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
    deadline=time.monotonic()+20; state=None
    while state is None and time.monotonic()<deadline: state=status(); time.sleep(.4)
    if state is None: raise RuntimeError("Panel antwortet nach 20 Sekunden nicht")
    denv=env.copy(); denv["DISPLAY"]=denv.get("DISPLAY") or ":0"; uid=os.getuid()
    for candidate in (Path(f"/run/user/{uid}/gdm/Xauthority"),Path.home()/".Xauthority"):
        if candidate.is_file(): denv["XAUTHORITY"]=str(candidate); break
    if Path(f"/run/user/{uid}/bus").exists(): denv["DBUS_SESSION_BUS_ADDRESS"]=f"unix:path=/run/user/{uid}/bus"
    with (logs/"panel-fenster.log").open("ab") as out:
        subprocess.Popen([py,str(repo/"panel/fenster.py"),"http://localhost:8080/?ansicht=mqtt"],cwd=repo,env=denv,
                         stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
    return state

def verify_agent(repo):
    out=subprocess.run(["systemctl","show","m3pro-microros.service","-p","ExecStart","--value"],
                       check=True,text=True,capture_output=True).stdout
    wrapper=str((repo/"scripts/microros_agent_stable.sh").resolve())
    if wrapper not in out: raise RuntimeError("Agent-Neustart abgelehnt: ExecStart verwendet nicht "+wrapper)
    subprocess.run(["sudo","-v"],check=True)


def agent_is_active():
    return subprocess.run(["systemctl", "is-active", "--quiet", "m3pro-microros.service"],
                          capture_output=True).returncode == 0

def battery_text(state):
    if isinstance(state,dict):
        value=state.get('akku')
        if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value):
            return f"{value:.3f} V"
    return "unbekannt"


def fresh_battery():
    request = urllib.request.Request('http://127.0.0.1:8080/api/akku_neu', data=b'{}',
                                     headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            print('Akkuabruf:', json.load(response).get('antwort', 'unbekannt'))
    except (OSError, ValueError) as error:
        print('Akkuabruf nicht bestätigt:', error)
    return status(timeout=3)

def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument("--activate",action="store_true"); parser.add_argument("--restart-agent",action="store_true")
    args=parser.parse_args(argv); repo=Path.home()/"smartcity-roboter"
    if not (repo/"panel/panel.py").is_file(): raise RuntimeError("Roboter-Repository ~/smartcity-roboter fehlt")
    preflight(process_rows()); downloaded=download_all()
    start_agent = args.restart_agent and not agent_is_active()
    if start_agent: verify_agent(repo)
    backup=install(repo,downloaded)
    if start_agent:
        subprocess.run(["sudo","systemctl","start","m3pro-microros.service"],check=True)
    elif args.restart_agent:
        print("Agent bereits aktiv: Neustart zum Schutz der Board-ROS-Entities ausgelassen.")
    state=activate(repo) if args.activate else status()
    if args.activate: state=fresh_battery()
    print("Installation erfolgreich. Sicherung:",backup)
    print("Panelstatus:","online" if state is not None else "nicht aktiv")
    print("Aktueller Akku:",battery_text(state))

if __name__ == "__main__": main()
