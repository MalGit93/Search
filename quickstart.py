"""One-command bootstrap for Garage News."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import venv

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_DIR = PROJECT_ROOT / ".garage-news-env"


def _venv_python(env_dir: Path) -> Path:
    if os.name == "nt":
        return env_dir / "Scripts" / "python.exe"
    return env_dir / "bin" / "python"


def _venv_pip(env_dir: Path) -> Path:
    if os.name == "nt":
        return env_dir / "Scripts" / "pip.exe"
    return env_dir / "bin" / "pip"


def ensure_environment() -> None:
    if ENV_DIR.exists():
        return
    print(f"Creating virtual environment at {ENV_DIR}...")
    builder = venv.EnvBuilder(with_pip=True)
    builder.create(ENV_DIR)


def install_project() -> None:
    pip_path = _venv_pip(ENV_DIR)
    if not pip_path.exists():
        raise RuntimeError("Virtual environment missing pip executable.")
    print("Installing Garage News dependencies (this might take a moment)...")
    subprocess.check_call([str(pip_path), "install", "--upgrade", "pip"])
    subprocess.check_call([str(pip_path), "install", "-e", str(PROJECT_ROOT)])


def launch_setup_wizard() -> int:
    python_path = _venv_python(ENV_DIR)
    if not python_path.exists():
        raise RuntimeError("Virtual environment missing python executable.")
    print("Launching the setup wizard...\n")
    return subprocess.call([str(python_path), "-m", "garage_news.cli", "setup"], cwd=str(PROJECT_ROOT))


def main() -> int:
    try:
        ensure_environment()
        install_project()
        return launch_setup_wizard()
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}: {exc.cmd}")
        return exc.returncode
    except Exception as exc:  # noqa: BLE001
        print(f"Setup failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
