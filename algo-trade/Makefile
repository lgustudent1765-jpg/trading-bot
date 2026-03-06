# file: Makefile
.PHONY: install test lint format backtest demo docker-build docker-run clean

install:
	pip install -r requirements.txt

test:
	pytest -q --tb=short

test-cov:
	pytest --cov=src --cov-report=term-missing --cov-report=html

lint:
	flake8 src/ tests/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/ scripts/
	isort src/ tests/ scripts/

backtest:
	python scripts/backtest.py sample_data/minute_sample.csv

demo:
	bash run_paper_demo.sh

docker-build:
	docker build -t algo-trade .

docker-run:
	docker run --env-file .env -p 8080:8080 algo-trade

docker-paper:
	docker-compose up -d

docker-backtest:
	docker-compose --profile backtest run --rm algo-trade-backtest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
