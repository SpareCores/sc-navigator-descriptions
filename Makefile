.PHONY: default
default: run ;

install:
	uv pip install -r requirements.txt

run:
	uv run python -m src.summarize.generate $(ARGS)
