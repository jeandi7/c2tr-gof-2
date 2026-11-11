# liss.py — LLM Instruction Schema Standard (LISS) pour le benchmark GoF
# Invariants globaux : règles de pattern, types autorisés. Ne changent pas entre sessions.
import re
from dataclasses import dataclass, field
from pathlib import Path

_RULES_FILE = Path(__file__).parent / "gof_pattern_rules.md"


def _load_pattern_rules(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    rules: dict[str, str] = {}
    sections = re.split(r"^### (.+)$", text, flags=re.MULTILINE)
    for i in range(1, len(sections), 2):
        name = sections[i].strip()
        body = sections[i + 1] if i + 1 < len(sections) else ""
        body = re.split(r"^##", body, flags=re.MULTILINE)[0].strip()
        rules[name] = body
    return rules


@dataclass
class LISS:
    allowed_class_types: list[str] = field(default_factory=lambda: [
        "class", "abstract", "interface"
    ])
    allowed_rel_types: list[str] = field(default_factory=lambda: [
        "inheritance", "implementation", "association",
        "dependency", "composition", "aggregation"
    ])
    pattern_rules: dict[str, str] = field(default_factory=dict)

    @classmethod
    def default(cls) -> "LISS":
        return cls(pattern_rules=_load_pattern_rules(_RULES_FILE))
