from __future__ import annotations

import json
from functools import lru_cache

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

import settings


@lru_cache(maxsize=None)
def _registry() -> Registry:
    resources = []
    for path in settings.SHARED_SCHEMA_DIR.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        res = Resource.from_contents(schema, default_specification=DRAFT202012)
        resources += [(path.name, res), (schema["$id"], res)]
    return Registry().with_resources(resources)


@lru_cache(maxsize=None)
def validator(name: str) -> Draft202012Validator:
    path = settings.SHARED_SCHEMA_DIR / f"{name}.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker(), registry=_registry())


def errors(name: str, data: dict) -> list[str]:
    """Readable validation errors, empty when the document is valid."""
    out = []
    for err in sorted(validator(name).iter_errors(data), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in err.path) or "(root)"
        out.append(f"{where}: {err.message}")
    return out
