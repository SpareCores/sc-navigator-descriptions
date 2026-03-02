# Spare Cores Navigator Descriptions

This repository contains AI-assisted descriptions of the Spare Cores Navigator database records.

The descriptions are generated using the Gemini 2.5 Flash model utilizing

- a low temperature,
- strictly constrained system and user prompts, and
- a rich JSON input on the server hardware details, pricing information,
  benchmark results, and derived performance metrics -- such as percentile
  scores among other servers.

## License

The data records published in this repository are licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## Repository Structure

The repository is updated via the following Python script:

```shell
python src/summarize/generate.py
```

All utilized inputs (including server and benchmark details, user and system
prompts, and model configuration) are stored in the repository for
reproducibility. The inputs and generated outputs are stored in separate files
for each server record under the `data` folder:

- `model.json` LLM model and its config
- `input.json` all data shared with the LLM
- `system_prompt.md` and `user_prompt.md`
- `hashes.json` hashes of the inputs to detect changes

## Further References

- [`sparecores-crawler` documentation](https://sparecores.github.io/sc-crawler/)
- [Database schemas](https://dbdocs.io/spare-cores/sc-crawler)
- [sparecores-data Python package](https://pypi.org/project/sparecores-data/)
- [sparecores.com](https://sparecores.com)
