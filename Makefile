.PHONY: default
default: run ;

ARGS ?= --n 5

install:
	uv pip install -r requirements.txt

run:
	uv run python -m src.summarize.generate $(ARGS)
