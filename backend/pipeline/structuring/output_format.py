"""Output instructions for JSON mode, generated from the Pydantic schema so the prompt can never drift from ``Record``.

JSON mode only guarantees valid JSON; it does not enforce a schema. So the prompt has to say exactly which keys to
return, what each one means, and which values are allowed.
"""

import json
import types
from typing import Any, Literal, Union, get_args, get_origin

from pydantic import BaseModel

_INDENT = "  "


def _describe_type(annotation: Any) -> str:
    """A short, plain description of a field's type."""
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, types.UnionType):
        return _describe_type(next(a for a in args if a is not type(None)))
    if origin is Literal:
        return "one of " + ", ".join(json.dumps(a) for a in args)
    if origin is list:
        return f"list of {_describe_type(args[0])}s"
    return {str: "string", int: "integer", bool: "true or false", float: "number"}.get(
        annotation, "value"
    )


def _nested_model(annotation: Any) -> type[BaseModel] | None:
    """The model behind ``Model | None``, if the field is a nested object."""
    candidates = [
        a
        for a in get_args(annotation)
        if isinstance(a, type) and issubclass(a, BaseModel)
    ]
    return (
        candidates[0]
        if candidates
        else (
            annotation
            if isinstance(annotation, type) and issubclass(annotation, BaseModel)
            else None
        )
    )


def _skeleton(model: type[BaseModel]) -> dict[str, Any]:
    """The expected JSON with every value null."""
    return {
        name: (
            _skeleton(nested) if (nested := _nested_model(field.annotation)) else None
        )
        for name, field in model.model_fields.items()
    }


def _field_lines(model: type[BaseModel], indent: int = 0, described: dict[type[BaseModel], str] | None = None) -> list[str]:
    """One line per key. A nested object used twice is described once; the second use points back to the first."""
    described = {} if described is None else described
    lines: list[str] = []
    for name, field in model.model_fields.items():
        nested = _nested_model(field.annotation)
        kind = "object" if nested else _describe_type(field.annotation)
        line = f"{_INDENT * indent}- {name} ({kind}): {field.description or ''}".rstrip()
        if nested and nested in described:
            lines.append(f"{line} Same keys and meanings as {described[nested]}.")
            continue
        lines.append(line)
        if nested:
            described[nested] = name
            lines += _field_lines(nested, indent + 1, described)
    return lines


def format_instructions(model: type[BaseModel]) -> str:
    """Instructions that make a chat model answer with exactly the JSON of ``model``."""
    return (
        "Output format\n"
        "Answer with one JSON object and nothing else: no text before or after it, no markdown, no code fence.\n"
        'The top-level keys are the field names themselves. Do not wrap them in "properties", "description" or any '
        "other key, and do not repeat the schema.\n"
        "Every key below must be present. Use null for a value that is missing, unreadable or not visible in the text.\n\n"
        f"JSON to fill (all values shown as null):\n{json.dumps(_skeleton(model), indent=2)}\n\n"
        f"Meaning of each key:\n" + "\n".join(_field_lines(model))
    )
