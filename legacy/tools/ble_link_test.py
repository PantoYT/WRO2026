#!/usr/bin/env python3
"""
Two-way BLE link test for the Espero-bot hub (Pybricks Profile v1.3+).

Connects to the hub, starts the stored user program (hub.py), prints every
line the hub writes to stdout, and lets you type commands that are delivered
to the hub's stdin. The hub answers every received command with
DEBUG:RX:<cmd> — seeing that ack proves the PC -> hub direction works.

Usage:
    python tools/ble_link_test.py              # interactive console
    python tools/ble_link_test.py --auto       # automatic round-trip test
    python tools/ble_link_test.py --name MyHub

No project dependencies beyond bleak — safe to run without torch/pygame.
"""

import argparse
import asyncio
import sys
import threading

from bleak import BleakClient, BleakScanner

PYBRICKS_CMD_UUID = "c5f50002-8280-46da-89f4-6d8051e4aeef"  # command/event
PYBRICKS_CAP_UUID = "c5f50003-8280-46da-89f4-6d8051e4aeef"  # hub capabilities
CMD_START_PROGRAM = 0x01
CMD_WRITE_STDIN   = 0x06
EVT_WRITE_STDOUT  = 0x01

AUTO_SEQUENCE = ["MODE:1", "MODE:2", "CONV_LISTEN", "CONV_DONE", "MODE:0"]


async def run(name: str, auto: bool) -> int:
    print(f"[scan] Looking for '{name}' (15 s)...")
    device = await BleakScanner.find_device_by_name(name, timeout=15.0)
    if device is None:
        print(f"[scan] Hub '{name}' not found. Is it on and not connected elsewhere?")
        return 1
    print(f"[scan] Found {device.name} ({device.address})")

    rx_buf = [""]
    lines: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def on_event(_, data: bytearray):
        if not data or data[0] != EVT_WRITE_STDOUT:
            return
        for ch in data[1:].decode("utf-8", "ignore"):
            if ch == "\n":
                line, rx_buf[0] = rx_buf[0].strip(), ""
                if line:
                    lines.put_nowait(line)
            else:
                rx_buf[0] += ch

    async with BleakClient(device) as client:
        await client.start_notify(PYBRICKS_CMD_UUID, on_event)

        max_chunk = 19
        try:
            caps = await client.read_gatt_char(PYBRICKS_CAP_UUID)
            max_chunk = max(int.from_bytes(caps[0:2], "little") - 1, 1)
            print(f"[ble] max stdin chunk: {max_chunk} B")
        except Exception as e:
            print(f"[ble] capabilities read failed ({e}), using {max_chunk} B")

        try:
            await client.write_gatt_char(
                PYBRICKS_CMD_UUID, bytes([CMD_START_PROGRAM]), response=True
            )
            print("[ble] user program started")
        except Exception as e:
            print(f"[ble] start command rejected (already running?): {e}")

        async def send(msg: str):
            data = (msg + "\n").encode("utf-8")
            for i in range(0, len(data), max_chunk):
                await client.write_gatt_char(
                    PYBRICKS_CMD_UUID,
                    bytes([CMD_WRITE_STDIN]) + data[i:i + max_chunk],
                    response=True,
                )
            print(f"[pc->hub] {msg!r}")

        async def print_lines_for(seconds: float, want_ack: str | None = None) -> bool:
            got_ack = False
            end = loop.time() + seconds
            while loop.time() < end:
                try:
                    line = await asyncio.wait_for(lines.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    continue
                print(f"[hub] {line}")
                if want_ack and line == f"DEBUG:RX:{want_ack}":
                    got_ack = True
            return got_ack

        # Give the program a moment to boot and print READY
        await print_lines_for(3.0)

        if auto:
            failures = 0
            for msg in AUTO_SEQUENCE:
                await send(msg)
                if await print_lines_for(2.0, want_ack=msg):
                    print(f"[test] ACK for {msg!r}  ✓")
                else:
                    print(f"[test] NO ACK for {msg!r}  ✗")
                    failures += 1
            print(f"\n[test] {len(AUTO_SEQUENCE) - failures}/{len(AUTO_SEQUENCE)} "
                  f"commands acknowledged.")
            return 1 if failures else 0

        # Interactive: stdin reader thread feeds the asyncio loop
        print("\nType a command for the hub (e.g. MODE:2, SLEEP, WAKE). "
              "Ctrl+C or 'quit' to exit.\n")
        inputs: asyncio.Queue = asyncio.Queue()

        def reader():
            while True:
                try:
                    s = input()
                except (EOFError, KeyboardInterrupt):
                    s = "quit"
                loop.call_soon_threadsafe(inputs.put_nowait, s)
                if s.strip().lower() == "quit":
                    return

        threading.Thread(target=reader, daemon=True).start()

        while True:
            printer = asyncio.create_task(print_lines_for(0.2))
            try:
                cmd = inputs.get_nowait()
            except asyncio.QueueEmpty:
                cmd = None
            await printer
            if cmd is None:
                continue
            cmd = cmd.strip()
            if cmd.lower() == "quit":
                return 0
            if cmd:
                await send(cmd)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--name", default="Espero-bot", help="hub Bluetooth name")
    ap.add_argument("--auto", action="store_true",
                    help="run automatic round-trip test instead of console")
    args = ap.parse_args()
    try:
        sys.exit(asyncio.run(run(args.name, args.auto)))
    except KeyboardInterrupt:
        print("\n[exit] bye")


if __name__ == "__main__":
    main()
