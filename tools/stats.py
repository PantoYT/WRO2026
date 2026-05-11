#!/usr/bin/env python3
"""
tools/stats.py — WRO2026 Espero-bot · Statystyki nauki
=======================================================
Pokazuje postęp SR, słabe jednostki, rozkład interwałów.

Użycie:
    python tools/stats.py
    python tools/stats.py --unit Robotics   # tylko jedna jednostka
    python tools/stats.py --weak 15         # top 15 najtrudniejszych słów
    python tools/stats.py --due             # słowa do powtórki dziś
    python tools/stats.py --no-color
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

ROOT       = Path(__file__).resolve().parent.parent
WORDS_FILE = ROOT / "assets" / "flashcards" / "wordlist.json"

# ─── Kolory ───────────────────────────────────────────────────────────────────
USE_COLOR = True

def c(code, text):
    if not USE_COLOR:
        return text
    CODES = {
        "bold":"\033[1m","red":"\033[91m","green":"\033[92m",
        "yellow":"\033[93m","cyan":"\033[96m","gray":"\033[90m",
        "magenta":"\033[95m","white":"\033[97m",
    }
    return f"{CODES.get(code,'')}{text}\033[0m"

def bar(value, total, width=30, color="green"):
    filled = int(round(value / total * width)) if total else 0
    b = "█" * filled + "░" * (width - filled)
    return c(color, b)

def header(t):
    print()
    print(c("cyan", "═" * 62))
    print(c("bold", f"  {t}"))
    print(c("cyan", "═" * 62))

# ─── Helpers ──────────────────────────────────────────────────────────────────

def mastery_level(w: dict) -> str:
    """Klasyfikacja słowa wg postępu SR."""
    reps = w.get("sr_repetitions", 0)
    iv   = w.get("sr_interval", 1)
    if reps == 0:
        return "new"
    if reps < 3 or iv < 7:
        return "learning"
    if iv < 21:
        return "reviewing"
    return "mastered"

LEVEL_ORDER  = ["new", "learning", "reviewing", "mastered"]
LEVEL_COLORS = {"new":"gray","learning":"yellow","reviewing":"cyan","mastered":"green"}
LEVEL_PL     = {"new":"Nowe","learning":"W nauce","reviewing":"Powtórka","mastered":"Opanowane"}

def accuracy(w: dict) -> float:
    total = w.get("correct_count", 0) + w.get("wrong_count", 0)
    if total == 0:
        return None
    return w.get("correct_count", 0) / total * 100

def parse_date(s) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

# ══════════════════════════════════════════════════════════════════════════════

def main():
    global USE_COLOR
    parser = argparse.ArgumentParser(description="WRO2026 — statystyki nauki")
    parser.add_argument("--unit",     default=None, help="Filtruj po jednostce")
    parser.add_argument("--weak",     type=int, default=10,
                        help="Pokaż N najtrudniejszych słów (domyślnie 10)")
    parser.add_argument("--due",      action="store_true",
                        help="Pokaż tylko słowa do powtórki dziś")
    parser.add_argument("--no-color", action="store_true")
    args = parser.parse_args()

    if args.no_color:
        USE_COLOR = False

    if not WORDS_FILE.exists():
        print(f"[ERR] Brak pliku: {WORDS_FILE}")
        sys.exit(1)

    all_words = json.loads(WORDS_FILE.read_text(encoding="utf-8"))
    now = datetime.now(tz=timezone.utc)

    if args.unit:
        words = [w for w in all_words if w.get("unit","") == args.unit]
        if not words:
            units = sorted({w.get("unit","") for w in all_words})
            print(f"[ERR] Brak jednostki '{args.unit}'. Dostępne:\n  {', '.join(units)}")
            sys.exit(1)
    else:
        words = all_words

    total = len(words)

    # ── 1. Przegląd ogólny ────────────────────────────────────────────────────
    header("1 · PRZEGLĄD OGÓLNY" + (f"  [{args.unit}]" if args.unit else ""))

    levels = defaultdict(list)
    for w in words:
        levels[mastery_level(w)].append(w)

    for lvl in LEVEL_ORDER:
        grp = levels[lvl]
        pct = len(grp) / total * 100 if total else 0
        b   = bar(len(grp), total, width=28, color=LEVEL_COLORS[lvl])
        print(f"  {LEVEL_PL[lvl]:12s}  {b}  {len(grp):4d}  ({pct:5.1f}%)")

    # Due today
    due_words = [w for w in words if (d := parse_date(w.get("next_review"))) and d <= now]
    overdue   = [w for w in words if (d := parse_date(w.get("next_review"))) and d < now
                 and (now - d).days > 1]
    print()
    print(f"  Do powtórki dziś : {c('yellow', str(len(due_words)))}")
    if overdue:
        print(f"  Przeterminowane  : {c('red', str(len(overdue)))}  (>1 dzień)")

    # Accuracy overall
    attempted = [w for w in words if w.get("correct_count",0) + w.get("wrong_count",0) > 0]
    if attempted:
        total_c = sum(w.get("correct_count",0) for w in attempted)
        total_w = sum(w.get("wrong_count",0)   for w in attempted)
        overall_acc = total_c / (total_c + total_w) * 100
        print(f"  Skuteczność      : {c('cyan', f'{overall_acc:.1f}%')}  "
              f"({total_c} dobrze / {total_w} źle)  z {len(attempted)} słów")

    # ── 2. Postęp per jednostka ───────────────────────────────────────────────
    if not args.unit:
        header("2 · POSTĘP PER JEDNOSTKA")
        by_unit = defaultdict(list)
        for w in words:
            by_unit[w.get("unit","?")].append(w)

        rows = []
        for unit, uw in by_unit.items():
            n      = len(uw)
            mast   = sum(1 for w in uw if mastery_level(w) == "mastered")
            learn  = sum(1 for w in uw if mastery_level(w) == "learning")
            new_   = sum(1 for w in uw if mastery_level(w) == "new")
            pct    = mast / n * 100 if n else 0
            rows.append((unit, n, mast, learn, new_, pct))

        rows.sort(key=lambda x: x[5])  # od najsłabszej

        for unit, n, mast, learn, new_, pct in rows:
            b = bar(mast, n, width=20, color="green")
            warn_marker = c("yellow", " ⚠") if pct < 30 and n >= 10 else "  "
            print(f"  {unit:25s} {b} {mast:3d}/{n:<3d} ({pct:5.1f}%){warn_marker}")

    # ── 3. Najtrudniejsze słowa ───────────────────────────────────────────────
    header(f"3 · NAJTRUDNIEJSZE SŁOWA  (top {args.weak})")

    # Słowa z przynajmniej jedną próbą, posortowane wg accuracy rosnąco
    attempted_words = [w for w in words
                       if w.get("correct_count",0) + w.get("wrong_count",0) > 0]
    attempted_words.sort(key=lambda w: accuracy(w))
    weak = attempted_words[:args.weak]

    if not weak:
        print(c("gray", "  Brak danych — żadne słowo nie było jeszcze ćwiczone."))
    else:
        for w in weak:
            acc  = accuracy(w)
            word = w["word"]
            tr   = w.get("translation", w.get("definition",""))[:30]
            unit = w.get("unit","")
            acc_str = c("red", f"{acc:5.1f}%") if acc < 50 else c("yellow", f"{acc:5.1f}%")
            print(f"  {word:20s}  {acc_str}  "
                  f"({w.get('correct_count',0)}✔/{w.get('wrong_count',0)}✘)  "
                  f"{tr}  [{unit}]")

    # ── 4. Słowa do powtórki (--due) ──────────────────────────────────────────
    if args.due or due_words:
        header("4 · DO POWTÓRKI DZIŚ")
        if not due_words:
            print(c("green", "  Brak słów do powtórki — wszystko aktualne!"))
        else:
            due_words.sort(key=lambda w: parse_date(w.get("next_review")) or now)
            for w in due_words[:30]:
                d    = parse_date(w.get("next_review"))
                late = (now - d).days if d else 0
                flag = c("red", f"  +{late}d") if late > 0 else ""
                tr   = w.get("translation", w.get("definition",""))[:28]
                print(f"  {w['word']:20s}  iv={w.get('sr_interval',1):3d}d  "
                      f"reps={w.get('sr_repetitions',0)}  {tr}{flag}")
            if len(due_words) > 30:
                print(c("gray", f"  … i {len(due_words)-30} więcej"))

    # ── 5. Rozkład interwałów SR ──────────────────────────────────────────────
    header("5 · ROZKŁAD INTERWAŁÓW SR")
    buckets = {"0d (nowe)":0, "1d":0, "2-6d":0, "7-20d":0, "21-60d":0, "60d+":0}
    for w in words:
        iv = w.get("sr_interval", 1)
        r  = w.get("sr_repetitions", 0)
        if r == 0:
            buckets["0d (nowe)"] += 1
        elif iv == 1:
            buckets["1d"] += 1
        elif iv <= 6:
            buckets["2-6d"] += 1
        elif iv <= 20:
            buckets["7-20d"] += 1
        elif iv <= 60:
            buckets["21-60d"] += 1
        else:
            buckets["60d+"] += 1

    for label, cnt in buckets.items():
        b = bar(cnt, total, width=24, color="cyan")
        print(f"  {label:12s}  {b}  {cnt:4d}")

    print()


if __name__ == "__main__":
    main()
