"""Runtime configuration, read from environment variables with local defaults."""
from __future__ import annotations

import os
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_DIR.parent.parent
DATA_DIR = REPO_ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
LEXICON_DIR = DATA_DIR / "lexicon"
SHARED_SCHEMA_DIR = REPO_ROOT / "packages" / "shared" / "schemas"

# The restaurant's own data: empty until a sales CSV is uploaded or calls are taken. The generated sample
# restaurant lives separately in data/seed and is used only by tests and development.
DB_PATH = Path(os.environ.get("TADKA_DB", DATA_DIR / "tadka.sqlite"))

# Restaurant local time zone. Everything is stored in UTC and shown in this zone.
RESTAURANT_TZ = os.environ.get("TADKA_TZ", "Asia/Kolkata")

# Mock PoS behaviour. Failure rate is a probability between 0 and 1.
POS_FAILURE_RATE = float(os.environ.get("TADKA_POS_FAILURE_RATE", "0"))
POS_MIN_LATENCY_MS = int(os.environ.get("TADKA_POS_MIN_LATENCY_MS", "200"))
POS_MAX_LATENCY_MS = int(os.environ.get("TADKA_POS_MAX_LATENCY_MS", "800"))

# Seed the upsell sampler from the call id so a recorded call replays identically (tests, demos).
DETERMINISTIC = os.environ.get("TADKA_DETERMINISTIC", "0") == "1"

NLU_MODEL_PATH = Path(os.environ.get("TADKA_INTENT_MODEL", API_DIR / "nlu" / "models" / "intent.joblib"))
SAMPLES_DIR = DATA_DIR / "samples"

# Load the built-in restaurant menu (no orders) into an empty database at startup, so the Call desk
# works straight away. Sales CSV uploads then only bring in order history for Analytics.
PRELOAD_MENU = os.environ.get("TADKA_PRELOAD_MENU", "1") == "1"

# Natural offline voice (Piper). Files: data/models/piper/<voice>.onnx and <voice>.onnx.json.
PIPER_DIR = Path(os.environ.get("TADKA_PIPER_DIR", DATA_DIR / "models" / "piper"))
PIPER_VOICE_HI = os.environ.get("TADKA_VOICE_HI", "hi_IN-priyamvada-medium.onnx")
PIPER_VOICE_EN = os.environ.get("TADKA_VOICE_EN", "en_US-lessac-medium.onnx")
