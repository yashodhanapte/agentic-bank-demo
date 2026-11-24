"""Tools the model may request, with input validation done in OUR code.

A JSON schema sent to the model is a request, not a guarantee. The model can still send
wrong types, unexpected fields or odd values, so every call is validated before it runs.
(For bigger schemas, use the `jsonschema` package instead of this small validator.)
"""

import re
from dataclasses import dataclass
from typing import Any, Callable

from .errors import ToolInputError

_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict
    func: Callable[..., Any]

    def to_api(self) -> dict:
        """The description we send to the model. It contains no code."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def validate(self, inputs: Any) -> dict:
        """Return cleaned inputs, or raise ToolInputError. Messages never include values."""
        if not isinstance(inputs, dict):
            raise ToolInputError("input must be an object")

        properties = self.input_schema.get("properties", {})
        for key in self.input_schema.get("required", []):
            if key not in inputs:
                raise ToolInputError(f"missing required field: {key}")

        clean = {}
        for key, value in inputs.items():
            if key not in properties:
                raise ToolInputError(f"unexpected field: {key}")
            spec = properties[key]
            kind = spec.get("type")
            expected = _TYPES.get(kind)
            if expected is None:
                raise ToolInputError(f"unsupported type for field: {key}")
            # In Python, True is an int, so reject booleans where a number is expected.
            if isinstance(value, bool) and kind != "boolean":
                raise ToolInputError(f"{key} must be {kind}")
            if not isinstance(value, expected):
                raise ToolInputError(f"{key} must be {kind}")
            if kind in ("integer", "number"):
                if "minimum" in spec and value < spec["minimum"]:
                    raise ToolInputError(f"{key} is out of range")
                if "maximum" in spec and value > spec["maximum"]:
                    raise ToolInputError(f"{key} is out of range")
            if isinstance(value, str):
                value = value.strip()
                if len(value) < spec.get("minLength", 1):
                    raise ToolInputError(f"{key} is too short")
                if len(value) > spec.get("maxLength", 200):
                    raise ToolInputError(f"{key} is too long")
                pattern = spec.get("pattern")
                if pattern and not re.fullmatch(pattern, value):
                    raise ToolInputError(f"{key} has an invalid format")
            if "enum" in spec and value not in spec["enum"]:
                raise ToolInputError(f"{key} is not an allowed value")
            clean[key] = value
        return clean
