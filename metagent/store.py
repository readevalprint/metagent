"""Persist crystallized skills and the prompt_log genome."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Genome:
    """On-disk memory of every generated skill version."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.skills_dir = self.root / "skills"
        self.log_path = self.root / "prompt_log.json"
        self.traces_path = self.root / "traces.json"
        self.specs_path = self.root / "specs.json"
        self.types_dir = self.root / "types"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.types_dir.mkdir(parents=True, exist_ok=True)

    def load_log(self) -> dict[str, list[dict[str, Any]]]:
        if not self.log_path.exists():
            return {}
        try:
            data = json.loads(self.log_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def save_log(self, log: dict[str, list[dict[str, Any]]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(json.dumps(log, indent=2, default=str) + "\n", encoding="utf-8")

    def skill_path(self, name: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
        return self.skills_dir / f"{safe}.py"

    def load_skill(self, name: str) -> str | None:
        path = self.skill_path(name)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def save_skill(self, name: str, source: str) -> Path:
        path = self.skill_path(name)
        header = (
            f"# metagent-skill: {name}\n"
            f"# crystallized: {utcnow()}\n"
            f"# This file was generated. Edit it; the harness will reuse it.\n\n"
        )
        body = source if source.lstrip().startswith("def ") else source
        if not body.startswith("# metagent-skill:"):
            body = header + body.rstrip() + "\n"
        path.write_text(body, encoding="utf-8")
        return path

    def load_traces(self) -> dict[str, list[dict[str, Any]]]:
        if not self.traces_path.exists():
            return {}
        try:
            data = json.loads(self.traces_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def save_traces(self, traces: dict[str, list[dict[str, Any]]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.traces_path.write_text(json.dumps(traces, indent=2, default=str) + "\n", encoding="utf-8")

    def load_specs(self) -> dict[str, Any]:
        if not self.specs_path.exists():
            return {}
        try:
            data = json.loads(self.specs_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def save_specs(self, specs: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.specs_path.write_text(json.dumps(specs, indent=2, default=str) + "\n", encoding="utf-8")

    def type_path(self, name: str) -> Path:
        safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
        return self.types_dir / f"{safe}.py"

    def list_types(self) -> list[str]:
        return [p.stem for p in sorted(self.types_dir.glob("*.py"))]

    def load_type(self, name: str) -> str | None:
        path = self.type_path(name)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    def save_type(self, name: str, source: str) -> Path:
        path = self.type_path(name)
        header = (
            f"# metagent-type: {name}\n"
            f"# crystallized: {utcnow()}\n"
            f"# Reloaded on the next Evolve boot.\n\n"
        )
        body = source if "class " in source or "def " in source else source
        if not body.lstrip().startswith("# metagent-type:"):
            body = header + body.rstrip() + "\n"
        path.write_text(body, encoding="utf-8")
        return path

    def list_skills(self) -> list[str]:
        names = []
        for path in sorted(self.skills_dir.glob("*.py")):
            names.append(path.stem)
        return names
