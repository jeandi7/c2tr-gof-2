# plot_rg_cpj.py
#
# Plots Rg and CPJ against iteration number from one benchmark_gof.py CSV
# (e.g. results/GOF-009_gof_20260806_104242.csv). Rg and CPJ live on separate
# Y axes since their scales aren't comparable (Rg in [0,1], CPJ varies ~10x
# across sessions) — the point is to see how the two curves move together,
# not to compare absolute values.

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt

STATUS_MARKERS = {"WARMUP": "^", "ACCEPTED": "o", "REJECTED": "x"}
RG_COLOR = "tab:blue"
CPJ_COLOR = "tab:orange"


def _read_rows(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def plot_rg_cpj(csv_path: str, out_path: str | None, show: bool) -> str:
    rows = _read_rows(csv_path)
    if not rows:
        raise ValueError(f"{csv_path} has no data rows")

    iterations = [int(r["Iteration"]) for r in rows]
    rg_values = [float(r["Rg"]) for r in rows]
    # CSV stores CPJ in /J; the console prints it x1000 as /kJ (see benchmark_gof.py's
    # "CPJ=...{cpj*1000:.4f}/kJ" prints) — match that convention here.
    cpj_values = [float(r["CPJ"]) * 1000 for r in rows]
    statuses = [r["Status"] for r in rows]

    fig, ax_rg = plt.subplots(figsize=(9, 5))
    ax_cpj = ax_rg.twinx()

    ax_rg.plot(iterations, rg_values, color=RG_COLOR, linewidth=1.5, zorder=1)
    ax_cpj.plot(iterations, cpj_values, color=CPJ_COLOR, linewidth=1.5, zorder=1)

    for status, marker in STATUS_MARKERS.items():
        xs = [i for i, s in zip(iterations, statuses) if s == status]
        if xs:
            ax_rg.scatter(xs, [rg_values[iterations.index(i)] for i in xs],
                          color=RG_COLOR, marker=marker, s=60, zorder=2,
                          label=f"Rg ({status.lower()})")
            ax_cpj.scatter(xs, [cpj_values[iterations.index(i)] for i in xs],
                           color=CPJ_COLOR, marker=marker, s=60, zorder=2,
                           label=f"CPJ ({status.lower()})")

    ax_rg.set_xlabel("Iteration")
    ax_rg.set_ylabel("Rg (rhythmic coherence)", color=RG_COLOR)
    ax_cpj.set_ylabel("CPJ = (Phi/E) x Rg  [/kJ]", color=CPJ_COLOR)
    ax_rg.tick_params(axis="y", labelcolor=RG_COLOR)
    ax_cpj.tick_params(axis="y", labelcolor=CPJ_COLOR)
    ax_rg.set_xticks(iterations)
    ax_rg.grid(True, alpha=0.3)

    session = rows[0].get("Session", "")
    mode = rows[0].get("Mode", "")
    ax_rg.set_title(f"{session} — {mode} — Rg & CPJ vs iteration\n({Path(csv_path).name})")

    handles_rg, labels_rg = ax_rg.get_legend_handles_labels()
    handles_cpj, labels_cpj = ax_cpj.get_legend_handles_labels()
    ax_rg.legend(handles_rg + handles_cpj, labels_rg + labels_cpj,
                 loc="upper left", fontsize="small")

    fig.tight_layout()

    if out_path is None:
        out_path = str(Path(csv_path).with_name(Path(csv_path).stem + "_rg_cpj.png"))
    fig.savefig(out_path, dpi=150)
    print(f"Saved: {out_path}")

    if show:
        plt.show()
    plt.close(fig)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot Rg and CPJ vs iteration from a benchmark_gof.py CSV.")
    parser.add_argument("csv_path", help="Path to a results/*.csv file produced by benchmark_gof.py")
    parser.add_argument("--out", default=None, help="Output image path (default: <csv_name>_rg_cpj.png next to the CSV)")
    parser.add_argument("--show", action="store_true", help="Also display the plot interactively")
    args = parser.parse_args()

    plot_rg_cpj(args.csv_path, args.out, args.show)


if __name__ == "__main__":
    main()
