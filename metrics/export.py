# metrics/export.py

import csv
from dataclasses import dataclass


@dataclass
class GofMetrics:
    """Per-iteration metrics for one CSV row — grouped to keep append_gof_row's
    parameter count down (Sonar S107)."""
    energy_j: float = 0.0
    comprehension: float = 0.0
    phi_e: float = 0.0
    ci: float = 0.0
    cpj: float = 0.0
    rg: float = 0.0
    understanding_event: bool = False
    understanding_reason: str = ""


def init_gof_csv(filename: str):
    with open(filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Session", "Mode", "Iteration", "Status",
            "Energy_J", "Phi_i", "Phi_E", "Ci", "CPJ", "Rg", "Pattern", "Error",
            "Understanding_Event", "Understanding_Reason",
        ])


def append_gof_row(
    filename: str,
    session: str,
    mode: str,
    iteration: int,
    accepted: bool,
    metrics: GofMetrics,
    pattern: str,
    errors: list,
    warmup: bool = False,
):
    if warmup:
        status = "WARMUP"
    elif accepted:
        status = "ACCEPTED"
    else:
        status = "REJECTED"
    with open(filename, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            session, mode, iteration,
            status,
            round(metrics.energy_j, 6),
            metrics.comprehension,
            round(metrics.phi_e, 8),
            round(metrics.ci, 6),
            round(metrics.cpj, 8),
            round(metrics.rg, 6),
            pattern,
            errors[0] if errors else "",
            metrics.understanding_event,
            metrics.understanding_reason,
        ])
