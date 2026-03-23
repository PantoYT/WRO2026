"""
tools/import_wordlist.py — WRO 2026 Esperanto Flashcard Robot
Digitalizacja słowników esperanto: import z pliku TSV/CSV do wordlist.json.

Użycie:
    python tools/import_wordlist.py <plik.tsv> [--wordlist assets/flashcards/wordlist.json]

Format wejściowy (TSV, bez nagłówka):
    słowo_eo<TAB>tłumaczenie_en / tłumaczenie_pl
    saluton<TAB>hello / cześć
    dankon<TAB>thank you / dziękuję

Format wejściowy (CSV, z nagłówkiem):
    word,translation
    saluton,"hello / cześć"

Opcje:
    --wordlist PATH   Ścieżka do wordlist.json (domyślnie: assets/flashcards/wordlist.json)
    --dry-run         Pokaż co zostałoby dodane, ale nie zapisuj

Ten skrypt jest narzędziem digitalizacji — importuje słownictwo z istniejących
słowników esperanto (np. Plena Ilustrita Vortaro w formacie CSV/TSV)
do archiwum robota, deduplikując względem istniejących wpisów.
"""

import json
import csv
import sys
import argparse
from pathlib import Path


def import_tsv(source_path: str, wordlist_path: str, dry_run: bool = False) -> int:
    wp = Path(wordlist_path)
    if wp.exists():
        with open(wp, encoding="utf-8") as f:
            existing = json.load(f)
    else:
        print(f"[IMPORT] Wordlist not found at {wordlist_path} — will create new.")
        existing = []

    existing_words = {e["word"].strip().lower() for e in existing}
    added = 0
    skipped = 0

    sp = Path(source_path)
    if not sp.exists():
        print(f"[IMPORT] ERROR: Source file not found: {source_path}")
        sys.exit(1)

    # Auto-detect delimiter
    with open(sp, encoding="utf-8") as f:
        sample = f.read(1024)
    delimiter = "\t" if "\t" in sample else ","

    with open(sp, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)

    # Skip header if first row looks like a header
    start = 0
    if rows and rows[0] and rows[0][0].strip().lower() in ("word", "vorto", "słowo", "eo", "esperanto"):
        start = 1
        print(f"[IMPORT] Header row detected and skipped: {rows[0]}")

    for row in rows[start:]:
        if len(row) < 2:
            continue
        word        = row[0].strip()
        translation = row[1].strip()
        if not word or not translation:
            continue
        if word.lower() in existing_words:
            skipped += 1
            continue
        new_entry = {"word": word, "translation": translation}
        if not dry_run:
            existing.append(new_entry)
        existing_words.add(word.lower())
        added += 1
        if dry_run:
            print(f"  [DRY] Would add: {word!r} → {translation!r}")

    if not dry_run and added > 0:
        wp.parent.mkdir(parents=True, exist_ok=True)
        with open(wp, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"[IMPORT] Saved {wordlist_path} ({len(existing)} total entries).")

    print(f"[IMPORT] Done — added: {added}, skipped (duplicates): {skipped}")
    return added


def main():
    parser = argparse.ArgumentParser(
        description="Import TSV/CSV word list into wordlist.json for the Esperanto Robot."
    )
    parser.add_argument("source", help="Path to TSV or CSV file with word,translation columns")
    parser.add_argument(
        "--wordlist",
        default="assets/flashcards/wordlist.json",
        help="Path to target wordlist.json (default: assets/flashcards/wordlist.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be added without writing anything"
    )
    args = parser.parse_args()

    if args.dry_run:
        print("[IMPORT] DRY RUN — no files will be modified.")

    import_tsv(args.source, args.wordlist, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
