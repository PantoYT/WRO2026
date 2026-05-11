#!/usr/bin/env python3
"""
tools/project_audit.py — WRO2026 Espero-bot · Kontrola projektu
================================================================
Uruchom z katalogu głównego projektu:
    python tools/project_audit.py
    python tools/project_audit.py --json        # zapis do audit_report.json
    python tools/project_audit.py --no-color    # bez kolorów ANSI (CI/logi)
    python tools/project_audit.py --quiet       # tylko błędy i podsumowanie
"""

import os
import sys
import json
import ast
import re
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─── Ścieżki względem ROOT (jeden poziom wyżej niż tools/) ───────────────────
ROOT          = Path(__file__).resolve().parent.parent
ASSETS        = ROOT / "assets"
WORDLIST_JSON = ASSETS / "flashcards" / "wordlist.json"
POEMS_JSON    = ASSETS / "poems" / "poems.json"
POEMS_DIR     = ASSETS / "poems"
MUSIC_JSON    = ASSETS / "music" / "music.json"   # opcjonalny
MUSIC_DIR     = ASSETS / "music"
REQUIREMENTS  = ROOT / "requirements.txt"
TOOLS_DIR     = ROOT / "tools"

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}

# ─── Kolory ANSI ──────────────────────────────────────────────────────────────
USE_COLOR = True

def c(code: str, text: str) -> str:
    if not USE_COLOR:
        return text
    CODES = {
        "reset":"",  # handled below
        "bold":  "\033[1m",  "red":   "\033[91m", "green": "\033[92m",
        "yellow":"\033[93m", "cyan":  "\033[96m", "gray":  "\033[90m",
        "white": "\033[97m", "magenta":"\033[95m",
    }
    return f"{CODES.get(code,'')}{text}\033[0m"

def header(title: str):
    w = 66
    print()
    print(c("cyan", "═" * w))
    print(c("bold", f"  {title}"))
    print(c("cyan", "═" * w))

def ok(msg):   print(c("green",  f"  ✔  {msg}"))
def warn(msg): print(c("yellow", f"  ⚠  {msg}"))
def err(msg):  print(c("red",    f"  ✘  {msg}"))
def info(msg): print(c("gray",   f"     {msg}"))
def bold(msg): print(c("bold",   f"  {msg}"))

report = {"generated_at": datetime.now().isoformat(timespec="seconds"),
          "root": None, "sections": {}}

