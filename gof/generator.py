# gof/generator.py
#
# Builds the LLM prompt for GoF class diagram generation.
# Takes a LISS (global invariants) and a PSIS (session context).

from __future__ import annotations

from liss import LISS
from psis import PSIS

_MULTI_PEAK_THRESHOLD = 0.50


def _rules_section(liss: LISS) -> str:
    return "\n\n".join(
        f"### {name}\n{body}"
        for name, body in liss.pattern_rules.items()
        if "+" not in name
    )


def _ai_section(ai_context: dict, pattern_rules: dict) -> str:
    pattern    = ai_context["pattern_name"]
    confidence = ai_context["confidence"]
    top3       = ai_context["top3"]
    top3_peaks = ai_context.get("top3_peaks", [confidence, 0.0, 0.0])
    rg         = ai_context["rg"]

    secondary_peak = top3_peaks[1] if len(top3_peaks) > 1 else 0.0
    multi = (confidence < 0.60 or secondary_peak >= _MULTI_PEAK_THRESHOLD) and len(top3) >= 2

    if multi:
        active = [top3[0]] + [p for p, pk in zip(top3[1:], top3_peaks[1:]) if pk >= _MULTI_PEAK_THRESHOLD]
        rules_block = ""
        for p in active:
            r = pattern_rules.get(p, "")
            if r:
                rules_block += f"\nUsage rules for {p}:\n{r}\n"
        combo_key = "+".join(sorted(active))
        combo_rule = pattern_rules.get(combo_key, "")
        if combo_rule:
            rules_block += f"\nCombination rule for {' + '.join(active)}:\n{combo_rule}\n"
        patterns_str = " + ".join(active)
        patterns_json = ", ".join(f'"{p}"' for p in active)
        return f"""
AI AGENT CONTEXT (Active Inference — Rg={rg:.4f}):
Detected patterns : {patterns_str} (peaks={[round(pk, 2) for pk in top3_peaks]})
Top candidates    : {', '.join(top3)}
{rules_block}
Suggestion: generate a class diagram that combines {patterns_str}.
Use the "patterns" field to list all: "patterns": [{patterns_json}].
"""
    else:
        rules = pattern_rules.get(pattern, "")
        rules_block = f"\nUsage rules for {pattern}:\n{rules}\n" if rules else ""
        return f"""
AI AGENT CONTEXT (Active Inference — Rg={rg:.4f}):
Detected pattern : {pattern} (confidence={confidence:.2f})
Top candidates   : {', '.join(top3)}
{rules_block}
Suggestion: generate a class diagram that strictly implements the {pattern} pattern.
"""


def build_prompt(liss: LISS, psis: PSIS) -> str:
    ai_section = _ai_section(psis.ai_context, liss.pattern_rules) if psis.ai_context else ""

    return f"""SYSTEM:
You generate GoF design pattern class diagrams as JSON.
You output JSON only. No explanations, no markdown, no comments.

PHASE:
Current iteration = {psis.iteration}
Last CPJ in previous iteration = {psis.last_cpj}
Last Comprehension in previous iteration = {psis.last_comprehension}
Maximize Comprehension while minimizing energy (CPJ).
{ai_section}
GOF PATTERN GUIDE:
{_rules_section(liss)}

JSON FORMAT:
{{
  "pattern": "<PatternName or 'PatternA+PatternB'>",
  "patterns": ["<PatternA>", "<PatternB>"],
  "classes": [
    {{
      "id": "<uniqueId>",
      "name": "<ClassName>",
      "type": "{' | '.join(liss.allowed_class_types)}",
      "attributes": ["<visibility> <name>: <Type>"],
      "methods": ["<visibility> <name>(<params>): <ReturnType>"]
    }}
  ],
  "relationships": [
    {{
      "type": "{' | '.join(liss.allowed_rel_types)}",
      "sourceId": "<id>",
      "targetId": "<id>",
      "label": "<optional>"
    }}
  ]
}}

RULES:
- "id" must be unique, letters only, no spaces.
- "type" for classes: {', '.join(f'"{t}"' for t in liss.allowed_class_types)}.
- Allowed relationship types: {', '.join(f'"{t}"' for t in liss.allowed_rel_types)}.
- Attributes and methods use visibility prefix: + public, - private, # protected.
- No duplicate IDs. No unused classes. Valid JSON only.
- "patterns" is optional: use it when the diagram combines two GoF patterns.

TASK:
{psis.objective}

OUTPUT:
{{ "pattern": "...", "patterns": [...], "classes": [...], "relationships": [...] }}
"""
