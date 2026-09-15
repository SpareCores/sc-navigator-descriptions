Generate technical and highly informative descriptions for the following cloud server.

Focus on key aspects:

- key hardware specifications,
- state CPU architecture,
- emphasize if GPU and storage is bundled,
- key performance characteristics,
- cost efficiency relative to the hardware profile (qualitative only; no exact prices),
- recommend appropriate workload fit.

Avoid speculation beyond the provided data.
Respect the formatting and length constraints exactly.

Draft fields from longest to shortest: write `page` first, then distill into the shorter fields.

Return the result in this JSON format:

{
  "page": ["<up to 500 words total when warranted, one paragraph per array item; use fewer words for simple servers; avoid repetition across paragraphs>"],
  "description": "<around 150 words, up to 175, single cohesive paragraph>",
  "og_description": "<175-225 characters, factual encyclopedia-style summary; include vendor and server name>",
  "meta_description": "<125-175 characters, factual encyclopedia-style summary; include vendor and server name>",
  "tagline": "<15-25 words, readable tagline, do NOT mention vendor or server name>",
  "bullet_points": ["<4-6 concise bullets on key features and best-fit workloads>"],
  "categories": ["<1-3 category values from the list below, most fitting first>"]
}

Additional constraints:

- page should cover hardware specs, benchmark-relative performance, qualitative cost efficiency, tradeoffs, and workload fit; use as many paragraphs as the server warrants, up to 500 words total with no minimum. Each paragraph should add distinct information; do not repeat facts or phrasing across paragraphs.
- description should be a single dense paragraph distilled from page content; aim for around 150 words, up to 175 with no minimum.
- meta_description and og_description must be neutral, factual summaries—not ads or social posts. Start with the vendor and server name as the grammatical subject (e.g. "Google Cloud Platform f1-micro is a ..."). Do not start with imperatives or CTAs such as "Explore", "Discover", or "Learn about".
- og_description should expand slightly beyond the meta description but remain concise.
- tagline should summarize positioning and key differentiators without naming the vendor or server.
- bullet_points must contain 4-6 distinct, concise items (not full sentences copied from page).
- Avoid repeating identical sentences across outputs.
- Discuss cost efficiency in qualitative terms only; do not mention exact prices, hourly rates, or currency amounts, even if present in the input JSON.
- categories must contain 1-3 distinct values from the list below, ordered by relevance (most fitting first):

1. General Purpose
   Balanced vCPU-to-RAM ratio (typically 1:4, like 4 vCPUs to 16 GB RAM).

2. Compute Optimized
   High clock-speed CPUs, lower RAM-to-CPU ratio (1:2, like 4 vCPUs to 8 GB RAM), or specialized high-compute chip families (e.g., AWS C series, GCP C series).

3. Memory Optimized
   Massive RAM arrays relative to vCPUs (1:8 or higher, like 4 vCPUs to 32 GB+ RAM; e.g., AWS R/X series, GCP M series).

4. Storage & Database
   High local NVMe SSD storage capacities, massive sequential read/write speeds, or extreme IOPS profiles.

5. GPU Accelerated
   Presence of hardware accelerators, specifically NVIDIA GPUs (H100, A100, L4) or TPUs/ASICs.

6. Burstable & Budget
   Shared-core configurations, fractioned vCPUs, or CPU credit models (e.g., AWS T instances, GCP E2 shared-core).

Input JSON data:
