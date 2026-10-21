#!/usr/bin/env python3
"""Historische Fehler reproduzieren; Exit 0 ist KEINE Produktabnahme.

Exportiert ausschliesslich den lokal vorhandenen BASIS_SHA per git archive.
Die Worker laufen mit lokalen ROS-Attrappen in getrennten Python-Prozessen.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
from basis import BASIS_SHA, REPO

HERE = Path(__file__).resolve().parent
QUELLEN = (
    "lib/lidar.py", "ki/zentrale.py", "ki/entscheider.py",
    "line_follower/line_follower.py", "tests/attrappen/rclpy/node.py",
)


def git(*args: str) -> bytes:
    lauf = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, check=False)
    if lauf.returncode:
        raise RuntimeError("lokale_git_quelle_fehlt")
    return lauf.stdout


def exportiere(ziel: Path) -> None:
    if git("rev-parse", "--verify", BASIS_SHA + "^{commit}").decode("ascii").strip() != BASIS_SHA:
        raise RuntimeError("falscher_basiscommit")
    # Kein Checkout, Fetch, Worktree oder Schreibzugriff auf Git-Metadaten.
    daten = git("-c", "core.autocrlf=false", "-c", "core.eol=lf",
                "archive", "--format=tar", BASIS_SHA)
    with tarfile.open(fileobj=io.BytesIO(daten), mode="r:") as archiv:
        for eintrag in archiv:
            pfad = PurePosixPath(eintrag.name)
            if (pfad.is_absolute() or "\\" in eintrag.name or ":" in eintrag.name
                    or any(teil in ("", ".", "..") for teil in eintrag.name.rstrip("/").split("/"))
                    or not (eintrag.isdir() or eintrag.isfile())):
                raise RuntimeError("unzulassiger_archiveintrag")
            datei = ziel.joinpath(*pfad.parts)
            try:
                datei.resolve().relative_to(ziel.resolve())
            except ValueError:
                raise RuntimeError("archiveintrag_verlaesst_export") from None
            if eintrag.isdir():
                datei.mkdir(parents=True, exist_ok=True)
            else:
                datei.parent.mkdir(parents=True, exist_ok=True)
                quelle = archiv.extractfile(eintrag)
                if quelle is None:
                    raise RuntimeError("archiveintrag_nicht_lesbar")
                with quelle, datei.open("wb") as aus:
                    aus.write(quelle.read())


def worker(name: str, export: Path) -> dict:
    lauf = subprocess.run(
        [sys.executable, "-I", "-B", str(HERE / name), "--export", str(export)],
        cwd=export, capture_output=True, text=True, encoding="utf-8",
        errors="strict", timeout=60, check=False,
    )
    if lauf.returncode:
        # Tracebacks koennen lokale Pfade enthalten und sind kein portabler Beleg.
        raise RuntimeError("worker_fehler:" + name)
    ergebnis = json.loads(lauf.stdout)
    if (ergebnis.get("product_acceptance") is not False
            or ergebnis.get("historical_signature_match") is not True):
        raise RuntimeError("historische_signatur_abweichend:" + name)
    return ergebnis


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="JSON-Zieldatei; Ergebnis erscheint auch auf stdout")
    args = parser.parse_args()
    bericht = {
        "purpose": "historical_error_reproduction",
        "basis_commit": BASIS_SHA,
        "product_acceptance": False,
        "hardware_access": False,
        "meaning_of_exit_zero": "Fehlersignatur am fixierten Altstand reproduziert; keine bestandene Sicherheitspruefung.",
        "python": platform.python_version(),
    }
    code = 1
    try:
        with tempfile.TemporaryDirectory(prefix="lidar-historisch-") as tmp:
            export = Path(tmp)
            exportiere(export)
            blob = {name: git("show", BASIS_SHA + ":" + name) for name in QUELLEN}
            bericht["source_sha256_git_blob_bytes"] = {
                name: hashlib.sha256(raw).hexdigest() for name, raw in blob.items()}
            bericht["source_sha256_export_bytes"] = {
                name: hashlib.sha256((export / name).read_bytes()).hexdigest() for name in QUELLEN}
            normalisiert = {}
            for name, raw in blob.items():
                text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                export_text = (export / name).read_text(encoding="utf-8")
                if text != export_text:
                    raise RuntimeError("exportinhalt_weicht_ab:" + name)
                normalisiert[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()
            bericht["source_sha256_normalized_utf8_lf"] = normalisiert
            bericht["fahrpfad"] = worker("historischer_fahrpfad.py", export)
            bericht["geometrie"] = worker("historische_geometrie.py", export)
        bericht["historical_signature_match"] = True
        bericht["status"] = "Fehler reproduziert"
        code = 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        bericht["historical_signature_match"] = False
        bericht["status"] = "Reproduktion unvollstaendig"
        # Nur selbst gesetzte, pfadfreie Fehlercodes ausgeben.
        bericht["error"] = str(exc) if type(exc) is RuntimeError else type(exc).__name__
    text = json.dumps(bericht, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
