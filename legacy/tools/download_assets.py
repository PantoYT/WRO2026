#!/usr/bin/env python3
"""
WRO2026 Asset Downloader
Pobiera nowe pliki audio do assets/music i assets/poems
Szuka po tytule na YouTube (ytsearch) — bez zmyślonych URL-i.

Wymaga: yt-dlp (pip install yt-dlp)
Użycie:  python download_assets.py
         python download_assets.py --only music
         python download_assets.py --only poems
         python download_assets.py --dry-run
"""

import subprocess
import sys
import json
import argparse
from pathlib import Path

# ─── Konfiguracja ─────────────────────────────────────────────────────────────

BASE_DIR  = Path(__file__).parent.parent   # tools/ → WRO2026/
MUSIC_DIR = BASE_DIR / "assets" / "music"
POEMS_DIR = BASE_DIR / "assets" / "poems"

# JSON-y z metadanymi
MUSIC_JSON = MUSIC_DIR / "music.json"
POEMS_JSON = POEMS_DIR / "poems.json"

# ─── Pomocnicze ───────────────────────────────────────────────────────────────

def check_ytdlp():
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("BŁĄD: yt-dlp nie jest zainstalowany.")
        print("Zainstaluj przez: pip install yt-dlp")
        sys.exit(1)


def load_new_items(json_path: Path, kind: str) -> list[tuple[str, str]]:
    """
    Wczytuje JSON i zwraca listę (filename, search_query) dla wpisów,
    których 'source' zaczyna się od 'http' (czyli są nowe, do pobrania).
    """
    with open(json_path, encoding="utf-8") as f:
        entries = json.load(f)

    items = []
    for e in entries:
        source = e.get("source", "")
        if not source.startswith("http"):
            continue  # 'existing' — plik już jest na dysku

        filename = e["filename"]

        # Budujemy zapytanie wyszukiwania z dostępnych pól
        if kind == "music":
            artist = e.get("artist") or ""
            title  = e.get("title")  or Path(filename).stem
            query  = f"{artist} {title}".strip()
        else:  # poems
            author = e.get("author") or e.get("artist") or ""
            title  = e.get("title")  or Path(filename).stem
            query  = f"{author} {title} esperanto".strip()

        items.append((filename, query))

    return items


def build_search_url(query: str) -> str:
    """ytsearch1: pobiera pierwszy wynik wyszukiwania YouTube."""
    return f"ytsearch1:{query}"


def download(items: list[tuple], dest_dir: Path, label: str, dry_run: bool = False):
    dest_dir.mkdir(parents=True, exist_ok=True)
    total   = len(items)
    ok      = 0
    skipped = 0
    failed  = []

    print(f"\n{'='*60}")
    print(f"  {label} — {total} plików → {dest_dir}")
    if dry_run:
        print("  [TRYB DRY-RUN — nic nie zostanie pobrane]")
    print(f"{'='*60}")

    for i, (filename, query) in enumerate(items, 1):
        dest_file = dest_dir / filename

        if dest_file.exists():
            print(f"[{i:>2}/{total}] POMIJA  {filename}")
            skipped += 1
            continue

        search_url = build_search_url(query)
        print(f"[{i:>2}/{total}] Szuka   \"{query}\"")
        print(f"           → {filename}")

        if dry_run:
            ok += 1
            continue

        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
            "--no-playlist",
            "--no-progress",
            "--quiet",
            "--no-warnings",
            "-o", str(dest_dir / filename),
            search_url,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and dest_file.exists():
            size_kb = dest_file.stat().st_size // 1024
            print(f"           OK  {size_kb} KB")
            ok += 1
        else:
            err = result.stderr.strip().splitlines()
            short_err = err[-1] if err else "nieznany błąd"
            print(f"           BŁĄD: {short_err}")
            failed.append((filename, query, short_err))

    print(f"\n  Wynik {label}: {ok} pobrano, {skipped} pominięto, {len(failed)} błędów")

    if failed:
        print(f"\n  Nieudane ({label}):")
        for fname, query, err in failed:
            print(f"    - {fname}")
            print(f"      zapytanie: {query}")
            print(f"      błąd:      {err}")

    return ok, skipped, failed


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WRO2026 asset downloader")
    parser.add_argument("--only",    choices=["music", "poems"], help="Pobierz tylko jedną kategorię")
    parser.add_argument("--dry-run", action="store_true",        help="Pokaż co zostałoby pobrane bez faktycznego pobierania")
    args = parser.parse_args()

    if not args.dry_run:
        check_ytdlp()

    print("WRO2026 Asset Downloader")
    print(f"Katalog bazowy: {BASE_DIR.resolve()}")

    total_ok   = 0
    total_skip = 0
    total_fail = []

    if args.only != "poems":
        items = load_new_items(MUSIC_JSON, "music")
        ok, skip, fail = download(items, MUSIC_DIR, "MUZYKA", dry_run=args.dry_run)
        total_ok += ok; total_skip += skip; total_fail += fail

    if args.only != "music":
        items = load_new_items(POEMS_JSON, "poems")
        ok, skip, fail = download(items, POEMS_DIR, "POEMS", dry_run=args.dry_run)
        total_ok += ok; total_skip += skip; total_fail += fail

    print(f"\n{'='*60}")
    print(f"  RAZEM: {total_ok} pobrano, {total_skip} pominięto, {len(total_fail)} błędów")
    print(f"{'='*60}\n")

    if total_fail:
        sys.exit(1)


if __name__ == "__main__":
    main()