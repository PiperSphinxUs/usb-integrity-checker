# Future Roadmap: Bootable Recovery Mode

Status: **Not yet developed (design/roadmap only)** — documented here to pick up after the main capstone deliverable is complete.

## Problem this would solve

The current tool must be run from inside a Windows installation that boots normally. If Windows is broken badly enough that it won't boot at all (e.g. critical system files are damaged), this tool becomes unusable — precisely the situation where a repair tool is needed most.

## Chosen approach: Linux Live USB (via Ventoy or equivalent)

Rather than building a custom WinPE image from scratch (requires the Windows ADK, is quite complex, and takes a long time to get right), use an existing, ready-made Live USB tool (such as Ventoy) to carry a lightweight Linux environment on the same drive as the program itself.

### Workflow (concept)

1. The user presses the boot menu key (F12/Esc at power-on) and boots from the USB instead of Windows.
2. Boots into a lightweight Linux live environment (nothing installed permanently).
3. Mounts the Windows partition (NTFS) as read-write via `ntfs-3g`.
4. Runs the exact same Scanner/Repair code used under normal Windows, with the profile's `os_family` set to `"linux"` or `"custom"`, and anchors pointed at the mount path (e.g. `/mnt/windows_c/Program Files/...`).
5. Shows the same GUI as normal usage, since the backend code is identical — no rewrite needed.

### Why the current architecture supports this "for free"

The anchor system (`anchors.py`), designed from the start to support multiple `os_family` values (`windows` / `linux` / `custom`), means running from a Linux live environment to repair a mounted Windows install is just a matter of setting the profile's `os_family` to `linux`/`custom` and pointing the anchors at the mount location. **No changes are needed to the Scanner, Repair, or Profile Builder code at all.**

## Remaining work (when actually implemented)

- Test building a Ventoy USB and picking a lightweight Linux distro with Python built in (e.g. Tiny Core Linux or Alpine).
- Write a script to auto-mount the Windows partition on entering the live environment.
- Test that the GUI (Tkinter) runs correctly in a live environment with limited resources.
- Decide whether to bundle Python + dependencies on the USB itself, or rely on the Python that ships with the live distro.

## Note on Autorun/Autoplay

Windows intentionally disables automatic program execution from USB drives (an `autorun.inf` that launches a program) for security reasons, to prevent malware spreading via flash drives — this should not be worked around, since doing so behaves like USB malware and gets blocked by antivirus software. The practical approach: give the program file a clearly visible name (e.g. `Start Here.exe`) at the root of the USB, alongside an `autorun.inf` limited to setting only the drive's icon/label (not launching anything), so the user can see and double-click it easily right after the AutoPlay dialog appears.
