"""AI News Parsing Agent.

This module implements an autonomous agent that collects the latest news
articles about artificial intelligence, extracts their main content, and
produces concise summaries.  It is designed to be composable – you can import
`AINewsAgent` in your own projects or run this file directly as a CLI tool.

Key features
------------
* Pulls articles from a configurable list of RSS/Atom feeds
* Downloads and cleans the full article body for better summaries
* Filters the stream by AI-related keywords
* Generates extractive summaries without the need for external LLM APIs
* Outputs the result as JSON or Markdown for further processing

Dependencies
------------
The agent relies on a handful of third-party libraries.  Install them with:

```
pip install feedparser beautifulsoup4 requests python-dateutil
```

All other modules used here are part of the Python standard library.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import json
import logging
import re
import textwrap
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


LOGGER = logging.getLogger("ai_news_agent")


DEFAULT_SOURCES: tuple[str, ...] = (
    "https://rss.app/feeds/AFa0yOqD5b79v8sP.xml",  # OpenAI News (community curated)
    "https://feeds.feedburner.com/VenturebeatAI",  # VentureBeat AI
    "https://www.technologyreview.com/feed/",  # MIT Technology Review
    "https://www.theverge.com/artificial-intelligence/rss/index.xml",
    "https://www.analyticsvidhya.com/blog/category/artificial-intelligence/feed/",
    "https://www.reuters.com/world/technology/rss",
)


DEFAULT_KEYWORDS: tuple[str, ...] = (
    "artificial intelligence",
    "ai",
    "machine learning",
    "deep learning",
    "neural network",
    "large language model",
    "llm",
)


STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "about",
        "after",
        "again",
        "against",
        "all",
        "am",
        "an",
        "and",
        "any",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "by",
        "can",
        "could",
        "did",
        "do",
        "does",
        "doing",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "he",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "itself",
        "just",
        "me",
        "more",
        "most",
        "my",
        "myself",
        "no",
        "nor",
        "not",
        "now",
        "of",
        "off",
        "on",
        "once",
        "only",
        "or",
        "other",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "she",
        "should",
        "so",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "too",
        "under",
        "until",
        "up",
        "very",
        "was",
        "we",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "you",
        "your",
        "yours",
        "yourself",
        "yourselves",
    }
)


@dataclass(slots=True)
class Article:
    """Structured representation of a parsed article."""

    title: str
    link: str
    published_at: Optional[dt.datetime]
    source: str
    tags: list[str]
    summary: str
    full_text: str
    raw: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "link": self.link,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "source": self.source,
            "tags": list(self.tags),
            "summary": self.summary,
            "full_text": self.full_text,
        }


class AINewsAgent:
    """Collects, filters, and summarizes AI-related news."""

    def __init__(
        self,
        sources: Sequence[str] | None = None,
        keywords: Sequence[str] | None = None,
        max_workers: int = 4,
        request_timeout: float = 10.0,
    ) -> None:
        self.sources: tuple[str, ...] = tuple(sources or DEFAULT_SOURCES)
        self.keywords: tuple[str, ...] = tuple(
            sorted({k.lower() for k in (keywords or DEFAULT_KEYWORDS)})
        )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "AI-News-Agent/1.0 (+https://github.com/cursor-ai)"
                )
            }
        )
        self.max_workers = max(1, max_workers)
        self.request_timeout = request_timeout

    # Public API -----------------------------------------------------------------
    def collect_articles(
        self,
        *,
        limit: int = 20,
        min_length: int = 600,
        summary_sentences: int = 3,
    ) -> list[Article]:
        """Fetch, parse, and summarize articles.

        Args:
            limit: Maximum number of matching articles to return.
            min_length: Minimum character count of the article body to qualify.
            summary_sentences: Number of sentences in the generated summary.
        """

        LOGGER.info("Collecting AI news from %d sources", len(self.sources))
        feed_entries = list(self._iter_feed_entries())
        LOGGER.info("Retrieved %d feed entries", len(feed_entries))

        # Filter early based on keywords in title/summary
        filtered_entries = [
            entry
            for entry in feed_entries
            if self._matches_keywords(entry.get("title", ""), entry.get("summary", ""))
        ]
        LOGGER.info("%d entries match AI keywords", len(filtered_entries))

        articles: list[Article] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = [pool.submit(self._build_article, e, summary_sentences) for e in filtered_entries]
            for future in concurrent.futures.as_completed(futures):
                article = future.result()
                if not article:
                    continue
                if len(article.full_text) < min_length:
                    continue
                articles.append(article)
                if len(articles) >= limit:
                    break

        articles.sort(
            key=lambda a: a.published_at or dt.datetime.fromtimestamp(0, tz=dt.timezone.utc),
            reverse=True,
        )
        return articles[:limit]

    def to_json(self, articles: Iterable[Article]) -> str:
        """Serialize articles to JSON."""

        payload = [article.to_dict() for article in articles]
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def to_markdown(self, articles: Iterable[Article]) -> str:
        """Render articles as a Markdown bullet list with summaries."""

        lines: list[str] = []
        for article in articles:
            published = (
                article.published_at.strftime("%Y-%m-%d %H:%M")
                if article.published_at
                else ""
            )
            header = f"- [{article.title}]({article.link})"
            if published:
                header += f" — {published}"
            if article.source:
                header += f" ({article.source})"
            lines.append(header)
            wrapped_summary = textwrap.wrap(article.summary, width=100)
            for line in wrapped_summary:
                lines.append(f"  {line}")
            lines.append("")
        return "\n".join(lines).strip()

    # Internal helpers -----------------------------------------------------------
    def _iter_feed_entries(self) -> Iterable[dict[str, object]]:
        for source in self.sources:
            try:
                feed = feedparser.parse(source)
                if feed.bozo:
                    LOGGER.warning("Issue while parsing feed %s: %s", source, feed.bozo_exception)
                for entry in getattr(feed, "entries", []):
                    entry_dict = {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "summary": entry.get("summary", ""),
                        "published": self._parse_published(entry),
                        "tags": [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")],
                        "source": feed.feed.get("title", source),
                        "raw": entry,
                    }
                    yield entry_dict
            except Exception as exc:  # noqa: BLE001 - best effort per-source
                LOGGER.exception("Failed to read feed %s: %s", source, exc)

    def _parse_published(self, entry: dict) -> Optional[dt.datetime]:
        for key in ("published", "updated", "created"):
            if value := entry.get(key):
                try:
                    parsed = date_parser.parse(value)
                    if parsed.tzinfo is None:
                        parsed = parsed.replace(tzinfo=dt.timezone.utc)
                    return parsed
                except (ValueError, TypeError, OverflowError):
                    continue
        return None

    def _matches_keywords(self, *texts: str) -> bool:
        haystack = " ".join(texts).lower()
        return any(keyword in haystack for keyword in self.keywords)

    def _build_article(self, entry: dict[str, object], summary_sentences: int) -> Optional[Article]:
        link = str(entry.get("link", ""))
        if not link:
            return None
        try:
            response = self.session.get(link, timeout=self.request_timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            LOGGER.warning("Failed to download %s: %s", link, exc)
            return None

        full_text = self._extract_text(response.text)
        if not full_text:
            full_text = str(entry.get("summary", ""))

        summary = summarize_text(full_text, max_sentences=summary_sentences)
        if not summary:
            summary = textwrap.shorten(full_text, width=280, placeholder="…")

        article = Article(
            title=str(entry.get("title", "Untitled")),
            link=link,
            published_at=entry.get("published"),
            source=str(entry.get("source", "")),
            tags=[tag for tag in entry.get("tags", []) if isinstance(tag, str)],
            summary=summary,
            full_text=full_text.strip(),
            raw=dict(entry.get("raw", {})),
        )
        return article

    def _extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for undesirable in soup(["script", "style", "noscript", "header", "footer", "svg", "form"]):
            undesirable.decompose()

        main = soup.find("article") or soup.find("main")
        container = main if main else soup.body or soup
        paragraphs: list[str] = []
        for element in container.find_all(["p", "li"]):
            text = element.get_text(separator=" ", strip=True)
            if not text:
                continue
            if len(text.split()) < 5:
                continue
            paragraphs.append(text)
        return "\n\n".join(paragraphs)


def summarize_text(text: str, *, max_sentences: int = 3) -> str:
    """Produce a lightweight extractive summary.

    The algorithm uses word-frequency scoring to select the top N sentences.
    """

    sentences = _split_into_sentences(text)
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    word_freq = Counter()
    for sentence in sentences:
        tokens = _tokenize(sentence)
        word_freq.update(token for token in tokens if token not in STOP_WORDS)

    if not word_freq:
        return " ".join(sentences[:max_sentences])

    max_freq = max(word_freq.values())
    for word in list(word_freq):
        word_freq[word] /= max_freq

    sentence_scores: list[tuple[float, str]] = []
    for sentence in sentences:
        tokens = _tokenize(sentence)
        if not tokens:
            continue
        score = sum(word_freq.get(token, 0.0) for token in tokens)
        sentence_scores.append((score, sentence))

    top_sentences = [s for _, s in sorted(sentence_scores, key=lambda item: item[0], reverse=True)[:max_sentences]]
    return " ".join(sorted(top_sentences, key=lambda s: sentences.index(s)))


def _split_into_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return []
    # Simple heuristic sentence splitter.
    pattern = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-Я0-9])")
    sentences = pattern.split(cleaned)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def _tokenize(sentence: str) -> list[str]:
    return re.findall(r"[a-zA-Zа-яА-Я0-9']+", sentence.lower())


def parse_cli_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI news parsing agent")
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of articles to return",
    )
    parser.add_argument(
        "--min-length",
        type=int,
        default=600,
        help="Minimum character length of article body to include",
    )
    parser.add_argument(
        "--summary-sentences",
        type=int,
        default=3,
        help="Number of sentences to keep in each summary",
    )
    parser.add_argument(
        "--output",
        choices=("json", "markdown"),
        default="markdown",
        help="Output format",
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        help="Override the default list of feed URLs",
    )
    parser.add_argument(
        "--keywords",
        nargs="*",
        help="Override the default list of keywords",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=6,
        help="Number of concurrent downloads",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP request timeout in seconds",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        help="Logging level (e.g. INFO, DEBUG)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_cli_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    agent = AINewsAgent(
        sources=args.sources,
        keywords=args.keywords,
        max_workers=args.max_workers,
        request_timeout=args.timeout,
    )

    articles = agent.collect_articles(
        limit=args.limit,
        min_length=args.min_length,
        summary_sentences=args.summary_sentences,
    )

    if args.output == "json":
        print(agent.to_json(articles))
    else:
        print(agent.to_markdown(articles))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
