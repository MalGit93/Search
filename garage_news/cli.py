from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich import print
from rich.console import Console
from rich.table import Table

from .config import AppConfig, load_config
from .pipeline import NewsPipeline
from .storage import Article
from .web import create_app

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


@app.command("guided-run")
def guided_run(
    config: Path = typer.Option(
        Path("config/sources.yaml"), "--config", "-c", help="Path to configuration file"
    ),
) -> None:
    """Run the guided pipeline using the configured sources."""

    try:
        existing_config = load_config(config)
    except FileNotFoundError:
        typer.echo(f"No configuration found at {config}. Please create it before running the guided flow.")
        raise typer.Exit(code=1)

    sources = list(existing_config.sources)
    if not sources:
        typer.echo("The configuration does not define any sources. Please add some and try again.")
        raise typer.Exit(code=1)

    typer.echo(f"Loaded {len(sources)} source(s) from {config}.")

    start_date = _prompt_date("Start date (YYYY-MM-DD, optional)")
    end_date = _prompt_date("End date (YYYY-MM-DD, optional)")
    if start_date and end_date and end_date < start_date:
        typer.echo("End date must be the same as or later than the start date.")
        raise typer.Exit(code=1)

    limit_per_source = _prompt_limit()
    fetch_full_content = typer.confirm("Download full article text?", default=False)

    app_config = AppConfig(sources=sources, database_path=existing_config.database_path)

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


@app.command()
def serve(
    config: Path = typer.Option(Path("config/sources.yaml"), "--config", "-c", help="Path to configuration file"),
    host: str = typer.Option("0.0.0.0", help="Host interface to bind"),
    port: int = typer.Option(8000, help="Port to bind"),
) -> None:
    """Launch the Garage News web dashboard."""

    import uvicorn

    app_instance = create_app(config_path=config)
    uvicorn.run(app_instance, host=host, port=port)


if __name__ == "__main__":
    app()
