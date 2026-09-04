# USB Integrity Checker

A portable, USB-based tool for capturing a known-good "baseline" of a program's files and Windows Registry settings, then scanning any machine against that baseline and safely repairing what's changed.

Built as a capstone project for the Digital Business Technology program, with the workflow of a hospital IT support desk in mind: staff workstations drift out of configuration constantly, and fixing that by hand across many machines doesn't scale.

## Why this exists

- Detect when a program's files or registry settings differ from a known-good baseline
- Repair those differences with a mandatory dry-run preview and automatic backup before any change
- Run entirely from a USB drive — no installation needed beyond Python
- Work across Windows, Linux, and custom environments through one portable rule format
- Guarantee personal files (Desktop/Documents/Downloads) and protected Windows Registry areas are never touched, even by mistake

## Safety design

This tool can automatically overwrite files and registry values, so safety was the primary design constraint from the start, not an afterthought:

- **Dry-run by default** — nothing is written until a repair plan is explicitly applied
- **Mandatory backup** — every file/value is backed up before being overwritten
- **Personal-zone guard (two layers)** — enforced both when a profile is created and again independently inside the repair module itself
- **Hard-blocked registry keys** — `SYSTEM`, `SECURITY`, `SAM`, `Run`/`RunOnce`, `Winlogon`, `Policies`, and the entire `HKEY_USERS` hive can never be touched, with no override
- **Full audit log** — every scan and repair is recorded with a timestamp and actor

See [`docs/`](docs/) for the full architecture writeup and roadmap.

## Getting started

Requires Python 3.10+.

```bash
cd src
pip install -r requirements.txt
python gui_ctk.py
```

On Windows, double-clicking `Start.bat` does the same thing and installs missing dependencies automatically.

### Running the tests

```bash
cd src
python -m unittest discover -s tests -p "test_*.py"
```

### Building a standalone .exe (no Python required to run it)

```bash
cd src
Build_EXE.bat
```

## Project structure

```
usb_integrity_checker/
├── Start.bat              # USB launcher
├── autorun.inf             # drive icon/label
├── docs/                   # architecture notes, roadmap
└── src/
    ├── gui_ctk.py           # application entry point
    ├── gui/                 # desktop interface (CustomTkinter)
    ├── tests/                # automated test suite
    ├── scanner.py, repair.py, registry_rules.py
    ├── profile_builder.py, anchors.py
    └── audit_log.py, i18n.py
```

## Status

Functional capstone submission. Supports Windows and Linux file/registry checking, 10 UI languages, and standalone `.exe` packaging via PyInstaller.

Not yet implemented: bootable recovery mode, code signing. See [`docs/bootable_roadmap.md`](docs/bootable_roadmap.md).
