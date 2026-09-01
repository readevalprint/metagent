# metagent

Class-based LLM agent harness. Subclass `Evolve`. The agent is supposed to automate itself away: missing methods are written by the model, then rewritten into ordinary Python the moment there is enough evidence that the work was a rule, not a judgment.

```python
import metagent

class ExampleAgent(metagent.Evolve):
    pass

if __name__ == "__main__":
    cli_flags = metagent.parse_flags()
    agent = ExampleAgent(cli_flags)
    agent.run()
```

See `metagent-design-handoff.md` for the full design spec and philosophy.

## Install

```
pip install -e .
python -m pytest tests/test_evolve.py
python examples/example_agent.py "topic" --dummy -v
```
