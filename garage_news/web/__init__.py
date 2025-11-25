from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..analysis import build_insights, group_trends_by_category
from ..config import AppConfig, SourceConfig, load_config, save_config
from ..pipeline import NewsPipeline
from ..storage import Storage


@dataclass
class WebState:
    config_path: Path
    config: AppConfig
    storage: Storage


# Lazily created templates instance is shared among handlers
_templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _load_or_initialize_config(path: Path) -> AppConfig:
    try:
        return load_config(path)
    except FileNotFoundError:
        default = AppConfig(sources=[], database_path=Path("garage_news.db"))
        save_config(default, path)
        return default


def create_app(config_path: Path | str = Path("config/sources.yaml")) -> FastAPI:
    """Create a FastAPI application that surfaces insights and source management."""

    app = FastAPI(title="Garage News Web")
    config_path = Path(config_path)
    config = _load_or_initialize_config(config_path)
    storage = Storage(config.database_path)
    state = WebState(config_path=config_path, config=config, storage=storage)
    app.state.garage_news = state

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request, message: str | None = None) -> HTMLResponse:
        articles = state.storage.recent_articles(limit=50)
        insight = build_insights(articles)
        trends_by_category = group_trends_by_category(articles)
        return _templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "articles": articles,
                "insight": insight,
                "trends_by_category": trends_by_category,
                "sources": state.config.sources,
                "message": message,
            },
        )

    @app.get("/sources", response_class=HTMLResponse)
    async def manage_sources(request: Request, message: str | None = None) -> HTMLResponse:
        return _templates.TemplateResponse(
            "sources.html",
            {
                "request": request,
                "sources": state.config.sources,
                "message": message,
            },
        )

    @app.post("/sources/add")
    async def add_source(
        request: Request,
        background_tasks: BackgroundTasks,
        name: str = Form(...),
        url: str = Form(...),
        type: str = Form("rss"),
        category: str | None = Form(None),
        polling_interval_minutes: int = Form(360),
        tags: str = Form(""),
    ) -> RedirectResponse:
        _validate_unique_name(name, state.config.sources)
        source = SourceConfig(
            name=name.strip(),
            url=url.strip(),
            type=type.strip() or "rss",
            category=category or None,
            polling_interval_minutes=int(polling_interval_minutes),
            tags=_parse_tags(tags),
        )
        state.config.sources.append(source)
        _persist_config(state)
        _queue_refresh(state, background_tasks)
        return RedirectResponse(url=request.url_for("manage_sources") + "?message=Source+added", status_code=303)

    @app.post("/sources/update")
    async def update_source(
        request: Request,
        background_tasks: BackgroundTasks,
        original_name: str = Form(...),
        name: str = Form(...),
        url: str = Form(...),
        type: str = Form("rss"),
        category: str | None = Form(None),
        polling_interval_minutes: int = Form(360),
        tags: str = Form(""),
    ) -> RedirectResponse:
        source = _find_source(original_name, state.config.sources)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")

        if name != original_name:
            _validate_unique_name(name, state.config.sources, exclude=source)

        source.name = name.strip()
        source.url = url.strip()
        source.type = type.strip() or "rss"
        source.category = category or None
        source.polling_interval_minutes = int(polling_interval_minutes)
        source.tags = _parse_tags(tags)

        _persist_config(state)
        _queue_refresh(state, background_tasks)
        return RedirectResponse(url=request.url_for("manage_sources") + "?message=Source+updated", status_code=303)

    @app.post("/sources/delete")
    async def delete_source(
        request: Request,
        background_tasks: BackgroundTasks,
        name: str = Form(...),
    ) -> RedirectResponse:
        source = _find_source(name, state.config.sources)
        if source is None:
            raise HTTPException(status_code=404, detail="Source not found")
        state.config.sources.remove(source)
        _persist_config(state)
        _queue_refresh(state, background_tasks)
        return RedirectResponse(url=request.url_for("manage_sources") + "?message=Source+removed", status_code=303)

    @app.post("/refresh")
    async def refresh_content(request: Request, background_tasks: BackgroundTasks) -> RedirectResponse:
        _queue_refresh(state, background_tasks)
        return RedirectResponse(url=request.url_for("home") + "?message=Refresh+started", status_code=303)

    return app


def _persist_config(state: WebState) -> None:
    save_config(state.config, state.config_path)
    state.storage = Storage(state.config.database_path)


def _parse_tags(raw: str) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _find_source(name: str, sources: Iterable[SourceConfig]) -> SourceConfig | None:
    normalized = name.strip().lower()
    for source in sources:
        if source.name.strip().lower() == normalized:
            return source
    return None


def _validate_unique_name(name: str, sources: Iterable[SourceConfig], exclude: SourceConfig | None = None) -> None:
    normalized = name.strip().lower()
    for source in sources:
        if exclude is not None and source is exclude:
            continue
        if source.name.strip().lower() == normalized:
            raise HTTPException(status_code=400, detail="A source with this name already exists")


def _queue_refresh(state: WebState, background_tasks: BackgroundTasks) -> None:
    background_tasks.add_task(_run_pipeline, state.config)


def _run_pipeline(config: AppConfig) -> None:
    pipeline = NewsPipeline(config)
    pipeline.run()
