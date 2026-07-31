#!/usr/bin/env python3
"""
Collect People's Daily e-paper articles from a fixed page.

Default target:
- Renmin Ribao page 05
- Section: comment
- Article keyword: commentator
- Max articles per day: 2

The script uses only Python standard-library modules so it can run for free in
GitHub Actions without installing dependencies.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


BASE_URL = "https://paper.people.com.cn/rmrb/pc/layout/{ym}/{day}/node_{page}.html"
DEFAULT_PAGE = "05"
DEFAULT_SECTION = "\u8bc4\u8bba"
DEFAULT_KEYWORDS = ["\u8bc4\u8bba\u5458"]
SOURCE_NAME = "\u4eba\u6c11\u65e5\u62a5"
SHANGHAI_TZ = timezone(timedelta(hours=8))


@dataclass
class Link:
    href: str
    text: str


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[Link] = []
        self._href: str | None = None
        self._pieces: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = {key.lower(): value for key, value in attrs}
        href = attrs_dict.get("href")
        if href:
            self._href = href
            self._pieces = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._pieces.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            text = normalize_text("".join(self._pieces))
            self.links.append(Link(href=self._href, text=text))
            self._href = None
            self._pieces = []


def normalize_text(value: str) -> str:
    value = unescape(value or "")
    value = value.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def strip_tags(fragment: str) -> str:
    fragment = re.sub(r"<script[\s\S]*?</script>", " ", fragment, flags=re.I)
    fragment = re.sub(r"<style[\s\S]*?</style>", " ", fragment, flags=re.I)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return normalize_text(fragment)


def fetch_html(url: str, retries: int = 2, timeout: int = 20) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        )
    }
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                charset_match = re.search(r"charset=([\w-]+)", content_type, re.I)
                charset = charset_match.group(1) if charset_match else "utf-8"
                return raw.decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Fetch failed: {url} ({last_error})")


def parse_date(value: str | None) -> date:
    if not value or value.lower() == "today":
        return datetime.now(SHANGHAI_TZ).date()
    return datetime.strptime(value, "%Y-%m-%d").date()


def iter_dates(start: date, end: date | None) -> Iterable[date]:
    if end is None:
        yield start
        return
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def layout_url(day: date, page: str) -> str:
    return BASE_URL.format(ym=day.strftime("%Y%m"), day=day.strftime("%d"), page=page)


def extract_page_name(html: str, page: str, section: str) -> str:
    text = strip_tags(html)
    patterns = [
        rf"\u7b2c\s*{re.escape(page)}\s*\u7248[\uff1a:]\s*[^<\n\r]+",
        r"\u7b2c\s*\d+\s*\u7248[\uff1a:]\s*[^<\n\r]+",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_text(match.group(0))
    return f"\u7b2c{page}\u7248\uff1a{section}"


def extract_article_links(html: str, base_url: str) -> list[Link]:
    parser = LinkParser()
    parser.feed(html)

    seen: set[str] = set()
    links: list[Link] = []
    for link in parser.links:
        href = urljoin(base_url, link.href)
        if "content_" not in href or "/rmrb/pc/content/" not in href:
            continue
        if href in seen:
            continue
        seen.add(href)
        links.append(Link(href=href, text=link.text))
    return links


def extract_first_tag(html: str, tag: str) -> str:
    match = re.search(rf"<{tag}\b[^>]*>([\s\S]*?)</{tag}>", html, flags=re.I)
    return strip_tags(match.group(1)) if match else ""


def extract_paragraphs(html: str) -> list[str]:
    content_html = html
    zoom_match = re.search(
        r"<div\b[^>]*id=[\"']?ozoom[\"']?[^>]*>([\s\S]*?)</div>",
        html,
        flags=re.I,
    )
    if zoom_match:
        content_html = zoom_match.group(1)

    paragraphs = [
        strip_tags(match.group(1))
        for match in re.finditer(r"<p\b[^>]*>([\s\S]*?)</p>", content_html, flags=re.I)
    ]
    paragraphs = [p for p in paragraphs if p and p not in {"###", "#", "##"}]

    if not paragraphs and not zoom_match:
        text = strip_tags(html)
        paragraphs = [p for p in re.split(r"\s{2,}", text) if p]

    return dedupe_keep_order(paragraphs)


def dedupe_keep_order(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def extract_author(paragraphs: list[str], keywords: list[str]) -> str:
    author_patterns = keywords + ["\u672c\u62a5", "\u4f5c\u8005", "\u8bb0\u8005"]
    for paragraph in paragraphs[:8]:
        if any(keyword in paragraph for keyword in author_patterns):
            if len(paragraph) <= 80:
                return paragraph
    return ""


def article_matches(article: dict, keywords: list[str]) -> tuple[bool, list[str]]:
    haystack = " ".join(
        [
            article.get("title", ""),
            article.get("subtitle", ""),
            article.get("author", ""),
            article.get("content", ""),
        ]
    )
    matched = [keyword for keyword in keywords if keyword and keyword in haystack]
    return bool(matched), matched


def parse_article(
    url: str,
    link_title: str,
    day: date,
    page: str,
    section: str,
    page_name: str,
    keywords: list[str],
) -> dict:
    html = fetch_html(url)
    title = extract_first_tag(html, "h1") or link_title
    subtitle = extract_first_tag(html, "h2")
    paragraphs = extract_paragraphs(html)
    content = "\n".join(paragraphs)

    source_line = ""
    text = strip_tags(html)
    source_match = re.search(r"\u300a\u4eba\u6c11\u65e5\u62a5\u300b\s*\uff08[^\uff09]+\uff09", text)
    if source_match:
        source_line = normalize_text(source_match.group(0))

    article = {
        "source": SOURCE_NAME,
        "publish_date": day.isoformat(),
        "page": page,
        "section": section,
        "page_name": page_name,
        "title": title,
        "subtitle": subtitle,
        "author": extract_author(paragraphs, keywords),
        "url": url,
        "source_line": source_line,
        "excerpt": content[:280],
        "content": content,
        "collected_at": datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds"),
    }
    return article


def trim_article(article: dict, content_mode: str) -> dict:
    if content_mode == "full":
        return article
    trimmed = dict(article)
    trimmed.pop("content", None)
    return trimmed


def collect_for_day(
    day: date,
    page: str,
    section: str,
    keywords: list[str],
    limit: int,
    content_mode: str,
) -> dict:
    url = layout_url(day, page)
    html = fetch_html(url)
    page_name = extract_page_name(html, page, section)
    links = extract_article_links(html, url)

    articles: list[dict] = []
    for link in links:
        article = parse_article(link.href, link.text, day, page, section, page_name, keywords)
        matched, matched_keywords = article_matches(article, keywords)
        if not matched:
            continue
        article["matched_keywords"] = matched_keywords
        articles.append(trim_article(article, content_mode))
        if len(articles) >= limit:
            break

    return {
        "source": SOURCE_NAME,
        "target": {
            "page": page,
            "section": section,
            "keywords": keywords,
            "limit": limit,
            "content_mode": content_mode,
        },
        "publish_date": day.isoformat(),
        "layout_url": url,
        "page_name": page_name,
        "article_count": len(articles),
        "articles": articles,
        "collected_at": datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds"),
    }


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, articles: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "publish_date",
        "page",
        "section",
        "page_name",
        "title",
        "subtitle",
        "author",
        "url",
        "source_line",
        "matched_keywords",
        "excerpt",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for article in articles:
            row = dict(article)
            row["matched_keywords"] = ",".join(row.get("matched_keywords", []))
            writer.writerow(row)


def update_article_index(index_path: Path, new_articles: list[dict]) -> None:
    existing: list[dict] = []
    if index_path.exists():
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
            existing = payload.get("articles", []) if isinstance(payload, dict) else []
        except json.JSONDecodeError:
            existing = []

    if any(not article.get("is_demo") for article in new_articles):
        existing = [article for article in existing if not article.get("is_demo")]

    by_url = {article.get("url"): article for article in existing if article.get("url")}
    for article in new_articles:
        by_url[article["url"]] = article

    articles = sorted(
        by_url.values(),
        key=lambda item: (item.get("publish_date", ""), item.get("title", "")),
        reverse=True,
    )
    payload = {
        "updated_at": datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds"),
        "article_count": len(articles),
        "articles": articles,
    }
    write_json(index_path, payload)


def write_site_config(output_dir: Path) -> None:
    payload = {
        "mode": "production",
        "demo_fallback": False,
        "updated_at": datetime.now(SHANGHAI_TZ).isoformat(timespec="seconds"),
    }
    write_json(output_dir / "site_config.json", payload)


def save_day(output_dir: Path, payload: dict) -> None:
    day = payload["publish_date"]
    articles = payload["articles"]
    write_json(output_dir / f"daily_{day}.json", payload)
    write_json(output_dir / "latest.json", payload)
    write_csv(output_dir / f"daily_{day}.csv", articles)
    update_article_index(output_dir / "articles.json", articles)
    write_site_config(output_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect People's Daily page 05 commentator articles.")
    parser.add_argument("--date", default="today", help="Publish date, YYYY-MM-DD. Default: today in UTC+8.")
    parser.add_argument("--start-date", help="Start date for history collection, YYYY-MM-DD.")
    parser.add_argument("--end-date", help="End date for history collection, YYYY-MM-DD.")
    parser.add_argument("--page", default=DEFAULT_PAGE, help="E-paper page number. Default: 05.")
    parser.add_argument("--section", default=DEFAULT_SECTION, help="Section name. Default: comment.")
    parser.add_argument(
        "--keyword",
        action="append",
        dest="keywords",
        help="Keyword for article filtering. Can be used more than once. Default: commentator.",
    )
    parser.add_argument("--limit", type=int, default=2, help="Max matched articles per day. Default: 2.")
    parser.add_argument("--output-dir", default="public/data", help="Output directory. Default: public/data.")
    parser.add_argument(
        "--content-mode",
        choices=["excerpt", "full"],
        default="full",
        help="full saves body text for the local reader; excerpt saves only a short snippet. Default: full.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    keywords = args.keywords or DEFAULT_KEYWORDS
    output_dir = Path(args.output_dir)

    if args.start_date:
        start = parse_date(args.start_date)
        end = parse_date(args.end_date) if args.end_date else start
    else:
        start = parse_date(args.date)
        end = None

    collected_days = 0
    collected_articles = 0
    for current_day in iter_dates(start, end):
        payload = collect_for_day(
            day=current_day,
            page=args.page,
            section=args.section,
            keywords=keywords,
            limit=args.limit,
            content_mode=args.content_mode,
        )
        save_day(output_dir, payload)
        collected_days += 1
        collected_articles += payload["article_count"]
        print(
            f"{current_day.isoformat()} page {args.page}: "
            f"{payload['article_count']} matched article(s)."
        )

    print(f"Done. {collected_articles} article(s) collected across {collected_days} day(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
