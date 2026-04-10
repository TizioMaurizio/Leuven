import pytest
from pathlib import Path
import json
import sys

# Ensure tests/ is on the path so test_simulation can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent))

TRACE_CACHE = Path(__file__).resolve().parent / "trace_cache.json"


@pytest.fixture(scope="session")
def traces():
    """Load cached traces or run headless."""
    from test_simulation import load_traces
    return load_traces(seeds=3, use_cache=TRACE_CACHE.exists())
