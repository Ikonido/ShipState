"""Inspect a limited static shell syntax; warn when an install is uncertain."""

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version

from shipstate.checks.pins import dynamic_pin_pattern
from shipstate.models import Finding, InputError


_GITHUB_EXPRESSION = re.compile(r"\$\{\{.*?\}\}", re.DOTALL)
_GLOBAL_FLAGS = {
    "--disable-pip-version-check", "--isolated", "--no-input", "--no-cache-dir",
    "--require-virtualenv", "--require-venv", "-q", "--quiet", "-v", "--verbose",
}
_GLOBAL_VALUES = {
    "--log", "--proxy", "--timeout", "--retries", "--cert", "--client-cert",
    "--cache-dir", "--trusted-host", "--exists-action", "--keyring-provider",
}
_DIRECTORY_COMMANDS = {"cd", "pushd", "popd", "Set-Location", "chdir"}
_VALUE_OPTIONS = {
    "-i", "--index-url", "--extra-index-url", "-f", "--find-links", "-t", "--target",
    "--prefix", "--root", "--cache-dir", "--log", "--timeout", "--retries",
    "--proxy", "--cert", "--client-cert", "--trusted-host", "--python",
    "--config-settings", "-C", "--platform", "--python-version", "--implementation", "--abi",
}
_FLAG_OPTIONS = {
    "-U", "--upgrade", "--pre", "--no-deps", "--no-cache-dir", "--require-hashes",
    "--force-reinstall", "--ignore-installed", "--no-build-isolation", "--disable-pip-version-check",
    "-q", "--quiet", "-v", "--verbose", "--user", "--break-system-packages",
    "--no-input", "--no-compile", "--compile", "--prefer-binary", "--use-pep517",
}


@dataclass
class _Install:
    requested: list[tuple[str, Requirement]] = field(default_factory=list)
    constraints: list[tuple[str, Requirement]] = field(default_factory=list)
    incomplete: bool = False


def _opaque_expressions(text: str) -> tuple[str, dict[str, str]]:
    prefix = "__shipstate_expression_"
    while prefix in text:
        prefix = "_" + prefix
    expressions: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = f"{prefix}{len(expressions)}__"
        expressions[token] = match.group()
        return token

    return _GITHUB_EXPRESSION.sub(replace, text), expressions


def _restore(text: str, expressions: dict[str, str]) -> str:
    for token, expression in expressions.items():
        text = text.replace(token, expression)
    return text


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


def _requirements_lines(text: str) -> list[str]:
    """Requirements directives use their existing line-oriented preprocessing."""
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


def _logical_commands(text: str) -> list[str]:
    """Join POSIX continuations without changing words or single-quoted text."""
    commands = []
    current: list[str] = []
    quote = None
    comment = False
    in_word = False
    index = 0
    while index < len(text):
        char = text[index]
        if comment:
            if char != "\n":
                index += 1
                continue
            comment = False
        elif char == "\\" and quote != "'" and index + 1 < len(text):
            following = text[index + 1]
            if following != "\n":
                current.extend((char, following))
                in_word = True
            index += 2
            continue
        elif quote:
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
            in_word = True
        elif char == "#" and not in_word:
            comment = True
            index += 1
            continue
        else:
            # Unquoted operators end a word even without whitespace. Braces
            # are reserved words, so '{#suffix' still belongs to one word.
            in_word = not (char.isspace() or char in ";&|()<>")
        if char == "\n" and quote is None:
            command = "".join(current).strip()
            if command:
                commands.append(command)
            current = []
            in_word = False
        else:
            current.append(char)
        index += 1
    command = "".join(current).strip()
    if command:
        commands.append(command)
    return commands


