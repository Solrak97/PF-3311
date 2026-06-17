from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@lru_cache(maxsize=1)
def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=()),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_template(name: str, **context: Any) -> str:
    template_name = name if name.endswith(".jinja2") else f"{name}.jinja2"
    return _env().get_template(template_name).render(**context).strip()


def render_string(template: str, **context: Any) -> str:
    return _env().from_string(template).render(**context).strip()
