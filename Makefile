.PHONY: default
default: run ;

install:
	uv pip install -r requirements.txt

run:
	uv run python src/summarize/generate.py $(ARGS)
