"""Bootstrap script for the Garage News scraper."""
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
    python_path = _venv_python(ENV_DIR)
    pip_path = _venv_pip(ENV_DIR)
    if not python_path.exists():
        raise RuntimeError("Virtual environment missing python executable.")

    if not pip_path.exists():
        print("Bootstrapping pip inside the virtual environment...")
        subprocess.check_call([str(python_path), "-m", "ensurepip", "--upgrade"])

    print("Installing Garage News dependencies...")
    subprocess.check_call([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    subprocess.check_call([str(python_path), "-m", "pip", "install", "--no-use-pep517", "-e", str(PROJECT_ROOT)])


def ensure_sources_file() -> Path:
    sources_path = PROJECT_ROOT / "sources.txt"
    if sources_path.exists():
        return sources_path

    examples = [
        "# One listing/section page per line (e.g., /news/). Do not add individual article URLs.",
        "# Feel free to replace these examples with your own sites.",
        "",
        "https://garagewire.co.uk/news/",
        "https://aftermarketonline.net/news/",
        "https://www.motortrader.com/latest-news/",
    ]
    sources_path.write_text("\n".join(examples), encoding="utf-8")
    print(f"Created starter sources file at {sources_path}")
    return sources_path


def main() -> int:
    try:
        ensure_environment()
        install_project()
        sources_path = ensure_sources_file()
        python_path = _venv_python(ENV_DIR)
        print("\nTo run the scraper, execute:\n")
        print(f"  {python_path} -m garage_news.cli run --sources {sources_path} --output news_articles.csv\n")
        return 0
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}: {exc.cmd}")
        return exc.returncode
    except Exception as exc:  # noqa: BLE001
        print(f"Setup failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
