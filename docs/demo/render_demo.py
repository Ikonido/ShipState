"""Render a GIF from actual ShipState output in a disposable local repository.

Run from the repository root after installing ShipState and Pillow:
    python -m pip install -e . Pillow
    python docs/demo/render_demo.py

Pillow is a documentation-only dependency. Nothing is fetched or published by
this script; its commits and release tag exist only in a temporary repository.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
WIDTH, HEIGHT = 1120, 790
BACKGROUND = "#0b1120"
PANEL = "#111b2e"
TEXT = "#e6edf3"
MUTED = "#9baac0"
GREEN, RED, AMBER = "#73e2a7", "#ff8e93", "#f4ca7a"
FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    filename = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
    override = os.environ.get("SHIPSTATE_DEMO_FONT_BOLD" if bold else "SHIPSTATE_DEMO_FONT")
    return ImageFont.truetype(override or str(FONT_DIR / filename), size)


def run(directory: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.run(
        args, cwd=directory, env=environment, capture_output=True, text=True,
        encoding="utf-8", check=False, timeout=10,
    )


def git(directory: Path, *args: str) -> None:
    result = run(directory, "git", *args)
    if result.returncode:
        raise RuntimeError(result.stderr)


def capture() -> tuple[str, str]:
    with tempfile.TemporaryDirectory(prefix="shipstate-demo-") as temporary:
        directory = Path(temporary)
        (directory / "pyproject.toml").write_text(
            '[project]\nname = "meshcontract"\nversion = "0.2.1"\n'
            '[build-system]\nrequires = ["setuptools>=77"]\n'
            'build-backend = "setuptools.build_meta"\n', encoding="utf-8",
        )
        good_readme = "# Example project\n\n```sh\npip install meshcontract==0.2.1\n```\n"
        readme = directory / "README.md"
        readme.write_text(good_readme, encoding="utf-8")
        (directory / "CHANGELOG.md").write_text("# Changelog\n\n## [0.2.1]\n", encoding="utf-8")
        (directory / "LICENSE").write_bytes((ROOT / "LICENSE").read_bytes())
        workflow = directory / ".github" / "workflows"
        workflow.mkdir(parents=True)
        (workflow / "tests.yml").write_text(
            'jobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n'
            '      - run: pip install meshcontract==0.2.1\n', encoding="utf-8",
        )
        git(directory, "init", "-q")
        git(directory, "config", "user.name", "ShipState Demo")
        git(directory, "config", "user.email", "demo@example.invalid")
        git(directory, "add", ".")
        git(directory, "commit", "-qm", "Create fictional release fixture")
        git(directory, "tag", "v0.2.1")
        readme.write_text(good_readme.replace("==0.2.1", "==0.2.0"), encoding="utf-8")
        before = run(directory, sys.executable, "-m", "shipstate", "check", ".")
        readme.write_text(good_readme, encoding="utf-8")
        after = run(directory, sys.executable, "-m", "shipstate", "check", ".")
        if before.returncode != 1 or after.returncode != 0:
            raise RuntimeError(f"Unexpected demo results: {before.returncode}, {after.returncode}")
        return before.stdout.rstrip(), after.stdout.rstrip()


def frame(phase: str, command: str, output: str = "", exit_code: int | None = None) -> Image.Image:
    canvas = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.text((40, 26), "ShipState", fill=TEXT, font=font(36, True))
    draw.text((40, 82), phase, fill=MUTED, font=font(22))
    draw.rounded_rectangle((24, 130, WIDTH - 24, 728), radius=16, fill=PANEL)
    for x, color in ((49, RED), (76, AMBER), (103, GREEN)):
        draw.ellipse((x, 152, x + 12, 164), fill=color)
    draw.text((138, 147), "meshcontract / fictional local project", fill=MUTED, font=font(17))
    draw.text((47, 190), "$ " + command, fill=GREEN, font=font(20))
    row = 0
    for line in output.splitlines():
        color = TEXT
        if line.startswith("PASS ") or line == "Release consistency: PASS":
            color = GREEN
        elif line.startswith("FAIL ") or line == "Release consistency: FAIL":
            color = RED
        elif line.startswith("WARN "):
            color = AMBER
        # Wrap at the terminal's character width without dropping output text.
        for chunk in [line[index:index + 88] for index in range(0, len(line), 88)] or [""]:
            draw.text((47, 234 + row * 25), chunk, fill=color, font=font(19))
            row += 1
    if exit_code is not None:
        draw.text((47, 685), f"Exit code: {exit_code}", fill=GREEN if exit_code == 0 else RED, font=font(20, True))
    draw.text((40, 751), "Real CLI output  |  Local files + Git  |  No network requests", fill=MUTED, font=font(18))
    return canvas


def main() -> None:
    before, after = capture()
    # Keep the full capture, including the uncommitted-change warning, auditable.
    output_dir = ROOT / "docs" / "demo"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "before.txt").write_text(before + "\n", encoding="utf-8")
    (output_dir / "after.txt").write_text(after + "\n", encoding="utf-8")
    frames: list[Image.Image] = []
    durations: list[int] = []

    def add(phase: str, command: str, output: str = "", exit_code: int | None = None, duration: int = 1000) -> None:
        frames.append(frame(phase, command, output, exit_code))
        durations.append(duration)

    phase = "1. Detect a stale README install pin"
    add(phase, "", duration=800)
    command = "shipstate check ."
    for index in range(1, len(command) + 1):
        add(phase, command[:index], duration=65)
    add(phase, command, before, 1, 5200)
    add("2. Correct the README example", "# README: meshcontract==0.2.0 -> meshcontract==0.2.1", duration=3000)
    phase = "3. Check again: release state is consistent"
    for index in range(1, len(command) + 1):
        add(phase, command[:index], duration=65)
    add(phase, command, after, 0, 6000)
    sample = Image.new("RGB", (WIDTH, HEIGHT * 2))
    sample.paste(frame("", command, before, 1), (0, 0))
    sample.paste(frames[-1], (0, HEIGHT))
    palette = sample.quantize(colors=64)
    indexed = [item.quantize(palette=palette, dither=Image.Dither.NONE) for item in frames]
    path = ROOT / "docs" / "demo.gif"
    indexed[0].save(path, save_all=True, append_images=indexed[1:], duration=durations, loop=0, optimize=True, disposal=1)
    print(f"Created {path.relative_to(ROOT)} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
