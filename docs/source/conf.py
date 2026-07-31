import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "_ext"))
"""Конфигурация документации DigitalDiaryApp."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


project = "DigitalDiaryApp"
author = "DigitalDiaryApp team"
copyright = "2026, DigitalDiaryApp team"

version = "baseline"
release = "baseline"

language = "ru"
root_doc = "index"

extensions = [
    "auto_navigation",
    "myst_parser",
    "sphinx_design",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.coverage",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

templates_path = ["_templates"]
exclude_patterns = []

autosummary_generate = True

autodoc_default_options = {
    "members": True,
    "show-inheritance": True,
    "member-order": "bysource",
    "exclude-members": "model_config, metadata",
}

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_attr_annotations = True

autosectionlabel_prefix_document = True
autosectionlabel_maxdepth = 2

# На первом этапе не загружаем внешние inventory-файлы.
# Это обеспечивает сборку документации без доступа к интернету.
intersphinx_mapping = {}

html_theme = "pydata_sphinx_theme"
html_title = "DigitalDiaryApp"
html_static_path = ["_static"]
html_css_files = ["custom.css"]

html_theme_options = {
    "navbar_start": ["navbar-logo"],
    "navbar_center": ["navbar-sections"],
    "navbar_end": ["search-button", "theme-switcher"],
    "show_nav_level": 2,
    "navigation_depth": 4,
    "show_toc_level": 2,
    "collapse_navigation": False,
    "navbar_align": "left",
    "show_prev_next": False,
    "secondary_sidebar_items": ["page-toc"],
}

html_sidebars = {
     "index": [],
     "**": ["sidebar-nav-bs"],
}

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "fieldlist",
    "tasklist",
]

# Показывать фрагменты текста в результатах поиска.
html_show_search_summary = True

# -- Search result location -----------------------------------------------
html_js_files = [
    *globals().get("html_js_files", []),
    "search_result_location.js",
]
html_css_files = [
    *globals().get("html_css_files", []),
    "search_result_location.css",
]