# ══════════════════════════════════════════════════════════════════════════════
# 1. WORDLIST
# ══════════════════════════════════════════════════════════════════════════════
def audit_wordlist() -> dict:
    header("1 · WORDLIST  (assets/flashcards/wordlist.json)")
    result = {"errors": [], "warnings": [], "stats": {}}

    if not WORDLIST_JSON.exists():
        err(f"Plik nie istnieje: {WORDLIST_JSON}")
        result["errors"].append("file_missing")
        return result

    try:
        words = json.loads(WORDLIST_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        err(f"Błąd JSON: {e}")
        result["errors"].append(f"json_error: {e}")
        return result

    total = len(words)
    ok(f"Wczytano {total} słów")
    result["stats"]["total_words"] = total

    REQUIRED = ["word", "pronunciation", "part_of_speech", "definition",
                "translation", "unit", "correct_count", "wrong_count",
                "sr_ease", "sr_interval", "sr_repetitions", "next_review"]

    parts_of_speech = defaultdict(int)
    units           = defaultdict(int)
    missing_fields  = defaultdict(list)
    seen_words      = {}
    duplicates      = []
    sr_zero         = 0

    for i, w in enumerate(words):
        wid = w.get("word", f"[{i}]")
        if wid in seen_words:
            duplicates.append(wid)
        else:
            seen_words[wid] = i
        for field in REQUIRED:
            if field not in w:
                missing_fields[field].append(wid)
        parts_of_speech[w.get("part_of_speech", "?")] += 1
        units[w.get("unit", "?")] += 1
        if w.get("sr_repetitions", 0) == 0:
            sr_zero += 1

    if missing_fields:
        for field, wl in missing_fields.items():
            warn(f"Brak pola '{field}' w {len(wl)} słowach: {wl[:5]}{'…' if len(wl)>5 else ''}")
            result["warnings"].append(f"missing_{field}: {len(wl)}")
    else:
        ok("Wszystkie wymagane pola obecne")

    if duplicates:
        err(f"Duplikaty ({len(duplicates)}): {duplicates[:10]}")
        result["errors"].append(f"duplicates: {duplicates}")
    else:
        ok("Brak duplikatów")

    bold("Parts of speech:")
    for pos, cnt in sorted(parts_of_speech.items(), key=lambda x: -x[1]):
        info(f"  {pos:20s} {cnt:4d}  ({cnt/total*100:.1f}%)")

    bold("Jednostki (units):")
    for unit, cnt in sorted(units.items(), key=lambda x: -x[1]):
        info(f"  {unit:30s} {cnt:4d}")

    info(f"Nigdy nie ćwiczone (sr_repetitions=0): {sr_zero}/{total}")

    result["stats"].update({
        "parts_of_speech": dict(parts_of_speech),
        "units": dict(units),
        "never_practiced": sr_zero,
        "duplicates_count": len(duplicates),
    })
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 2. AUDIO (poems + music)
# ══════════════════════════════════════════════════════════════════════════════
def audit_audio_dir(label: str, json_path: Path, audio_dir: Path) -> dict:
    header(f"{label}  ({json_path.relative_to(ROOT)})")
    result = {"errors": [], "warnings": [], "stats": {}}

    # JSON
    if not json_path.exists():
        err(f"Plik JSON nie istnieje: {json_path}")
        result["errors"].append("json_missing")
        entries = []
    else:
        try:
            entries = json.loads(json_path.read_text(encoding="utf-8"))
            ok(f"JSON wczytany — {len(entries)} wpisów")
        except json.JSONDecodeError as e:
            err(f"Błąd JSON: {e}")
            result["errors"].append(f"json_error: {e}")
            entries = []

    # Pliki na dysku
    if not audio_dir.exists():
        warn(f"Katalog nie istnieje: {audio_dir}")
        result["warnings"].append("dir_missing")
        files_on_disk = set()
    else:
        files_on_disk = {
            f.name for f in audio_dir.iterdir()
            if f.is_file() and f.suffix.lower() in AUDIO_EXTS
        }
        ok(f"Plików audio na dysku: {len(files_on_disk)}")

    result["stats"] = {
        "json_entries": len(entries),
        "files_on_disk": len(files_on_disk),
    }

    REQUIRED = ["id", "filename", "title", "language"]
    files_in_json  = set()
    seen_ids       = {}
    seen_filenames = {}
    missing_audio  = []

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"[{i}]")

        if eid in seen_ids:
            err(f"Zduplikowane ID: {eid}")
            result["errors"].append(f"duplicate_id: {eid}")
        else:
            seen_ids[eid] = i

        for field in REQUIRED:
            if not entry.get(field):
                result["warnings"].append(f"entry {eid} brak pola '{field}'")

        fname = entry.get("filename", "")
        if fname:
            if fname in seen_filenames:
                result["warnings"].append(
                    f"duplikat filename: '{fname}' (id {seen_filenames[fname]} i {eid})"
                )
            else:
                seen_filenames[fname] = eid
            files_in_json.add(fname)
            if fname not in files_on_disk:
                missing_audio.append(f"[{eid}] {fname}")

    orphan_files = sorted(files_on_disk - files_in_json)

    if missing_audio:
        for m in missing_audio:
            err(f"Brak pliku audio: {m}")
        result["errors"].extend([f"missing_audio: {m}" for m in missing_audio])
    else:
        ok("Wszystkie pliki z JSON istnieją na dysku  ✓")

    if orphan_files:
        for o in orphan_files:
            warn(f"Plik bez wpisu w JSON: {o}")
        result["warnings"].extend([f"orphan: {o}" for o in orphan_files])
    else:
        ok("Brak osieroconych plików audio  ✓")

    # Statystyki
    if entries:
        played = sum(1 for e in entries if e.get("play_count", 0) > 0)
        rated  = sum(1 for e in entries if e.get("rating") is not None)
        langs  = defaultdict(int)
        genres = defaultdict(int)
        for e in entries:
            langs[e.get("language", "?")]  += 1
            genres[e.get("genre", "?")] += 1

        info(f"Odtworzone przynajmniej raz: {played}/{len(entries)}")
        info(f"Ocenione: {rated}/{len(entries)}")
        bold("Języki:")
        for lang, cnt in sorted(langs.items(), key=lambda x: -x[1]):
            info(f"  {lang:20s} {cnt}")
        bold("Gatunki:")
        for genre, cnt in sorted(genres.items(), key=lambda x: -x[1]):
            info(f"  {genre:35s} {cnt}")

        result["stats"].update({
            "played": played, "rated": rated,
            "languages": dict(langs), "genres": dict(genres),
        })

    return result


