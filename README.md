# crnkey

Types your course registration numbers (CRNs) with one keybind.

While `crnkey` is running, press **Ctrl+Alt+R** and it types the first CRN,
Tab, the second CRN, Tab, and so on; after the last CRN it presses Tab and
then Enter. It works in any focused window, including a browser.

Target: Linux, KDE Plasma on Wayland, Python 3. How it works: keys are typed
through a virtual keyboard on `/dev/uinput` (python-evdev), and the hotkey is
a global shortcut registered with KDE (`kglobalaccel` over D-Bus), so it needs
no access to `/dev/input`.

## One-time setup

Needs `python3-evdev`, `dbus-python` and PyGObject (already installed here)
and write access to `/dev/uinput`. Check:

    python3 -c "import evdev, dbus, gi" && test -w /dev/uinput && echo OK

If `/dev/uinput` is not writable, `crnkey` prints the fix. Quick version
(until reboot):

    sudo setfacl -m u:$USER:rw /dev/uinput

If you use a venv, create it with `--system-site-packages` so it sees the
system `dbus` and `gi` modules, then `pip install -r requirements.txt`.

## Set the CRNs

Edit `crns.txt`: one per line or space/comma separated, `#` starts a comment.

    # Fall registration
    12345
    23456 34567   # lab + lecture

Or override on the command line (the file is then ignored):

    ./crnkey.py 12345 23456 34567

CRNs must be digits only. Other lengths than 5 digits only give a warning.

## Run

    ./crnkey.py

It prints the keybind and the CRNs loaded, then waits. Click into the first
CRN field of the registration page and press **Ctrl+Alt+R**. Press Ctrl+C to
quit. A second press while typing is ignored.

Options:

| Option | Meaning |
| --- | --- |
| `-k`, `--keybind Ctrl+Shift+F9` | change the keybind (modifiers + A-Z, 0-9 or F1-F12) |
| `-f`, `--file path` | use another CRN file |
| `--delay-ms 20` | pause between keystrokes; `0` disables |
| `--start-delay-ms 400` | wait before typing, so you can let go of the keybind |
| `--dry-run` | print what would be typed, send nothing |
| `--test` | type the sequence after a 3 second countdown; click into a text field first |

Do a `--dry-run` the night before, and a `--test` into a text editor to
check the sequence.

## Troubleshooting

- **"/dev/uinput is not writable"**: run the `setfacl` command above (the
  error message shows a permanent udev rule too).
- **"Could not claim Ctrl+Alt+R"**: another shortcut uses it; pick another
  with `--keybind`, or free it in System Settings > Shortcuts.
- **Nothing happens on the keybind**: check `crnkey` is still running and
  that it printed "Listening". Run `--test` to see whether typing itself
  works; if it does, only the hotkey is the problem, so try another keybind.
- **Digits arrive as shortcuts (Ctrl+1 ...)**: you held the modifiers too
  long; raise `--start-delay-ms`.
- **Fields skipped or digits dropped**: the page is slow; raise `--delay-ms`.
- **Cannot reach kglobalaccel**: you are not in a KDE Plasma session.

## Tests

    python3 -m unittest
