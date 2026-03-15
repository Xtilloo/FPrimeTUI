# F-Prime-TUI Project Makefile

.PHONY: TUI install clean help cmux close remind

# Path to the project's virtual environment python
PYTHON = ./venv/bin/python3
PIP = ./venv/bin/pip

TUI: ## Launch Mission Control (F-Prime-TUI)
	@echo "🚀 Launching Mission Control..."
	@PYTHONPATH=./TUI $(PYTHON) TUI/app.py

alias: ## Create a symbolic link to fprime-tui in /usr/local/bin (requires sudo)
	@echo "🔗 Creating fprime-tui alias..."
	@sudo ln -sf $(CURDIR)/fprime-tui /usr/local/bin/fprime-tui
	@echo "✅ You can now run 'fprime-tui' from anywhere!"

install: ## Install dependencies from requirements.txt
	@echo "📦 Setting up virtual environment..."
	@python3 -m venv venv
	@echo "📦 Installing project dependencies..."
	@$(PIP) install -r requirements.txt

clean: ## Remove temporary and build files
	@echo "🧹 Cleaning up project..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

lint: ## Run static analysis (ruff and mypy)
	@echo "🔍 Running static analysis with ruff..."
	@$(PYTHON) -m ruff check .
	@echo "🔍 Checking types with mypy..."
	@$(PYTHON) -m mypy .

test: lint ## Run the full test suite (lint + pytest)
	@echo "🧪 Running test suite with pytest..."
	@PYTHONPATH=./TUI $(PYTHON) -m pytest tests/

help: ## Show this help message
	@echo "Mission Control Commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
