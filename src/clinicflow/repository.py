"""Atomic JSON persistence for ClinicFlow state."""

from __future__ import annotations

import json
import os
from contextlib import suppress
from pathlib import Path

from .models import DomainError
from .service import ClinicFlow


class PersistenceError(RuntimeError):
    """Raised when a durable snapshot cannot be loaded or stored."""


class ClinicFlowRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> ClinicFlow:
        if not self.path.exists():
            return ClinicFlow()
        try:
            raw = self.path.read_text(encoding="utf-8")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise DomainError("clinic snapshot root must be an object")
            return ClinicFlow.from_dict(value)
        except (OSError, json.JSONDecodeError, DomainError) as error:
            raise PersistenceError(f"cannot load {self.path}: {error}") from error

    def save(self, clinic: ClinicFlow) -> None:
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(clinic.to_dict(), indent=2, sort_keys=True) + "\n"
            with temporary.open("w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except OSError as error:
            with suppress(OSError):
                temporary.unlink(missing_ok=True)
            raise PersistenceError(f"cannot save {self.path}: {error}") from error
