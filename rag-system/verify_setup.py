#!/usr/bin/env python3
"""
Verify RAG system setup is complete and working.

Checks:
- Python version
- Dependencies installed
- Ollama running and model available
- Claude API key set
- Directory structure in place
"""

import sys
import os
import subprocess
import json
from pathlib import Path


def check_python():
    """Check Python version. 3.9 is enough; the code avoids 3.10-only syntax."""
    v = sys.version_info
    if (v.major, v.minor) >= (3, 9):
        print(f"✓ Python {v.major}.{v.minor}")
        return True
    print(f"✗ Python {v.major}.{v.minor} (need 3.9+)")
    return False


def check_dependencies():
    """requests is required. anthropic is only needed for answer generation."""
    ok = True
    try:
        __import__("requests")
        print("✓ requests installed (required)")
    except ImportError:
        print("✗ requests NOT installed  ->  pip3 install requests")
        ok = False

    try:
        __import__("anthropic")
        print("✓ anthropic installed (generation available)")
    except ImportError:
        print("○ anthropic not installed (optional)")
        print("  Retrieval measurement works without it. For generation:")
        print("  pip3 install anthropic")
    return ok


def check_ollama():
    """Check Ollama service and model."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=2)

        if response.status_code != 200:
            print("✗ Ollama not responding")
            return False

        models = response.json().get("models", [])
        model_names = [m.get("name", "").split(":")[0] for m in models]

        if "nomic-embed-text" in model_names:
            print("✓ Ollama running with nomic-embed-text model")
            return True
        else:
            print("✗ Ollama running but nomic-embed-text not found")
            print(f"  Available models: {model_names}")
            print("  Run: ollama pull nomic-embed-text")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ Ollama not running")
        print("  Run: ollama serve")
        return False
    except Exception as e:
        print(f"✗ Ollama error: {e}")
        return False


def check_api_key():
    """Check Claude API key."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key and key.startswith("sk-"):
        print("✓ ANTHROPIC_API_KEY set")
        return True
    else:
        print("✗ ANTHROPIC_API_KEY not set")
        print("  Run: export ANTHROPIC_API_KEY='sk-...'")
        return False


def check_directories():
    """Check/create required directories."""
    dirs = ["corpus", "embeddings", "measurements"]
    all_ok = True

    for dir_name in dirs:
        if os.path.isdir(dir_name):
            print(f"✓ {dir_name}/ exists")
        else:
            try:
                os.makedirs(dir_name, exist_ok=True)
                print(f"✓ {dir_name}/ created")
            except Exception as e:
                print(f"✗ Cannot create {dir_name}/: {e}")
                all_ok = False

    return all_ok


def test_imports():
    """Test that RAG modules can be imported."""
    modules = [
        "config",
        "chunking",
        "embeddings",
        "retrieval",
        "rag_system",
        "gold_set",
        "measurement",
        "corpus_builder"
    ]
    all_ok = True

    for module in modules:
        try:
            __import__(module)
            print(f"✓ {module} imports OK")
        except Exception as e:
            print(f"✗ {module} import failed: {e}")
            all_ok = False

    return all_ok


def test_cosine_similarity():
    """Quick test of cosine similarity implementation."""
    try:
        from retrieval import CosineSimilaritySearch

        # Test vectors
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]  # Same = 1.0
        v3 = [0.0, 1.0, 0.0]  # Orthogonal = 0.0

        s1 = CosineSimilaritySearch.cosine_similarity(v1, v2)
        s2 = CosineSimilaritySearch.cosine_similarity(v1, v3)

        if abs(s1 - 1.0) < 0.01 and abs(s2 - 0.0) < 0.01:
            print("✓ Cosine similarity works correctly")
            return True
        else:
            print(f"✗ Cosine similarity wrong: same={s1}, orthogonal={s2}")
            return False
    except Exception as e:
        print(f"✗ Cosine similarity test failed: {e}")
        return False


def main():
    print("=" * 60)
    print("RAG SYSTEM SETUP VERIFICATION")
    print("=" * 60)
    print()

    # required=True blocks the offline pipeline test; required=False blocks only
    # the real thesis run, which needs genuine embeddings and generation.
    checks = [
        ("Python Version", check_python, True),
        ("Dependencies", check_dependencies, True),
        ("Directories", check_directories, True),
        ("Module Imports", test_imports, True),
        ("Cosine Similarity", test_cosine_similarity, True),
        ("Ollama Service", check_ollama, False),
        ("Claude API Key", check_api_key, False),
    ]

    results = []
    for name, check_fn, required in checks:
        print(f"\n{name}")
        print("-" * 40)
        try:
            ok = check_fn()
        except Exception as e:
            print(f"✗ Check failed with error: {e}")
            ok = False
        results.append((name, ok, required))

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, ok, required in results:
        tag = "" if required else "  (needed only for the real run)"
        print(f"{'✓' if ok else '✗'} {name}{tag}")

    core_ok = all(ok for _, ok, required in results if required)
    full_ok = all(ok for _, ok, _ in results)

    print()
    if full_ok:
        print("✓ Fully configured. Real experiment:")
        print("    python3 run_experiment.py")
    elif core_ok:
        print("✓ Core pipeline works. You can run the offline test now:")
        print("    python3 run_experiment.py --bootstrap --offline --quick")
        print()
        print("  For results valid in the thesis you still need:")
        for name, ok, required in results:
            if not ok and not required:
                print(f"    - {name}")
        return 0
    else:
        print("✗ Core checks failed - fix those first.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
