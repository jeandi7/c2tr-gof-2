# benchmark_gof.py
#
# CIITR Benchmark: LLM alone or LLM + Active Inference on GoF class diagram generation.
# Each run executes exactly ONE mode — the two are never run head-to-head, since
# LLM_AI's own reasoning calls (analyze + update_wiki) make its energy structurally
# higher than LLM_ONLY's single call, and a forced comparison would mostly measure
# "3 LLM calls cost more than 1" rather than anything about diagram quality.
#
# --ai false : objective -> prompt -> LLM -> JSON -> validate -> PlantUML
# --ai true  : wiki agent (own LLM calls: analyze + update_wiki) -> enriched
#              prompt -> LLM -> JSON -> validate -> PlantUML
#
# Within LLM_AI, Ci = Phi * Rg and CPJ = Ci/E are logged for reference (Rg is the
# agent's empirical rhythmic coherence — see agent_ai/gof_ai_agent.py).
#
# Usage:
#   python benchmark_gof.py --session GOF-001
#   python benchmark_gof.py --session GOF-001 --remote
#   python benchmark_gof.py --ai false
#   python benchmark_gof.py

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime

import yaml

from agent_ai.gof_ai_agent import GofAIAgent
from agent_llm.llm import call_llm
from gof.generator import build_prompt
from gof.metamodel import validate_gof, compute_phi, is_understanding_event
from gof.plantuml import to_plantuml
from liss import LISS
from metrics.export import init_gof_csv, append_gof_row, GofMetrics
from psis import PSIS

CPU_WATTS = 28.0   # generic CPU (Ollama local or remote)
M3_WATTS = 12.0    # Apple M-series Neural Engine + GPU (MLX)
MAX_ITER = 3


def _watts(use_mlx: bool) -> float:
    return M3_WATTS if use_mlx else CPU_WATTS
SESSIONS_FILE = "sessions_gof.yaml"

_liss = LISS.default()


@dataclass
class ModeResult:
    best_score: float           # best per-iteration Phi/E — informational only, not for cross-mode ranking
    best_plantuml: str
    best_iter: int
    total_energy: float         # J, summed over non-warmup iterations (accepted + rejected)
    n_accepted: int
    total_comprehension: float  # sum of Phi over accepted non-warmup iterations
    n_iters: int                # non-warmup iterations run
    total_cpj: float = 0.0      # sum of CPJ (Ci/E) over accepted non-warmup iterations — reference only
    n_understanding: int = 0    # non-warmup iterations that passed is_understanding_event

    @property
    def avg_comprehension(self) -> float:
        return self.total_comprehension / self.n_accepted if self.n_accepted else 0.0

    @property
    def avg_energy(self) -> float:
        return self.total_energy / self.n_iters if self.n_iters else 0.0

    @property
    def avg_cpj(self) -> float:
        return self.total_cpj / self.n_accepted if self.n_accepted else 0.0


