# Reddit Insight Engine — Project Guide

## What This Project Does

Extracts posts and comments from `r/finance_ukr`, processes and cleans the data, summarizes each discussion, extracts recurring themes and pain points, and generates actionable financial insights using LLMs.

## Architecture

```
src/main/
  models.py      # Pydantic models: Post, Comment, Opportunity, AnalysisResult
  scraper.py     # PRAW client — fetches posts & comment trees from Reddit
  storage.py     # DuckDB persistence (STUB — not yet implemented)
  processor.py   # Text cleaning: strips URLs, removes deleted comments, truncates
  analyzer.py    # OpenAI Chat Completions: structured financial insight extraction
  pipeline.py    # Orchestrator (STUB — run() not yet implemented)
  config.py      # Loads config.json, validates with Pydantic, exposes get_config()
  logger.py      # Structured logging — get_logger(name) + configure_root(level)

config.json          # Local config (gitignored — never commit)
config.example.json  # Committed template with empty values
scripts/
  main.py         # Entry point — calls Pipeline().run()
```

## Implementation Status

| Module | Status |
|---|---|
| `models.py` | Complete |
| `config.py` | Complete |
| `logger.py` | Complete |
| `scraper.py` | Complete |
| `processor.py` | Complete |
| `analyzer.py` | Complete |
| `storage.py` | **Stub** — method signatures only, no DuckDB logic |
| `pipeline.py` | **Stub** — `run()` is empty |
| `tests/` | Stubs/placeholders only |
| CI (`.github/workflows/ci.yml`) | **Stub** — TODO steps only |

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `models.py` | Single source of truth for data shapes shared across all modules |
| `scraper.py` | PRAW client — credentials from env vars; fetches posts sorted by score, top N comments per post |
| `storage.py` | DuckDB read/write — idempotent (skip already-stored post IDs) |
| `processor.py` | Strip URLs, normalise whitespace, remove deleted comments, truncate to 1000 chars |
| `analyzer.py` | One Chat Completions call per post; returns JSON parsed into `AnalysisResult` |
| `pipeline.py` | Only module that knows execution order; wires all others together |
| `config.py` | Loads and validates `config.json` at startup via singleton `get_config()` |

## Data Models (`models.py`)

```python
Comment(id, post_id, body, author, score, created_at)

Post(id, title, selftext, author, score, num_comments, created_at, url, comments: list[Comment])

Opportunity(
    type: "investment" | "product" | "business" | "content",
    description, rationale,
    risk_level: "low" | "medium" | "high",
    time_horizon: "short" | "medium" | "long"
)

AnalysisResult(
    post_id, summary,
    sentiment: "bullish" | "bearish" | "neutral" | "mixed",
    key_topics: list[str],
    pain_points: list[str],
    user_intents: list[str],
    market_signals: list[str],
    opportunities: list[Opportunity],
    contrarian_insights: list[str],
    confidence_score: int,   # 0–100
    analyzed_at
)
```

## Tech Stack

| Need | Library |
|---|---|
| Reddit API | `praw` |
| Data models + config validation | `pydantic` v2 |
| LLM | `openai` (Chat Completions, `response_format=json_object`, `temperature=0.2`) |
| Storage | `duckdb` |
| Retry / rate-limit handling | `tenacity` |

## Configuration

### config.json (gitignored)

Copy `config.example.json` → `config.json` and fill in values:

```json
{
  "reddit": {
    "client_id": "",
    "client_secret": "",
    "user_agent": "reddit-insight-engine/0.1",
    "subreddit": "finance_ukr",
    "post_limit": 10,
    "comment_limit": 10
  },
  "openai": {
    "api_key": "",
    "model": "gpt-4o",
    "max_tokens": 1024
  },
  "storage": {
    "db_path": "data/insights.duckdb"
  },
  "logging": {
    "level": "INFO"
  }
}
```

### Reddit credentials (env vars)

`scraper.py` reads Reddit credentials from environment variables, **not** from config.json:

```
REDDIT_CLIENT_ID      (required)
REDDIT_CLIENT_SECRET  (required)
REDDIT_USER_AGENT     (optional, defaults to "reddit-insight-engine/0.1")
```

`config.json` values for `client_id` / `client_secret` / `user_agent` are validated by Pydantic but not used at runtime.

## Development Commands

```bash
make install    # poetry install (creates .venv/)
make shell      # poetry shell (activate venv)
make test       # pytest with coverage
make lint       # ruff check src tests
make format     # ruff format src tests
make typecheck  # mypy src (strict)
make clean      # remove __pycache__, .coverage, .mypy_cache, etc.
```

## Key Constraints

- Python only
- Simple MVP first — no overengineering
- Each module has a single responsibility; `pipeline.py` is the only orchestrator
- `config.json` is gitignored — never commit secrets
