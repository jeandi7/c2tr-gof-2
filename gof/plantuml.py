# gof/plantuml.py
#
# PlantUML export for GoF JSON class models.

_ARROWS = {
    "inheritance":    "--|>",
    "implementation": "..|>",
    "association":    "-->",
    "dependency":     "..>",
    "composition":    "*-->",
    "aggregation":    "o-->",
}

_CLASS_KEYWORD = {"interface": "interface", "abstract": "abstract class"}


def _primary_class_id(model: dict, pattern: str) -> str | None:
    """Returns a class id (not name) — relationships and the GoFLabel connector
    must reference the same id/alias used in the class's `class X as id` line."""
    classes = model.get("classes", [])
    if not classes:
        return None
    pattern_lower = pattern.lower()
    for cls in classes:
        if cls.get("name", "").lower() == pattern_lower:
            return cls["id"]
    return classes[0]["id"]


# Role labels for patterns that follow a Component / Container / Leaf structure.
# Add any pattern that shares this three-tier hierarchy.
_ROLE_LABELS: dict[str, tuple[str, str, str]] = {
    "Composite": ("Component", "Composite", "Leaf"),
    "Decorator": ("Component", "Decorator", "ConcreteComponent"),
}


def _infer_roles(model: dict, labels: tuple[str, str, str]) -> dict[str, str]:
    """Infer structural roles from relationships, using caller-supplied label names.

    Heuristics (purely relational, no class-name assumptions):
      component  = class most targeted by implementation/inheritance
      container  = implements component AND has composition/aggregation to it
      leaf       = implements component, is not a container
    """
    component_label, container_label, leaf_label = labels
    rels = model.get("relationships", [])
    classes = model.get("classes", [])

    impl_count: dict[str, int] = {}
    for rel in rels:
        if rel.get("type") in ("implementation", "inheritance"):
            impl_count[rel.get("targetId", "")] = impl_count.get(rel.get("targetId", ""), 0) + 1
    if not impl_count:
        return {}
    component_id = max(impl_count, key=lambda k: impl_count[k])

    container_ids: set[str] = {
        rel["sourceId"] for rel in rels
        if rel.get("type") in ("composition", "aggregation")
        and rel.get("targetId") == component_id
    }
    leaf_ids: set[str] = {
        rel["sourceId"] for rel in rels
        if rel.get("type") in ("implementation", "inheritance")
        and rel.get("targetId") == component_id
        and rel["sourceId"] not in container_ids
    }

    roles: dict[str, str] = {}
    for cls in classes:
        cid = cls["id"]
        if cid == component_id:
            roles[cid] = component_label
        elif cid in container_ids:
            roles[cid] = container_label
        elif cid in leaf_ids:
            roles[cid] = leaf_label
    return roles


def _cls_lines(cls: dict, stereotype: str = "") -> list[str]:
    keyword = _CLASS_KEYWORD.get(cls.get("type", "class"), "class")
    cid = cls["id"]
    name = cls.get("name", cid)
    # Relationships reference classes by id, not name (see _rel_line). When the
    # LLM gives a class a domain name distinct from its GoF-role id (e.g.
    # name="PaymentAdapter", id="Adapter"), alias the id so PlantUML resolves
    # the relationship to this same box instead of drawing an orphan node.
    alias = f" as {cid}" if name != cid else ""
    stereo = f" <<{stereotype}>>" if stereotype else ""
    body = [f"  {m}" for m in cls.get("attributes", [])] + \
           [f"  {m}" for m in cls.get("methods", [])]
    # Quoted: this local PlantUML build (1.2024.3) fails to parse an unquoted
    # `class Name as alias` declaration — `class "Name" as alias` is unaffected.
    return [f'{keyword} "{name}"{alias}{stereo} {{', *body, "}"]


def _rel_line(rel: dict) -> str:
    arrow = _ARROWS.get(rel["type"], "-->")
    line = f"{rel['sourceId']} {arrow} {rel['targetId']}"
    label = rel.get("label", "")
    return line + (f" : {label}" if label else "")


def _active_patterns(model: dict) -> set[str]:
    patterns = model.get("patterns")
    if isinstance(patterns, list):
        return set(patterns)
    return {model.get("pattern", "")}


def _find_singleton_id(model: dict) -> str | None:
    """Find the Singleton class — the one exposing getInstance() in its methods."""
    for cls in model.get("classes", []):
        if any("getinstance" in m.lower() for m in cls.get("methods", [])):
            return cls["id"]
    return None


def to_plantuml(model: dict) -> str:
    pattern = model.get("pattern", "")
    lines = ["@startuml"]

    if pattern:
        lines += [f"title GoF Pattern : {pattern}", "",
                  "note as GoFLabel", f"  **<<{pattern}>>**", "end note", ""]

    active = _active_patterns(model)
    roles: dict[str, str] = {}
    for p in active:
        if p in _ROLE_LABELS:
            roles = _infer_roles(model, _ROLE_LABELS[p])
            break

    if "Singleton" in active:
        sid = _find_singleton_id(model)
        if sid and sid not in roles:
            roles[sid] = "Singleton"

    for cls in model.get("classes", []):
        lines += _cls_lines(cls, roles.get(cls["id"], ""))

    lines.append("")

    for rel in model.get("relationships", []):
        lines.append(_rel_line(rel))

    if pattern:
        primary = _primary_class_id(model, pattern)
        if primary:
            lines.append(f"GoFLabel .. {primary}")

    lines.append("@enduml")
    return "\n".join(lines)