# ══════════════════════════════════════════════════════════════════════════════
# 3. PLIKI PYTHON (root/*.py + tools/**/*.py)
# ══════════════════════════════════════════════════════════════════════════════
def audit_python_files() -> dict:
    header("3 · PLIKI PYTHON  (root/ + tools/)")
    result = {"files": {}, "errors": [], "warnings": []}

    py_files = sorted(ROOT.glob("*.py")) + sorted(TOOLS_DIR.rglob("*.py"))
    self_path = Path(__file__).resolve()
    py_files = [p for p in py_files if p.resolve() != self_path]

    if not py_files:
        warn("Brak plików .py")
        return result

    all_imports = set()

    for fpath in py_files:
        rel = fpath.relative_to(ROOT)
        info_data = {
            "size_kb": round(fpath.stat().st_size / 1024, 1),
            "imports": [], "functions": [], "classes": [],
            "top_comment": "", "parse_error": None,
        }

        src = fpath.read_text(encoding="utf-8", errors="replace")

        # Nagłówek pliku
        for line in src.splitlines()[:8]:
            stripped = line.strip().lstrip("#").strip()
            if stripped and not stripped.startswith("!"):
                info_data["top_comment"] = stripped[:80]
                break

        # AST
        try:
            tree = ast.parse(src, filename=str(fpath))
        except SyntaxError as e:
            err(f"{rel} — błąd składni: {e}")
            info_data["parse_error"] = str(e)
            result["errors"].append(f"syntax_error: {rel}")
            result["files"][str(rel)] = info_data
            continue

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module.split(".")[0])
        info_data["imports"] = sorted(set(imports))
        all_imports.update(info_data["imports"])

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
                info_data["functions"].append(f"{prefix}{node.name}()")
            elif isinstance(node, ast.ClassDef):
                info_data["classes"].append(node.name)

        result["files"][str(rel)] = info_data

        # Wydruk
        bold(f"  {rel}  [{info_data['size_kb']} KB]")
        if info_data["top_comment"]:
            info(f"    ↳ {info_data['top_comment']}")
        if info_data["imports"]:
            info(f"    imports  : {', '.join(info_data['imports'])}")
        if info_data["functions"]:
            info(f"    funkcje  : {', '.join(info_data['functions'][:8])}"
                 + ("  …" if len(info_data["functions"]) > 8 else ""))
        if info_data["classes"]:
            info(f"    klasy    : {', '.join(info_data['classes'])}")

    ok(f"Przeskanowano {len(py_files)} plików Python")
    result["all_unique_imports"] = sorted(all_imports)

    # ── Krzyżowe sprawdzenie importów vs requirements.txt ──────────────────
    MODULE_TO_PKG = {
        "dotenv":         "python-dotenv",
        "gtts":           "gtts",
        "pygame":         "pygame-ce",
        "edge_tts":       "edge-tts",
        "sounddevice":    "sounddevice",
        "numpy":          "numpy",
        "transformers":   "transformers",
        "torch":          "torch",
        "faster_whisper": "faster-whisper",
        "groq":           "groq",
        "pybricks":       "pybricksdev",
    }
    STDLIB = {
        "ast","asyncio","argparse","collections","csv","datetime","functools",
        "importlib","io","json","logging","math","os","pathlib","queue",
        "random","re","shutil","signal","subprocess","sys","tempfile",
        "threading","time","typing","unittest","urllib","urandom","warnings",
    }
    if REQUIREMENTS.exists():
        req_text = REQUIREMENTS.read_text(encoding="utf-8").lower()
        bold("  Import vs requirements:")
        missing_in_req = []
        for mod in sorted(all_imports):
            if mod in STDLIB:
                continue
            pkg = MODULE_TO_PKG.get(mod, mod).lower().replace("_", "-")
            if pkg not in req_text:
                missing_in_req.append(mod)
                warn(f"    import '{mod}' — brak w requirements.txt?")
        if not missing_in_req:
            ok("    Wszystkie importy pokryte w requirements.txt")
        result["imports_not_in_requirements"] = missing_in_req

    return result


# ══════════════════════════════════════════════════════════════════════════════
# 4. REQUIREMENTS.TXT
# ══════════════════════════════════════════════════════════════════════════════
def audit_requirements() -> dict:
    header("4 · REQUIREMENTS.TXT")
    result = {"errors": [], "warnings": [], "stats": {}}

    if not REQUIREMENTS.exists():
        err(f"Brak pliku: {REQUIREMENTS}")
        result["errors"].append("file_missing")
        return result

    lines = REQUIREMENTS.read_text(encoding="utf-8").splitlines()
    packages = []
    groups   = defaultdict(list)
    current  = "inne"

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            m = re.search(r"[─—–-]{2,}\s*(.+?)\s*[─—–-]{2,}", s)
            if m:
                current = m.group(1).strip()
            continue
        pkg_match = re.match(r"^([A-Za-z0-9_\-]+)", s)
        if pkg_match:
            pkg = s.split("#")[0].strip()
            packages.append(pkg)
            groups[current].append(pkg)

    ok(f"Znaleziono {len(packages)} pakietów")
    for group, pkgs in groups.items():
        bold(f"  [{group}]")
        for p in pkgs:
            info(f"    {p}")

    result["stats"] = {"total": len(packages), "groups": {k: v for k, v in groups.items()}}
    return result


