from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich import print
from rich.console import Console
from rich.table import Table
import yaml

from .config import AppConfig, SourceConfig, load_config
from .pipeline import NewsPipeline

app = typer.Typer(help="Independent garage news aggregation toolkit")
console = Console()


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


@app.command("guided-run")
def guided_run() -> None:
    """Prompt for URLs and date range, ideal for quick experiments (e.g. Google Colab)."""

    typer.echo("Enter the website or RSS URLs you want to scan.")
    typer.echo("Separate entries with commas or new lines. We'll normalise missing https:// prefixes for you.")
    urls = _prompt_urls()
    if not urls:
        typer.echo("No valid URLs supplied, exiting.")
        raise typer.Exit(code=1)

    start_date = _prompt_date("Start date (YYYY-MM-DD, optional)")
    end_date = _prompt_date("End date (YYYY-MM-DD, optional)")
    if start_date and end_date and end_date < start_date:
        typer.echo("End date must be the same as or later than the start date.")
        raise typer.Exit(code=1)

    limit_per_source = _prompt_limit()
    fetch_full_content = typer.confirm("Download full article text?", default=False)

    sources = [SourceConfig(name=_derive_name(url), url=url, type="website") for url in urls]
    app_config = AppConfig(sources=sources, database_path=Path("garage_news_colab.db"))

    console.rule("Fetching articles")
    pipeline = NewsPipeline(app_config)
    pipeline.run(limit_per_source=limit_per_source, fetch_full_content=fetch_full_content)

    console.rule("Filtered results")
    articles = pipeline.storage.articles_between(start=start_date, end=end_date, limit=200)
    if not articles:
        console.print("[yellow]No articles found for the selected date range.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Published (UTC)", justify="center")
    table.add_column("Source")
    table.add_column("Title")
    table.add_column("Link")

    for article in articles:
        published = article.published_at or article.fetched_at
        published_utc = published.astimezone(timezone.utc)
        table.add_row(
            published_utc.strftime("%Y-%m-%d %H:%M"),
            article.source_name,
            article.title,
            article.link,
        )

    console.print(table)


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


def _prompt_urls() -> list[str]:
    raw_urls = typer.prompt("URLs", default="")
    return _parse_urls(raw_urls)


def _prompt_date(message: str) -> datetime | None:
    while True:
        value = typer.prompt(message, default="", show_default=False)
        value = value.strip()
        if not value:
            return None
        try:
            return _parse_date(value)
        except ValueError as exc:
            typer.echo(f"Invalid date '{value}': {exc}")


def _parse_date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("use ISO 8601 or YYYY-MM-DD format") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _prompt_limit() -> int:
    while True:
        raw_value = typer.prompt("Articles to fetch per source", default="5")
        try:
            value = int(raw_value)
        except ValueError:
            typer.echo("Please enter a whole number.")
            continue
        if value <= 0:
            typer.echo("Please choose a positive number of articles.")
            continue
        return value


if __name__ == "__main__":
    app()
