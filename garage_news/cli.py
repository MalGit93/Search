from __future__ import annotations

from pathlib import Path

import typer
from rich import print

from .config import load_config
from .pipeline import NewsPipeline

app = typer.Typer(help="Independent garage news aggregation toolkit")


@app.command()
def run(
    config: Path = typer.Option(Path("config/sources.yaml"), "--config", "-c", help="Path to configuration file"),
    limit_per_source: int = typer.Option(5, help="Maximum articles fetched per source"),
    skip_full_content: bool = typer.Option(False, help="Skip fetching full article body"),
) -> None:
    """Run the ingestion + analysis pipeline."""

    app_config = load_config(config)
    pipeline = NewsPipeline(app_config)
    pipeline.run(limit_per_source=limit_per_source, fetch_full_content=not skip_full_content)


@app.command()
def list_sources(config: Path = typer.Option(Path("config/sources.yaml"), "--config", "-c")) -> None:
    """Display configured sources."""

    app_config = load_config(config)
    for source in app_config.sources:
        print(f"[bold]{source.name}[/bold] ({source.type}) - {source.url}")


if __name__ == "__main__":
    app()
