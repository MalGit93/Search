from __future__ import annotations

import csv
import json
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
from .storage import Article

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
def guided_run(
    config: Path = typer.Option(
        Path("config/sources.yaml"), "--config", "-c", help="Path to configuration file"
    ),
    use_config_sources: bool = typer.Option(
        False,
        "--use-config-sources",
        help="Include sources defined in the configuration file",
    ),
) -> None:
    """Prompt for URLs and date range, ideal for quick experiments (e.g. Google Colab)."""

    base_sources: list[SourceConfig] = []
    database_path: Path = Path("garage_news_colab.db")

    if use_config_sources:
        try:
            existing_config = load_config(config)
        except FileNotFoundError:
            typer.echo(f"No configuration found at {config}. Continuing without preloaded sources.")
        else:
            base_sources = list(existing_config.sources)
            database_path = existing_config.database_path
            typer.echo(f"Loaded {len(base_sources)} source(s) from {config}.")

    typer.echo("Enter the website or RSS URLs you want to scan.")
    typer.echo("Separate entries with commas or new lines. We'll normalise missing https:// prefixes for you.")
    urls = _prompt_urls(allow_empty=bool(base_sources))

    if not urls and not base_sources:
        typer.echo("No valid URLs supplied, exiting.")
        raise typer.Exit(code=1)

    existing_urls = {source.url for source in base_sources}
    additions: list[SourceConfig] = []
    for url in urls:
        if url in existing_urls:
            typer.echo(f"Skipping duplicate source: {url}")
            continue
        source = SourceConfig(name=_derive_name(url), url=url, type="website")
        base_sources.append(source)
        existing_urls.add(url)
        additions.append(source)

    if additions:
        typer.echo(f"Added {len(additions)} new source(s) for this guided run.")

    start_date = _prompt_date("Start date (YYYY-MM-DD, optional)")
    end_date = _prompt_date("End date (YYYY-MM-DD, optional)")
    if start_date and end_date and end_date < start_date:
        typer.echo("End date must be the same as or later than the start date.")
        raise typer.Exit(code=1)

    limit_per_source = _prompt_limit()
    fetch_full_content = typer.confirm("Download full article text?", default=False)

    app_config = AppConfig(sources=base_sources, database_path=database_path)

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

    _maybe_export_articles(articles)


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


def _prompt_urls(*, allow_empty: bool = False) -> list[str]:
    while True:
        raw_urls = typer.prompt("URLs", default="")
        urls = _parse_urls(raw_urls)
        if urls or allow_empty:
            return urls
        typer.echo("Please provide at least one valid URL or load sources from the config.")


def _maybe_export_articles(articles: list[Article]) -> None:
    if not articles:
        return

    choice = typer.prompt(
        "Export results? (none/csv/json/txt)",
        default="none",
        value_proc=lambda value: value.strip().lower(),
    )

    valid_choices = {"none", "csv", "json", "txt"}
    while choice not in valid_choices:
        typer.echo("Please choose from: none, csv, json, txt")
        choice = typer.prompt(
            "Export results? (none/csv/json/txt)",
            default="none",
            value_proc=lambda value: value.strip().lower(),
        )

    if choice == "none":
        return

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    extension = "txt" if choice == "txt" else choice
    default_name = Path(f"guided_run_results_{timestamp}.{extension}")
    destination = typer.prompt("Destination file", default=str(default_name))
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)

    if choice == "csv":
        _export_csv(articles, path)
    elif choice == "json":
        _export_json(articles, path)
    else:
        _export_text(articles, path)

    typer.echo(f"Saved {len(articles)} article(s) to {path.resolve()}")


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _article_to_mapping(article: Article) -> dict[str, object]:
    published = _ensure_utc(article.published_at or article.fetched_at)
    fetched = _ensure_utc(article.fetched_at)
    return {
        "source_name": article.source_name,
        "source_url": article.source_url,
        "title": article.title,
        "link": article.link,
        "summary": article.summary,
        "content": article.content,
        "published_at": published.isoformat(),
        "fetched_at": fetched.isoformat(),
        "category": article.category,
        "tags": article.tags,
    }


def _export_csv(articles: list[Article], path: Path) -> None:
    rows = [_article_to_mapping(article) for article in articles]
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _export_json(articles: list[Article], path: Path) -> None:
    rows = [_article_to_mapping(article) for article in articles]
    with path.open("w", encoding="utf8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)


def _export_text(articles: list[Article], path: Path) -> None:
    lines: list[str] = []
    for article in articles:
        published = _ensure_utc(article.published_at or article.fetched_at)
        lines.append(published.strftime("%Y-%m-%d %H:%M UTC"))
        lines.append(article.source_name)
        lines.append(article.title)
        lines.append(article.link)
        if article.summary:
            lines.append(article.summary)
        lines.append("")
    with path.open("w", encoding="utf8") as handle:
        handle.write("\n".join(lines).strip() + "\n")


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
