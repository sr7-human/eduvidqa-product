"""Pytest bootstrap — ensures repo root is on sys.path so `pipeline`, `backend`, etc. import."""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Manual integration scripts (not real pytest tests) — skip collection.
collect_ignore_glob = [
    "tests/test_evaluator_live.py",
]
