#!/usr/bin/env python3
"""Thin wrappers around two agent CLIs, used for translation and polish.

- CursorAgent: Cursor CLI (`agent` / `cursor-agent`). Key = CURSOR_API_KEY (in CI: an Actions secret).
- AgyAgent:    Google Antigravity CLI (`agy`), run locally on the owner's machine. It uses the owner's
               signed-in Antigravity session (no key in the repo); a GEMINI_API_KEY in the environment
               also works if `modelProvider` is set to `gemini` in ~/.gemini/antigravity-cli/settings.json.

Design rules (both):
- No key is ever written to a file or put on a command line.
- The model is named explicitly and checked against the CLI's model list first (`agent --list-models`,
  `agy models`); if it is not there, nothing is substituted: the caller skips the step and reports
  the models that are available.
- Every call runs in an empty temporary workspace, so the agent cannot see or touch the repository
  (Cursor additionally runs with --mode ask; agy headless mode soft-denies tools that need approval).
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
BACKENDS = ("cursor", "agy")


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
        if m and m.group(1) not in ("available", "models", "loading", "tip", "fetching", "error"):
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


def find_agy(env: dict[str, str] | None = None) -> str | None:
    env = os.environ if env is None else env
    explicit = env.get("AGY_BIN")
    if explicit:
        return explicit if shutil.which(explicit) else None
    return shutil.which("agy")


def build_agy_command(binary: str, model: str, prompt: str) -> list[str]:
    """argv for one headless call: JSON envelope out, bounded time, slash commands off."""
    return [binary, "-p", prompt, "--model", model, "--output-format", "json",
            "--print-timeout", "4m", "--disable-slash-commands"]


class AgyAgent(CursorAgent):
    """Google Antigravity CLI. Same interface as CursorAgent; no API key is required by this code."""

    def __init__(self, model: str = DEFAULT_MODEL, env: dict[str, str] | None = None,
                 run: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        base = dict(os.environ if env is None else env)
        super().__init__(model, env=base, run=run)
        # the agent needs neither the repo token nor the Cursor key
        for k in ("GITHUB_TOKEN", "GH_TOKEN", KEY_ENV):
            self.env.pop(k, None)
        self.binary = find_agy(self.env)

    def unavailable_reason(self) -> str | None:
        if not self.binary:
            return "Antigravity CLI (`agy`) is not installed (curl -fsSL https://antigravity.google/cli/install.sh | bash)"
        try:
            ids = self.list_models()
        except LLMError as e:
            return f"could not list agy models: {e}"
        if self.model.lower() not in ids:
            gem = [i for i in ids if "gemini" in i] or ids[:20]
            return (f"model {self.model!r} is not available in agy for this account; "
                    f"available: {', '.join(gem) or '(none listed)'}")
        return None

    def list_models(self) -> list[str]:
        out = self._exec([self.binary, "models"], timeout=60)
        err = re.search(r"^\s*error:?\s*(.+)$", out, re.I | re.M)
        if err:  # agy prints "Error: Please sign in ..." and still exits 0
            raise LLMError(err.group(1).strip()[:160])
        return parse_model_ids(out)

    def ask(self, prompt: str) -> str:
        with tempfile.TemporaryDirectory(prefix="risers-agy-") as ws:
            out = self._exec(build_agy_command(self.binary, self.model, prompt), timeout=CALL_TIMEOUT, cwd=ws)
        try:
            env = json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return out  # plain text: extract_json will decide
        if not isinstance(env, dict):
            return out
        if env.get("status") not in (None, "SUCCESS"):
            raise LLMError(f"agy status {env.get('status')}: {str(env.get('error', ''))[:160]}")
        return str(env.get("response", ""))


def make_agent(backend: str, model: str, env: dict[str, str] | None = None) -> CursorAgent:
    if backend == "cursor":
        return CursorAgent(model, env=env)
    if backend == "agy":
        return AgyAgent(model, env=env)
    raise ValueError(f"unknown backend {backend!r}; use one of {BACKENDS}")


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
