# plot_understanding_gates.py
#
# Visualizes, per iteration, whether each of is_understanding_event()'s three
# independent gates (Phi_i, Rg, energy) stays inside its threshold "surface" —
# not just the final AND verdict already stored in the CSV's Understanding_Event
# column, but each gate individually, since Understanding_Reason only names the
# FIRST gate that failed (short-circuit) and hides whether a later gate would
# also have failed.
#
# Recomputes the energy gate's threshold exactly as gof/metamodel.py::
# is_understanding_event() does: 2x the median of the session's own PRIOR
# accepted-iteration energies (warmup included, rejected excluded) — not a
# fixed constant, so it's plotted as a moving line, not a flat one.
#
# rg_floor isn't stored in the CSV (it depends on --mlx vs local/remote at run
# time, see benchmark_gof.py), so it must be passed in with --rg-floor to match
# whatever the run actually used, or the per-gate Rg verdict below will disagree
# with the CSV's own Understanding_Event — the script checks for that and warns.

import argparse
import csv
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

PASS_COLOR = "tab:green"
FAIL_COLOR = "tab:red"
REJECTED_COLOR = "tab:gray"
MARKERS = {"WARMUP": "^", "ACCEPTED": "o"}


def _read_rows(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _energy_gate(energy_j: float, prior_energies: list[float], ceiling_ratio: float) -> tuple[bool, float]:
    """Mirrors gof/metamodel.py::is_understanding_event()'s energy gate exactly:
    baseline is the median of prior accepted energies, or this iteration's own
    energy if there is no prior history yet (which makes the gate trivially
    pass on the very first accepted iteration)."""
    baseline = statistics.median(prior_energies) if prior_energies else energy_j
    threshold = ceiling_ratio * baseline
    return energy_j <= threshold, threshold


def _plot_gate(ax, iterations, values, statuses, floor, ylabel, higher_is_better=True):
    ax.axhline(floor, color="black", linestyle="--", linewidth=1, alpha=0.6)
    span = ax.get_xlim()
    if higher_is_better:
        ax.axhspan(floor, max(values + [floor]) * 1.1, color=PASS_COLOR, alpha=0.06)
    else:
        ax.axhspan(0, floor, color=PASS_COLOR, alpha=0.06)
    ax.plot(iterations, values, color="0.4", linewidth=1, zorder=1)
    for it, val, status in zip(iterations, values, statuses):
        passed = (val >= floor) if higher_is_better else (val <= floor)
        ax.scatter([it], [val], color=PASS_COLOR if passed else FAIL_COLOR,
                   marker=MARKERS[status], s=70, zorder=2, edgecolors="black", linewidths=0.5)
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)


