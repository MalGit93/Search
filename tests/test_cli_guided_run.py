from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from garage_news.cli import app
from garage_news.storage import Article


class DummyPipeline:
    def __init__(self, config, articles: list[Article]):
        self.config = config
        self.articles = articles
        self.storage = SimpleNamespace(
            articles_between=lambda **_: list(self.articles),
        )
        self.run_calls: list[dict] = []

    def run(self, *, limit_per_source: int, fetch_full_content: bool) -> None:  # pragma: no cover
        self.run_calls.append(
            {
                "limit_per_source": limit_per_source,
                "fetch_full_content": fetch_full_content,
            }
        )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _sample_article() -> Article:
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    return Article(
        source_name="Example",
        source_url="https://example.com",
        title="Example headline",
        link="https://example.com/post",
        summary="Summary",
        content="Content",
        published_at=now,
        fetched_at=now,
        category=None,
        tags="",
    )


def test_guided_run_uses_config_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        """
database_path: guided.db
sources:
  - name: Saved Source
    url: https://saved.example
    type: website
        """.strip()
    )

    created_pipelines: list[DummyPipeline] = []

    def pipeline_factory(config):
        pipeline = DummyPipeline(config, [_sample_article()])
        created_pipelines.append(pipeline)
        return pipeline

    monkeypatch.setattr("garage_news.cli.NewsPipeline", pipeline_factory)

    result = runner.invoke(app, ["guided-run", "--config", str(config_path)], input="\n\n\n\n\n")

    assert result.exit_code == 0, result.stdout
    assert created_pipelines, "pipeline was not created"
    pipeline = created_pipelines[0]
    assert len(pipeline.config.sources) == 1
    assert pipeline.config.sources[0].url == "https://saved.example"
    assert str(pipeline.config.database_path) == "guided.db"


def test_guided_run_exports_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    created_pipelines: list[DummyPipeline] = []

    def pipeline_factory(config):
        pipeline = DummyPipeline(config, [_sample_article()])
        created_pipelines.append(pipeline)
        return pipeline

    monkeypatch.setattr("garage_news.cli.NewsPipeline", pipeline_factory)

    config_path = tmp_path / "sources.yaml"
    config_path.write_text(
        """
database_path: guided.db
sources:
  - name: Saved Source
    url: https://saved.example
    type: website
        """.strip()
    )

    export_path = tmp_path / "results.txt"
    inputs = "\n".join(["", "", "", "n", "txt", str(export_path)]) + "\n"
    result = runner.invoke(app, ["guided-run", "--config", str(config_path)], input=inputs)

    assert result.exit_code == 0, result.stdout
    assert export_path.exists()
    contents = export_path.read_text(encoding="utf8")
    assert "Example headline" in contents
    assert "https://saved.example" not in contents  # ensure link from article, not input URL list

