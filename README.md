# Spare Cores Navigator Descriptions

This repository contains AI-assisted descriptions of the Spare Cores Navigator database records.

The descriptions are generated using the Gemini 3.5 Flash model utilizing

- a low temperature,
- strictly constrained system and user prompts, and
- a rich JSON input on the server hardware details, pricing information,
  benchmark results, and derived performance metrics -- such as percentile
  scores among other servers.

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

    - `page`: list of paragraph strings, up to 500 words total when warranted (no minimum; avoid repetition across paragraphs)
    - `description`: around 150 words, up to 175, single paragraph (no minimum)
    - `og_description`: around 200 characters, factual encyclopedia-style summary, including vendor and server name
    - `meta_description`: around 150 characters, factual encyclopedia-style summary, including vendor and server name
    - `tagline`: around 20 words, readable tagline, without mentioning vendor or server name
    - `bullet_points`: list of 4-6 concise bullet points on key features and best-fit workloads
    - `categories`: list of 1-3 workload categories, most fitting first (General Purpose, Compute Optimized, Memory Optimized, Storage & Database, GPU Accelerated, or Burstable & Budget)

## Example

Using GCP `a2-highgpu-8g`'s output generated on June 19, 2026 as an example.

Long-form description:

> Google Cloud Platform a2-highgpu-8g is an accelerator-optimized server configured with 8 NVIDIA Ampere A100 GPUs providing a total of 320 GB of VRAM. The host system features 96 vCPUs powered by an Intel Xeon x86_64 processor with 48 physical cores, operating at a base frequency of 2.2 GHz. The CPU allocation is fully dedicated, supported by 680.0 GB of system memory (7.08 GB per core), and cache capacities of 1536 KB L1d, 48 MB L2, and 77 MB L3. Local storage is not bundled with this instance type.
>
> Benchmark data reveals top-tier performance in large-scale parallel processing and machine learning tasks. The server achieves top-10% tier results in LLM inference prompt processing across small, medium, and large models, as well as top-tier text generation speeds for 7B and 70B models. Multi-core CPU performance is strong, as demonstrated by stress-ng multi-core and PassMark CPU extended instructions tests. Memory bandwidth is also highly performant, reaching 4215.1 GB/sec for cached small blocks and 219.95 GB/sec for uncached large blocks. Conversely, single-core CPU performance is relatively weak, with lower scores in single-threaded compression and decompression tasks.
>
> Given the high-density GPU and memory configuration, this server represents a specialized hardware class designed for resource-intensive workloads. While single-threaded CPU tasks do not leverage the system's strengths, the massive parallel processing capabilities of the 8 NVIDIA A100 GPUs and 96 dedicated vCPUs make it highly cost-efficient for large-scale AI training, LLM inference, complex simulations, and data science pipelines. It is optimized for workloads that can offload massive computational tasks to the GPU array rather than relying on single-core CPU speed.

Short-form description:

> Google Cloud Platform a2-highgpu-8g is an accelerator-optimized server designed for intensive parallel computing and machine learning workloads. It features 8 NVIDIA Ampere A100 GPUs with a total of 320 GB of VRAM, paired with 96 dedicated Intel Xeon vCPUs (48 physical cores) running at 2.2 GHz on an x86_64 architecture. The system is equipped with 680.0 GB of RAM, though it lacks local storage. Performance benchmarks highlight top-tier capabilities in LLM inference prompt processing and text generation, alongside strong multi-core CPU execution and high memory bandwidth. However, single-core CPU performance remains weak. This server is highly suited for large-scale AI model training, deep learning inference, and complex data science pipelines that require massive GPU acceleration and high memory capacity.

Shorter description:

> Google Cloud Platform a2-highgpu-8g is an accelerator-optimized server featuring 8 NVIDIA Ampere A100 GPUs, 96 dedicated Intel Xeon vCPUs, and 680 GB of RAM, designed for high-performance AI and machine learning workloads.

Tagline:

> An accelerator-optimized platform featuring eight dedicated GPUs and high-capacity memory for demanding machine learning and parallel computing workloads.

Bullet points:

- 8 NVIDIA Ampere A100 GPUs with 320 GB total VRAM
- 96 dedicated Intel Xeon vCPUs and 680 GB of system memory
- Top-tier LLM inference performance for prompt processing and text generation
- Strong multi-core CPU performance and high memory bandwidth
- No local storage bundled with the instance
- Best suited for AI training, large-scale inference, and data science

Categories:

- GPU Accelerated
- Memory Optimized

## License

All data records and software in this repository are licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Please contact us if you are unhappy with these licensing terms -- we would love to hear what you are working on and help you find the best setup.

## Further References

- [`sparecores-crawler` documentation](https://sparecores.github.io/sc-crawler/)
- [Database schemas](https://dbdocs.io/spare-cores/sc-crawler)
- [sparecores-data Python package](https://pypi.org/project/sparecores-data/)
- [sparecores.com](https://sparecores.com)
