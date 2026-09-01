"""metagent — class-based self-evolving LLM agent harness.

Minimal interface::

    import metagent

    class ExampleAgent(metagent.Evolve):
        pass

    if __name__ == "__main__":
        agent = ExampleAgent(metagent.parse_flags())
        agent.run()

Any method that is not implemented on the subclass is synthesized by an
LLM the first time it is called. Once it has been seen to work, the
harness tries to rewrite it into deterministic Python that no longer
calls the model. The agent is supposed to automate itself away.
"""

from metagent.evolve import Evolve
from metagent.flags import Flags, parse_flags
from metagent.llm import LLM, DummyLLM, OpenAICompatLLM

__all__ = [
    "Evolve",
    "Flags",
    "parse_flags",
    "LLM",
    "DummyLLM",
    "OpenAICompatLLM",
]
__version__ = "0.1.0"
