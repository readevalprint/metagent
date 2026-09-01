"""Exception debugger: source + stack in, tools out.

On an uncaught error the model gets the originating file, the live
frames and locals, and the exception. It then works like a person at a
pdb prompt: exec Python, read files, patch files, set a return value,
retry, or re-raise.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

DEBUG_SYSTEM = """\
You are debugging a live metagent agent.
You have a Python shell and a debugger. The process already runs in a sandbox.

Reply with a single JSON object, no markdown:
  {{"tool": "py", "code": "python to exec"}}
  {{"tool": "stack"}}
  {{"tool": "read", "path": "relative or absolute file"}}
  {{"tool": "patch", "path": "file.py", "content": "full new file contents"}}
  {{"tool": "patch", "name": "method_name", "source": "def method_name(self, ...): ..."}}
  {{"tool": "return", "value": ...}}
  {{"tool": "retry"}}
  {{"tool": "raise", "message": "optional"}}

Prefer patch + retry when the body is wrong so the next call does not
need you. Prefer return when this one call just needs a value. Use py
to inspect or compute. Use raise only when you cannot recover.
"""

DEBUG_USER = """\
Source:
{source}

Stack:
{stack}

The current function `{name}` had an uncaught exception:
{error}

Call: {name}({call_shape})
Agent class: {cls}
Workspace: {workspace}

Transcript so far:
{transcript}
"""


def capture_stack(exc: BaseException, *, skip_parts: tuple[str, ...] = ("metagent/evolve.py", "metagent/debug.py", "metagent/sandbox.py")) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    tb = exc.__traceback__
    while tb is not None:
        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        skipped = any(part in filename.replace("\\", "/") for part in skip_parts)
        locals_map = {}
        if not skipped:
            for key, value in list(frame.f_locals.items())[:40]:
                if key.startswith("__"):
                    continue
                locals_map[key] = _brief(value)
        frames.append(
            {
                "file": filename,
                "line": tb.tb_lineno,
                "func": frame.f_code.co_name,
                "skipped": skipped,
                "locals": locals_map,
            }
        )
        tb = tb.tb_next
    return frames


def format_stack(frames: list[dict[str, Any]]) -> str:
    lines = []
    for frame in frames:
        if frame.get("skipped") and not frame.get("locals"):
            continue
        lines.append(f'  File "{frame["file"]}", line {frame["line"]}, in {frame["func"]}')
        if frame.get("locals"):
            for key, value in frame["locals"].items():
                lines.append(f"      {key} = {value}")
    return "\n".join(lines) if lines else "(no user frames)"


def load_origin_source(exc: BaseException, cls: type, fallback: str = "") -> tuple[str, str]:
    tb = exc.__traceback__
    last_user = None
    while tb is not None:
        filename = tb.tb_frame.f_code.co_filename
        if "metagent/" not in filename.replace("\\", "/"):
            last_user = filename
        tb = tb.tb_next
    path = last_user
    if path is None:
        try:
            path = inspect.getfile(cls)
        except TypeError:
            path = None
    if path and Path(path).exists():
        try:
            return path, Path(path).read_text(encoding="utf-8")
        except OSError:
            pass
    return "(memory)", fallback or "(source unavailable)"


def _brief(value: Any, limit: int = 200) -> str:
    if inspect.isfunction(value) or inspect.ismethod(value) or inspect.isclass(value):
        return f"<{type(value).__name__} {getattr(value, '__qualname__', getattr(value, '__name__', ''))}>"
    try:
        text = repr(value)
    except Exception:
        text = f"<{type(value).__name__}>"
    if len(text) > limit:
        return text[:limit] + "\u2026"
    return text


def parse_tool(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if "```" in text:
        inner = text.split("```", 2)
        if len(inner) >= 2:
            body = inner[1]
            if body.lstrip().lower().startswith("json"):
                body = body.split("\n", 1)[-1]
            text = body.strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            if "tool" not in data and "op" in data:
                data = _legacy_op(data)
            return data
    except json.JSONDecodeError:
        pass
    return {"tool": "raise", "message": f"debugger did not return JSON: {raw[:240]}"}


def _legacy_op(data: dict[str, Any]) -> dict[str, Any]:
    op = data.get("op")
    if op == "return":
        return {"tool": "return", "value": data.get("value")}
    if op == "patch_code":
        return {"tool": "patch", "name": data.get("name"), "source": data.get("source")}
    if op == "raise":
        return {"tool": "raise", "message": data.get("message")}
    if op == "continue":
        return {"tool": "retry"}
    return {"tool": "raise", "message": f"unknown op {op!r}"}
