#!/usr/bin/env python3
"""Thin wrapper around the Cursor CLI (`agent` / `cursor-agent`) used for translation and polish.

Design rules:
- The API key is read from the CURSOR_API_KEY environment variable only (in CI: a GitHub Actions
  secret). It is never written to a file and never put on a command line.
- The model is named explicitly. It is checked against `agent --list-models` first; if it is not
  there, nothing is substituted: the caller skips the step and reports the models that are available.
- Every call is read-only (`--mode ask`) in an empty temporary workspace, so the agent cannot see or
  touch the repository.
- Any failure raises LLMError; callers keep the text they already have.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from typing import Callable

# The Cursor CLI names the effort variants of Gemini 3.8 Flash gemini-3.8-flash-{low,medium,high}.
DEFAULT_MODEL = "gemini-3.8-flash-medium"
KEY_ENV = "CURSOR_API_KEY"
CALL_TIMEOUT = 240


class LLMError(RuntimeError):
    pass


def find_binary(env: dict[str, str] | None = None) -> str | None:
    env = os.environ if env is None else env
    explicit = env.get("CURSOR_AGENT_BIN")
    if explicit:
        return explicit if shutil.which(explicit) else None
    return shutil.which("agent") or shutil.which("cursor-agent")


def parse_model_ids(listing: str) -> list[str]:
    """Model ids from `agent --list-models` output (one `<id> - <label>` per line, extras tolerated)."""
    ids = []
    for line in re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", listing).splitlines():
        m = re.match(r"^\W*([a-z0-9][a-z0-9._\-\[\]=,]*)\b", line.strip().lower())
        if m and m.group(1) not in ("available", "models", "loading", "tip"):
            ids.append(m.group(1))
    return ids


def build_command(binary: str, model: str, prompt: str, workspace: str) -> list[str]:
    """argv for one non-interactive, read-only call. The key is deliberately not part of it."""
    return [binary, "-p", "--output-format", "text", "--mode", "ask", "--trust",
            "--workspace", workspace, "--model", model, prompt]


class CursorAgent:
    """Runs prompts through the Cursor CLI. `ask(prompt) -> str` is the only thing callers need."""

    def __init__(self, model: str = DEFAULT_MODEL, env: dict[str, str] | None = None,
                 run: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self.model = model
        self.env = {k: v for k, v in (os.environ if env is None else env).items()
                    if k not in ("GITHUB_TOKEN", "GH_TOKEN")}  # the agent never needs the repo token
        self._run = run
        self.binary = find_binary(self.env)

    def unavailable_reason(self) -> str | None:
        """None when ready to use; otherwise why not (never substitutes another model)."""
        if not self.env.get(KEY_ENV):
            return f"{KEY_ENV} is not set (add it as a GitHub Actions secret)"
        if not self.binary:
            return "Cursor CLI (`agent`) is not installed"
        try:
            ids = self.list_models()
        except LLMError as e:
            return f"could not list Cursor models: {e}"
        if self.model.lower() not in ids:
            gem = [i for i in ids if "gemini" in i] or ids[:20]
            return (f"model {self.model!r} is not available in Cursor for this account; "
                    f"available: {', '.join(gem) or '(none listed)'}")
        return None

    def list_models(self) -> list[str]:
        out = self._exec([self.binary, "--list-models"], timeout=60)
        return parse_model_ids(out)

    def ask(self, prompt: str) -> str:
        with tempfile.TemporaryDirectory(prefix="risers-llm-") as ws:
            return self._exec(build_command(self.binary, self.model, prompt, ws), timeout=CALL_TIMEOUT, cwd=ws)

    def _exec(self, argv: list[str], timeout: int, cwd: str | None = None) -> str:
        try:
            r = self._run(argv, capture_output=True, text=True, timeout=timeout, env=self.env, cwd=cwd)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise LLMError(type(e).__name__) from None
        if r.returncode != 0:
            tail = (r.stderr or r.stdout or "").strip().splitlines()[-1:] or ["no output"]
            raise LLMError(f"exit {r.returncode}: {tail[0][:200]}".replace(self.env.get(KEY_ENV, "\0"), "***"))
        return r.stdout


def extract_json(text: str) -> dict:
    """The first JSON object in a model reply (tolerates code fences and chatter around it)."""
    text = re.sub(r"```(?:json)?", "", text)
    a, b = text.find("{"), text.rfind("}")
    if a < 0 or b <= a:
        raise LLMError("no JSON object in reply")
    try:
        obj = json.loads(text[a:b + 1])
    except ValueError:
        raise LLMError("reply is not valid JSON") from None
    if not isinstance(obj, dict):
        raise LLMError("reply JSON is not an object")
    return obj
