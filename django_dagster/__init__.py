from typing import Any

__all__ = [
    "DagsterJob",
    "DagsterRun",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .models import DagsterJob, DagsterRun

        _exports = {"DagsterJob": DagsterJob, "DagsterRun": DagsterRun}
        return _exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
