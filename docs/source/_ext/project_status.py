"""Generate the DigitalDiaryApp project status summary during Sphinx builds.

The extension compares the current ``app`` tree with a configured Git baseline,
combines automatic drift detection with a small manually editable status file,
and writes a MyST include consumed by ``status/index.md``.

The manual file is not a registry. New folders and files are discovered even if
they are absent from the configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
import subprocess
import tomllib
from typing import Iterable

from sphinx.application import Sphinx
from sphinx.errors import ExtensionError


IMPLEMENTATION_VALUES = {"PLANNED", "IN PROGRESS", "READY", "INACTIVE"}
VERIFICATION_VALUES = {"UNVERIFIED", "TESTED", "PRODUCT VERIFIED"}
DOCUMENTATION_VALUES = {"MISSING", "DRAFT", "CURRENT"}

DEFAULT_IMPLEMENTATION = "READY"
DEFAULT_VERIFICATION = "UNVERIFIED"
DEFAULT_DOCUMENTATION = "MISSING"


@dataclass
class Component:
    key: str
    title: str
    path: str
    implementation: str
    verification: str
    documentation: str
    docs: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    note: str = ""
    source: str = "AUTO"
    changed: bool = False
    new: bool = False
    signals: list[str] = field(default_factory=list)


def _run_git(project_root: Path, *args: str, check: bool = True) -> str:
    """Run Git in the project root and return normalized stdout."""
    process = subprocess.run(
        ["git", *args],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if check and process.returncode != 0:
        stderr = process.stderr.strip()
        raise ExtensionError(
            f"project_status: git {' '.join(args)} failed: {stderr}"
        )

    return process.stdout.replace("\\", "/").strip()


def _load_config(project_root: Path) -> dict:
    """Load the manually editable project status configuration."""
    path = project_root / "project-status.toml"
    if not path.is_file():
        raise ExtensionError(
            "project_status: project-status.toml was not found in project root."
        )

    with path.open("rb") as file:
        config = tomllib.load(file)

    if int(config.get("version", 0)) != 1:
        raise ExtensionError("project_status: unsupported project-status.toml version.")

    baseline = str(config.get("baseline_commit", "")).strip()
    if not baseline:
        raise ExtensionError("project_status: baseline_commit is required.")

    return config


def _normalize_path(value: str) -> str:
    """Normalize a project-relative path to Git-style separators."""
    return PurePosixPath(value.replace("\\", "/")).as_posix().strip("/")


def _ignored(path: str, ignore: dict) -> bool:
    """Return whether a project-relative path is ignored by discovery."""
    pure = PurePosixPath(path)
    names = {str(item) for item in ignore.get("names", [])}
    suffixes = {str(item) for item in ignore.get("suffixes", [])}
    ignored_paths = {
        _normalize_path(str(item))
        for item in ignore.get("paths", [])
    }

    if _normalize_path(path) in ignored_paths:
        return True

    if any(part in names for part in pure.parts):
        return True

    if pure.suffix in suffixes:
        return True

    return False


def _baseline_files(
    project_root: Path,
    baseline: str,
    source_root: str,
    ignore: dict,
) -> set[str]:
    """Read tracked source files from the configured Git baseline."""
    output = _run_git(
        project_root,
        "ls-tree",
        "-r",
        "--name-only",
        baseline,
        "--",
        source_root,
    )

    return {
        _normalize_path(line)
        for line in output.splitlines()
        if line.strip() and not _ignored(line.strip(), ignore)
    }


def _current_files(
    project_root: Path,
    source_root: str,
    ignore: dict,
) -> set[str]:
    """Read current source files, including untracked working-tree files."""
    root = project_root / source_root
    if not root.is_dir():
        raise ExtensionError(
            f"project_status: source root does not exist: {root}"
        )

    result: set[str] = set()

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative = path.relative_to(project_root).as_posix()
        if _ignored(relative, ignore):
            continue

        result.add(relative)

    return result


def _all_directories(files: Iterable[str], source_root: str) -> set[str]:
    """Return directory paths implied by file paths, below source_root."""
    root = PurePosixPath(source_root)
    directories: set[str] = set()

    for value in files:
        path = PurePosixPath(value)
        parent = path.parent

        while parent != root and root in parent.parents:
            directories.add(parent.as_posix())
            parent = parent.parent

        if parent == root:
            directories.add(root.as_posix())

    return directories


def _minimal_new_directories(
    baseline_files: set[str],
    current_files: set[str],
    source_root: str,
) -> list[str]:
    """Return only top-most newly introduced directories."""
    baseline_dirs = _all_directories(baseline_files, source_root)
    current_dirs = _all_directories(current_files, source_root)

    candidates = sorted(
        current_dirs - baseline_dirs,
        key=lambda value: (len(PurePosixPath(value).parts), value.casefold()),
    )

    result: list[str] = []

    for candidate in candidates:
        pure = PurePosixPath(candidate)
        if any(PurePosixPath(parent) in pure.parents for parent in result):
            continue
        result.append(candidate)

    return result


def _under_any(path: str, directories: Iterable[str]) -> bool:
    pure = PurePosixPath(path)
    return any(
        pure == PurePosixPath(directory)
        or PurePosixPath(directory) in pure.parents
        for directory in directories
    )


def _changed_paths(
    project_root: Path,
    baseline: str,
    source_root: str,
    ignore: dict,
) -> set[str]:
    """Return tracked paths changed against baseline in HEAD or working tree."""
    output = _run_git(
        project_root,
        "diff",
        "--name-only",
        baseline,
        "--",
        source_root,
    )

    return {
        _normalize_path(line)
        for line in output.splitlines()
        if line.strip() and not _ignored(line.strip(), ignore)
    }


def _validate_status(value: str, allowed: set[str], field_name: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ExtensionError(
            f"project_status: invalid {field_name}={value!r}; "
            f"expected one of: {allowed_text}"
        )
    return normalized


def _path_matches(component_path: str, candidate: str) -> bool:
    """Return whether candidate belongs to a component path."""
    component = PurePosixPath(component_path)
    path = PurePosixPath(candidate)
    return path == component or component in path.parents


def _component_docs_status(project_root: Path, docs: list[str]) -> str:
    if not docs:
        return "MISSING"

    existing = [
        project_root / _normalize_path(path)
        for path in docs
    ]

    return "DRAFT" if not all(path.is_file() for path in existing) else "CURRENT"


def _configured_components(
    project_root: Path,
    config: dict,
    changed_paths: set[str],
) -> dict[str, Component]:
    """Build configured baseline components and degrade changed ones."""
    result: dict[str, Component] = {}

    for key, raw in config.get("components", {}).items():
        component_path = _normalize_path(str(raw["path"]))
        docs = [_normalize_path(str(item)) for item in raw.get("docs", [])]

        component = Component(
            key=str(key),
            title=str(raw.get("title", key)),
            path=component_path,
            implementation=_validate_status(
                raw.get("implementation", DEFAULT_IMPLEMENTATION),
                IMPLEMENTATION_VALUES,
                "implementation",
            ),
            verification=_validate_status(
                raw.get("verification", DEFAULT_VERIFICATION),
                VERIFICATION_VALUES,
                "verification",
            ),
            documentation=_validate_status(
                raw.get(
                    "documentation",
                    _component_docs_status(project_root, docs),
                ),
                DOCUMENTATION_VALUES,
                "documentation",
            ),
            docs=docs,
            source="MANUAL",
        )

        relevant_changes = sorted(
            path for path in changed_paths
            if _path_matches(component_path, path)
        )

        if relevant_changes:
            component.changed = True
            component.implementation = "IN PROGRESS"
            component.verification = "UNVERIFIED"
            component.documentation = (
                "DRAFT"
                if any((project_root / path).is_file() for path in docs)
                else "MISSING"
            )
            component.source = "AUTO DRIFT"
            component.signals.append(
                f"изменено путей: {len(relevant_changes)}"
            )

        result[component.key] = component

    return result


def _top_level_directory_components(
    project_root: Path,
    config: dict,
    baseline_files: set[str],
    current_files: set[str],
    changed_paths: set[str],
    new_directories: list[str],
) -> dict[str, Component]:
    """Ensure baseline/current top-level source directories appear in dashboard."""
    source_root = _normalize_path(str(config.get("source_root", "app")))
    root = PurePosixPath(source_root)
    configured_paths = {
        _normalize_path(str(value["path"]))
        for value in config.get("components", {}).values()
    }

    top_dirs: set[str] = set()

    for value in baseline_files | current_files:
        path = PurePosixPath(value)
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue

        if len(relative.parts) >= 2:
            top_dirs.add((root / relative.parts[0]).as_posix())

    result: dict[str, Component] = {}

    for directory in sorted(top_dirs, key=str.casefold):
        if directory in configured_paths:
            continue

        key = PurePosixPath(directory).name
        is_new = _under_any(directory, new_directories) or directory in new_directories
        relevant_changes = sorted(
            path for path in changed_paths
            if _path_matches(directory, path)
        )

        implementation = "IN PROGRESS" if (is_new or relevant_changes) else "READY"
        verification = "UNVERIFIED"
        documentation = "MISSING"

        component = Component(
            key=key,
            title=key,
            path=directory,
            implementation=implementation,
            verification=verification,
            documentation=documentation,
            source="NEW" if is_new else "AUTO",
            changed=bool(relevant_changes),
            new=is_new,
        )

        if relevant_changes:
            component.signals.append(
                f"изменено путей: {len(relevant_changes)}"
            )

        result[key] = component

    return result


def _apply_overrides(
    components: dict[str, Component],
    config: dict,
) -> None:
    """Apply explicit human overrides last."""
    for key, raw in config.get("overrides", {}).items():
        key = str(key)
        if key not in components:
            continue

        component = components[key]

        if "implementation" in raw:
            component.implementation = _validate_status(
                raw["implementation"],
                IMPLEMENTATION_VALUES,
                "implementation",
            )

        if "verification" in raw:
            component.verification = _validate_status(
                raw["verification"],
                VERIFICATION_VALUES,
                "verification",
            )

        if "documentation" in raw:
            component.documentation = _validate_status(
                raw["documentation"],
                DOCUMENTATION_VALUES,
                "documentation",
            )

        component.flags = [
            str(item).strip().upper()
            for item in raw.get("flags", component.flags)
            if str(item).strip()
        ]
        component.note = str(raw.get("note", component.note)).strip()

        if any(
            field in raw
            for field in ("implementation", "verification", "documentation")
        ):
            component.source = "MANUAL"

        if component.flags:
            component.signals.extend(component.flags)


def _planned_components(config: dict) -> dict[str, Component]:
    result: dict[str, Component] = {}

    for key, raw in config.get("planned", {}).items():
        key = str(key)
        result[key] = Component(
            key=key,
            title=str(raw.get("title", key)),
            path=str(raw.get("path", "—")),
            implementation="PLANNED",
            verification="UNVERIFIED",
            documentation=_validate_status(
                raw.get("documentation", "MISSING"),
                DOCUMENTATION_VALUES,
                "documentation",
            ),
            note=str(raw.get("note", "")).strip(),
            source="MANUAL",
        )

    return result


def _discover_added_files(
    baseline_files: set[str],
    current_files: set[str],
    new_directories: list[str],
) -> list[str]:
    """Return added files not hidden by a newly introduced directory."""
    added = current_files - baseline_files
    return sorted(
        path for path in added
        if not _under_any(path, new_directories)
    )


def _discover_deleted_files(
    baseline_files: set[str],
    current_files: set[str],
) -> list[str]:
    return sorted(baseline_files - current_files)


def _source_label(component: Component) -> str:
    parts = [component.source]
    if component.new and "NEW" not in component.source:
        parts.append("NEW")
    return " + ".join(parts)


def _signals_text(component: Component) -> str:
    """Return compact flags and automatically generated signals."""
    values = list(dict.fromkeys(component.signals))
    return "; ".join(values) if values else "—"


def _build_markdown(
    config: dict,
    components: dict[str, Component],
    new_directories: list[str],
    added_files: list[str],
    deleted_files: list[str],
    changed_paths: set[str],
    current_head: str,
) -> str:
    baseline = str(config["baseline_commit"])
    attention = [
        component for component in components.values()
        if (
            component.implementation != "READY"
            or component.verification == "UNVERIFIED"
            or component.documentation != "CURRENT"
            or component.flags
            or component.changed
            or component.new
        )
    ]

    ready_count = sum(
        component.implementation == "READY"
        for component in components.values()
    )
    tested_count = sum(
        component.verification in {"TESTED", "PRODUCT VERIFIED"}
        for component in components.values()
    )
    current_docs_count = sum(
        component.documentation == "CURRENT"
        for component in components.values()
    )

    lines = [
        "## Автоматическая сводка",
        "",
        f"- Базовая точка оценки: `{baseline}`",
        f"- Текущий HEAD: `{current_head}`",
        f"- Компонентов в сводке: **{len(components)}**",
        f"- Готовы: **{ready_count}/{len(components)}**",
        f"- Подтверждены тестами или продуктом: **{tested_count}/{len(components)}**",
        f"- Документация актуальна: **{current_docs_count}/{len(components)}**",
        f"- Требуют внимания: **{len(attention)}**",
        "",
        "| Компонент | Реализация | Проверка | Документация | Источник | Сигналы |",
        "|---|---|---|---|---|---|",
    ]

    for component in sorted(
        components.values(),
        key=lambda item: item.title.casefold(),
    ):
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{component.title}`",
                    f"`{component.implementation}`",
                    f"`{component.verification}`",
                    f"`{component.documentation}`",
                    f"`{_source_label(component)}`",
                    _signals_text(component).replace("|", "\\|"),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Обнаруженные изменения",
            "",
        ]
    )

    if not new_directories and not added_files and not deleted_files and not changed_paths:
        lines.append("Изменений относительно базовой точки не обнаружено.")
        return "\n".join(lines) + "\n"

    if new_directories:
        lines.extend(
            [
                "### Новые папки",
                "",
                "Новая папка отображается одной записью; файлы внутри неё отдельно не",
                "перечисляются, пока папка остаётся новой.",
                "",
            ]
        )
        for path in new_directories:
            lines.append(
                f"- `NEW DIRECTORY` — `{path}/` → "
                "`IN PROGRESS` · `UNVERIFIED` · `MISSING`"
            )
        lines.append("")

    if added_files:
        lines.extend(["### Новые файлы в известных папках", ""])
        for path in added_files:
            lines.append(f"- `NEW FILE` — `{path}`")
        lines.append("")

    modified_existing = sorted(
        path for path in changed_paths
        if path not in set(added_files)
        and not _under_any(path, new_directories)
        and path not in set(deleted_files)
    )

    if modified_existing:
        lines.extend(["### Изменённые существующие файлы", ""])
        for path in modified_existing:
            lines.append(f"- `MODIFIED` — `{path}`")
        lines.append("")

    if deleted_files:
        lines.extend(["### Удалённые файлы", ""])
        for path in deleted_files:
            lines.append(f"- `DELETED` — `{path}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def generate_status(app: Sphinx) -> None:
    """Generate the MyST include before Sphinx starts reading documents."""
    source_dir = Path(app.srcdir).resolve()
    project_root = source_dir.parents[1]

    config = _load_config(project_root)
    baseline = str(config["baseline_commit"]).strip()
    source_root = _normalize_path(str(config.get("source_root", "app")))
    ignore = dict(config.get("ignore", {}))

    # Verify the configured baseline exists.
    _run_git(project_root, "rev-parse", "--verify", f"{baseline}^{{commit}}")

    baseline_files = _baseline_files(
        project_root,
        baseline,
        source_root,
        ignore,
    )
    current_files = _current_files(
        project_root,
        source_root,
        ignore,
    )
    changed_paths = _changed_paths(
        project_root,
        baseline,
        source_root,
        ignore,
    )
    new_directories = _minimal_new_directories(
        baseline_files,
        current_files,
        source_root,
    )
    added_files = _discover_added_files(
        baseline_files,
        current_files,
        new_directories,
    )
    deleted_files = _discover_deleted_files(
        baseline_files,
        current_files,
    )

    components = _configured_components(
        project_root,
        config,
        changed_paths | set(added_files) | set(deleted_files),
    )

    auto_components = _top_level_directory_components(
        project_root,
        config,
        baseline_files,
        current_files,
        changed_paths | set(added_files) | set(deleted_files),
        new_directories,
    )
    for key, component in auto_components.items():
        components.setdefault(key, component)

    components.update(_planned_components(config))
    _apply_overrides(components, config)

    # Newly introduced directories absent from manual config must always surface.
    configured_paths = {component.path for component in components.values()}
    for directory in new_directories:
        if directory in configured_paths:
            continue

        key = f"new:{directory}"
        title = PurePosixPath(directory).name
        components[key] = Component(
            key=key,
            title=title,
            path=directory,
            implementation="IN PROGRESS",
            verification="UNVERIFIED",
            documentation="MISSING",
            source="NEW",
            new=True,
            signals=[f"новая папка: {directory}/"],
        )

    current_head = _run_git(project_root, "rev-parse", "--short", "HEAD")

    content = _build_markdown(
        config,
        components,
        new_directories,
        added_files,
        deleted_files,
        changed_paths,
        current_head,
    )

    generated_dir = source_dir / "_generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    output_path = generated_dir / "project_status.inc"
    output_path.write_text(content, encoding="utf-8", newline="\n")


def setup(app: Sphinx) -> dict[str, object]:
    app.connect("builder-inited", generate_status)

    return {
        "version": "1.0",
        "parallel_read_safe": False,
        "parallel_write_safe": True,
    }
