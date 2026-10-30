import subprocess
from pathlib import Path


def test_the_installed_console_script_answers_help():
    repo = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["uv", "run", "assay", "check", "--help"],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0
    assert "usage: assay check" in result.stdout
