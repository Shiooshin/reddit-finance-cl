# main

Short project description.

## Setup

```bash
poetry install        # creates .venv/ and installs all dependencies
```

Activate the virtual environment:

```bash
poetry shell          # spawns a shell inside the venv
# or
source .venv/bin/activate
```

## Usage

```bash
python scripts/run.py
# or without activating the venv:
poetry run python scripts/run.py
```

## Development

| Command          | Description              |
|------------------|--------------------------|
| `make test`      | Run test suite           |
| `make lint`      | Lint with ruff           |
| `make format`    | Auto-format with ruff    |
| `make typecheck` | Type-check with mypy     |
| `make clean`     | Remove build artifacts   |

## Architecture

Describe key modules and their responsibilities here.

## License

MIT
