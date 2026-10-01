# README animation

`../demo.gif` shows actual CLI output from a fictional `meshcontract` project.
The renderer creates a temporary local Git repository with a matching release
tag, changes its README pin to an older version, captures exit code 1, restores
the correct pin, and captures exit code 0. The first capture includes the real
dirty-working-tree warning; restoring the committed README makes the second
capture clean. No ShipState release tags or remote repositories are changed.

Rebuild from the ShipState repository root:

```sh
python -m pip install -e . Pillow
python docs/demo/render_demo.py
```

Pillow is used only to render documentation, not by the ShipState package.
The default fonts are DejaVu Sans Mono from `/usr/share/fonts/truetype/dejavu`.
On other platforms set `SHIPSTATE_DEMO_FONT` and `SHIPSTATE_DEMO_FONT_BOLD`
to paths to equivalent regular and bold monospaced TrueType fonts.

`before.txt` and `after.txt` preserve the full captured output for review.
