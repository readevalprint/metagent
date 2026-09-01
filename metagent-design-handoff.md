# metagent

## Design Spec and Philosophy

Handoff document for the class-based self-evolving LLM agent harness.

> The agent is not the product. The product is the code the agent leaves behind when it has automated itself away.

Status: working prototype (v0.1.0) · Audience: next implementer · 1 September 2026

Package: `artifacts/metagent` · Superclass: `metagent.Evolve`

## Contents

1. [Why this exists](#1-why-this-exists)
2. [Philosophy](#2-philosophy)
3. [Minimal interface](#3-minimal-interface)
4. [Lifecycle](#4-lifecycle)
5. [Object model](#5-object-model)
6. [Load-bearing constraints](#6-design-constraints-that-are-load-bearing)
7. [Surface available to generated skills](#7-surface-available-to-generated-skills)
8. [Worked example](#8-worked-example)
9. [How to extend this](#9-how-to-extend-this)
10. [Non-goals and open questions](#10-non-goals-and-open-questions)
11. [Handoff notes](#11-handoff-notes)

## 1. Why this exists

Most agent harnesses treat the model as the runtime. Every turn is another prompt. Memory is a transcript. Tools are a menu. The system gets more capable only by becoming more talkative.

metagent inverts that. The model is a bootstrap. The runtime we want is ordinary Python. The harness exists so that a path which has been seen to work can be written down as a function, bound onto an object, persisted to disk, and never paid for again.

The original sketch was a class you subclass and leave empty. Missing methods are not errors. They are vacancies. The first call fills the vacancy with generated code. Later calls should not know an LLM was ever involved.

That idea only becomes a philosophy when it is allowed to continue after the first generation. A function that still calls `self.prompt` is not finished. It is a temporary scaffold. Compact is the second stage: given observed traces, rewrite the scaffold into a rule. Residue is whatever cannot yet be a rule. The agent is done when residue is empty.

### 1.1 One sentence

Spend tokens only until the work can be compiled; then stop.

### 1.2 What this is not

- Not a ReAct framework with a prettier loop. The planner exists only as a default `act()` for empty subclasses.
- Not fine-tuning, weight updates, or a Gödel machine that rewrites its own kernel.
- Not an access-control system. The process is assumed to already run in a sandbox.
- Not a claim that all work can go cold. Open language and genuine judgment stay generative on purpose.

## 2. Philosophy

### 2.1 Automate yourself away

An agent that is still talking after it has seen the same shape of problem twice is wasting the only expensive resource it has. Repetition is evidence that a rule exists. The ethical and economic obligation of the harness is to notice that evidence and act on it.

This is closer to skill compilation than to “self-improving agents” in the popular sense. We are not trying to make the model smarter. We are trying to need the model less. Capability growth is measured as a falling token curve on a stable workload, not as a rising benchmark score.

### 2.2 Hot, cold, residue

Every synthesized method has a temperature.

- **Hot.** The source still calls `self.prompt`, or a live invocation just did. Tokens are still being spent on this name.
- **Cold.** The source is deterministic Python. Further calls are free of the model.
- **Residue.** The set of hot skills. `agent.residue()` is the only honest progress metric.

Temperature is not a moral ranking of tasks. Some tasks should stay hot. Summarizing an unseen document is language. Parsing a known log format is a rule. The compact prompt is explicit: if the work cannot be a rule, return the original function unchanged. Compact must be allowed to fail. A rejected rewrite leaves the skill hot. That is success of a different kind — the harness refused to pretend.

### 2.3 Traces are tests

A compact rewrite is not accepted because it looks cleaner. It is accepted because it reproduces observed `(args → result)` pairs. Those pairs are the acceptance tests. `prompt_log` is the genome of attempts. `traces.json` is the spec the genome must satisfy.

This is why compact is conservative. Two traces are the default minimum. Sixteen are retained. Replay happens against the candidate function with `compacting=True` so the replay does not itself emit new traces or recurse into another compact. If any pair mismatches, the candidate is discarded.

### 2.4 The model writes code, not answers

When a method is missing, the model is not asked for the return value of the user’s call. It is asked for a function that will compute that value from now on. The first execution of that function is a test of the function, not a substitute for it. If the function still delegates to `self.prompt`, the first execution is only a data-collection step toward compact.

### 2.5 Vacancy as interface

The public API is a class with holes in it. Application code is allowed to look like the finished program:

```python
class ExampleAgent(metagent.Evolve):
    def act(self):
        notes = self.research(self.flags.goal)
        return self.write_report(notes)
```

`research` and `write_report` do not exist on the class. That is the point. The source of the program is the call graph the author wished they had. The harness materializes the nodes. This is why `Evolve` is a superclass rather than a function that takes tools. Inheritance is the vacancy mechanism: anything not defined falls through to `__getattr__`.

### 2.6 Sandbox is someone else’s job

Generated skills run as ordinary Python: `import`, `open`, `subprocess`, the network, whatever is installed. Path jail and restricted builtins were removed on purpose. The process is assumed to already live inside an outer sandbox. The harness will not pretend to be a security boundary it cannot honor.

What the harness does refuse is object suicide. Names that would replace `__getattribute__`, `__setattr__`, `__init__`, and similar are blocked. That is integrity of the running object, not permissions on the machine.

## 3. Minimal interface

This is the contract that must keep working. Everything else is allowed to move.

```python
import metagent

class ExampleAgent(metagent.Evolve):
    pass

if __name__ == "__main__":
    cli_flags = metagent.parse_flags()
    agent = ExampleAgent(cli_flags)
    agent.run()
```

### 3.1 Constructor

`Evolve.__init__(flags=None, llm=None, **kwargs)`.

`flags` may be a `Flags` object, a dict, an argparse namespace, a raw argv list, or omitted. Keyword arguments overlay the same fields (`goal=`, `dummy=True`, `persist=False`). `llm=` injects any object that implements `complete(system, user) -> str`.

### 3.2 run, act, solve

- **`run()`.** Template method. Calls `act()`, then `compact()` if automate is on. Subclasses that want the compact sweep should override `act`, not `run`.
- **`act()`.** Default: if `flags.goal` is set, call `solve(goal)`; otherwise do nothing. This is the method to override with a concrete workflow.
- **`solve(goal)`.** Default planner loop. Asks the model for JSON `{op, method, args, kwargs}` or `{op: done|fail}`. Invented method names fall through to synthesis. Prefer existing, especially cold, skills.

### 3.3 prompt

`self.prompt(instruction, payload=None, *, system=None) -> str` is the only generative primitive a skill should use. Every call increments `_prompt_hits`. If it happens while a named skill is on the `_active` stack, that skill is marked hot. Compact exists to drive this number to zero on workloads that turned out to be regular.

### 3.4 residue and compact

- **`residue()`.** Dict of hot skills. Empty means the current genome is fully deterministic for what it has seen.
- **`compact()`.** Attempts a rewrite of every eligible hot skill. Returns the list of names that went cold. Also invoked eagerly after a hot skill collects `min_traces` samples, and again at the end of `run()`.

## 4. Lifecycle

A call to a missing method walks this path. Names in parentheses are the functions that implement the step.

### 4.1 Miss

`__getattr__(name)` fires only for public names. Leading-underscore names raise `AttributeError`. Dunders other than `__call__`, `__str__`, `__repr__`, `__iter__` raise `AttributeError`. Blocked integrity names raise `AttributeError` even if someone calls `Evolve.__getattr__` directly. The returned object is a closure named after the skill; its body is `_evolve_and_call`.

### 4.2 Synthesize

`_request_skill` sends `SYSTEM_PROMPT` + `USER_PROMPT`. The model sees the call shape (repr of small args, type names of large ones), the agent class name, the current goal, up to four historical versions from `prompt_log`, and the last traceback if this is a retry. It must return a function definition named after the skill, with `self` as the first parameter. Markdown fences are stripped. Top-level imports in the reply are kept (`extract_def`).

`max_evolutions` (default 3) is the retry budget for compile failures and runtime exceptions. Each failure is appended to `prompt_log` with `ok=False` and the traceback. The next prompt includes that history. This is how a bad first draft becomes a working second draft without the application noticing.

### 4.3 Compile and bind

`compile_skill` parses the extracted source, inserts a `self` parameter if the model forgot it, and execs it in a namespace that has full builtins plus a `self` binding. The resulting function is wrapped (`_install_skill`) so later calls still record traces and can compact. The wrapper is stored on the instance, so the next attribute lookup never reaches `__getattr__`.

### 4.4 Execute and trace

The function runs. Relative paths in `read_text` / `write_text` / `list_dir` resolve against `flags.workspace`; absolute paths are used as-is. On success, an `(args, kwargs, result)` sample is appended to `_traces[name]`, capped at 16, and written to `traces.json` when persist is on. The source is written to `.metagent/skills/<name>.py`. `prompt_log` records the successful version with temperature hot or cold depending on whether the source calls `self.prompt`.

### 4.5 Compact

If automate is on, the skill is hot, and `len(traces) >= min_traces` (default 2), `_compact_one` runs. It is skipped if a compact was already attempted at this exact trace length, so a rejected rewrite does not hammer the model on every subsequent call. The compact model is shown current source plus traces and asked for a prompt-free rewrite. Acceptance gates, in order:

- The reply extracts to a function.
- `uses_prompt(candidate)` is false. A rewrite that still calls `self.prompt` is rejected even if it would replay.
- The candidate compiles.
- Every stored trace replays with `==` or, failing that, matching `repr`.

On acceptance the cold function is installed, persisted, and logged with `attempt="compact"`. On rejection the hot function stays. Either outcome is progress: we either shed residue or we learned the work is not yet a rule.

### 4.6 Reload

The next process constructs `Evolve`, `Genome` loads `prompt_log` and traces, and every `skills/*.py` file is compiled and installed. If those files are already cold, the process can serve the same call graph with zero model calls. Humans are allowed to edit the skill files. The harness will reuse the edited source.

## 5. Object model

### 5.1 Modules

| Module | Responsibility |
| --- | --- |
| `metagent.evolve` | `Evolve` superclass: lifecycle, `__getattr__`, compact, residue, planner |
| `metagent.flags` | `Flags` dataclass, `parse_flags`, `normalize_flags` |
| `metagent.llm` | LLM protocol, `DummyLLM`, `OpenAICompatLLM`, `build_llm` |
| `metagent.sandbox` | `extract_def`, `compile_skill`, `uses_prompt`, blocked names |
| `metagent.store` | Genome: `prompt_log.json`, `traces.json`, `skills/*.py` |
| `metagent.cli` | `python -m metagent` entry |

### 5.2 Flags

| Field | Default | Meaning |
| --- | --- | --- |
| `goal` | `None` | Task for default `act()` / `solve()` |
| `model` | `METAGENT_MODEL` or `gpt-4o-mini` | Chat-completions model id |
| `base_url` | `METAGENT_BASE_URL` | OpenAI-compatible gateway |
| `api_key` | `METAGENT_API_KEY` / `OPENAI_API_KEY` / `XAI_API_KEY` | Bearer token |
| `workspace` | cwd | Root for relative paths and default `evolve_dir` |
| `evolve_dir` | `<workspace>/.metagent` | Genome root |
| `max_evolutions` | `3` | Synthesize retries per missing method |
| `max_steps` | `8` | Planner steps in `solve()` |
| `dry_run` | `False` | Return generated source, do not exec |
| `persist` | `True` | Write genome to disk |
| `verbose` | `False` | Log prompt previews and compact promotions |
| `dummy` | `False` | Force `DummyLLM` |
| `quiet` | `False` | Suppress default printing |
| `automate` | `True` | Allow compact rewrites |
| `min_traces` | `2` | Observed calls before a compact attempt |

CLI mirrors the fields: positional `goal`, `--no-persist`, `--no-automate`, `--min-traces`, `--dummy`, `--dry-run`, and so on. `python -m metagent` constructs `Evolve` itself rather than a subclass.

### 5.3 LLM backends

`LLM` is an ABC with `complete(system, user) -> str`. `OpenAICompatLLM` posts to `{base_url}/chat/completions`. `DummyLLM` is selected when `dummy=True`, model is `dummy` / `none` / `offline`, or no API key is present. `DummyLLM` returns a stub function for synthesis prompts and `{"op": "done", "result": "dummy-complete"}` for the planner, so the wiring can be tested offline.

Any other backend is an injected `llm=`. Tests use a `ScriptedLLM` that pops canned replies. That is the expected way to unit-test evolution without a network.

### 5.4 Genome on disk

```
.metagent/
  prompt_log.json     # name -> [{ts, attempt, ok, error, code, temperature}]
  traces.json         # name -> [{args, kwargs, result, ts}]
  skills/
    research.py       # crystallized source, editable by hand
    write_report.py
```

Skill files are prefixed with a short header (`metagent-skill`, crystallized timestamp). `extract_def` / `compile_skill` ignore the comments. If persist is false, the process is amnesiac: synthesis still works, compact still works in memory, nothing is reloaded next time.

## 6. Design constraints that are load-bearing

### 6.1 Do not generate the answer

The synthesize prompt must keep asking for a function. If it ever starts asking for the value of this call, the harness collapses into a chat wrapper and compact has nothing to compile. Reviewers should treat a change that makes `__getattr__` return a model string as a spec violation.

### 6.2 Compact is allowed to fail

A compact that always succeeds will invent fake rules. Replay against traces is the whole of the safety story for promotion. Do not weaken `_same()` into “close enough.” Do not accept a rewrite that still contains `self.prompt`. Do not compact during replay.

### 6.3 Override act, not run

`run()` is the wrapper that guarantees a compact sweep at the end of a job. Eager compact on hot skills covers most of the same ground, so a subclass that overrides `run()` is not doomed. It is still the wrong default. Documented interface: put workflow in `act()`.

### 6.4 Instance bind, not class monkeypatch

Generated functions are set on the instance. Two agents of the same class can carry different genomes. Class-level mutation would leak skills across unrelated tasks and make tests lie. Persistence across processes is the job of `skills/*.py`, not of mutating `ExampleAgent.__dict__`.

### 6.5 Recursion guards

`_evolving` prevents a skill from synthesizing itself while it is already synthesizing. `_compacting` prevents trace recording and nested compact during replay. `_compact_at[name] = len(traces)` prevents a failed compact from retrying until a new sample arrives. Depth of synthesis-calling-synthesis is bounded only by this and by the model not inventing infinite graphs; a hard generation-depth cap is an open item, not current code.

### 6.6 Dunders

`__call__` is defined on the class and means `run()`, with a string argument treated as goal. `__repr__` reports cold and hot skill lists. `__str__`, `__repr__`, and `__iter__` are in the synthesizable set if missing, but `__repr__` is already defined. Integrity dunders are never synthesized.

## 7. Surface available to generated skills

A generated function is ordinary Python with a `self`. It may import. It should prefer the harness surface when the alternative is reimplementing path joins against workspace.

| Name | Role |
| --- | --- |
| `self.prompt(instruction, payload)` | Only generative primitive. Marks the caller hot. |
| `self.read_text(path)` | Read UTF-8. Relative paths join workspace. |
| `self.write_text(path, text)` | Write UTF-8, creating parents. |
| `self.list_dir(path=".")` | Sorted names in a directory. |
| `self.workspace` | `pathlib.Path`, `flags.workspace` |
| `self.flags` | Normalized `Flags` |
| `self.prompt_log` | Genome of prior versions |
| `self.residue()` | Currently hot skills |
| `self.compact()` | Force a compact sweep |

The synthesize prompt tells the model to call `self.prompt` only when the work cannot be compiled. The compact prompt tells it to stop calling `self.prompt` entirely. Those two sentences are the policy. The code only enforces the second, via `uses_prompt()` on the candidate.

## 8. Worked example

An application calls `agent.parity(2)` and later `agent.parity(3)`. Neither method exists.

- First miss: the model emits `def parity(self, n): return self.prompt('even or odd', n)`. It compiles. The live prompt returns `"even"`. Temperature is hot. One trace is stored. Compact waits (`min_traces=2`).
- Second call hits the installed wrapper, not `__getattr__`. The live prompt returns `"odd"`. Two traces now exist. Compact asks for a prompt-free rewrite.
- Candidate: `def parity(self, n): return 'even' if n % 2 == 0 else 'odd'`. `uses_prompt` is false. Replay of `(2 → even)` and `(3 → odd)` succeeds. The wrapper is replaced. Temperature is cold.
- `parity(4)` and `parity(7)` do not touch the model. `residue()` no longer lists `parity`. `skills/parity.py` on disk is the rule.

If the candidate had kept `self.prompt`, compact would reject it and `parity` would stay hot. That is the correct outcome for a task that is still language.

## 9. How to extend this

### 9.1 A domain agent

Subclass `Evolve`. Put the workflow you wish you had in `act()`. Leave the steps unimplemented. Pass a real LLM. Run until residue shrinks. Commit `.metagent/skills/` if the cold code is the artifact you want to keep. Treat those files as source, not cache: review them, edit them, delete them if they encoded the wrong rule.

### 9.2 A new backend

Implement `complete(system, user) -> str`. Inject via `Evolve(..., llm=...)`. Do not add SDK-specific branches to `evolve.py`.

### 9.3 A new primitive

Add a real method on `Evolve`. Generated code will discover it from the synthesize prompt only if you also mention it there. Methods that start with `_` will not be synthesized and will not be callable via vacancy; that is the private namespace of the harness.

### 9.4 Tests

`tests/test_evolve.py` is the spec in executable form: synthesis, crystallization, reload without LLM, retry on bad source, retry on runtime error, blocked dunders, normal-Python imports inside a skill, `dry_run`, planner dummy path, cold-not-in-residue, compact promotion, compact rejection of a still-hot rewrite. Add a test when you change a gate. Do not test against a live model in the default suite.

## 10. Non-goals and open questions

### 10.1 Non-goals

- In-process security. No restricted builtins, no path jail, no seccomp. Outer sandbox or do not run untrusted goals.
- Multi-agent orchestration, tool registries, MCP, browser drivers. Those can be libraries that generated skills import. They are not the harness.
- Persistent identity across hosts beyond the `evolve_dir` folder.
- Guaranteeing that compact finds the true function. It finds a function that fits the traces it has. That is induction, not proof.

### 10.2 Open questions

- Hard cap on nested synthesis depth if a generated skill calls three missing names that each call three more.
- Whether traces should hash large objects instead of dropping them. `_is_recordable` currently requires json-ability via `default=str`, so most values record; replay of un-equal-but-equivalent objects can fail `_same()`.
- Whether cold skills should ever be re-heated on distribution shift. Today a cold skill is trusted until it raises. A mismatch against a new implicit spec is silent.
- Whether the planner (`solve`) should itself go cold — a compiled policy over known method names — or remain residue by definition.
- Promotion of instance skills onto the subclass source tree, so the human repository absorbs the genome instead of only `.metagent/`.
- Cost accounting: `residue()` names the leftover skills but does not yet report tokens per skill over time, which is the actual “automated away” chart.

## 11. Handoff notes

If you are picking this up, start in this order.

- Read `metagent/evolve.py` from the module docstring through compact. That file is the design.
- Read `tests/test_evolve.py` next, not the README. The tests name the gates.
- Run `PYTHONPATH=artifacts python -m pytest tests/test_evolve.py`. The suite is offline.
- Do not add a permission layer unless the outer sandbox requirement is being dropped. That argument was closed.
- Do not change `__getattr__` so that it returns model text. Functions only.
- Do not make compact mandatory-success. Refusal is a feature.
- If you add a stage beyond compact — for example, lifting cold skills into the subclass module itself — keep traces as the acceptance tests. Do not promote on vibe.

The original user sketch is still the north star and still valid: a class, mostly empty, whose dunders and missing methods are vacancies that an LLM fills, with the explicit goal that repetitive action become deterministic code. The implementation added one thing the sketch implied but did not name: a second pass that treats “it worked” as insufficient and asks “can it work without me.”

That second pass is the philosophy. Keep it.
