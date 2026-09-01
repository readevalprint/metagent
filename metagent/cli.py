"""``python -m metagent`` / the ``metagent`` console script."""

from __future__ import annotations

from metagent.evolve import Evolve
from metagent.flags import parse_flags


def main(argv: list[str] | None = None) -> int:
    flags = parse_flags(argv)
    agent = Evolve(flags)
    result = agent.run()
    if result is not None and not flags.quiet:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
