"""Inspect YAML run steps and local pip requirements without executing commands."""

import re
import shlex
from pathlib import Path

import yaml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from shipstate.checks.pins import dynamic_pin_pattern, extract_pins
from shipstate.models import Finding, InputError


def _without_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index]
    return line


def _logical_commands(text: str) -> list[str]:
    commands: list[str] = []
    pending = ""
    for line in text.splitlines():
        cleaned = _without_comment(line).strip()
        if not cleaned:
            continue
        pending = f"{pending} {cleaned}".strip()
        trailing_slashes = len(pending) - len(pending.rstrip("\\"))
        if trailing_slashes % 2:
            pending = pending[:-1].rstrip()
            continue
        commands.append(pending)
        pending = ""
    if pending:
        commands.append(pending)
    return commands


def _install_arguments(command: str) -> list[list[str]]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    segments: list[list[str]] = [[]]
    for token in lexer:
        if token and all(char in ";&|" for char in token):
            segments.append([])
        else:
            segments[-1].append(token)
    installs = []
    for tokens in segments:
        if tokens and tokens[0] == "env":
            tokens = tokens[1:]
        while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
            tokens = tokens[1:]
        if len(tokens) >= 2 and re.fullmatch(r"pip[0-9.]*", tokens[0]) and tokens[1] == "install":
            installs.append(tokens[2:])
        elif (
            len(tokens) >= 4 and re.fullmatch(r"python[0-9.]*", tokens[0])
            and tokens[1:4] == ["-m", "pip", "install"]
        ):
            installs.append(tokens[4:])
        elif tokens[:3] == ["uv", "pip", "install"]:
            installs.append(tokens[3:])
    return installs


def _requirement_files(arguments: list[str]) -> list[str]:
    paths = []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token in {"-r", "--requirement", "-c", "--constraint"}:
            index += 1
            paths.append(arguments[index] if index < len(arguments) else "")
        elif token.startswith(("--requirement=", "--constraint=")):
            paths.append(token.split("=", 1)[1])
        elif token.startswith(("-r", "-c")) and not token.startswith("--") and len(token) > 2:
            paths.append(token[2:])
        index += 1
    return paths


def _working_directory(mapping: dict, fallback: object = ".") -> object:
    defaults = mapping.get("defaults", {})
    run = defaults.get("run", {}) if isinstance(defaults, dict) else {}
    return run.get("working-directory", fallback) if isinstance(run, dict) else fallback


def _run_steps(document: dict):
    # A standalone run mapping is useful for small workflow excerpts as well.
    if isinstance(document.get("run"), str):
        yield document["run"], document.get("working-directory", ".")
    jobs = document.get("jobs", {})
    if not isinstance(jobs, dict):
        return
    default = _working_directory(document)
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        working_directory = _working_directory(job, default)
        for step in steps:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                yield step["run"], step.get("working-directory", working_directory)


def _same_version(actual: str, expected: str) -> bool:
    try:
        return Version(actual) == Version(expected)
    except InvalidVersion:
        return False


