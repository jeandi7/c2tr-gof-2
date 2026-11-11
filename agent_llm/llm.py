# agent_llm/llm.py

import subprocess
import requests
import time
import threading
import psutil

OLLAMA_BASE_URL = "https://yourllm"
OLLAMA_MODEL_LOCAL = "llama3.1:8b"
OLLAMA_MODEL_REMOTE = "devstral-small-2:24b"

# MLX — Apple Silicon (M-series Neural Engine + GPU). Optional: requires `pip
# install mlx-lm` and macOS on Apple Silicon; unused unless use_mlx=True.
MLX_MODEL_ID = "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"

_mlx_cache: tuple | None = None  # (model, tokenizer) — loaded once per process


def _ensure_mlx() -> tuple:
    global _mlx_cache
    if _mlx_cache is None:
        from mlx_lm import load
        print(f"  Loading MLX model {MLX_MODEL_ID} (first call — cached for the session)...")
        _mlx_cache = load(MLX_MODEL_ID)
        print("  MLX model ready.")
    return _mlx_cache


def _call_mlx(prompt: str) -> tuple[str, float]:
    """Local inference via mlx-lm on Apple Silicon Neural Engine + GPU."""
    from mlx_lm import generate
    model, tokenizer = _ensure_mlx()

    # Apply the model's chat template so the instruct model behaves correctly.
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        formatted = tokenizer.apply_chat_template(
            [{"role": "user", "content": prompt}],
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        formatted = prompt

    wall_start = time.perf_counter()
    response = generate(
        model,
        tokenizer,
        prompt=formatted,
        max_tokens=2000,
        verbose=False,
    )
    elapsed = time.perf_counter() - wall_start

    print("MLX inference (M-series) = OK")
    print(f"MLX Model                = {MLX_MODEL_ID}")
    print(f"Elapsed wall time        = {elapsed:.2f} s")
    return response.strip(), elapsed


def call_llm(prompt: str, local: bool = True, use_mlx: bool = False) -> tuple[str, float]:
    """
    Returns:
        raw_output (str)
        cpu_seconds (float)  — wall_time × avg_cpu% for local Ollama, wall_time
                               for MLX or remote
    """

    # -------- MLX MODE (Apple Silicon — Neural Engine + GPU) --------
    if local and use_mlx:
        return _call_mlx(prompt)

    # -------- LOCAL MODE (Ollama subprocess for example) --------
    if local:
        cpu_samples = []
        stop_event = threading.Event()

        def _monitor():
            while not stop_event.is_set():
                cpu_samples.append(psutil.cpu_percent(interval=0.5))

        monitor_thread = threading.Thread(target=_monitor, daemon=True)
        wall_start = time.perf_counter()
        monitor_thread.start()

        try:
            result = subprocess.run(
                ["ollama", "run", OLLAMA_MODEL_LOCAL],
                input=prompt,
                encoding="utf-8",
                capture_output=True,
                timeout=1500,
            )
        except Exception as e:
            print(f"LLM local error: {e}")
            stop_event.set()
            return "", 0.0
        finally:
            stop_event.set()
            monitor_thread.join(timeout=2)

        elapsed = time.perf_counter() - wall_start
        avg_cpu_pct = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 50.0
        cpu_seconds = elapsed * (avg_cpu_pct / 100.0)

        print("LLM Ollama (local)      = OK")
        print(f"LLM Model               = {OLLAMA_MODEL_LOCAL}")
        print(f"Elapsed wall time       = {elapsed:.2f} s")
        print(f"Avg CPU utilization     = {avg_cpu_pct:.1f} %")
        return result.stdout.strip(), cpu_seconds

    # -------- REMOTE MODE (API) --------
    else:
        start = time.perf_counter()
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL_REMOTE,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 2000,
                        "temperature": 0.2,
                        "repeat_penalty": 1.1,
                        "top_p": 0.9,
                    },
                },
                timeout=1500,
            )
            response.raise_for_status()
            result = response.json().get("response", "").strip()
            cpu_seconds = time.perf_counter() - start

            print("LLM Ollama (remote)     = OK")
            print(f"LLM URL                 = {OLLAMA_BASE_URL}")
            print(f"LLM Model               = {OLLAMA_MODEL_REMOTE}")
            print(f"Elapsed wall time       = {cpu_seconds:.2f} s")
            return result, cpu_seconds

        except Exception as e:
            print(f"LLM remote error: {e}")
            return "", 0.0
