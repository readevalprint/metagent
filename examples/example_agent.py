"""Minimal interface from the design sketch.

    python examples/example_agent.py "summarize this workspace" --dummy
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running the example without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import metagent


class ExampleAgent(metagent.Evolve):
    """Docstring stubs are the first prompt. They get sharpened, then compiled away."""

    def act(self):
        topic = self.flags.goal or "metagent"
        notes = self.research(topic)
        report = self.write_report(notes)
        return report

    def research(self, topic: str):
        """Gather short notes about the topic from the workspace if possible."""
        pass

    def write_report(self, notes):
        """Turn notes into a one-page report string."""
        pass


if __name__ == "__main__":
    cli_flags = metagent.parse_flags()
    agent = ExampleAgent(cli_flags)
    print(agent.run())
