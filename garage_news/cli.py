from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich import print
import yaml

from .config import AppConfig, SourceConfig, load_config
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


@app.command("setup")
def setup_ui(
    config: Path = typer.Option(Path("config/sources.yaml"), "--config", "-c", help="Path to configuration file"),
    limit_per_source: int = typer.Option(5, help="Articles to fetch per website when running now"),
) -> None:
    """Interactive helper for adding website URLs and running the pipeline."""

    typer.echo("Paste the website URLs you want to monitor. Separate entries with commas or new lines.")
    raw_urls = typer.prompt("Website URLs")
    urls = _parse_urls(raw_urls)
    if not urls:
        typer.echo("No URLs provided, exiting without changes.")
        raise typer.Exit(code=1)

    config_path = Path(config)
    try:
        existing_config = load_config(config_path)
        sources = list(existing_config.sources)
        database_path = existing_config.database_path
    except FileNotFoundError:
        sources = []
        database_path = AppConfig.__dataclass_fields__["database_path"].default

    existing_urls = {source.url for source in sources}
    additions: list[SourceConfig] = []
    for url in urls:
        if url in existing_urls:
            typer.echo(f"Skipping existing source: {url}")
            continue
        name = _derive_name(url)
        source = SourceConfig(name=name, url=url, type="website")
        sources.append(source)
        additions.append(source)

    if not additions:
        typer.echo("All provided URLs were already configured. Nothing to update.")
        raise typer.Exit()

    new_config = AppConfig(sources=sources, database_path=database_path)
    _write_config(new_config, config_path)

    typer.echo(f"Saved {len(additions)} new source(s) to {config_path}.")

    if typer.confirm("Fetch the latest articles now?", default=True):
        pipeline = NewsPipeline(new_config)
        pipeline.run(limit_per_source=limit_per_source)


def _parse_urls(raw: str) -> list[str]:
    chunks: list[str] = []
    for piece in raw.replace("\r", "\n").split("\n"):
        chunks.extend(part.strip() for part in piece.split(","))
    urls: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        url = chunk if _has_scheme(chunk) else f"https://{chunk}"
        parsed = urlparse(url)
        if not parsed.netloc:
            typer.echo(f"Ignoring invalid URL: {chunk}")
            continue
        urls.append(url)
    return urls


def _has_scheme(url: str) -> bool:
    return "://" in url


def _derive_name(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc or parsed.path
    host = host.lower().lstrip("www.")
    parts = [part for part in host.replace("-", " ").replace("_", " ").split(".") if part]
    if not parts:
        return url
    primary = parts[0].split()
    words = [word.capitalize() for word in primary[:3]]
    return " ".join(words) or url


def _write_config(app_config: AppConfig, path: Path) -> None:
    payload = {
        "database_path": str(app_config.database_path),
        "sources": [_source_to_mapping(source) for source in app_config.sources],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf8") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False)


def _source_to_mapping(source: SourceConfig) -> dict:
    data = asdict(source)
    if not data.get("category"):
        data.pop("category", None)
    if not data.get("tags"):
        data.pop("tags", None)
    return data


if __name__ == "__main__":
    app()
