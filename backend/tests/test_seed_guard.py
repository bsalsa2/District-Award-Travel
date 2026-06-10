import os
import subprocess
import sys

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "seed_staging.py")


def test_seed_refuses_in_production():
    env = {**os.environ, "ENV": "production"}
    result = subprocess.run([sys.executable, SCRIPT], env=env, cwd=REPO_ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    assert "REFUSING TO RUN" in result.stdout


def test_seed_refuses_unknown_env():
    env = {**os.environ, "ENV": "prod"}  # typos/unknowns must also refuse
    result = subprocess.run([sys.executable, SCRIPT], env=env, cwd=REPO_ROOT,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 1
    assert "REFUSING TO RUN" in result.stdout
