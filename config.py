"""Settings. Every value can be overridden with an environment variable (see deploy/override.conf.example)."""
import os
from pathlib import Path


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return int(default)


def _float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


BASE = Path(__file__).resolve().parent
JOBS_DIR = Path(os.environ.get('JOBS_DIR', str(BASE / 'jobs')))

# AI models (Bedrock inference profile IDs). MODEL_SMALL is optional and is used for small chunks.
MODEL = os.environ.get('MODEL', 'eu.anthropic.claude-opus-4-6-v1')
MODEL_SMALL = os.environ.get('MODEL_SMALL', '')
SMALL_FILE_CHARS = _int('SMALL_FILE_CHARS', 4000)
REGION = os.environ.get('AWS_REGION_NAME', 'eu-north-1')

# Speed and rate limits
WORKERS = _int('WORKERS', 1)
MIN_INTERVAL = _float('MIN_INTERVAL', 0.0)      # minimum seconds between AI calls
MAX_CHUNK_CHARS = _int('MAX_CHUNK_CHARS', 12000)  # files larger than this are split into parts

# Prices in USD per million tokens. Fill in from the Bedrock pricing page; 0 hides the cost in the UI.
PRICE_IN_PER_M = _float('PRICE_IN_PER_M', 0)
PRICE_OUT_PER_M = _float('PRICE_OUT_PER_M', 0)

# Safety limits
MAX_UPLOAD_MB = _int('MAX_UPLOAD_MB', 300)
MAX_RUN_TOKENS = _int('MAX_RUN_TOKENS', 600000)   # estimated tokens allowed in one cleaning run

# Which files are pre-selected
SUGGEST_MAX_FILES = _int('SUGGEST_MAX_FILES', 25)
SUGGEST_TOKEN_BUDGET = _int('SUGGEST_TOKEN_BUDGET', 250000)
MIN_FILE_CHARS = _int('MIN_FILE_CHARS', 600)
