#!/usr/bin/env python3
"""crnkey: type your course registration numbers with one global keybind.

Linux / KDE Plasma on Wayland. Keys are typed through a uinput virtual
keyboard (works in any focused window). The hotkey is registered with KDE's
kglobalaccel over D-Bus, so no access to /dev/input is needed.
"""

import argparse
import re
import signal
import sys
import threading
import time
from pathlib import Path

DEFAULT_KEYBIND = "Ctrl+Alt+R"
DEFAULT_CRN_FILE = Path(__file__).resolve().parent / "crns.txt"
DEFAULT_DELAY_MS = 20
# Extra time after the keybind is released before typing, so held modifiers
# are up (we cannot read key state without /dev/input).
DEFAULT_START_DELAY_MS = 400
EXPECTED_CRN_LEN = 5

UINPUT_FIX = """\
/dev/uinput is not writable by your user. Fix it (one-time, needs sudo):

  echo 'KERNEL=="uinput", GROUP="input", MODE="0660", TAG+="uaccess"' \\
    | sudo tee /etc/udev/rules.d/99-uinput.rules
  sudo udevadm control --reload-rules && sudo udevadm trigger /dev/uinput

then log out and back in. For a quick temporary fix instead:

  sudo setfacl -m u:$USER:rw /dev/uinput
"""


# ---------------------------------------------------------------- parsing --

def parse_crns(text):
    """Split text into CRN strings. Whitespace/commas separate, '#' comments."""
    crns = []
    for line in text.splitlines():
        line = line.split("#", 1)[0]
        crns.extend(tok for tok in re.split(r"[\s,]+", line) if tok)
    return crns


def validate_crns(crns):
    """Return (errors, warnings). Non-digit CRNs are errors; odd length warns."""
    errors, warnings = [], []
    if not crns:
        errors.append("no CRNs given")
    for crn in crns:
        if not (crn.isascii() and crn.isdigit()):
            errors.append(f"CRN {crn!r} is not digits only")
        elif len(crn) != EXPECTED_CRN_LEN:
            warnings.append(
                f"CRN {crn} has {len(crn)} digits (expected {EXPECTED_CRN_LEN})"
            )
    seen = set()
    for crn in crns:
        if crn in seen:
            warnings.append(f"CRN {crn} is listed more than once")
        seen.add(crn)
    return errors, warnings


def build_sequence(crns):
    """Key names to press: each CRN's digits then TAB, finally ENTER."""
    keys = []
    for crn in crns:
        keys.extend(crn)
        keys.append("TAB")
    keys.append("ENTER")
    return keys


# Qt key encoding used by kglobalaccel: modifier flags OR'd with a key code.
_QT_MODS = {"shift": 0x02000000, "ctrl": 0x04000000, "control": 0x04000000,
            "alt": 0x08000000, "meta": 0x10000000, "super": 0x10000000}


def parse_keybind(spec):
    """'Ctrl+Alt+R' -> Qt key code int. Supports A-Z, 0-9, F1-F12."""
    *mods, key = [p.strip() for p in spec.split("+")]
    code = 0
    for mod in mods:
        if mod.lower() not in _QT_MODS:
            raise ValueError(f"unknown modifier {mod!r} in keybind {spec!r}")
        code |= _QT_MODS[mod.lower()]
    if not code:
        raise ValueError(f"keybind {spec!r} needs at least one modifier")
    if re.fullmatch(r"[A-Za-z0-9]", key):
        return code | ord(key.upper())
    m = re.fullmatch(r"[Ff](\d{1,2})", key)
    if m and 1 <= int(m.group(1)) <= 12:
        return code | (0x01000030 + int(m.group(1)) - 1)
    raise ValueError(f"unsupported key {key!r} in keybind {spec!r}")


# ----------------------------------------------------------------- typing --

class Typer:
    """Virtual keyboard on /dev/uinput."""

    def __init__(self, delay_ms, start_delay_ms):
        from evdev import UInput, ecodes
        self.ecodes = ecodes
        self.delay = delay_ms / 1000
        self.start_delay = start_delay_ms / 1000
        names = [str(d) for d in range(10)] + ["TAB", "ENTER"]
        self.codes = {n: getattr(ecodes, f"KEY_{n}") for n in names}
        try:
            self.ui = UInput({ecodes.EV_KEY: list(self.codes.values())},
                             name="crnkey virtual keyboard")
        except PermissionError:
            sys.exit(UINPUT_FIX)
        except FileNotFoundError:
            sys.exit("/dev/uinput does not exist: run `sudo modprobe uinput`.")
        # Give the compositor time to notice the new device.
        time.sleep(0.5)

    def type_keys(self, keys):
        time.sleep(self.start_delay)
        ec = self.ecodes
        for name in keys:
            code = self.codes[name]
            self.ui.write(ec.EV_KEY, code, 1)
            self.ui.syn()
            self.ui.write(ec.EV_KEY, code, 0)
            self.ui.syn()
            time.sleep(self.delay)

    def close(self):
        self.ui.close()


