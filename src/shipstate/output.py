import json

from shipstate.models import CheckResult, Finding, InputError


def render_json_result(result: CheckResult, shipstate_version: str) -> str:
    return json.dumps(result.to_dict(shipstate_version), ensure_ascii=False, indent=2)


def render_json_error(error: InputError, shipstate_version: str) -> str:
    return json.dumps(error.to_dict(shipstate_version), ensure_ascii=False, indent=2)


def _finding_detail(finding: Finding) -> str:
    if finding.code == "package_version_valid":
        return f"package version: {finding.actual}"
    if finding.code in {"version_tag_matches_head", "missing_version_tag"}:
        return f"git tag: {finding.source.removeprefix('tag:') if finding.source != 'git' else finding.expected}"
    if finding.code == "tag_commit_mismatch":
        return f"git tag: {finding.source.removeprefix('tag:')} points to another commit"
    if finding.code == "changelog_version_found":
        return f"changelog: {finding.actual} found"
    if finding.code in {"changelog_missing", "changelog_version_missing"}:
        return f"changelog: {finding.message}"
    if finding.code in {"readme_pin_matches", "readme_pin_not_found"}:
        if finding.actual:
            package = finding.message.removeprefix("README.md pins ").split(" to ", 1)[0]
            return f"README pin: {package}=={finding.actual}"
        return "README pin: no pinned install found"
    if finding.code == "readme_version_drift":
        package = finding.message.removeprefix("README.md pins ").split(" to ", 1)[0]
        return f"README pin: {package}=={finding.actual}"
    if finding.code == "workflow_pin_matches":
        package = finding.message.removeprefix("Workflow install pins ").split(" to ", 1)[0]
        return f"workflow pin: {package}=={finding.actual}"
    if finding.code == "workflow_version_drift":
        package = finding.message.removeprefix("Workflow install pins ").split(" to ", 1)[0]
        return f"workflow pin: {package}=={finding.actual}"
    if finding.code == "workflow_pin_not_found":
        return "workflow pin: no pinned install found"
    if finding.code == "workflow_dynamic_version":
        return f"workflow pin: {finding.message}"
    if finding.code == "license_present":
        return f"license: {finding.source} found"
    if finding.code == "license_missing":
        return "license: LICENSE not found"
    if finding.code == "build_system_present":
        return "build system: present"
    if finding.code == "build_system_missing":
        return "build system: [build-system] not found"
    if finding.code == "build_system_requires_missing":
        return "build system: [build-system].requires not found"
    if finding.code == "build_backend_missing":
        return "build system: [build-system].build-backend not found"
    if finding.code == "build_system_invalid":
        return f"build system: {finding.message}"
    return finding.message


def render_text_result(result: CheckResult, shipstate_version: str) -> str:
    lines = [
        f"ShipState {shipstate_version}",
        "",
        f"Project: {result.project.name}",
        f"Version: {result.project.version}",
        "",
    ]
    for finding in result.findings:
        lines.append(f"{finding.severity.upper()} {_finding_detail(finding)}")
    lines.extend(["", f"Release consistency: {result.status.upper()}"])
    return "\n".join(lines)


def render_text_error(error: InputError, shipstate_version: str) -> str:
    return f"ShipState {shipstate_version}\nERROR [{error.code}]: {error.message}"