class _ShellWords(list[str]):
    """Unquoted argv plus the raw, unquoted assignment prefix length."""

    def __init__(self, text: str):
        super().__init__(shlex.split(text))
        self.assignments = 0
        index = 0
        while match := re.match(r"\s*[A-Za-z_][A-Za-z0-9_]*=", text[index:]):
            index += match.end()
            quote = None
            while index < len(text):
                char = text[index]
                if char == "\\" and quote != "'":
                    index += 2
                    continue
                if quote:
                    if char == quote:
                        quote = None
                elif char in {"'", '"'}:
                    quote = char
                elif char.isspace():
                    break
                index += 1
            self.assignments += 1


def _segments(command: str) -> list[list[str]]:
    """Split only unquoted chain operators, then let shlex unquote each segment."""
    if "\n" in command:
        raise ValueError("multiline quoted text is not interpreted")
    parts = []
    start = 0
    quote = None
    escaped = False
    index = 0
    while index < len(command):
        char = command[index]
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char in "()" or (char in "{}" and (index == 0 or command[index - 1].isspace() or command[index - 1] in ";&|")):
            raise ValueError("shell grouping is not interpreted")
        elif char in ";&|":
            parts.append(command[start:index])
            following = index + 1
            while following < len(command) and command[following] in ";&|":
                following += 1
            if command[index:following] not in {";", "&&", "||"}:
                raise ValueError("pipes and background commands are not interpreted")
            index = following - 1
            start = following
        index += 1
    parts.append(command[start:])
    return [_ShellWords(part) for part in parts if part.strip()]


def _command_tokens(tokens: list[str]) -> list[str]:
    tokens = tokens[getattr(tokens, "assignments", 0):]
    if tokens and tokens[0] == "env":
        tokens = tokens[1:]
        # env receives argv strings: unlike shell assignment words, quoting
        # an env utility argument does not stop it being an assignment.
        while tokens and re.match(r"[A-Za-z_][A-Za-z0-9_]*=", tokens[0]):
            tokens = tokens[1:]
    return tokens


def _install_arguments(tokens: list[str]) -> list[str] | None:
    tokens = _command_tokens(tokens)
    if tokens and re.fullmatch(r"pip(?:\d+(?:\.\d+)*)?", tokens[0]):
        tokens = tokens[1:]
    elif len(tokens) >= 3 and re.fullmatch(r"python[0-9.]*", tokens[0]) and tokens[1:3] == ["-m", "pip"]:
        tokens = tokens[3:]
    elif tokens[:3] == ["uv", "pip", "install"]:
        return tokens[3:]
    else:
        return None
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "install":
            return tokens[index + 1:]
        option, separator, value = token.partition("=")
        if token in _GLOBAL_FLAGS or re.fullmatch(r"-(?:q+|v+)", token):
            index += 1
        elif option in _GLOBAL_VALUES:
            if not separator:
                index += 1
                if index >= len(tokens) or tokens[index].startswith("-"):
                    raise ValueError("missing global pip option value")
            elif not value:
                raise ValueError("missing global pip option value")
            index += 1
        elif token.startswith("-"):
            raise ValueError("unsupported global pip option")
        else:
            return None
    return None


def _changes_directory(tokens: list[str]) -> bool:
    tokens = _command_tokens(tokens)
    if tokens and tokens[0] in {"command", "builtin"}:
        tokens = tokens[1:]
        if tokens[:1] == ["-p"]:
            tokens = tokens[1:]
        if tokens[:1] == ["--"]:
            tokens = tokens[1:]
    return bool(tokens and tokens[0] in _DIRECTORY_COMMANDS)


def _pip_environment(mapping: dict, inherited: bool = False) -> bool:
    environment = mapping.get("env", {})
    if not isinstance(environment, dict):
        return True
    return inherited or any(isinstance(key, str) and key.startswith("PIP_") for key in environment)


def _pip_assignments(tokens: list[str]) -> bool:
    """Recognize configuration names, without evaluating values or shell state."""
    count = getattr(tokens, "assignments", 0)
    if any(token.startswith("PIP_") for token in tokens[:count]):
        return True
    tokens = tokens[count:]
    if tokens and tokens[0] in {"env", "export"}:
        tokens = tokens[1:]
    else:
        return False
    for token in tokens:
        if not re.match(r"[A-Za-z_][A-Za-z0-9_]*=", token):
            break
        if token.startswith("PIP_"):
            return True
    return False


