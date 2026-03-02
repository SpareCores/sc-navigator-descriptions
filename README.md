# Spare Cores Navigator Descriptions

This repository contains AI-assisted descriptions of the Spare Cores Navigator database records.

The descriptions are generated using the Gemini 2.5 Flash model utilizing

- a low temperature,
- strictly constrained system and user prompts, and
- a rich JSON input on the server hardware details, pricing information,
  benchmark results, and derived performance metrics -- such as percentile
  scores among other servers.

## License

All data records and software in this repository are licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Please contact us if you are unhappy with these licensing terms -- we would love to hear what you are working on and help you find the best setup.

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
- `output.json` the generated summary in JSON format with the following fields:

    - `w20`: around 20 words, readable tagline, without mentioning vendor or server name
    - `c150`: around 150 characters description, including vendor and server name
    - `c200`: around 200 characters, longer-format description
    - `w150`: around 150 words, even longer description

## Further References

- [`sparecores-crawler` documentation](https://sparecores.github.io/sc-crawler/)
- [Database schemas](https://dbdocs.io/spare-cores/sc-crawler)
- [sparecores-data Python package](https://pypi.org/project/sparecores-data/)
- [sparecores.com](https://sparecores.com)
