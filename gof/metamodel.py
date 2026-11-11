# gof/metamodel.py
#
# GoF JSON model — validation and Phi_i (structural integration) metric.

import statistics

from gof.schema import GOF_SCHEMA

VALID_CLASS_TYPES = {"class", "abstract", "interface"}
VALID_REL_TYPES = {
    "inheritance", "implementation",
    "association", "dependency",
    "composition", "aggregation",
}


def _validate_classes(classes: list, errors: list) -> set[str]:
    ids: set[str] = set()
    for cls in classes:
        cid = cls.get("id")
        if not cid:
            errors.append(f"Class missing 'id': {cls}")
            continue
        if cid in ids:
            errors.append(f"Duplicate id: {cid}")
        ids.add(cid)
        if cls.get("type") not in VALID_CLASS_TYPES:
            errors.append(f"Invalid class type '{cls.get('type')}' for {cid}")
    return ids


def _validate_relationships(rels: list, ids: set[str], errors: list) -> list:
    """Returns the relationships to keep. A relationship with an empty/missing
    sourceId or targetId is never a valid reference under any pattern — it's
    dropped rather than failing the whole diagram (the raw LLM output is still
    saved separately for audit, see benchmark_gof.py::_save_raw). A non-empty
    but unrecognized id, or an invalid relationship type, still fails
    validation — that's real generation-quality signal (e.g. a misspelled or
    hallucinated class reference), not a degenerate no-op relationship."""
    kept: list = []
    for rel in rels:
        source_id, target_id = rel.get("sourceId"), rel.get("targetId")
        if not source_id or not target_id:
            continue  # degenerate reference (empty id) — drop silently, don't reject the diagram
        if rel.get("type") not in VALID_REL_TYPES:
            errors.append(f"Invalid relationship type '{rel.get('type')}'")
        if source_id not in ids:
            errors.append(f"Unknown sourceId '{source_id}'")
        if target_id not in ids:
            errors.append(f"Unknown targetId '{target_id}'")
        kept.append(rel)
    return kept


def validate_gof(model: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(model.get("classes"), list):
        errors.append("Missing or invalid 'classes' array")
        return errors
    if not isinstance(model.get("relationships"), list):
        errors.append("Missing or invalid 'relationships' array")
        return errors
    ids = _validate_classes(model["classes"], errors)
    model["relationships"] = _validate_relationships(model["relationships"], ids, errors)
    return errors


_PATTERN_NAMES_LOWER = {name.lower(): name for name in GOF_SCHEMA}


def _match_pattern(name: str) -> str | None:
    key = name.strip().lower().replace(" ", "")
    if key in _PATTERN_NAMES_LOWER:
        return _PATTERN_NAMES_LOWER[key]
    for lower, canonical in _PATTERN_NAMES_LOWER.items():
        if lower in key or key in lower:
            return canonical
    return None


def _model_pattern_names(model: dict) -> list[str]:
    patterns = model.get("patterns")
    raw = [str(p) for p in patterns if p] if isinstance(patterns, list) and patterns \
        else str(model.get("pattern", "")).split("+")
    return [name for p in raw if (name := _match_pattern(p))]


def _class_score(model: dict, min_classes: int) -> float:
    n_classes = len(model.get("classes", []))
    return min(n_classes / min_classes, 1.0) * 3.0


def _rel_score(model: dict, expected_rel_types: set) -> float:
    if not expected_rel_types:
        return 3.0
    # "implementation" (interface realization) is structurally equivalent to "inheritance"
    # for pattern-matching purposes — gof/plantuml.py already treats them as one in its own
    # heuristics (see _cls_lines/_rel_line), so scoring should not penalize a diagram for
    # correctly using "implementation" on an interface instead of "inheritance".
    present = {
        ("inheritance" if r.get("type") == "implementation" else r.get("type"))
        for r in model.get("relationships", [])
    }
    return len(present & expected_rel_types) / len(expected_rel_types) * 3.0


# Generic GoF-textbook method names (operation, operationImpl, ...) that
# gof_pattern_rules.md explicitly tells the LLM to rename to a domain-specific verb
# (e.g. "format", "render", "draw"). Without this, following that naming guidance would
# always score 0 on these fragments.
_METHOD_SYNONYMS: dict[str, list[str]] = {
    "operation": ["execute", "perform", "process", "apply", "run", "handle", "render", "draw", "format", "compute"],
    "operationimpl": ["execute", "perform", "process", "apply", "run", "render", "draw", "format", "compute"],
    "primitiveoperation": ["step", "process", "execute", "render", "draw", "format"],
    "factorymethod": ["create", "make", "build", "instantiate"],
}


def _method_score(model: dict, key_methods: list) -> float:
    if not key_methods:
        return 4.0
    signatures = " ".join(
        str(m).lower() for cls in model.get("classes", []) for m in cls.get("methods", [])
    )
    found = sum(
        1 for fragment in key_methods
        if fragment in signatures
        or any(synonym in signatures for synonym in _METHOD_SYNONYMS.get(fragment, []))
    )
    return found / len(key_methods) * 4.0


def compute_phi(model: dict) -> float:
    """
    Φᵢ — intégration structurelle (formule C2TR, docs/equations_gof1_eg.md §2).
    Par pattern déclaré et reconnu : class_score (0-3, classes / C_min) +
    rel_score (0-3, types de relations canoniques présents) + method_score
    (0-4, fragments de méthodes clés trouvés) — borné à [0, 10]. Moyenne sur
    tous les patterns déclarés reconnus ; 0.0 si aucun n'est reconnu.
    """
    pattern_names = _model_pattern_names(model)
    if not pattern_names:
        return 0.0

    scores = [
        _class_score(model, GOF_SCHEMA[name]["min_classes"])
        + _rel_score(model, GOF_SCHEMA[name]["expected_rel_types"])
        + _method_score(model, GOF_SCHEMA[name]["key_methods"])
        for name in pattern_names
    ]
    return sum(scores) / len(scores)


def is_understanding_event(
    phi_i: float,
    rg: float,
    energy_j: float,
    session_energies: list[float],
    phi_floor: float = 6.0,
    rg_floor: float = 0.3,
    energy_ceiling_ratio: float = 2.0,
) -> tuple[bool, str]:
    """
    CIITR structural predicate — C_i = Phi_i x Rg is a boundary condition, not a
    score (WhyUnderstandingIsaRelational_FR.md §3/§7): whether THIS iteration
    satisfies the relational conditions for understanding, not whether the
    system "has" understanding. Three independent gates, ANDed:
      - Phi_i >= phi_floor  : structural integration (60% of the 10-point scale)
      - Rg >= rg_floor      : rhythmic coherence magnitude, not mere presence
        (Rg > 0 alone is guaranteed by construction in LLM_AI — analyze() +
        update_wiki() always contribute >= 2 cadence samples — so it only ever
        separates LLM_AI from LLM_ONLY, never discriminates within LLM_AI runs)
      - energy_j not an outlier vs this session's own accepted-iteration median
        (the CPJ-collapse signature: cost blowing up relative to the session's
        own baseline, rather than an arbitrary absolute threshold)
    Returns (passed, reason) — reason names the first failed gate, or
    "conditional_understanding" if all three hold.
    """
    if phi_i < phi_floor:
        return False, "phi_below_floor"
    if rg < rg_floor:
        return False, "rg_below_floor"
    baseline = statistics.median(session_energies) if session_energies else energy_j
    if energy_j > energy_ceiling_ratio * baseline:
        return False, "energy_outlier"
    return True, "conditional_understanding"