def _pip_arguments(arguments: list[str]) -> tuple[list[str], list[tuple[str, bool]]]:
    entries = []
    references = []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        option, _, value = token.partition("=")
        if option in {"-r", "--requirement", "-c", "--constraint", "-e", "--editable"}:
            if "=" not in token:
                index += 1
                if index >= len(arguments):
                    raise ValueError("missing pip option value")
                value = arguments[index]
            if option in {"-e", "--editable"}:
                entries.append("-e " + value)
            else:
                references.append((value, option in {"-c", "--constraint"}))
        elif token.startswith(("-r", "-c", "-e")) and not token.startswith("--") and len(token) > 2:
            if token.startswith("-e"):
                entries.append("-e " + token[2:])
            else:
                references.append((token[2:], token.startswith("-c")))
        elif option in _VALUE_OPTIONS:
            if "=" not in token:
                index += 1
                if index >= len(arguments):
                    raise ValueError("missing pip option value")
        elif token in _FLAG_OPTIONS:
            pass
        elif token.startswith("-"):
            raise ValueError("unsupported pip option")
        else:
            if index + 2 < len(arguments) and arguments[index + 1] == "@":
                token += " @ " + arguments[index + 2]
                index += 2
            entries.append(token)
        index += 1
    return entries, references


def _run_default(mapping: dict, name: str, fallback: object) -> object:
    defaults = mapping.get("defaults", {})
    run = defaults.get("run", {}) if isinstance(defaults, dict) else {}
    return run.get(name, fallback) if isinstance(run, dict) else fallback


def _runner_shell(runner: object) -> str:
    # Missing runs-on is allowed for workflow excerpts used by local callers.
    if runner is None:
        return "bash"
    labels = runner if isinstance(runner, list) else [runner]
    if any(isinstance(label, str) and (label.lower() in {"linux", "macos"} or label.lower().startswith(("ubuntu-", "macos-"))) for label in labels):
        return "bash"
    return "unknown"


def _run_steps(document: dict):
    if isinstance(document.get("run"), str):
        yield document["run"], document.get("working-directory", "."), document.get("shell", "bash"), _pip_environment(document)
    jobs = document.get("jobs", {})
    if not isinstance(jobs, dict):
        return
    default_directory = _run_default(document, "working-directory", ".")
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        steps = job.get("steps", [])
        if not isinstance(steps, list):
            continue
        directory = _run_default(job, "working-directory", default_directory)
        shell = _run_default(job, "shell", _run_default(document, "shell", _runner_shell(job.get("runs-on"))))
        environment = _pip_environment(job, _pip_environment(document))
        for step in steps:
            if isinstance(step, dict) and isinstance(step.get("run"), str):
                yield step["run"], step.get("working-directory", directory), step.get("shell", shell), _pip_environment(step, environment)


def _same_version(actual: str, expected: str) -> bool:
    try:
        return Version(actual) == Version(expected)
    except InvalidVersion:
        return False


def _exact_version(requirement: Requirement) -> str | None:
    specs = list(requirement.specifier)
    if requirement.url or len(specs) != 1 or specs[0].operator != "==" or "*" in specs[0].version:
        return None
    return specs[0].version


