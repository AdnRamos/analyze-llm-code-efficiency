"""
Study configuration: LLM provider, models and generation parameters, and credentials.

Values come from `config.json` at the repository root (not versioned; copy `config.example.json`), and can be
overridden by environment variables. Missing keys fall back to the configuration used in the paper.
"""
import json
import os

from .paths import ROOT

# The 11 models of the paper (Groq Cloud ids, July-September 2025). Most of them were later retired by Groq;
# see REPRODUCING.md, "What will differ from the paper".
STUDY_MODELS = [
    "allam-2-7b",
    "deepseek-r1-distill-llama-70b",
    "gemma2-9b-it",
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "moonshotai/kimi-k2-instruct",
    "qwen/qwen3-32b",
]

DEFAULTS = {
    "provider": "groq",          # "groq" or "openai_compatible" (any OpenAI-compatible server: vLLM, Ollama, ...)
    "base_url": None,            # required for "openai_compatible", e.g. http://localhost:8000/v1
    "api_key": None,
    "models": STUDY_MODELS,
    "temperature": 0,
    "leetcode_user": None,       # only for pipeline/5_submit/submit_missing.py (login fallback)
    "leetcode_pass": None,
}

ENV = {"provider": "LLM_PROVIDER", "base_url": "LLM_BASE_URL", "api_key": "LLM_API_KEY",
       "leetcode_user": "LC_LOGIN_USER", "leetcode_pass": "LC_LOGIN_PASS"}


def load_config(path=None):
    cfg = dict(DEFAULTS)
    p = path or ROOT / "config.json"
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            cfg.update({k: v for k, v in json.load(f).items() if v not in (None, "")})
    for key, var in ENV.items():
        if os.getenv(var):
            cfg[key] = os.getenv(var)
    if os.getenv("LLM_MODELS"):
        cfg["models"] = [m.strip() for m in os.getenv("LLM_MODELS").split(",") if m.strip()]
    if cfg["provider"] == "groq_cloud":   # name used in 2025
        cfg["provider"] = "groq"
    return cfg