def check_workflows(root: Path, project_name: str, version: str) -> list[Finding]:
    root = root.resolve()
    workflow_dir = root / ".github" / "workflows"
    try:
        files = sorted(
            (path for path in workflow_dir.iterdir() if path.is_file() and path.suffix.lower() in {".yml", ".yaml"}),
            key=lambda item: item.name.casefold(),
        ) if workflow_dir.is_dir() else []
    except OSError as exc:
        raise InputError("workflow_unreadable", "The workflow directory could not be inspected.") from exc

    pins: list[tuple[str, str]] = []
    dynamic_pins: list[tuple[str, str]] = []
    warnings: list[Finding] = []

    def warn(source: str, message: str) -> None:
        finding = Finding(
            code="workflow_requirements_unchecked", severity="warn", source=source, message=message,
        )
        if finding not in warnings:
            warnings.append(finding)

    def read_requirements(reference: str, directory: Path, source: str, active: set[Path]) -> None:
        if not reference or "$" in reference or "://" in reference:
            warn(source, f"Requirements reference {reference!r} cannot be verified statically.")
            return
        try:
            target = (directory / reference).resolve()
            if not target.is_relative_to(root):
                warn(source, "Requirements paths outside the project are not inspected.")
                return
            label = target.relative_to(root).as_posix()
            if target in active:
                warn(label, "A cyclic requirements include cannot be verified.")
                return
            text = target.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError, RuntimeError, ValueError):
            warn(source, f"Requirements reference {reference!r} could not be read.")
            return
        active = active | {target}
        for line in _logical_commands(text):
            if line.startswith("-"):
                try:
                    nested = _requirement_files(shlex.split(line))
                except ValueError:
                    warn(label, "A requirements directive could not be parsed.")
                    continue
                for reference in nested:
                    read_requirements(reference, target.parent, label, active)
                continue
            requirement_text = re.split(r"\s+--hash(?:=|\s)", line, maxsplit=1)[0]
            try:
                requirement = Requirement(requirement_text)
            except InvalidRequirement:
                warn(label, "A requirements entry could not be verified statically.")
                continue
            if canonicalize_name(requirement.name) != canonicalize_name(project_name):
                continue
            exact = [spec.version for spec in requirement.specifier if spec.operator == "==" and "*" not in spec.version]
            if exact:
                pins.extend((label, pin) for pin in exact)
            else:
                warn(label, f"The requirement for {project_name} has no statically verifiable exact version.")

    for path in files:
        source = path.relative_to(root).as_posix()
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            raise InputError("workflow_unreadable", f"{source} could not be read as UTF-8.") from exc
        except yaml.YAMLError as exc:
            raise InputError("workflow_invalid_yaml", f"{source} is not valid YAML: {exc}") from exc
        if document is None:
            continue
        if not isinstance(document, dict):
            raise InputError("workflow_invalid_yaml", f"{source} must contain a YAML mapping.")
        for script, working_directory in _run_steps(document):
            for command in _logical_commands(script):
                try:
                    installs = _install_arguments(command)
                except ValueError:
                    warn(source, "A run command could not be parsed statically.")
                    continue
                for arguments in installs:
                    joined = " ".join(arguments)
                    pins.extend((source, pin) for pin in extract_pins(joined, project_name))
                    dynamic_pins.extend(
                        (source, match.group("version"))
                        for match in dynamic_pin_pattern(project_name).finditer(joined)
                    )
                    references = _requirement_files(arguments)
                    if not references:
                        continue
                    if not isinstance(working_directory, str) or "$" in working_directory:
                        warn(source, "The requirements working directory cannot be resolved statically.")
                        continue
                    for reference in references:
                        read_requirements(reference, root / working_directory, source, set())

    findings: list[Finding] = []
    matching = [(source, pin) for source, pin in pins if _same_version(pin, version)]
    drifting = sorted({(source, pin) for source, pin in pins if not _same_version(pin, version)})
    if matching:
        source, actual = sorted(matching)[0]
        findings.append(Finding(
            code="workflow_pin_matches", severity="pass", source=source,
            message=f"Workflow install pins {project_name} to version {version}.", actual=actual, expected=version,
        ))
    for source, actual in drifting:
        findings.append(Finding(
            code="workflow_version_drift", severity="fail", source=source,
            message=f"Workflow install pins {project_name} to {actual}; expected {version}.", actual=actual, expected=version,
        ))
    for source, actual in sorted(set(dynamic_pins)):
        findings.append(Finding(
            code="workflow_dynamic_version", severity="warn", source=source,
            message=f"A dynamic version cannot be verified statically for {project_name}.", actual=actual, expected=version,
        ))
    if not pins and not dynamic_pins:
        findings.append(Finding(
            code="workflow_pin_not_found", severity="pass", source=".github/workflows",
            message=f"No pinned workflow install of {project_name} was found.",
        ))
    return findings + warnings