def check_workflows(root: Path, project_name: str, version: str) -> list[Finding]:
    root = root.resolve()
    workflow_dir = root / ".github" / "workflows"
    pins: list[tuple[str, str]] = []
    warnings: list[Finding] = []

    def warn(source: str, message: str, code: str = "workflow_requirements_unchecked", actual: str | None = None) -> None:
        finding = Finding(code=code, severity="warn", source=source, message=message, actual=actual,
                          expected=version if code == "workflow_dynamic_version" else None)
        if finding not in warnings:
            warnings.append(finding)

    def potential_install(script: str, configuration: bool = False) -> bool:
        package = r"[-_.]+".join(re.escape(part) for part in canonicalize_name(project_name).split("-"))
        masked, expressions = _opaque_expressions(script)
        for command in _logical_commands(masked):
            try:
                segments = _segments(command)
            except ValueError:
                # Lexical fallback only: unsupported shell operators are never executed.
                segments = [[command]]
            for tokens in segments:
                head = _command_tokens(tokens)
                if head and head[0] in {"echo", "printf"}:
                    continue
                text = _restore(" ".join(tokens), expressions)
                self_name = re.search(rf"(?<![A-Za-z0-9_.-]){package}(?![A-Za-z0-9_.-])", text, re.IGNORECASE)
                pip = re.search(r"\bpip(?:\d+(?:\.\d+)*)?\b", text, re.IGNORECASE)
                install = re.search(r"\binstall\b", text, re.IGNORECASE)
                opaque_head = bool(head and "$" in _restore(head[0], expressions))
                reference = re.search(r"(?:-r|-c|--requirement|--constraint|-e|--editable|install\s+\.)", text)
                pip_setting = re.search(r"\bPIP_[A-Z_]+\s*=", text)
                if ((pip and install and (self_name or "$" in text or reference or pip_setting or configuration))
                        or (self_name and (install or opaque_head))):
                    return True
        return False

    def collect(text: str, directory: Path, source: str, install: _Install, constraint: bool = False) -> None:
        candidate = re.match(r"[A-Za-z0-9][A-Za-z0-9_.-]*", text)
        is_self = candidate is not None and canonicalize_name(candidate.group()) == canonicalize_name(project_name)
        if is_self and "$" in text:
            match = dynamic_pin_pattern(project_name).search(text)
            actual = match.group("version") if match else text
            warn(source, f"A dynamic version cannot be verified statically for {project_name}.", "workflow_dynamic_version", actual)
            install.incomplete = True
            return
        local = text.removeprefix("-e ")
        if text.startswith("-e ") or local == "." or local.startswith(("./", "../", "/", "~", "file:")):
            try:
                current_project = "$" not in local and (directory / local).resolve() == root
            except (OSError, RuntimeError, ValueError):
                current_project = False
            warn(source, "A local project install has no statically pinned distribution version." if current_project else "A local install cannot be verified as the current project statically.",
                 "workflow_local_project_install" if current_project else "workflow_requirements_unchecked")
            install.incomplete = True
            return
        try:
            requirement = Requirement(text)
        except InvalidRequirement:
            warn(source, "A requirements entry could not be verified statically.")
            install.incomplete = True
            return
        if canonicalize_name(requirement.name) == canonicalize_name(project_name):
            (install.constraints if constraint else install.requested).append((source, requirement))

    def read_requirements(reference: str, directory: Path, source: str, active: set[Path], install: _Install, constraint: bool = False) -> None:
        if not reference or "$" in reference or "://" in reference:
            warn(source, f"Requirements reference {reference!r} cannot be verified statically.")
            install.incomplete = True
            return
        try:
            target = (directory / reference).resolve()
            if not target.is_relative_to(root):
                warn(source, "Requirements paths outside the project are not inspected.")
                install.incomplete = True
                return
            label = target.relative_to(root).as_posix()
            if target in active:
                warn(label, "A cyclic requirements include cannot be verified.")
                install.incomplete = True
                return
            text = target.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError, RuntimeError, ValueError):
            warn(source, f"Requirements reference {reference!r} could not be read.")
            install.incomplete = True
            return
        active = active | {target}
        masked, expressions = _opaque_expressions(text)
        for line in _requirements_lines(masked):
            if line.startswith("-"):
                try:
                    entries, nested = _pip_arguments(shlex.split(line))
                except ValueError:
                    warn(label, "A requirements directive could not be parsed statically.")
                    install.incomplete = True
                    continue
                for entry in entries:
                    collect(_restore(entry, expressions), target.parent, label, install, constraint)
                for child, child_constraint in nested:
                    read_requirements(_restore(child, expressions), target.parent, label, active, install, constraint or child_constraint)
            else:
                entry = re.split(r"\s+--hash(?:=|\s)", line, maxsplit=1)[0]
                collect(_restore(entry, expressions), target.parent, label, install, constraint)

    def finish_install(install: _Install) -> None:
        for source, requirement in install.requested:
            exact = _exact_version(requirement)
            if exact is not None:
                if any(c.url or c.marker or not c.specifier.contains(exact, prereleases=True) for _, c in install.constraints):
                    warn(source, "Constraints do not establish a consistent install for the requested exact version.", "workflow_version_not_exact")
                else:
                    pins.append((source, exact))
                continue
            # Only a bare explicitly requested self package can inherit an exact
            # constraint. Do not implement dependency or general constraint resolution.
            constraint_pins = [(label, _exact_version(c)) for label, c in install.constraints]
            if (not requirement.specifier and not requirement.url and not requirement.marker
                    and not install.incomplete and constraint_pins
                    and all(not c.marker and not c.extras and not c.url for _, c in install.constraints)
                    and all(pin is not None for _, pin in constraint_pins)
                    and len({pin for _, pin in constraint_pins}) == 1):
                pins.append((constraint_pins[0][0], constraint_pins[0][1]))
            else:
                warn(source, f"The requirement for {project_name} has no statically verifiable exact version.", "workflow_version_not_exact")

    try:
        if not workflow_dir.resolve().is_relative_to(root):
            warn(".github/workflows", "Workflow directory outside the project is not inspected.", "workflow_outside_project")
            return warnings
        files = sorted((path for path in workflow_dir.iterdir() if path.suffix.lower() in {".yml", ".yaml"}), key=lambda item: item.name.casefold()) if workflow_dir.is_dir() else []
    except (OSError, RuntimeError, ValueError) as exc:
        raise InputError("workflow_unreadable", "The workflow directory could not be inspected.") from exc

    for path in files:
        source = path.relative_to(root).as_posix()
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                warn(source, "Workflow files outside the project are not inspected.", "workflow_outside_project")
                continue
            if not resolved.is_file():
                continue
            document = yaml.safe_load(resolved.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, RuntimeError, ValueError) as exc:
            raise InputError("workflow_unreadable", f"{source} could not be read as UTF-8.") from exc
        except yaml.YAMLError as exc:
            raise InputError("workflow_invalid_yaml", f"{source} is not valid YAML: {exc}") from exc
        if document is None:
            continue
        if not isinstance(document, dict):
            raise InputError("workflow_invalid_yaml", f"{source} must contain a YAML mapping.")
        for script, working_directory, shell, environment in _run_steps(document):
            potential = potential_install(script, environment)
            if not isinstance(shell, str) or shell not in {"bash", "sh"}:
                if potential:
                    warn(source, "The run step shell is not supported for static install analysis.", "workflow_shell_not_supported")
                continue
            masked, expressions = _opaque_expressions(script)
            commands = _logical_commands(masked)
            if not isinstance(working_directory, str):
                warn(source, "The requirements working directory is not a string and cannot be resolved statically.", "workflow_working_directory_ambiguous")
                continue
            # Here-documents, substitutions and control flow need a shell parser.
            if potential and any(re.search(r"<<|\$\(|`|(?:^|[;&|]\s*)(?:if|for|while|until|case|function)\b|\b[A-Za-z_]\w*\s*\(\s*\)\s*\{", command) for command in commands):
                warn(source, "Shell constructs or documentation text cannot be interpreted reliably.", "workflow_shell_ambiguous")
                continue
            try:
                segments_by_command = [_segments(command) for command in commands]
            except ValueError:
                if potential:
                    if re.search(r"\b(?:cd|pushd|popd|chdir|Set-Location)\b", " ".join(commands)):
                        warn(source, "Working directory may have changed before package installation; local requirement paths cannot be verified statically.", "workflow_working_directory_ambiguous")
                    else:
                        warn(source, "A run block could not be parsed statically.", "workflow_shell_ambiguous")
                continue
            if potential and any(
                _command_tokens(tokens) and "$" in _restore(_command_tokens(tokens)[0], expressions)
                for segments in segments_by_command for tokens in segments
            ):
                warn(source, "An opaque executable cannot be interpreted as a static install command.", "workflow_install_ambiguous")
                continue
            if potential and any(
                _command_tokens(tokens) and _command_tokens(tokens)[0] in {"source", ".", "eval", "alias", "unalias", "exec", "trap"}
                for segments in segments_by_command for tokens in segments
            ):
                warn(source, "Shell command definitions or sourced code cannot be interpreted reliably.", "workflow_shell_ambiguous")
                continue
            cwd_changed = False
            for segments in segments_by_command:
                for tokens in segments:
                    command_tokens = _command_tokens(tokens)
                    if _changes_directory(tokens):
                        cwd_changed = True
                        continue
                    if _pip_assignments(tokens) and (not command_tokens or command_tokens[0] == "export"):
                        environment = True
                        continue
                    try:
                        arguments = _install_arguments(tokens)
                    except ValueError:
                        if potential_install(_restore(" ".join(tokens), expressions), environment):
                            warn(source, "Global pip options cannot be interpreted reliably.", "workflow_install_ambiguous")
                        continue
                    if arguments is None:
                        if command_tokens and command_tokens[0] not in {"echo", "printf"} and potential_install(_restore(" ".join(tokens), expressions), environment):
                            warn(source, "An install command cannot be interpreted reliably.", "workflow_install_ambiguous")
                        continue
                    environment_ambiguous = environment or _pip_assignments(tokens)
                    if environment_ambiguous:
                        warn(source, "Explicit pip environment configuration may change the effective install and is not interpreted.", "workflow_pip_environment_ambiguous")
                    try:
                        entries, references = _pip_arguments([_restore(arg, expressions) for arg in arguments])
                    except ValueError:
                        warn(source, "Pip arguments cannot be interpreted reliably.", "workflow_shell_ambiguous")
                        continue
                    install = _Install(incomplete=environment_ambiguous)
                    known_directory = isinstance(working_directory, str) and "$" not in working_directory
                    directory = root / working_directory if known_directory else root
                    for entry in entries:
                        if (cwd_changed or not known_directory) and (entry.startswith("-e ") or entry == "." or entry.startswith(("./", "../"))):
                            warn(source, "The local install working directory cannot be resolved statically.", "workflow_working_directory_ambiguous")
                            install.incomplete = True
                        else:
                            collect(entry, directory, source, install)
                    if references and (cwd_changed or not known_directory):
                        warn(source, "Working directory may have changed before package installation; local requirement paths cannot be verified statically.", "workflow_working_directory_ambiguous")
                        install.incomplete = True
                    elif not environment_ambiguous:
                        for reference, constraint in references:
                            read_requirements(reference, directory, source, set(), install, constraint)
                    finish_install(install)

    findings: list[Finding] = []
    matching = sorted({(source, pin) for source, pin in pins if _same_version(pin, version)})
    if matching:
        source, actual = matching[0]
        findings.append(Finding(code="workflow_pin_matches", severity="pass", source=source,
                                message=f"Workflow install pins {project_name} to version {version}.", actual=actual, expected=version))
    for source, actual in sorted({(source, pin) for source, pin in pins if not _same_version(pin, version)}):
        findings.append(Finding(code="workflow_version_drift", severity="fail", source=source,
                                message=f"Workflow install pins {project_name} to {actual}; expected {version}.", actual=actual, expected=version))
    if not pins and not warnings:
        findings.append(Finding(code="workflow_pin_not_found", severity="pass", source=".github/workflows",
                                message=f"No static self-package workflow install of {project_name} requires checking."))
    return findings + warnings
