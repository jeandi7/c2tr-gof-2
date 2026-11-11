# psis.py — Per-Session Instruction Schema (PSIS) pour le benchmark GoF
# Contexte de session : objectif, itération courante, feedback CPJ inter-itérations, contexte AI.
from dataclasses import dataclass


@dataclass
class PSIS:
    session_id: str
    objective: str
    iteration: int = 1
    last_cpj: float = 0.0
    last_comprehension: float = 0.0
    ai_context: dict | None = None  # None → LLM_ONLY ; dict → LLM_AI
