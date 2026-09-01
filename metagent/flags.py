"""CLI / constructor flags for Evolve."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping


@dataclass
class Flags:
    """Normalized constructor argument for ``Evolve``.

    Accepts this object, a dict, an argparse Namespace, or raw argv.
    """

    goal: str | None = None
    model: str = field(default_factory=lambda: os.environ.get("METAGENT_MODEL", "gpt-4o-mini"))
    base_url: str | None = field(default_factory=lambda: os.environ.get("METAGENT_BASE_URL"))
    api_key: str | None = field(
        default_factory=lambda: os.environ.get("METAGENT_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("XAI_API_KEY")
    )
    workspace: Path = field(default_factory=lambda: Path.cwd())
    evolve_dir: Path | None = None
    max_evolutions: int = 3
    max_steps: int = 8
    dry_run: bool = False
    persist: bool = True
    verbose: bool = False
    dummy: bool = False
    quiet: bool = False
    automate: bool = True
    min_traces: int = 2

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace).resolve()
        if self.evolve_dir is None:
            self.evolve_dir = self.workspace / ".metagent"
        else:
            self.evolve_dir = Path(self.evolve_dir).resolve()

    @property
    def genome_dir(self) -> Path:
        return self.evolve_dir / "skills"

    @property
    def log_path(self) -> Path:
        return self.evolve_dir / "prompt_log.json"


def parse_flags(argv: list[str] | None = None) -> Flags:
    """Parse CLI flags. Safe to call from ``if __name__ == '__main__'``."""
    p = argparse.ArgumentParser(
        prog="metagent",
        description="Self-evolving class-based LLM agent harness.",
    )
    p.add_argument("goal", nargs="?", default=None, help="Task the agent should solve")
    p.add_argument("--model", default=os.environ.get("METAGENT_MODEL", "gpt-4o-mini"))
    p.add_argument("--base-url", default=os.environ.get("METAGENT_BASE_URL"))
    p.add_argument("--api-key", default=None)
    p.add_argument("--workspace", default=".")
    p.add_argument("--evolve-dir", default=None)
    p.add_argument("--max-evolutions", type=int, default=3)
    p.add_argument("--max-steps", type=int, default=8)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-persist", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    p.add_argument("--dummy", action="store_true", help="Use the offline DummyLLM backend")
    p.add_argument("--quiet", "-q", action="store_true")
    p.add_argument("--no-automate", action="store_true", help="Do not rewrite prompt-using skills into code")
    p.add_argument("--min-traces", type=int, default=2, help="Observed calls before a compact rewrite")
    ns = p.parse_args(argv)
    return Flags(
        goal=ns.goal,
        model=ns.model,
        base_url=ns.base_url,
        api_key=ns.api_key,
        workspace=Path(ns.workspace),
        evolve_dir=Path(ns.evolve_dir) if ns.evolve_dir else None,
        max_evolutions=ns.max_evolutions,
        max_steps=ns.max_steps,
        dry_run=ns.dry_run,
        persist=not ns.no_persist,
        verbose=ns.verbose,
        dummy=ns.dummy,
        quiet=ns.quiet,
        automate=not ns.no_automate,
        min_traces=ns.min_traces,
    )


def normalize_flags(raw: Any = None, extra: Mapping[str, Any] | None = None) -> Flags:
    """Coerce constructor input into a Flags instance."""
    extra = dict(extra or {})
    if raw is None:
        flags = Flags()
    elif isinstance(raw, Flags):
        flags = raw
    elif isinstance(raw, Mapping):
        allowed = {f.name for f in fields(Flags)}
        flags = Flags(**{k: v for k, v in raw.items() if k in allowed})
    elif hasattr(raw, "__dict__") and not isinstance(raw, type):
        allowed = {f.name for f in fields(Flags)}
        payload = {k: v for k, v in vars(raw).items() if k in allowed}
        flags = Flags(**payload)
    elif isinstance(raw, (list, tuple)):
        flags = parse_flags(list(raw))
    else:
        raise TypeError(f"Cannot coerce flags from {type(raw).__name__}")

    if extra:
        allowed = {f.name for f in fields(Flags)}
        for key, value in extra.items():
            if key in allowed:
                setattr(flags, key, value)
        flags.__post_init__()
    return flags
