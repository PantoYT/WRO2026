#!/usr/bin/env python3
"""
tools/check_tts.py — WRO2026 Espero-bot · Test TTS
====================================================
Generuje i odtwarza TTS dla próbki słów z wordlisty.
Pozwala ocenić jakość eo_to_pl_phonetic() przed zawodami.

Użycie:
    python tools/check_tts.py                  # 10 losowych słów
    python tools/check_tts.py -n 20            # 20 słów
    python tools/check_tts.py -u Robotics      # tylko jednostka Robotics
    python tools/check_tts.py -w roboto amiko  # konkretne słowa
    python tools/check_tts.py --dry            # tylko transkrypcja, bez dźwięku
    python tools/check_tts.py --engine gtts    # wymuś gTTS zamiast edge-tts
"""

import sys
import os
import json
import math
import random
import tempfile
import argparse
import asyncio
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
WORDS_FILE    = ROOT / "assets" / "flashcards" / "wordlist.json"
sys.path.insert(0, str(ROOT))

# ─── Transkrypcja (skopiowana z computer.py, bez zależności od całego pliku) ──

def eo_to_pl_phonetic(text: str) -> str:
    specials = [
        ("ĉ", "\uE000"), ("Ĉ", "\uE001"), ("ŝ", "\uE002"), ("Ŝ", "\uE003"),
        ("ĝ", "\uE004"), ("Ĝ", "\uE005"), ("ĵ", "\uE006"), ("Ĵ", "\uE007"),
        ("ĥ", "\uE008"), ("Ĥ", "\uE009"), ("ŭ", "\uE00A"), ("Ŭ", "\uE00B"),
    ]
    result = text
    for src, ph in specials:
        result = result.replace(src, ph)
    for src, dst in [("io","ijo"),("Io","Ijo"),("IO","IJO"),
                     ("ia","ija"),("Ia","Ija"),("ie","ije"),("Ie","Ije")]:
        result = result.replace(src, dst)
    result = result.replace("qu","kw").replace("Qu","Kw").replace("QU","KW")
    result = result.replace("c","ts").replace("C","Ts")
    finals = [
        ("\uE000","cz"),("\uE001","Cz"),("\uE002","sz"),("\uE003","Sz"),
        ("\uE004","dż"),("\uE005","Dż"),("\uE006","ż"), ("\uE007","Ż"),
        ("\uE008","h"), ("\uE009","H"), ("\uE00A","ł"), ("\uE00B","Ł"),
    ]
    for ph, dst in finals:
        result = result.replace(ph, dst)
    import re
    result = re.sub(r'on\b', 'onn', result)
    result = re.sub(r'an\b', 'ann', result)
    result = re.sub(r'en\b', 'enn', result)
    return result


# ─── TTS ──────────────────────────────────────────────────────────────────────

def speak_edge(text: str, lang: str, tmp: str):
    import edge_tts
    VOICES = {"pl": "pl-PL-MarekNeural", "en": "en-GB-RyanNeural"}
    voice = VOICES.get(lang, "pl-PL-MarekNeural")
    async def _run():
        await edge_tts.Communicate(text, voice).save(tmp)
    asyncio.run(_run())

def speak_gtts(text: str, lang: str, tmp: str):
    from gtts import gTTS
    gTTS(text=text, lang=lang).save(tmp)

def play_mp3(path: str):
    import pygame
    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.wait(50)
    pygame.mixer.music.unload()

def speak(text: str, lang: str, engine: str, dry: bool):
    phonetic = eo_to_pl_phonetic(text) if lang == "eo" else text
    out_lang  = "pl" if lang == "eo" else lang
    print(f"     eo  : {text}")
    if lang == "eo":
        print(f"     →pl : {phonetic}")
    if dry:
        return
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        tmp = f.name
    try:
        if engine == "edge":
            try:
                speak_edge(phonetic, out_lang, tmp)
            except Exception as e:
                print(f"     [edge-tts failed: {e}] → gTTS")
                speak_gtts(phonetic, out_lang, tmp)
        else:
            speak_gtts(phonetic, out_lang, tmp)
        play_mp3(tmp)
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="WRO2026 — test TTS esperanto")
    parser.add_argument("-n", "--count",  type=int, default=10,
                        help="Liczba losowych słów (domyślnie 10)")
    parser.add_argument("-u", "--unit",   default=None,
                        help="Filtruj po jednostce (np. Robotics)")
    parser.add_argument("-w", "--words",  nargs="+", default=None,
                        help="Konkretne słowa do przetestowania")
    parser.add_argument("--dry",          action="store_true",
                        help="Tylko transkrypcja, bez odtwarzania")
    parser.add_argument("--engine",       choices=["edge","gtts"], default="edge",
                        help="Backend TTS (domyślnie edge-tts)")
    args = parser.parse_args()

    if not WORDS_FILE.exists():
        print(f"[ERR] Brak pliku: {WORDS_FILE}")
        sys.exit(1)

    words = json.loads(WORDS_FILE.read_text(encoding="utf-8"))

    # Wybór słów
    if args.words:
        pool = [w for w in words if w["word"] in args.words]
        if not pool:
            print(f"[ERR] Nie znaleziono słów: {args.words}")
            sys.exit(1)
    else:
        if args.unit:
            pool = [w for w in words if w.get("unit","") == args.unit]
            if not pool:
                units = sorted({w.get("unit","") for w in words})
                print(f"[ERR] Brak jednostki '{args.unit}'. Dostępne: {units}")
                sys.exit(1)
        else:
            pool = words
        random.shuffle(pool)
        pool = pool[:args.count]

    print(f"\n[TTS CHECK]  silnik={args.engine}  dry={args.dry}  słów={len(pool)}\n")

    for i, entry in enumerate(pool, 1):
        word        = entry["word"]
        pron        = entry.get("pronunciation", "")
        pos         = entry.get("part_of_speech", "")
        definition  = entry.get("definition", entry.get("translation", ""))
        unit        = entry.get("unit", "")

        print(f"  [{i:02d}/{len(pool)}]  {word}  ({pron})  [{pos}]  — {definition}  [{unit}]")
        speak(word, "eo", args.engine, args.dry)

        if not args.dry and i < len(pool):
            try:
                input("     [Enter → następne, Ctrl+C → stop] ")
            except (KeyboardInterrupt, EOFError):
                print("\n[TTS CHECK] Przerwano.")
                break
        print()

    print("[TTS CHECK] Gotowe.\n")


if __name__ == "__main__":
    main()
