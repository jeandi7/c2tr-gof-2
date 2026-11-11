# agent_ai/gof_ai_agent.py
#
# LLM-based "wiki" agent for GoF design pattern detection (Karpathy wiki pattern):
# instead of a fixed Bayesian generative model (matrices A/B), beliefs live in a
# single persistent markdown document that the LLM itself reads and edits, turn
# after turn — memory that converges rather than memory that accumulates in-context.
#
# Two dedicated LLM calls per iteration (agent_llm.llm.call_llm), separate from
# the diagram-generation call:
#
#   analyze(objective)      — reads gof_pattern_rules.md (canonical, read-only)
#                              + wiki/learned_notes.md (grows across runs), and
#                              asks the LLM which GoF pattern(s) fit the objective.
#   update_wiki(obj, model) — after a diagram is accepted, asks the LLM to rewrite
#                              that pattern's wiki page with what this run taught it.
#
# CIITR reading:
#   Rg (rg_proxy) = empirical rhythmic coherence, per C2TR.md's token-cadence /
#   phase-jitter observables — not a confidence proxy. One cycle = one analyze()
#   call + the update_wiki() call it leads to; their tokens and elapsed time are
#   summed into a single tokens/sec sample for that cycle. Rg = 1 minus the
#   coefficient of variation of those per-cycle samples across the session,
#   clamped to [0, 1]. Rg -> 1 means the agent's inference rhythm stayed stable
#   cycle to cycle (C2TR.md p.23: "<2% jitter" over a session); Rg -> 0 means
#   erratic timing, or fewer than 2 cycles closed so far (no rhythm to measure
#   yet). Cycles are summed, never compared analyze-vs-update_wiki directly —
#   those two calls have structurally different output lengths (short JSON vs
#   up to 120 words of prose), so comparing them to each other would measure
#   that structural gap, not rhythm drift across iterations.

import json
import re
import statistics
from pathlib import Path

from agent_llm.llm import call_llm

PATTERN_NAMES = [
    "Singleton", "FactoryMethod", "AbstractFactory", "Builder", "Prototype",
    "Adapter", "Bridge", "Composite", "Decorator", "Facade", "Flyweight", "Proxy",
    "ChainOfResponsibility", "Command", "Interpreter", "Iterator", "Mediator",
    "Memento", "Observer", "State", "Strategy", "TemplateMethod", "Visitor",
]

_RULES_FILE = Path(__file__).resolve().parent.parent / "gof_pattern_rules.md"
_WIKI_DIR = Path(__file__).resolve().parent / "wiki"
_WIKI_FILE = _WIKI_DIR / "learned_notes.md"

_WIKI_HEADER = (
    "# Learned Notes — GoF Wiki Agent\n\n"
    "Notes accumulated across benchmark runs. One section per pattern, written "
    "and rewritten by the LLM itself after each accepted diagram generation.\n"
)

_SECTION_RE = re.compile(r"^### (.+)$", re.MULTILINE)

_DEFAULT_CONTEXT = {
    "pattern_name": "Singleton",
    "confidence": None,  # None = no reliable value yet (unparsed / not analyzed) — never
                         # conflate with a real 0.0 confidence the model actually reported
    "top3": ["Singleton", "FactoryMethod", "AbstractFactory"],
    "top3_peaks": [0.0, 0.0, 0.0],
    "rg": 0.0,
}


def _ensure_wiki() -> None:
    _WIKI_DIR.mkdir(parents=True, exist_ok=True)
    if not _WIKI_FILE.exists():
        _WIKI_FILE.write_text(_WIKI_HEADER, encoding="utf-8")


def _split_wiki(text: str) -> tuple[str, dict[str, str]]:
    parts = _SECTION_RE.split(text)
    header = parts[0]
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections[name] = body.strip()
    return header, sections


def _join_wiki(header: str, sections: dict[str, str]) -> str:
    body = "\n\n".join(f"### {name}\n{text}" for name, text in sections.items() if text)
    return header.rstrip() + "\n\n" + body + "\n"


