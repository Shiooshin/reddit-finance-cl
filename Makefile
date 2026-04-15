.PHONY: install shell run test lint format typecheck clean

install:
	poetry install

run:
	poetry run python run.py

shell:
	poetry shell

test:
	poetry run pytest

lint:
	poetry run ruff check src tests
	poetry run flake8 src/ tests/

format:
	poetry run ruff format src tests

typecheck:
	poetry run mypy src

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov .pytest_cache .mypy_cache .ruff_cache dist
