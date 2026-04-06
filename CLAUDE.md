# Reddit Insight Engine — Project Guide

## What This Project Does

Extracts posts and comments from `r/finance_ukr`, processes and cleans the data, summarizes each discussion, extracts recurring themes and pain points, and generates actionable recommendations using LLMs.

## Architecture

```
src/main/
  models.py      # Pydantic data models: Post, Comment, AnalysisResult
  scraper.py     # Fetch posts & comments from Reddit via PRAW
  storage.py     # DuckDB persistence: raw posts/comments + analysis results
  processor.py   # Text cleaning and chunking for LLM context limits
  analyzer.py    # OpenAI Chat Completions: summarize, themes, recommendations
  pipeline.py    # Orchestrates: scrape → store raw → process → analyze → store
  config.py      # Reads config.json, validates with Pydantic, exposes Config singleton
  logger.py      # Structured logging

config.json          # Local config file (gitignored — contains secrets)
config.example.json  # Committed template with empty values
scripts/
  run.py         # Entry point — calls pipeline
```

## Module Responsibilities

| Module | Responsibility |
|---|---|
| `models.py` | Single source of truth for data shapes shared across all modules |
| `scraper.py` | PRAW client — fetches posts and comment trees, returns typed models |
| `storage.py` | DuckDB read/write — idempotent (skip already-stored post IDs) |
| `processor.py` | Strip URLs/markdown/noise, truncate/chunk long threads |
| `analyzer.py` | Stateless LLM calls — takes text in, returns structured output |
| `pipeline.py` | Only module that knows execution order; wires all others together |
| `config.py` | Loads and validates `config.json` at startup |

## Tech Stack

| Need | Library |
|---|---|
| Reddit API | `praw` |
| Data models + config validation | `pydantic` v2 |
| LLM | `openai` (Chat Completions, default model: `gpt-4o`) |
| Storage | `duckdb` |
| Retry / rate-limit handling | `tenacity` |

## Configuration

Config is file-based. Copy `config.example.json` → `config.json` and fill in credentials.

```json
{
  "reddit": {
    "client_id": "",
    "client_secret": "",
    "user_agent": "reddit-insight-engine/0.1",
    "subreddit": "finance_ukr",
    "post_limit": 100
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

`config.json` is gitignored. Never commit secrets.

## Development Commands

```bash
make test       # pytest with coverage
make lint       # ruff check
make format     # ruff format
make typecheck  # mypy (strict)
```

## Key Constraints

- Python only
- Simple MVP first — no overengineering
- Scalable: pipeline designed for future batch processing
- Each module has a single responsibility; `pipeline.py` is the only orchestrator
