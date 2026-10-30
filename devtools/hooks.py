# Turns on the repository's commit-message hook for this clone: git runs .githooks/commit-msg once core.hooksPath points there.
# Run once after cloning (python devtools/hooks.py); safe to run again.
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

subprocess.run(['git', 'config', 'core.hooksPath', '.githooks'], cwd=REPO, check=True)
print(f'commit-msg hook on: core.hooksPath = .githooks in {REPO}')
