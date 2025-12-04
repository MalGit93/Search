# Garage News Scraper

A small, self-contained tool that ingests news **listing pages**, discovers article links, fetches each article, and exports the results to CSV. Each record includes the website, article URL, headline, full text (best effort), and the UTC timestamp when it was scraped.

## How it works

1. You maintain a `sources.txt` file with **one listing URL per line** (e.g., a site's "News" or "Latest stories" page). Use only listing/section pages—**do not paste individual article URLs**; the scraper will discover them for you.
2. For each listing page the scraper:
   - Downloads the HTML.
   - Filters in-domain links that look like article URLs (news/story/date-like paths).
3. It deduplicates every discovered article URL.
4. For each article URL it fetches the page and pulls:
   - Headline (prefers `og:title`, falls back to `<title>` or `<h1>`)
   - Body text from `<article>` or common content containers
5. Everything is written to `news_articles.csv` with columns: `website`, `article_url`, `headline`, `content`, `scraped_at`.

## Quick start

1. (Optional) Install the CLI locally. There are no external dependencies, but installation enables the `garage-news` command:

   ```bash
   python -m venv .venv
   .venv/bin/pip install --no-use-pep517 -e .
   ```

   You can also run the module directly without installation using `python -m garage_news.cli ...`.

2. Create `sources.txt` (one listing URL per line). You can generate a starter file. Listing URLs are the pages that list stories (e.g., `/news/`, `/latest-news/`), not the article pages themselves:

   ```bash
   python -m garage_news.cli init-sources
   ```

3. Run the scraper:

   ```bash
   python -m garage_news.cli run --sources sources.txt --output news_articles.csv
   ```

4. Optional: preview discovered article URLs without fetching full pages:

   ```bash
   python -m garage_news.cli preview --limit 5
   ```

## Configuration notes

- Only links on the **same domain** as the listing page are considered.
- A handful of keywords (`news`, `article`, `story`, `2025`, `2024`, `2023`) plus a minimum path depth help weed out navigation links. Adjust the logic inside `garage_news/scraper.py` if you want a tighter or looser filter.
- Paragraphs shorter than 40 characters are dropped by default; override with `--min-paragraph-length` on the CLI.

## Output

The generated CSV uses UTF-8 with BOM (`utf-8-sig`) and the following columns:

| column        | description                                   |
|---------------|-----------------------------------------------|
| `website`     | Domain name hosting the article                |
| `article_url` | Full URL of the article                        |
| `headline`    | Extracted headline                             |
| `content`     | Raw article text (best effort)                 |
| `scraped_at`  | UTC timestamp when the article was processed   |

## License

MIT
