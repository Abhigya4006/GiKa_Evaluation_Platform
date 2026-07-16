
from __future__ import annotations

from typing import Any, Callable

try:  # pragma: no cover - exercised implicitly by import
    from pydantic import BaseModel, Field, field_validator, model_validator  # type: ignore

    PYDANTIC_AVAILABLE = True

except Exception:  # noqa: BLE001 - broad on purpose; any import failure -> shim
    PYDANTIC_AVAILABLE = False

    import dataclasses
    from typing import get_type_hints

    _MISSING = object()

    class FieldInfo:
        __slots__ = ("default", "default_factory")

        def __init__(self, default: Any = _MISSING, default_factory: Any = None):
            self.default = default
            self.default_factory = default_factory

    def Field(default: Any = _MISSING, *, default_factory: Any = None):  # noqa: N802
        return FieldInfo(default=default, default_factory=default_factory)

    def field_validator(*_fields: str, **_kwargs: Any):  # noqa: N802
        def deco(fn: Callable) -> Callable:
            return staticmethod(fn)
        return deco

    def model_validator(*_args: Any, **_kwargs: Any):  # noqa: N802
        def deco(fn: Callable) -> Callable:
            fn.__is_model_validator__ = True  # type: ignore[attr-defined]
            return fn
        return deco

    class BaseModel:

        model_config: dict = {}

        def __init__(self, **data: Any):
            hints = self._collect_hints()
            for name in hints:
                if name in data:
                    setattr(self, name, data[name])
                    continue
                default = getattr(type(self), name, _MISSING)
                if isinstance(default, FieldInfo):
                    if default.default_factory is not None:
                        setattr(self, name, default.default_factory())
                    elif default.default is not _MISSING:
                        setattr(self, name, default.default)
                    else:
                        setattr(self, name, None)
                elif default is _MISSING:
                    # Required field with no default provided.
                    setattr(self, name, None)
                else:
                    setattr(self, name, default)
            # Keep any extra keys if model_config allows extra.
            if type(self).model_config.get("extra") == "allow":
                for k, v in data.items():
                    if k not in hints:
                        setattr(self, k, v)
            self._run_validators()

        @classmethod
        def _collect_hints(cls) -> dict:
            hints: dict = {}
            for klass in reversed(cls.__mro__):
                if klass in (object, BaseModel):
                    continue
                try:
                    hints.update(get_type_hints(klass))
                except Exception:  # noqa: BLE001
                    ann = getattr(klass, "__annotations__", {})
                    hints.update(ann)
            # model_config is configuration, not a data field.
            hints.pop("model_config", None)
            return hints

        def _run_validators(self) -> None:
            for name in dir(type(self)):
                attr = getattr(type(self), name, None)
                if callable(attr) and getattr(attr, "__is_model_validator__", False):
                    attr(self)

        @classmethod
        def model_validate(cls, data: Any) -> "BaseModel":
            if isinstance(data, cls):
                return data
            if isinstance(data, dict):
                return cls(**data)
            raise TypeError(f"Cannot validate {type(data)} into {cls.__name__}")

        def model_dump(self, *args: Any, **kwargs: Any) -> dict:
            out: dict = {}
            for name in self._collect_hints():
                val = getattr(self, name, None)
                out[name] = _dump(val)
            # include extras
            if type(self).model_config.get("extra") == "allow":
                for k, v in self.__dict__.items():
                    if k not in out:
                        out[k] = _dump(v)
            return out

    def _dump(val: Any) -> Any:
        if isinstance(val, BaseModel):
            return val.model_dump()
        if isinstance(val, list):
            return [_dump(v) for v in val]
        if isinstance(val, dict):
            return {k: _dump(v) for k, v in val.items()}
        return val

    _ = dataclasses  # keep import referenced