# ══════════════════════════════════════════════════════════════════════════════
# 5. STRUKTURA PROJEKTU
# ══════════════════════════════════════════════════════════════════════════════
def audit_structure() -> dict:
    header("5 · STRUKTURA PROJEKTU  (root, bez assets/)")
    result = {"tree": {}, "errors": [], "warnings": []}

    SKIP = {"assets", "__pycache__", ".git", "node_modules",
            "espero_env", ".venv", "venv", "build", "dist", ".idea", ".vscode"}

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for item in ROOT.rglob("*"):
        parts = item.relative_to(ROOT).parts
        if any(p in SKIP or p.startswith(".") for p in parts):
            continue
        if item.is_file():
            top = parts[0] if len(parts) > 1 else "."
            ext = item.suffix.lower() or "(brak)"
            counts[top][ext] += 1

    for top_dir in sorted(counts.keys()):
        bold(f"  {top_dir}/")
        for ext, cnt in sorted(counts[top_dir].items()):
            info(f"    {ext:14s}  ×{cnt}")
        result["tree"][top_dir] = dict(counts[top_dir])

    KEY_FILES = [
        ROOT / "computer.py", ROOT / "hub.py", ROOT / "config.json",
        ROOT / ".env",        ROOT / ".env.example", ROOT / "README.md",
        REQUIREMENTS,
    ]
    bold("  Kluczowe pliki:")
    for f in KEY_FILES:
        if f.exists():
            ok(f"    {f.relative_to(ROOT)}")
        else:
            warn(f"    {f.relative_to(ROOT)}  (brak)")
            result["warnings"].append(f"missing: {f.name}")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# PODSUMOWANIE
# ══════════════════════════════════════════════════════════════════════════════
def print_summary(all_results: dict):
    header("PODSUMOWANIE")
    total_err  = 0
    total_warn = 0
    for section, res in all_results.items():
        e = len(res.get("errors", []))
        w = len(res.get("warnings", []))
        total_err  += e
        total_warn += w
        status   = c("green", "  OK") if e == 0 else c("red", f"  BŁĘDY: {e}")
        warn_str = f"  {c('yellow', f'ostrzeżenia: {w}')}" if w else ""
        print(f"  {section:35s}{status}{warn_str}")

    print()
    if total_err == 0:
        print(c("green", c("bold", "  ✔  Brak błędów krytycznych — projekt OK")))
    else:
        print(c("red",   c("bold", f"  ✘  Błędy krytyczne łącznie: {total_err}")))
    if total_warn:
        print(c("yellow", f"  ⚠  Ostrzeżeń łącznie: {total_warn}"))
    print()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    global USE_COLOR

    parser = argparse.ArgumentParser(description="WRO2026 Espero-bot — kontrola projektu")
    parser.add_argument("--json",     action="store_true", help="Zapisz raport JSON → audit_report.json")
    parser.add_argument("--no-color", action="store_true", help="Wyłącz kolory ANSI")
    parser.add_argument("--quiet",    action="store_true", help="Tylko błędy i podsumowanie")
    args = parser.parse_args()

    if args.no_color or not sys.stdout.isatty():
        USE_COLOR = False

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print()
    print(c("cyan", c("bold",
        "╔════════════════════════════════════════════════════════════════╗\n"
       f"║  WRO2026 Espero-bot — PROJECT AUDIT          {ts}  ║\n"
        "╚════════════════════════════════════════════════════════════════╝"
    )))
    print(c("gray", f"  Root: {ROOT}\n"))

    all_results: dict = {}
    all_results["wordlist"]     = audit_wordlist()
    all_results["poems"]        = audit_audio_dir("2a · POEMS", POEMS_JSON, POEMS_DIR)
    if MUSIC_DIR.exists() or MUSIC_JSON.exists():
        all_results["music"]    = audit_audio_dir("2b · MUSIC", MUSIC_JSON, MUSIC_DIR)
    all_results["python_files"] = audit_python_files()
    all_results["requirements"] = audit_requirements()
    all_results["structure"]    = audit_structure()

    print_summary(all_results)

    if args.json:
        out = ROOT / "audit_report.json"
        report["root"] = str(ROOT)
        report["sections"] = all_results
        out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8"
        )
        print(c("cyan", f"  Raport JSON → {out}\n"))


if __name__ == "__main__":
    main()