def plot_gates(csv_path: str, out_path: str | None, show: bool,
                phi_floor: float, rg_floor: float, energy_ceiling_ratio: float) -> str:
    rows = _read_rows(csv_path)
    if not rows:
        raise ValueError(f"{csv_path} has no data rows")

    accepted = [r for r in rows if r["Status"] in ("WARMUP", "ACCEPTED")]
    rejected_iters = [int(r["Iteration"]) for r in rows if r["Status"] == "REJECTED"]
    if not accepted:
        raise ValueError(f"{csv_path} has no ACCEPTED/WARMUP rows to plot")

    iterations = [int(r["Iteration"]) for r in accepted]
    statuses = [r["Status"] for r in accepted]
    phi_values = [float(r["Phi_i"]) for r in accepted]
    rg_values = [float(r["Rg"]) for r in accepted]
    energy_values = [float(r["Energy_J"]) for r in accepted]

    energy_thresholds = []
    energy_pass = []
    prior_energies: list[float] = []
    for e in energy_values:
        passed, threshold = _energy_gate(e, prior_energies, energy_ceiling_ratio)
        energy_pass.append(passed)
        energy_thresholds.append(threshold)
        prior_energies.append(e)

    phi_pass = [v >= phi_floor for v in phi_values]
    rg_pass = [v >= rg_floor for v in rg_values]
    recomputed_verdict = [p and r and e for p, r, e in zip(phi_pass, rg_pass, energy_pass)]
    csv_verdict = [r["Understanding_Event"].strip().lower() == "true" for r in accepted]

    mismatches = [it for it, mine, theirs in zip(iterations, recomputed_verdict, csv_verdict) if mine != theirs]
    if mismatches:
        print(f"WARNING: recomputed verdict disagrees with the CSV's Understanding_Event on "
              f"iteration(s) {mismatches} — check that --rg-floor ({rg_floor}) matches what this "
              f"run actually used (0.3 for local/remote, 0.05 for --mlx).")

    fig, (ax_phi, ax_rg, ax_energy, ax_verdict) = plt.subplots(
        4, 1, figsize=(10, 10), sharex=True,
        gridspec_kw={"height_ratios": [3, 3, 3, 1]},
    )

    _plot_gate(ax_phi, iterations, phi_values, statuses, phi_floor,
               f"Phi_i (floor={phi_floor})", higher_is_better=True)
    _plot_gate(ax_rg, iterations, rg_values, statuses, rg_floor,
               f"Rg (floor={rg_floor})", higher_is_better=True)

    ax_energy.plot(iterations, energy_thresholds, color="black", linestyle="--", linewidth=1, alpha=0.6,
                   label=f"{energy_ceiling_ratio}x running median")
    ax_energy.plot(iterations, energy_values, color="0.4", linewidth=1, zorder=1)
    for it, val, status, passed in zip(iterations, energy_values, statuses, energy_pass):
        ax_energy.scatter([it], [val], color=PASS_COLOR if passed else FAIL_COLOR,
                          marker=MARKERS[status], s=70, zorder=2, edgecolors="black", linewidths=0.5)
    ax_energy.set_ylabel("Energy_J")
    ax_energy.legend(loc="upper left", fontsize="small")
    ax_energy.grid(True, alpha=0.3)

    for it in rejected_iters:
        for ax in (ax_phi, ax_rg, ax_energy):
            ax.axvline(it, color=REJECTED_COLOR, linestyle=":", linewidth=1.5, alpha=0.7)

    verdict_colors = [PASS_COLOR if v else FAIL_COLOR for v in csv_verdict]
    ax_verdict.scatter(iterations, [0] * len(iterations), color=verdict_colors, marker="s", s=200)
    for it in rejected_iters:
        ax_verdict.scatter([it], [0], color=REJECTED_COLOR, marker="x", s=120)
    for r, it in zip(accepted, iterations):
        if r["Understanding_Reason"] not in ("conditional_understanding", ""):
            ax_verdict.annotate(r["Understanding_Reason"], (it, 0), textcoords="offset points",
                                xytext=(0, -18), ha="center", fontsize=7, rotation=0)
    ax_verdict.set_ylabel("Verdict")
    ax_verdict.set_yticks([])
    ax_verdict.set_xlabel("Iteration")
    ax_verdict.set_xticks(sorted(set(iterations) | set(rejected_iters)))

    session = rows[0].get("Session", "")
    mode = rows[0].get("Mode", "")
    fig.suptitle(f"{session} — {mode} — understanding-event gates vs iteration\n({Path(csv_path).name})")
    fig.tight_layout()

    if out_path is None:
        out_path = str(Path(csv_path).with_name(Path(csv_path).stem + "_gates.png"))
    fig.savefig(out_path, dpi=150)
    print(f"Saved: {out_path}")

    if show:
        plt.show()
    plt.close(fig)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot the three is_understanding_event() gates (Phi_i, Rg, energy) vs iteration.")
    parser.add_argument("csv_path", help="Path to a results/*.csv file produced by benchmark_gof.py")
    parser.add_argument("--out", default=None, help="Output image path (default: <csv_name>_gates.png next to the CSV)")
    parser.add_argument("--show", action="store_true", help="Also display the plot interactively")
    parser.add_argument("--phi-floor", type=float, default=6.0, help="Phi_i gate floor (default: 6.0)")
    parser.add_argument("--rg-floor", type=float, default=0.3,
                        help="Rg gate floor used by this run — 0.3 for local/remote, 0.05 for --mlx (default: 0.3)")
    parser.add_argument("--energy-ceiling-ratio", type=float, default=2.0,
                        help="Energy gate ceiling as a multiple of the running median (default: 2.0)")
    args = parser.parse_args()

    plot_gates(args.csv_path, args.out, args.show, args.phi_floor, args.rg_floor, args.energy_ceiling_ratio)


if __name__ == "__main__":
    main()
