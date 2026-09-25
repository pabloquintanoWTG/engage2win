"""Progress + error reporting shared by both analysis flows.

Both flows (quick /analyze and session maps) run the same Phase 0 core. This
module defines the steps the user sees, builds the JSON status payload the
progress widget (static/analysis_progress.js) renders, and translates the
recognisable failures — `claude` CLI missing, not signed in, rate-limited, too
slow, or not returning a valid evaluation — into {title, where, message, fix,
detail} so the user knows where it broke and what to do.
"""
import json
import subprocess
from datetime import datetime, timezone

from jsonschema import ValidationError

STEPS = ["prepare", "evaluate", "validate", "describe", "done"]
STEP_LABELS = {
    "prepare":  "Preparing the map",
    "evaluate": "Reading & scoring the map",
    "validate": "Checking the evaluation",
    "describe": "Writing the description",
    "done":     "Done",
}
# What happens after the current step finishes (shown as "Next: …").
STEP_NEXT = {
    "prepare":  "The AI reads and scores the map — usually 30–90 seconds.",
    "evaluate": "Check that the evaluation is complete.",
    "validate": "Write a structured description of the map.",
    "describe": "Show your results.",
}


def status_payload(state, step, started_at=None, finished_at=None, error=None,
                   timeout_s=None):
    """JSON-ready status: state is pending|running|done|error."""
    elapsed = None
    if started_at is not None:
        if started_at.tzinfo is None:  # SQLite returns naive UTC datetimes
            started_at = started_at.replace(tzinfo=timezone.utc)
        end = finished_at or datetime.now(timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        elapsed = max(0, int((end - started_at).total_seconds()))
    return {
        "state": state,
        "step": step,
        "steps": [{"key": k, "label": STEP_LABELS[k]} for k in STEPS],
        "label": STEP_LABELS.get(step, ""),
        "next": STEP_NEXT.get(step, "") if state == "running" else "",
        "elapsed_s": elapsed,
        "timeout_s": timeout_s,
        "error": error,
    }


_RETRY = "Click Retry analysis."
_SERVER_LOG = "If it keeps failing, check the terminal running the app for the full error."


class NoBackendError(RuntimeError):
    """Neither the `claude` CLI nor ANTHROPIC_API_KEY is available (run.py would
    silently fall back to stub results, which must never reach a user)."""


def _root(exc):
    """The most specific exception: run.analyze_map wraps failures in RuntimeError."""
    while exc.__cause__ is not None:
        exc = exc.__cause__
    return exc


def _err(title, where, message, fix, detail=""):
    return {"title": title, "where": where, "message": message, "fix": fix,
            "detail": (detail or "")[:1500]}


def explain_error(exc, step):
    """Return a user-facing error dict for an exception raised during `step`."""
    root = _root(exc)
    where = STEP_LABELS.get(step, step or "Analysis")
    detail = str(root)
    low = detail.lower()

    if isinstance(root, NoBackendError):
        return _err(
            "No AI engine available", where,
            "The app couldn't find the `claude` command or an ANTHROPIC_API_KEY, so it can't analyse maps.",
            "Install Claude Code and check that `claude --version` works in a terminal "
            "(or add ANTHROPIC_API_KEY to .env.local), then restart the app and retry.",
            detail)

    if isinstance(root, subprocess.TimeoutExpired):
        mins = max(1, round((root.timeout or 0) / 60))
        return _err(
            "The AI took too long to respond", where,
            f"No answer from the Claude CLI after {mins} min, so the analysis was stopped.",
            f"{_RETRY} Large or very busy photos take longer; if it keeps timing out, "
            "check your internet connection or raise E2W_CLI_TIMEOUT (seconds) in .env.local.",
            detail)

    # subprocess raises FileNotFoundError (filename None or the exe) when `claude` is missing.
    fname = str(getattr(root, "filename", "") or "").lower()
    if isinstance(root, FileNotFoundError) and (not fname or "claude" in fname):
        return _err(
            "Claude CLI not found", where,
            "The app analyses maps with the local `claude` command, but it isn't installed "
            "or isn't on PATH for the app.",
            "Install Claude Code, open a terminal and check that `claude --version` works, "
            "then restart the app and retry.",
            detail)

    if "claude cli exited" in low:
        if any(k in low for k in ("login", "log in", "auth", "401", "credential", "api key")):
            return _err(
                "Claude CLI is not signed in", where,
                "The `claude` command refused the request because it isn't authenticated.",
                f"Open a terminal, run `claude` and sign in, then come back. {_RETRY}",
                detail)
        if any(k in low for k in ("rate limit", "usage limit", "429", "overloaded", "529")):
            return _err(
                "Claude is busy or your usage limit was reached", where,
                "The model service asked us to slow down.",
                f"Wait a few minutes, then {_RETRY.lower()}",
                detail)
        return _err(
            "The Claude CLI reported an error", where,
            "The `claude` command stopped with an error before finishing.",
            f"{_RETRY} {_SERVER_LOG}",
            detail)

    if isinstance(root, ValidationError):
        return _err(
            "The evaluation was incomplete", where,
            f"The AI answered, but its evaluation didn't match the expected format ({root.message}).",
            f"{_RETRY} This is usually a one-off.",
            detail)

    if isinstance(root, json.JSONDecodeError) or "no json object" in low:
        return _err(
            "The AI couldn't produce an evaluation", where,
            "The AI replied, but not with a structured evaluation — often because it "
            "couldn't read the photo.",
            f"{_RETRY} If it happens again, upload a sharper, well-lit photo that shows the whole map.",
            detail)

    if "image not found" in low:
        return _err(
            "The map photo is missing", where,
            "The uploaded image file is no longer in app/uploads.",
            "Delete this map and upload the photo again.",
            detail)

    return _err(
        "Something went wrong", where,
        "The analysis stopped because of an unexpected error.",
        f"{_RETRY} {_SERVER_LOG}",
        f"{type(root).__name__}: {detail}")


def interrupted_error(step):
    """The worker thread is gone (app restarted) but the row still says running."""
    return _err(
        "The analysis was interrupted", STEP_LABELS.get(step, step or "Analysis"),
        "The app was restarted while this map was being analysed, so the work was lost.",
        _RETRY)
