from __future__ import annotations

import argparse
from pathlib import Path

from .scraper import collect_all_articles, export_csv, find_article_links, read_source_file


def cmd_run(args: argparse.Namespace) -> int:
    sources_path = Path(args.sources)
    listing_urls = read_source_file(sources_path)
    if not listing_urls:
        print(f"No listing URLs found in {sources_path}. Add one URL per line and try again.")
        return 1

    records = collect_all_articles(listing_urls, timeout=args.timeout, min_paragraph_length=args.min_paragraph_length)
    saved = export_csv(records, Path(args.output))
    print(f"Saved {saved} articles to {args.output}")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    sources_path = Path(args.sources)
    listing_urls = read_source_file(sources_path)
    if not listing_urls:
        print(f"No listing URLs found in {sources_path}. Add one URL per line and try again.")
        return 1

    collected = []
    for listing_url in listing_urls:
        collected.extend(find_article_links(listing_url, timeout=args.timeout))

    unique_urls = sorted(set(collected))[: args.limit]
    if not unique_urls:
        print("No article links found.")
        return 0

    for idx, url in enumerate(unique_urls, start=1):
        print(f"{idx:02d}. {url}")
    return 0


def cmd_init_sources(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.exists():
        print(f"{path} already exists. Skipping creation.")
        return 0

    examples = [
        "# One listing/section page per line (e.g., /news/). Do not add individual article URLs.",
        "# Feel free to replace these examples with your own sites.",
        "",
        "https://garagewire.co.uk/news/",
        "https://aftermarketonline.net/news/",
        "https://www.motortrader.com/latest-news/",
    ]
    path.write_text("\n".join(examples), encoding="utf-8")
    print(f"Created starter listing file at {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape news listing pages into a CSV of articles")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Scrape articles and export to CSV")
    run_parser.add_argument("--sources", "-s", default="sources.txt", help="Path to listing URLs file")
    run_parser.add_argument("--output", "-o", default="news_articles.csv", help="CSV destination")
    run_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds")
    run_parser.add_argument(
        "--min-paragraph-length",
        type=int,
        default=40,
        help="Paragraph length threshold for article text",
    )
    run_parser.set_defaults(func=cmd_run)

    preview_parser = subparsers.add_parser("preview", help="List discovered article URLs")
    preview_parser.add_argument("--sources", "-s", default="sources.txt", help="Path to listing URLs file")
    preview_parser.add_argument("--limit", type=int, default=10, help="Maximum URLs to display")
    preview_parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds")
    preview_parser.set_defaults(func=cmd_preview)

    init_parser = subparsers.add_parser("init-sources", help="Create a starter sources.txt")
    init_parser.add_argument("--path", "-p", default="sources.txt", help="Where to create the file")
    init_parser.set_defaults(func=cmd_init_sources)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
