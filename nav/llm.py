"""Thin wrapper around the Anthropic API that forces structured (tool) output."""
from __future__ import annotations

import os

from .common import load_env

DEFAULT_MODEL = "claude-sonnet-5-5"
_USE_TEMPERATURE = True


class TruncatedOutput(Exception):
    """Model ran out of output tokens (we then split the input and retry)."""


def get_model() -> str:
    load_env()
    return os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)


def get_client():
    load_env()
    import anthropic

    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Paste your key after ANTHROPIC_API_KEY=\n"
            "  (see GUIDE.md, step 4)"
        )
    kwargs = {"api_key": key, "max_retries": 6, "timeout": 600.0}
    base = os.environ.get("ANTHROPIC_BASE_URL")
    if base:  # used only by the offline test-suite
        kwargs["base_url"] = base
    return anthropic.Anthropic(**kwargs)


_FORCE_TOOL = True
_NUDGE = ("\n\nIMPORTANT: respond ONLY by calling the tool '{name}' exactly once with the complete result. "
          "Do not write any other text.")


def _create(client, kwargs):
    """messages.create with automatic fallbacks for models that reject temperature or forced tool choice."""
    global _USE_TEMPERATURE, _FORCE_TOOL
    for _ in range(4):
        kw = dict(kwargs)
        if _USE_TEMPERATURE:
            kw["temperature"] = 0
        if not _FORCE_TOOL:
            kw["tool_choice"] = {"type": "auto"}
            kw["system"] = kw["system"] + _NUDGE.format(name=kw["tools"][0]["name"])
        try:
            return client.messages.create(**kw)
        except Exception as e:
            msg = str(e).lower()
            # (checks use what THIS request sent, so parallel threads cannot race each other)
            if "temperature" in kw and "temperature" in msg:
                _USE_TEMPERATURE = False
            elif kw["tool_choice"].get("type") != "auto" and "tool_choice" in msg:
                _FORCE_TOOL = False  # e.g. models with thinking on: 'type tool and any are not supported'
            else:
                raise
    raise RuntimeError("could not find request settings this model accepts")


def call_tool(client, *, system: str, user: str, tool: dict, max_tokens: int = 12000, model: str | None = None) -> dict:
    """Call the model, get the answer through `tool`, return the tool input dict."""
    model = model or get_model()
    kwargs = dict(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
        messages=[{"role": "user", "content": user}],
    )
    for attempt in range(3):
        resp = _create(client, kwargs)
        if resp.stop_reason == "max_tokens":
            raise TruncatedOutput()
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                return {
                    "input": block.input,
                    "model": getattr(resp, "model", model),
                    "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens},
                }
        kwargs["messages"] = [{"role": "user", "content": user + "\n\n(Reminder: you must answer by calling the tool.)"}]
    raise RuntimeError(f"Model did not call tool {tool['name']}: stop_reason={resp.stop_reason}")