"""Fixierte oeffentliche Quellen der historischen Fehlerreproduktion.

Keine Netzwerkzugriffe. ``lese_quelle`` liest den Git-Blob, nicht den Arbeitsbaum.
"""
from __future__ import annotations

import ast
from pathlib import Path, PurePosixPath
import subprocess

BASIS_SHA = "d92e366907fd538c377c272250a0e2d75120b5e2"
REPO = Path(__file__).resolve().parents[3]


def lese_quelle(relpath: str) -> str:
    """UTF-8-Quelltext aus BASIS_SHA, mit LF und ohne lokale Dateinamen."""
    teile = relpath.split("/")
    if (not relpath or "\\" in relpath or ":" in relpath
            or PurePosixPath(relpath).is_absolute()
            or any(teil in ("", ".", "..") for teil in teile)):
        raise ValueError("Erwartet wird ein relativer Git-Dateipfad.")
    lauf = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{BASIS_SHA}:{relpath}"],
        capture_output=True, check=False,
    )
    if lauf.returncode:
        raise RuntimeError("Fixierte Git-Quelle ist lokal nicht verfuegbar.")
    return lauf.stdout.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def pruefe_modul(modul, export: Path, relpath: str) -> None:
    """Vor Konstruktoraufrufen den exakten erwarteten Import pruefen."""
    datei = getattr(modul, "__file__", None)
    if datei is None or Path(datei).resolve() != (export / relpath).resolve():
        raise RuntimeError("Unerwarteter Modulpfad: " + relpath)


def zentrale_methoden(export: Path, numpy, lidar) -> dict:
    """Nur die drei unveraenderten Auswertungsmethoden aus Zentrale laden."""
    baum = ast.parse((export / "ki/zentrale.py").read_text(encoding="utf-8"))
    klassen = [n for n in baum.body if isinstance(n, ast.ClassDef) and n.name == "Zentrale"]
    if len(klassen) != 1:
        raise RuntimeError("Historische Zentrale ist nicht eindeutig.")
    namen = {"_scan", "lidar_pruefen", "lidar_hinten"}
    methoden = [n for n in klassen[0].body if isinstance(n, ast.FunctionDef) and n.name in namen]
    if len(methoden) != 3 or {n.name for n in methoden} != namen:
        raise RuntimeError("Historische Auswertungsmethoden fehlen.")
    import time
    raum = {"np": numpy, "time": time, "lidar": lidar}
    exec(compile(ast.Module(body=methoden, type_ignores=[]), "ki/zentrale.py", "exec"), raum)
    return {name: raum[name] for name in namen}