def load_sessions() -> list[dict]:
    with open(SESSIONS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_json(raw: str) -> str:
    start = None
    stack = []
    for i, c in enumerate(raw):
        if c in "{[":
            if start is None:
                start = i
            stack.append(c)
        elif c in "}]":
            if not stack:
                continue
            stack.pop()
            if not stack:
                return raw[start:i + 1]
    raise ValueError("No complete JSON found in LLM response")


def _call_and_parse(liss: LISS, psis: PSIS, local: bool, use_mlx: bool = False):
    """Returns (model_or_None, energy_j, errors, raw, plantuml)."""
    prompt = build_prompt(liss, psis)
    raw, elapsed = call_llm(prompt, local=local, use_mlx=use_mlx)
    energy = elapsed * _watts(use_mlx)

    if not raw:
        return None, energy, ["Empty LLM response"], raw, ""

    if raw.count("{") != raw.count("}"):
        return None, energy, ["Unbalanced braces — incomplete JSON"], raw, ""

    try:
        raw_json = extract_json(raw)
        model = json.loads(raw_json)
    except ValueError as exc:
        return None, energy, [f"JSON parse error: {exc}"], raw, ""

    errors = validate_gof(model)
    if errors:
        return None, energy, errors, raw, ""

    return model, energy, [], raw, to_plantuml(model)


def _pattern_name(ai_context: dict | None, model: dict | None) -> str:
    if model:
        patterns = model.get("patterns")
        if isinstance(patterns, list) and len(patterns) > 1:
            return "+".join(patterns)
        p = model.get("pattern", "")
        if p:
            return p
    if ai_context:
        return ai_context["pattern_name"]
    return ""


def _save_raw(raw_dir: str, session_id: str, mode: str, iteration: int, raw: str):
    path = os.path.join(raw_dir, f"{session_id}_{mode}_iter{iteration}.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw or "")


def _run_iteration(
    liss: LISS,
    psis: PSIS,
    ai_agent: GofAIAgent | None,
    use_ai: bool,
    local: bool,
    csv_path: str,
    raw_dir: str,
    accepted_energies: list[float],
    agent_energy: float = 0.0,
    warmup: bool = False,
    use_mlx: bool = False,
) -> tuple[float, float, str, float, float, bool]:
    """Run one iteration. Returns (phi_e, energy_j, plantuml, comprehension, cpj,
    understanding_event)."""
    mode = "LLM_AI" if psis.ai_context else "LLM_ONLY"
    model, energy, errors, raw, plantuml = _call_and_parse(liss, psis, local, use_mlx)
    energy += agent_energy  # cost of the wiki agent's own analyze() LLM call

    _save_raw(raw_dir, psis.session_id, mode, psis.iteration, raw)

    pattern = _pattern_name(psis.ai_context, model)
    warmup_tag = " [warmup]" if warmup else ""

    if model is None:
        if use_ai and ai_agent:
            ai_agent.flush_incomplete_cycle(warmup=warmup)
        rg = ai_agent.rg_proxy if (use_ai and ai_agent) else 0.0
        metrics = GofMetrics(energy_j=energy, rg=rg, understanding_reason="rejected")
        append_gof_row(csv_path, psis.session_id, mode, psis.iteration,
                       False, metrics, pattern, errors, warmup=warmup)
        print(f"    iter {psis.iteration}: REJECTED{warmup_tag}  ({errors[0] if errors else 'unknown'})")
        return 0.0, energy, "", 0, 0.0, False

    # Feed the generated diagram back to the wiki agent — CIITR continuous learning
    if use_ai and ai_agent:
        wiki_elapsed = ai_agent.update_wiki(psis.objective, model, warmup=warmup)
        energy += wiki_elapsed * _watts(use_mlx)

    rg = ai_agent.rg_proxy if (use_ai and ai_agent) else 0.0
    comprehension = compute_phi(model)
    phi_e = comprehension / (energy + 1e-12)
    ci    = comprehension * rg
    cpj   = ci / (energy + 1e-12)
    understood, reason = is_understanding_event(comprehension, rg, energy, accepted_energies, rg_floor=0.05 if use_mlx else 0.3)
    accepted_energies.append(energy)
    metrics = GofMetrics(
        energy_j=energy, comprehension=comprehension, phi_e=phi_e, ci=ci, cpj=cpj, rg=rg,
        understanding_event=understood, understanding_reason=reason,
    )
    append_gof_row(csv_path, psis.session_id, mode, psis.iteration,
                   True, metrics, pattern, [], warmup=warmup)
    print(f"    iter {psis.iteration}: ACCEPTED{warmup_tag}  E={energy:.3f}J  Phi={comprehension:.2f}  "
          f"(Phi/E)={phi_e*1000:.4f}/kJ  Rg={rg:.4f}  CPJ=(Phi/E)xRg={cpj*1000:.4f}/kJ  pattern={pattern}  "
          f"understanding_event={understood} ({reason})")
    return phi_e, energy, plantuml, comprehension, cpj, understood


@dataclass
class _ModeAccumulator:
    """Running totals across a mode's iterations — kept off _run_mode's stack
    to keep its cognitive complexity down (Sonar S3776)."""
    best_score: float = 0.0
    best_plantuml: str = ""
    best_iter: int = 0
    total_energy: float = 0.0
    total_comprehension: float = 0.0
    total_cpj: float = 0.0
    n_accepted: int = 0
    n_iters: int = 0
    n_understanding: int = 0
    last_cpj: float = 0.0
    last_comprehension: float = 0.0


def _record_iteration(
    acc: _ModeAccumulator,
    iteration: int,
    is_warmup: bool,
    phi_e: float,
    energy: float,
    plantuml: str,
    comprehension: float,
    cpj: float,
    understood: bool,
) -> None:
    """Folds one iteration's outcome into the running mode totals. last_cpj/
    last_comprehension feed the *next* iteration's PSIS regardless of warmup;
    everything else is excluded from warmup iterations."""
    if comprehension > 0:
        acc.last_cpj = cpj
        acc.last_comprehension = comprehension

    if is_warmup:
        return

    acc.n_iters += 1
    acc.total_energy += energy
    if comprehension > 0:
        acc.n_accepted += 1
        acc.total_comprehension += comprehension
        acc.total_cpj += cpj
    if understood:
        acc.n_understanding += 1
    if phi_e > acc.best_score:
        acc.best_score = phi_e
        acc.best_plantuml = plantuml
        acc.best_iter = iteration


def _run_mode(
    session_data: dict,
    ai_agent: GofAIAgent | None,
    local: bool,
    use_ai: bool,
    csv_path: str,
    mode: str,
    raw_dir: str,
    warmup_iters: int = 1,
    max_iter: int = MAX_ITER,
    use_mlx: bool = False,
):
    objective = session_data["objective"].strip()
    if ai_agent:
        ai_agent.reset()

    acc = _ModeAccumulator()
    accepted_energies: list[float] = []

    print(f"\n  [{mode}]")

    for iteration in range(1, max_iter + 1):
        is_warmup = iteration <= warmup_iters
        agent_energy = 0.0
        ai_context = None
        if use_ai and ai_agent:
            ai_context, agent_elapsed = ai_agent.analyze(objective)
            agent_energy = agent_elapsed * _watts(use_mlx)

        psis = PSIS(
            session_id=session_data["session_id"],
            objective=objective,
            iteration=iteration,
            last_cpj=acc.last_cpj,
            last_comprehension=acc.last_comprehension,
            ai_context=ai_context,
        )

        phi_e, energy, plantuml, comprehension, cpj, understood = _run_iteration(
            _liss, psis, ai_agent, use_ai, local, csv_path, raw_dir, accepted_energies,
            agent_energy, warmup=is_warmup, use_mlx=use_mlx,
        )

        _record_iteration(acc, iteration, is_warmup, phi_e, energy, plantuml,
                           comprehension, cpj, understood)

    result = ModeResult(acc.best_score, acc.best_plantuml, acc.best_iter, acc.total_energy,
                         acc.n_accepted, acc.total_comprehension, acc.n_iters, acc.total_cpj,
                         acc.n_understanding)
    status = "ACCEPTED" if acc.n_accepted > 0 else "ALL_REJECTED"
    print(f"    SUMMARY: {status}  best_iter={acc.best_iter}  "
          f"avg_Phi={result.avg_comprehension:.2f}  avg_energy={result.avg_energy:.3f}J/iter  "
          f"avg_CPJ=(Phi/E)xRg={result.avg_cpj*1000:.4f}/kJ (reference only)  "
          f"understanding_events={acc.n_understanding}/{acc.n_iters}")
    return result


def _write_puml(session_id: str, suffix: str, plantuml: str) -> None:
    puml_path = os.path.join("results", f"{session_id}_{suffix}.puml")
    with open(puml_path, "w", encoding="utf-8") as f:
        f.write(plantuml)
    print(f"  PlantUML ({suffix}): {puml_path}")


def _print_ai_status(ai_agent: GofAIAgent) -> None:
    ctx = ai_agent.get_pattern_context()
    rg = ai_agent.rg_proxy
    confidence = "N/A (parse failed)" if ctx["confidence"] is None else f"{ctx['confidence']:.2f}"
    print(f"  AI detected : {ctx['pattern_name']}  (confidence={confidence})"
          f"  top3={ctx['top3']}")
    print(f"  Rg (rhythmic coherence): {rg:.4f}  |  Rg > 0: {rg > 0}"
          f"  — inference rhythm {'stable' if rg > 0 else 'not yet established'}")


def run_session(
    session_data: dict,
    use_ai: bool,
    local: bool,
    warmup_iters: int = 1,
    max_iter: int = MAX_ITER,
    use_mlx: bool = False,
):
    """Runs exactly one mode: LLM_AI if use_ai else LLM_ONLY. The two modes are
    never run together — no head-to-head comparison is computed or printed."""
    ai_agent = GofAIAgent(local=local, use_mlx=use_mlx) if use_ai else None
    mode = "LLM_AI" if use_ai else "LLM_ONLY"

    os.makedirs("results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = os.path.join("results", f"{session_data['session_id']}_gof_{timestamp}.csv")
    init_gof_csv(csv_path)

    raw_dir = os.path.join("results", "raw")
    os.makedirs(raw_dir, exist_ok=True)

    if use_mlx:
        llm_label = "LOCAL MLX (Apple Silicon)"
    elif local:
        llm_label = "LOCAL llama3.1:8b"
    else:
        llm_label = "REMOTE devstral-small-2:24b"
    print(f"\n{'='*60}")
    print(f"Session  : {session_data['session_id']}")
    print(f"Objective: {session_data['objective'].strip()[:80]}...")
    print(f"LLM      : {llm_label}  |  Mode: {mode}")
    print(f"{'='*60}")

    result = _run_mode(session_data, ai_agent, local, use_ai, csv_path, mode, raw_dir,
                        warmup_iters, max_iter, use_mlx)

    if use_ai and ai_agent:
        print()
        _print_ai_status(ai_agent)

    print(f"  CPJ: {result.avg_cpj*1000:.4f}/kJ")

    if mode == "LLM_ONLY":
        print(f"  Understanding events: {result.n_understanding}/{result.n_iters}  "
              f"— structurally 0 in LLM_ONLY (Rg forced to 0, no rhythm to establish)")
    else:
        print(f"  Understanding events: {result.n_understanding}/{result.n_iters} iterations "
              f"satisfied Phi>=6, Rg>=0.3 and energy within 2x the session's own median "
              f"(see Understanding_Event/Understanding_Reason columns in the CSV)")

    if result.best_plantuml:
        _write_puml(session_data["session_id"], "AI" if use_ai else "LLM", result.best_plantuml)

    print(f"\nResults: {csv_path}")
    _generate_plots(csv_path, use_mlx)


def _generate_plots(csv_path: str, use_mlx: bool) -> None:
    """Best-effort: renders the Rg/CPJ and understanding-gates PNGs for this
    run's CSV. matplotlib is an optional dependency (not in requirements_mac.txt
    nor a Windows requirements file) — its absence must not fail the benchmark
    run itself, so import and plotting errors are caught and reported, not
    raised."""
    try:
        from plot_rg_cpj import plot_rg_cpj
        from plot_understanding_gates import plot_gates
    except ImportError as e:
        print(f"  (skipping plots — {e}; `pip install matplotlib` to enable)")
        return

    rg_floor = 0.05 if use_mlx else 0.3
    try:
        plot_rg_cpj(csv_path, None, show=False)
    except ValueError as e:
        print(f"  (skipping Rg/CPJ plot — {e})")
    try:
        plot_gates(csv_path, None, show=False, phi_floor=6.0, rg_floor=rg_floor, energy_ceiling_ratio=2.0)
    except ValueError as e:
        print(f"  (skipping understanding-gates plot — {e})")


def _str2bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def main():
    parser = argparse.ArgumentParser(description="CIITR GoF benchmark: LLM vs LLM+AI")
    parser.add_argument("--session", default=None,
                        help="session_id from sessions_gof.yaml (default: run all)")
    parser.add_argument("--remote", action="store_true", help="Use remote LLM")
    parser.add_argument("--mlx", action="store_true",
                        help="Use MLX (Apple Silicon, local) instead of Ollama — requires macOS "
                             "on M-series and `pip install mlx-lm`; incompatible with --remote")
    parser.add_argument("--ai", type=_str2bool, default=True,
                        help="true = LLM_AI (agent), false = LLM_ONLY (default: true)")
    parser.add_argument("--warmup-iters", type=int, default=1,
                        help="Number of warmup iterations to exclude from stats (default: 1)")
    parser.add_argument("--max-iters", type=int, default=MAX_ITER,
                        help=f"Total iterations per mode (default: {MAX_ITER})")
    args = parser.parse_args()

    if args.mlx and args.remote:
        parser.error("--mlx is local-only, incompatible with --remote")

    sessions = load_sessions()

    if args.session:
        matching = [s for s in sessions if s["session_id"] == args.session]
        if not matching:
            print(f"Session '{args.session}' not found in {SESSIONS_FILE}")
            return
        sessions_to_run = matching
    else:
        sessions_to_run = sessions

    for session in sessions_to_run:
        run_session(session, use_ai=args.ai, local=not args.remote,
                    warmup_iters=args.warmup_iters, max_iter=args.max_iters, use_mlx=args.mlx)


if __name__ == "__main__":
    main()
