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

    python_path = _venv_python(ENV_DIR)
    if not python_path.exists():
        raise RuntimeError("Virtual environment missing python executable.")

    pip_path = _venv_pip(ENV_DIR)
    if pip_path.exists():
        return

    print("Bootstrapping pip inside the virtual environment...")
    subprocess.check_call([str(python_path), "-m", "ensurepip", "--upgrade"])


def install_project() -> None:
    python_path = _venv_python(ENV_DIR)
    if not python_path.exists():
        raise RuntimeError("Virtual environment missing python executable.")

    if not _venv_pip(ENV_DIR).exists():
        print("Pip was not detected; attempting to bootstrap it...")
        subprocess.check_call([str(python_path), "-m", "ensurepip", "--upgrade"])

    print("Installing Garage News dependencies (this might take a moment)...")
    try:
        subprocess.check_call([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    except subprocess.CalledProcessError as exc:
        print(
            "Warning: Unable to upgrade pip automatically; proceeding with the existing version."
        )
        print(f"  Command {exc.cmd} exited with status {exc.returncode}.")
    subprocess.check_call(
        [
            str(python_path),
            "-m",
            "pip",
            "install",
            "--no-use-pep517",
            "-e",
            str(PROJECT_ROOT),
        ]
    )


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