def _closest_pattern_name(name: str) -> str | None:
    if not name:
        return None
    lname = name.lower()
    for p in PATTERN_NAMES:
        if p.lower() == lname:
            return p
    for p in PATTERN_NAMES:
        if p.lower() in lname or lname in p.lower():
            return p
    return None


def _parse_analyze_output(raw: str) -> dict:
    context = dict(_DEFAULT_CONTEXT)
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
    except (ValueError, json.JSONDecodeError):
        return context

    name = _closest_pattern_name(str(data.get("pattern_name", "")).strip())
    if name:
        context["pattern_name"] = name

    try:
        context["confidence"] = max(0.0, min(0.99, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        pass

    top3_raw = data.get("top3")
    if isinstance(top3_raw, list) and top3_raw:
        top3 = [_closest_pattern_name(str(t)) for t in top3_raw]
        top3 = [t for t in top3 if t]
        if top3:
            context["top3"] = top3[:3]

    peaks_raw = data.get("top3_peaks")
    if isinstance(peaks_raw, list) and peaks_raw:
        try:
            context["top3_peaks"] = [max(0.0, min(1.0, float(p))) for p in peaks_raw[:3]]
        except (TypeError, ValueError):
            pass

    if context["pattern_name"] not in context["top3"]:
        context["top3"] = [context["pattern_name"]] + context["top3"][:2]
        context["top3_peaks"] = [context["confidence"]] + context["top3_peaks"][:2]

    return context


def _build_analyze_prompt(objective: str, rules_text: str, wiki_text: str) -> str:
    return f"""SYSTEM:
You are the pattern-recognition module of a GoF design-pattern benchmark agent.
You maintain a wiki of design-pattern knowledge and must decide, from the objective
below, which Gang-of-Four pattern(s) best fit. Use both the canonical rules and your
own learned notes (accumulated from previous runs) to make the call.
You output STRICT JSON only. No markdown, no explanation, no code fences.

CANONICAL PATTERN RULES:
{rules_text}

LEARNED NOTES (accumulated from previous runs — may be sparse or empty):
{wiki_text}

VALID PATTERN NAMES (choose only from this list):
{", ".join(PATTERN_NAMES)}

OBJECTIVE:
{objective}

TASK:
Identify the single dominant GoF pattern for this objective, plus the two next most
plausible candidates, with your confidence in each (0.0-1.0). Confidence reflects how
sure you are given the rules and notes above — use the full range, do not default to 1.0.

OUTPUT (strict JSON, one line, no other text):
{{"pattern_name": "<name from the list>", "confidence": <float>, "top3": ["<name>", "<name>", "<name>"], "top3_peaks": [<float>, <float>, <float>]}}
"""


def _build_update_prompt(pattern: str, objective: str, model: dict, current_notes: str) -> str:
    classes = model.get("classes", [])
    class_summary = "\n".join(
        f"- {c.get('name')} ({c.get('type')}): {', '.join(c.get('methods', []))}"
        for c in classes
    ) or "(none)"

    return f"""SYSTEM:
You maintain the "{pattern}" page of a design-pattern wiki. You just watched a class
diagram get generated for a new objective. Rewrite this wiki page to fold in whatever
is worth remembering from this run — a domain example, a naming choice, a pitfall —
without losing what was useful in the existing page. Output the page body only:
plain markdown, no "### {pattern}" header (the caller adds that), no code fences.
Keep it under 120 words, bullet points preferred.

OBJECTIVE:
{objective}

GENERATED CLASSES:
{class_summary}

CURRENT PAGE:
{current_notes}

OUTPUT:
<the rewritten page body>
"""


class GofAIAgent:
    """
    LLM-based wiki agent (Karpathy wiki pattern). Perception (analyze) and
    memory update (update_wiki) are both LLM calls, kept separate from the
    diagram-generation call so their cost is visible in the benchmark.
    """

    def __init__(self, local: bool = True, use_mlx: bool = False):
        self._local = local
        self._use_mlx = use_mlx
        self._rules_text = _RULES_FILE.read_text(encoding="utf-8") if _RULES_FILE.exists() else ""
        _ensure_wiki()
        self.reset()

    def reset(self) -> None:
        """Clears per-session state. The wiki file on disk is NOT cleared —
        it persists across sessions and benchmark runs by design."""
        self._context: dict = dict(_DEFAULT_CONTEXT)
        self._cadences: list[float] = []
        self._pending_analyze: tuple[int, float] | None = None

    @staticmethod
    def _token_count(raw: str) -> int:
        return len(raw.split()) if raw else 0

    def _sample_cycle(self, tokens: int, elapsed: float, warmup: bool = False) -> None:
        """One cycle = one analyze() + the update_wiki() it leads to (or its
        absence, if the diagram was rejected). Combines the pending analyze()
        call with the tokens/elapsed passed here into a single tokens/sec
        sample, then clears the pending call — nothing accumulates beyond one
        analyze/update pair. Warmup cycles are discarded rather than sampled:
        they're already excluded from every other session statistic
        (energy, Phi, accepted_energies), so letting one into Rg's cumulative
        pool would let a cold-start outlier permanently dilute-in instead of
        being cleanly excluded."""
        p_tokens, p_elapsed = self._pending_analyze or (0, 0.0)
        self._pending_analyze = None
        if warmup:
            return
        total_tokens = p_tokens + tokens
        total_elapsed = p_elapsed + elapsed
        if total_tokens > 0 and total_elapsed > 0:
            self._cadences.append(total_tokens / total_elapsed)

    def flush_incomplete_cycle(self, warmup: bool = False) -> None:
        """Call when a diagram is rejected, so update_wiki() never runs this
        iteration: samples the cycle from analyze() alone right away, instead
        of leaving it pending to be added to a future cycle's elapsed time."""
        self._sample_cycle(0, 0.0, warmup=warmup)

    def analyze(self, objective: str) -> tuple[dict, float]:
        """LLM call: detect pattern(s) from objective + canonical rules + wiki.
        Returns (ai_context, elapsed_seconds)."""
        wiki_text = _WIKI_FILE.read_text(encoding="utf-8")
        prompt = _build_analyze_prompt(objective, self._rules_text, wiki_text)
        raw, elapsed = call_llm(prompt, local=self._local, use_mlx=self._use_mlx)

        context = _parse_analyze_output(raw)
        self._pending_analyze = (self._token_count(raw), elapsed)
        context["rg"] = self.rg_proxy
        self._context = context
        return context, elapsed

    def update_wiki(self, objective: str, model: dict, warmup: bool = False) -> float:
        """LLM call: rewrite the detected pattern's wiki page from this run's
        output. Samples the cycle opened by analyze(), even when skipped below
        (an unrecognized pattern name). Returns elapsed_seconds (0.0 if skipped)."""
        pattern = self._context.get("pattern_name", "")
        if pattern not in PATTERN_NAMES:
            self._sample_cycle(0, 0.0, warmup=warmup)
            return 0.0

        header, sections = _split_wiki(_WIKI_FILE.read_text(encoding="utf-8"))
        current_notes = sections.get(pattern, "*(no notes yet — first observation)*")

        prompt = _build_update_prompt(pattern, objective, model, current_notes)
        raw, elapsed = call_llm(prompt, local=self._local, use_mlx=self._use_mlx)
        self._sample_cycle(self._token_count(raw), elapsed, warmup=warmup)

        new_notes = raw.strip()
        if new_notes:
            sections[pattern] = new_notes
            _WIKI_FILE.write_text(_join_wiki(header, sections), encoding="utf-8")
        return elapsed

    @property
    def rg_proxy(self) -> float:
        """Rhythmic coherence: 1 - coefficient of variation of per-cycle
        tokens/sec across this session's closed cycles. Needs >= 2 closed
        cycles; 0.0 otherwise."""
        if len(self._cadences) < 2:
            return 0.0
        mean = statistics.fmean(self._cadences)
        if mean <= 0:
            return 0.0
        jitter = statistics.pstdev(self._cadences) / mean
        return max(0.0, min(1.0, 1.0 - jitter))

    def get_pattern_context(self) -> dict:
        return self._context
