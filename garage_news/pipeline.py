from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .analysis import build_insights
from .config import AppConfig, SourceConfig
from .fetchers import rss
from .fetchers.webpage import fetch_article_body
from .storage import Storage

console = Console()


class NewsPipeline:
    def __init__(self, config: AppConfig):
        self.config = config
        self.storage = Storage(config.database_path)

    def run(self, *, limit_per_source: int = 5, fetch_full_content: bool = True) -> None:
        for source in self.config.sources:
            self._process_source(source, limit=limit_per_source, fetch_full_content=fetch_full_content)

        articles = self.storage.recent_articles(limit=50)
        insight = build_insights(articles)
        self._render_insight(insight)

    def _process_source(self, source: SourceConfig, *, limit: int, fetch_full_content: bool) -> None:
        console.log(f"Fetching {source.name} ({source.url})")
        if source.type.lower() == "rss":
            iterator = rss.fetch_articles(source, limit=limit)
        else:
            console.log(f"Unknown source type '{source.type}' for {source.name}, skipping")
            return

        for entry in iterator:
            link = entry.get("link")
            if not link:
                continue
            content = None
            if fetch_full_content:
                try:
                    content = fetch_article_body(link)
                except Exception as exc:  # noqa: BLE001
                    console.log(f"[red]Failed to retrieve full article[/red] {link}: {exc}")
            self.storage.upsert_article(
                source=source,
                title=entry.get("title", "Untitled"),
                link=link,
                summary=entry.get("summary"),
                content=content,
                published_at=entry.get("published"),
                fetched_at=datetime.utcnow(),
            )

    def _render_insight(self, insight) -> None:
        console.print(Panel("Latest Insights", style="bold cyan"))
        console.print(insight.summary or "No articles available.")

        if insight.trends:
            table = Table(title="Emerging Trends", show_header=True, header_style="bold magenta")
            table.add_column("Keyword")
            table.add_column("Mentions", justify="right")
            for trend in insight.trends:
                table.add_row(trend.keyword, str(trend.frequency))
            console.print(table)

        if insight.policy_suggestions:
            console.print(Panel("Policy Suggestions", style="green"))
            for suggestion in insight.policy_suggestions:
                console.print(f"- {suggestion}")
