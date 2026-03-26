"""
tools/import_wordlist.py — Esperanto dictionary digitization tool
WRO 2026 Esperanto Flashcard Robot

Usage:
    python tools/import_wordlist.py source.tsv
    python tools/import_wordlist.py source.tsv --wordlist assets/flashcards/wordlist.json
    python tools/import_wordlist.py source.tsv --dry-run

Input format (TSV, one word per line):
    esperanto_word<TAB>english_translation / polish_translation
    ami<TAB>to love / kochać
    paco<TAB>peace / pokój

If only one translation column is present, it is used as English.
Existing SM-2 progress (sr_ease, sr_interval, etc.) is NEVER overwritten.
Only new words are appended.
"""

import json
import csv
import sys
import argparse
from pathlib import Path

DEFAULT_WORDLIST = Path(__file__).parent.parent / "assets" / "flashcards" / "wordlist.json"


def import_tsv(tsv_path: str, wordlist_path: Path, dry_run: bool = False) -> int:
    """
    Import words from a TSV file into the robot's wordlist.
    Returns the number of new words added.
    """
    if wordlist_path.exists():
        with open(wordlist_path, encoding="utf-8") as f:
            existing: list = json.load(f)
    else:
        existing = []

    existing_words = {e["word"].strip().lower() for e in existing}
    added = 0
    skipped = 0

    with open(tsv_path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f, delimiter="\t")
        for row_num, row in enumerate(reader, start=1):
            if not row or row[0].startswith("#"):
                continue  # skip empty lines and comments
            if len(row) < 2:
                print(f"[IMPORT] Line {row_num}: skipped (need at least 2 columns): {row}")
                continue

            word         = row[0].strip()
            translation  = row[1].strip()
            unit         = row[2].strip() if len(row) > 2 else ""
            pronunciation = row[3].strip() if len(row) > 3 else ""
            part_of_speech = row[4].strip() if len(row) > 4 else ""

            if not word or not translation:
                continue

            if word.lower() in existing_words:
                skipped += 1
                continue

            entry: dict = {"word": word, "translation": translation}
            if unit:           entry["unit"]           = unit
            if pronunciation:  entry["pronunciation"]  = pronunciation
            if part_of_speech: entry["part_of_speech"] = part_of_speech
            existing.append(entry)
            existing_words.add(word.lower())
            added += 1

    print(f"[IMPORT] New words: {added}  |  Already present: {skipped}")

    if added > 0 and not dry_run:
        wordlist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(wordlist_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"[IMPORT] Saved to {wordlist_path}")
    elif dry_run:
        print("[IMPORT] Dry run — nothing written.")

    return added


def main():
    parser = argparse.ArgumentParser(
        description="Import Esperanto words from TSV into the robot's wordlist."
    )
    parser.add_argument("tsv", help="Path to the TSV source file")
    parser.add_argument(
        "--wordlist", default=str(DEFAULT_WORDLIST),
        help=f"Path to wordlist.json (default: {DEFAULT_WORDLIST})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be added without writing anything"
    )
    args = parser.parse_args()

    added = import_tsv(args.tsv, Path(args.wordlist), dry_run=args.dry_run)
    sys.exit(0 if added >= 0 else 1)


if __name__ == "__main__":
    main()