"""Automatic section navigation for the DigitalDiaryApp documentation.

The ``autotoctree`` directive discovers direct child documents of the
current section and creates a normal Sphinx toctree only when entries exist.

Supported discoveries:
- ``section/page.md`` or ``section/page.rst`` -> ``page``
- ``section/topic/index.md`` or ``.rst`` -> ``topic/index``

Key pages can be placed first with the ``:order:`` option. Remaining pages
are appended alphabetically.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from docutils.parsers.rst import directives
from docutils.statemachine import StringList
from sphinx.application import Sphinx
from sphinx.directives.other import TocTree
from sphinx.environment import BuildEnvironment
from sphinx.errors import ExtensionError


def _source_suffixes(source_suffix: object) -> tuple[str, ...]:
    """Return configured source suffixes in a normalized form."""
    if isinstance(source_suffix, str):
        return (source_suffix,)

    if isinstance(source_suffix, dict):
        return tuple(str(value) for value in source_suffix.keys())

    if isinstance(source_suffix, Iterable):
        return tuple(str(value) for value in source_suffix)

    raise ExtensionError("Unsupported source_suffix configuration.")


def _parse_names(value: str | None) -> list[str]:
    """Parse a comma-separated directive option."""
    if not value:
        return []

    return [item.strip() for item in value.split(",") if item.strip()]


class AutoTocTree(TocTree):
    """Create a toctree from direct child documents without empty-glob warnings."""

    has_content = False
    option_spec = dict(TocTree.option_spec)
    option_spec.update(
        {
            "order": directives.unchanged,
            "exclude": directives.unchanged,
        }
    )

    def run(self):  # type: ignore[override]
        env = self.state.document.settings.env
        source_root = Path(env.srcdir)
        current_doc = Path(env.docname)
        section_doc_dir = current_doc.parent
        section_fs_dir = source_root / section_doc_dir

        if not section_fs_dir.is_dir():
            raise ExtensionError(
                f"Section directory does not exist: {section_fs_dir}"
            )

        suffixes = _source_suffixes(env.config.source_suffix)
        excluded = set(_parse_names(self.options.pop("exclude", None)))
        preferred_order = _parse_names(self.options.pop("order", None))

        discovered: dict[str, Path] = {}

        for child in sorted(
            section_fs_dir.iterdir(),
            key=lambda item: item.name.casefold(),
        ):
            if child.name.startswith(("_", ".")):
                continue

            entry: str | None = None

            if child.is_file() and child.suffix in suffixes:
                if child.stem == "index":
                    continue
                entry = child.stem

            if child.is_dir():
                for suffix in suffixes:
                    nested_index = child / f"index{suffix}"
                    if nested_index.is_file():
                        entry = f"{child.name}/index"
                        break

            if entry is None or entry in excluded:
                continue

            if entry in discovered:
                raise ExtensionError(
                    "Several source files resolve to the same navigation "
                    f"entry '{entry}': {discovered[entry]} and {child}"
                )

            discovered[entry] = child

        entries: list[str] = []

        for entry in preferred_order:
            if entry in discovered and entry not in entries:
                entries.append(entry)

        remaining = sorted(
            (entry for entry in discovered if entry not in entries),
            key=str.casefold,
        )
        entries.extend(remaining)

        if not entries:
            return []

        source_name = self.state.document.current_source or str(section_fs_dir)
        self.content = StringList(entries, source=source_name)

        return super().run()


def _mark_section_indexes_outdated(
    app: Sphinx,
    env: BuildEnvironment,
    added: set[str],
    changed: set[str],
    removed: set[str],
) -> list[str]:
    """Re-read section indexes when source documents are added or removed."""
    del app, changed

    if not added and not removed:
        return []

    all_docs = set(env.found_docs) | set(added)
    return sorted(
        docname
        for docname in all_docs
        if docname != "index" and docname.endswith("/index")
    )


def setup(app: Sphinx) -> dict[str, object]:
    app.add_directive("autotoctree", AutoTocTree)
    app.connect("env-get-outdated", _mark_section_indexes_outdated)

    return {
        "version": "1.0",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