# ----------------------------------------------------------------- hotkey --

COMPONENT = "crnkey"
ACTION = "type-crns"


def run_listener(keybind, typer, keys):
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    try:
        from gi.repository import GLibUnix  # newer PyGObject
        signal_add = GLibUnix.signal_add
    except ImportError:
        signal_add = GLib.unix_signal_add

    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    try:
        ga = dbus.Interface(
            bus.get_object("org.kde.kglobalaccel", "/kglobalaccel"),
            "org.kde.KGlobalAccel")
    except dbus.DBusException as e:
        sys.exit(f"Cannot reach KDE's kglobalaccel service ({e}).\n"
                 "This tool needs a KDE Plasma session.")

    action_id = dbus.Array([COMPONENT, ACTION, "crnkey", "Type CRNs"],
                           signature="s")
    qt_key = parse_keybind(keybind)
    ga.doRegister(action_id)
    # 0x2 = SetPresent (without it KWin never grabs the key), 0x4 = NoAutoloading
    # (use exactly this key, not one remembered from before).
    got = ga.setShortcut(action_id, dbus.Array([qt_key], signature="i"),
                         dbus.UInt32(0x6))
    if list(got) != [qt_key]:
        ga.unRegister(action_id)
        sys.exit(f"Could not claim {keybind}: it is probably used by another "
                 "shortcut. Pick another with --keybind.")

    loop = GLib.MainLoop()
    busy = threading.Event()
    released = threading.Event()

    def worker():
        try:
            # Wait for the keybind's release so held modifiers don't turn the
            # digits into Ctrl+digit; the start delay covers the modifiers.
            released.wait(timeout=2)
            typer.type_keys(keys)
        finally:
            busy.clear()

    def on_pressed(_component, action, _timestamp):
        if action != ACTION or busy.is_set():
            return
        busy.set()
        released.clear()
        threading.Thread(target=worker, daemon=True).start()

    def on_released(_component, action, _timestamp):
        if action == ACTION:
            released.set()

    comp_path = ga.getComponent(COMPONENT)
    bus.add_signal_receiver(
        on_pressed, signal_name="globalShortcutPressed",
        dbus_interface="org.kde.kglobalaccel.Component", path=comp_path)

    bus.add_signal_receiver(
        on_released, signal_name="globalShortcutReleased",
        dbus_interface="org.kde.kglobalaccel.Component", path=comp_path)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal_add(GLib.PRIORITY_DEFAULT, sig, loop.quit)
    print(f"Listening. Press {keybind} to type; Ctrl+C to quit.", flush=True)
    try:
        loop.run()
    finally:
        try:
            ga.unRegister(action_id)
        except dbus.DBusException:
            pass


# -------------------------------------------------------------------- cli --

def main(argv=None):
    p = argparse.ArgumentParser(
        description="Type your CRNs (digits, Tab, ..., Tab, Enter) on a global keybind.")
    p.add_argument("crns", nargs="*",
                   help="CRNs to type (overrides the CRN file)")
    p.add_argument("-f", "--file", type=Path, default=DEFAULT_CRN_FILE,
                   help="CRN file (default: crns.txt next to this script)")
    p.add_argument("-k", "--keybind", default=DEFAULT_KEYBIND,
                   help=f"global keybind (default: {DEFAULT_KEYBIND})")
    p.add_argument("--delay-ms", type=float, default=DEFAULT_DELAY_MS,
                   help="delay between keystrokes, 0 to disable (default: %(default)s)")
    p.add_argument("--start-delay-ms", type=float, default=DEFAULT_START_DELAY_MS,
                   help="wait before typing so you can release the keybind "
                        "(default: %(default)s)")
    p.add_argument("--dry-run", action="store_true",
                   help="print what would be typed; send nothing")
    p.add_argument("--test", action="store_true",
                   help="type the sequence after a 3 s countdown, then exit")
    args = p.parse_args(argv)

    if args.crns:
        crns = parse_crns(" ".join(args.crns))
        source = "command line"
    else:
        try:
            crns = parse_crns(args.file.read_text())
        except OSError as e:
            sys.exit(f"Cannot read CRN file: {e}")
        source = str(args.file)
    errors, warnings = validate_crns(crns)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    if errors:
        sys.exit("error: " + "; ".join(errors))
    try:
        parse_keybind(args.keybind)
    except ValueError as e:
        sys.exit(f"error: {e}")

    keys = build_sequence(crns)
    print(f"CRNs ({source}): {' '.join(crns)}")
    print(f"Sequence: {' '.join(keys)}")
    if args.dry_run:
        print("Dry run: nothing typed.")
        return

    typer = Typer(args.delay_ms, args.start_delay_ms)
    try:
        if args.test:
            for n in (3, 2, 1):
                print(f"Typing in {n}... click into a text field", flush=True)
                time.sleep(1)
            typer.type_keys(keys)
            print("Done.")
        else:
            print(f"Keybind: {args.keybind}")
            run_listener(args.keybind, typer, keys)
    finally:
        typer.close()


if __name__ == "__main__":
    main()
