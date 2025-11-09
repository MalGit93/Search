# Garage News Aggregator

A lightweight toolkit for aggregating and analysing news about independent garages.

## Features

* Load a configurable list of RSS sources describing independent garage news outlets.
* Fetch latest articles and store them locally in a SQLite database.
* Retrieve full article content (best effort) for deeper analysis.
* Generate quick insight summaries, extract trending keywords, and draft policy suggestions.
* Provide a Typer-powered CLI for running ingestion jobs or listing sources.

## Getting Started

1. **Install dependencies**

   ```bash
   pip install -e .
   ```

2. **Configure sources**

   Update `config/sources.yaml` with the feeds you want to follow. Each source entry supports:

   ```yaml
   - name: Garage Wire           # Display name
     url: https://example.com    # RSS/Atom feed URL
     type: rss                   # Currently only 'rss' is supported
     category: business          # Optional category label
     polling_interval_minutes: 360
     tags: [uk, independent]     # Optional keyword tags
   ```

3. **Run the pipeline**

   ```bash
   garage-news run
   ```

   The command fetches the latest items from each configured source, stores them in `garage_news.db`,
   and prints summarised insights to the console. Use `--limit-per-source` to cap the number of
   articles per source and `--skip-full-content` to avoid downloading full article pages.

4. **List configured sources**

   ```bash
   garage-news list-sources
   ```

## Architecture Overview

```
config/sources.yaml --> garage_news.config --> garage_news.pipeline --> garage_news.storage (SQLite)
                                                   |                       |
                                                   v                       v
                                            garage_news.fetchers       garage_news.analysis
```

* `garage_news.config`: Parses YAML configuration into dataclasses.
* `garage_news.fetchers`: Currently includes an RSS fetcher and an HTML body extractor.
* `garage_news.storage`: Wraps SQLite persistence with an upsert helper.
* `garage_news.analysis`: Provides basic summarisation, keyword extraction, and policy suggestion heuristics.
* `garage_news.pipeline`: Orchestrates fetching, storage, and rendering insights.
* `garage_news.cli`: Command-line entrypoint using Typer.

## Extending the Project

* **Additional source types**: Implement new fetchers (e.g., JSON APIs) and register them in the pipeline.
* **LLM integration**: Replace `garage_news.analysis.build_insights` with a call to your preferred LLM API,
  providing article summaries and requesting structured outputs (policy memos, trend reports, etc.).
* **Scheduling**: Run `garage-news run` on a cron schedule or via a task queue like Celery.
* **UI/Reporting**: Export insights to a dashboard, Slack message, or email digest.

## License

MIT
