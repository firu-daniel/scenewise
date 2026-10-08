# Review r1: q3-summaries-chapters.md

Reviewer: fresh review agent (did not write the file). All sources re-opened on 2026-10-08.
Severity scale: **wrong** (contradicted by source), **unsupported** (source does not back the claim as written, or the claim omits a material caveat), **missing option** (an alternative or consideration the research should have covered), **minor** (citation, wording, precision).

Cost arithmetic was re-done line by line. Every figure in the cost tables, the caching saving, the Haiku 4.5 comparison, the scale estimates, the 4090 break-even and the per-video timing table checks out (see "Verified as correct"). Most findings are about caveats and missed options, not arithmetic.

## Findings

1. **"Thinking (estimate). 0 when off or at `low` effort."** (line 90; also implied by "Set effort `low` or turn thinking off", line 11)
   → Effort docs: "Effort is a behavioral signal, not a strict token budget. At lower effort levels, Claude still thinks on sufficiently difficult problems, but thinks less than it would at higher effort levels." Haiku 5.5 section: "you can also send `thinking: {"type": "disabled"}` at `high` effort or below." (https://platform.claude.com/docs/en/build-with-claude/effort, read 2026-10-08)
   → **wrong**
   → Say thinking is 0 only with `thinking: {type: "disabled"}`. `low` effort reduces thinking but does not guarantee zero. Recommend sending **both** `thinking: {type:"disabled"}` and `output_config.effort: "low"` (allowed together on Haiku 5.5). Change "or" to "and" in the recommendation, and fix open question 2 to match.

2. **"Neither side supports numeric constraints in the schema [S4][S24]"** (lines 26, 205: "Neither schema dialect expresses numeric bounds")
   → llama.cpp grammars README: "minimum, exclusiveMinimum, maximum, exclusiveMaximum: only supported for "type": "integer" for now, not number". The example also uses minLength/maxLength and minItems/maxItems, which compile into repetition bounds. (https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md, read 2026-10-08). The claim holds for Anthropic only: "Numerical constraints (such as `minimum`, `maximum`, `multipleOf`)" and "Array constraints beyond `minItems` of 0 or 1" are unsupported (structured-outputs page).
   → **wrong** (for the llama.cpp half)
   → Say that llama.cpp supports integer `minimum`/`maximum` and item and length bounds, and Anthropic does not. The conclusion still stands: cross-field rules (ascending, at least 10 s apart, last start before the duration) need the Python validator either way. A useful side effect: on the local backend, `start_s` as an integer with `minimum: 0` and `minItems: 3` can be enforced at decode time.

3. **"When fine-tuned, 1B models are clearly too small (23.5 F1). 3B (35.2) is close to 8B (38.5)" / "3B is the practical floor."** (lines 22, 177)
   → Chapter-Llama Table A.8 (LLM variants): speech only gives 1B 23.5, 3B 35.2, 8B 38.5, 11B 39.8. **Speech + captions** gives 1B 24.6, **3B 34.7, 8B 42.6**. These are validation-set ablations (300 videos, 1k training videos). (https://arxiv.org/html/2504.00072v1, appendix, read 2026-10-08)
   → **unsupported** (cherry-picked condition)
   → The doc recommends speech plus frame labels. Under that input the 3B-to-8B gap is about 8 F1 points, not 3, and 3B gains nothing from captions (34.7 vs 35.2). Report both rows. Note that this weakens the case for a ~4B default when labels are used. Add it to open question 10, and consider Qwen3.5-9B (or a small-active MoE, see finding 14) as the self-host default whenever frame labels are passed.

4. **"Expected cost … about $0.0024 per video-hour with Batch"** together with **"Prod (Expause): Claude Haiku 5.5 through the Message Batches API"** (lines 9–12)
   → Batch docs: "most batches completing within 1 hour … Batches expire if processing does not complete within 24 hours." Also: "processing may be slowed down based on current demand … you may see more requests expiring after 24 hours." (https://platform.claude.com/docs/en/build-with-claude/batch-processing, read 2026-10-08)
   → **missing option / unsupported** (latency trade-off not discussed)
   → State that Batch latency is up to 24 h, and that expired requests must be resubmitted. For Expause, a summary that appears hours after upload may be unacceptable. Recommend: synchronous calls for fresh uploads (still about $0.005 per video-hour, which is negligible) and Batch for backfills and re-processing. Or make the choice per-operator config.

5. **"Prompt caching of the 800-token fixed prefix saves … about 18% of Scenario A, and only while traffic keeps the 5-minute cache warm"** (line 101), combined with the Batch recommendation
   → Batch docs: "cache hits are provided on a best-effort basis. Users typically experience cache hit rates ranging from 30% to 98%". Also: "Because batches can take longer than 5 minutes to process, consider using the 1-hour cache duration." (same URL)
   → **unsupported** (caveat missing)
   → Add that with Batch the saving is best-effort (30–98% hit rate) and that a 1-hour cache write (2× input) is recommended. The 1-hour write ($0.20/MTok) changes the break-even. The arithmetic itself (800 × $0.09/M × 12 ≈ $0.00086/h ≈ 18%) is correct.

6. **"Minimum cacheable prefix is 512 tokens for Haiku 5.5 … I did not confirm it there (open question)"** (line 61; open question 2)
   → Prompt-caching page: "512 tokens for … Claude Haiku 5.5"; "4,096 tokens for Claude Haiku 4.5". (https://platform.claude.com/docs/en/build-with-claude/prompt-caching, read 2026-10-08)
   → **minor** (now confirmed)
   → Cite the docs page, drop the caveat, and remove that part of open question 2. Optionally note that Haiku 4.5's 4,096-token minimum means the 800-token prefix would not cache on 4.5 at all.

7. **"Thinking tokens are billed as output [S2][S3]"** (line 11)
   → Neither S2 nor S3 says this. The Thinking page does: "the tokens Claude spends reasoning are billed as output tokens, even when the thinking text isn't returned to you, and they count toward `max_tokens`." (https://platform.claude.com/docs/en/build-with-claude/thinking, read 2026-10-08)
   → **minor** (citation)
   → Cite the Thinking page. Add the practical consequence: with thinking on, a small `max_tokens` can stop after the thinking block, which gives `stop_reason: "max_tokens"` and invalid JSON.

8. **Refusal / no server-side fallback, cited to [S5]** (a local skill file) (lines 104, 271)
   → Primary source: What's new in Haiku 5.5 table: "Safety classifiers can decline a request … Handle `stop_reason: "refusal"` in your client. Server-side fallback isn't available." (https://platform.claude.com/docs/en/models/haiku-5-5/whats-new-haiku-5-5, read 2026-10-08)
   → **minor** (citation; claim is correct)
   → Replace [S5] with this URL. Once findings 6 and 8 are applied, [S5] can be dropped entirely.

9. **Missing Haiku 5.5 breaking changes relevant to the implementation**
   → The same What's new page lists these as breaking or changed: "Assistant message prefill returns an error" (end `messages` with a user turn), "Responses can begin with thinking blocks" (select content blocks by `type`, not position), and "Thinking text is omitted by default".
   → **missing option** (implementation guidance)
   → Add a short note to the Haiku section. Prefilling `{` to force JSON is a common pattern and fails with a 400 on Haiku 5.5. Code that reads `content[0]` breaks when thinking is on.

10. **"Some older Qwen checkpoints used non-Apache Qwen licences (memory, not verified; open question)" / open question 6 / "Family-wide Apache-2.0 per secondary report [S10a]"** (lines 111, 268)
    → Hugging Face model API (https://huggingface.co/api/models/<id>, read 2026-10-08): Qwen3.5-0.8B, -2B, -4B, -9B, -27B, -35B-A3B are all `apache-2.0`, and so are Qwen3-4B-Instruct-2507 and Qwen3-8B. **Qwen2.5-3B-Instruct is `license: other`** (the Qwen Research licence). **Qwen3.8-Flash-Next (Aug 2026) is `license: other`, `license_name: qwen-community-1.0`.** Qwen3.8-27B is `apache-2.0`.
    → **unsupported → now resolvable** (and the caveat is stronger than stated)
    → Replace the secondary [S10a] with per-card verification of all four Qwen3.5 small sizes (all Apache-2.0). Change the memory note to the verified fact: Qwen2.5-3B uses a non-Apache licence, and the newest Qwen3.8-Flash-Next uses a new "Qwen Community" licence. Keep the per-checkpoint check as a rule. Close open question 6.

11. **"Gemma 4 (E2B, E4B, 12B, 26B A4B, 31B; Apr 2026)" and "E2B/E4B have 128K context and take text, image and audio input"** (line 112)
    → Gemma 4 blog dated 2026-04-02 (correct). HF: E2B/E4B repos were created 2026-03-02, 26B-A4B and 31B on 2026-03-11, but **12B on 2026-05-23**. The E4B card lists "Text, Image, Audio, Video (as frames)" for E2B/E4B/12B, with audio only on E2B, E4B and 12B; 12B/26B/31B have 256K context. (https://huggingface.co/google/gemma-4-E4B-it, read 2026-10-08)
    → **minor**
    → Write "Apr 2026 (12B added May 2026)". Add video-as-frames to the modalities. Note that 12B, 26B and 31B have 256K context. 12B is a natural escalation step between Qwen3.5-9B and 26B.

12. **Gemma 3 terms "hosted API counts as distribution (secondary reading) [S13]"** (line 113)
    → Primary Gemma Terms of Use (last modified 2026-04-01), §1.1(b): distribution includes "providing or making Gemma or its functionality available as a hosted service via API, web access". §3.1 requires the use restrictions to flow down as "an enforceable provision". The Appendix covers Gemma 3 and 3n; Gemma 4 is under a separate licence. (https://ai.google.dev/gemma/terms, read 2026-10-08)
    → **minor** (claim correct; source weak)
    → Cite the primary terms instead of Vorp Labs.

13. **Llama 3.2 licence: "You must display 'Built with Llama'. Derivative models must be named starting with 'Llama'." "Above 700M MAU you must request a licence"** (line 114)
    → Licence §1.b.i: attribution applies "If you distribute or make available the Llama Materials (or any derivative works thereof)…". The naming rule applies to a model you "create, train, fine tune, or otherwise improve" **that is distributed or made available**. §2: the 700M MAU test is applied to MAU "in the preceding calendar month" **on the Llama 3.2 release date**. (https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct/blob/main/LICENSE.txt, read 2026-10-08)
    → **minor** (over-broad paraphrase)
    → Add the triggers. Scenewise distributing or serving Llama would trigger the attribution, but the naming rule does not apply because there is no fine-tuning. The MAU test is a snapshot at release, not an ongoing threshold. The EU multimodal AUP clauses for 3.2 and 4 were verified verbatim, including the end-user exemption.

14. **Missing local model options released before 2026-10-08**
    → HF API (read 2026-10-08):
    - **Granite 4.2 3B and 8B** (2026-08-07, `apache-2.0`, GGUF published) supersede the listed Granite 4.0 micro (2025-09).
    - **Qwen3.6-35B-A3B** (2026-04-15) and **Qwen3.5-35B-A3B** (2026-02-24) are `apache-2.0` MoEs with about 3B active parameters. Their generation speed is near a 3B model's, at much higher quality, on any host with about 20+ GB of RAM or VRAM at Q4.
    - **Qwen3.8-27B** (2026-08-05, `apache-2.0`) is a GPU-tier option.
    - **Ministral 3 3B Instruct 2512** (`apache-2.0`) is a smaller sibling of the listed 8B.
    - **microsoft/FrogNano-4B-2609** (2026-09-17, `mit`) is a new 4B. It is unevaluated, so check the card.
    - **LiquidAI LFM2.5 / d1-3B** (Aug–Oct 2026) use `lfm1.0`, which is not Apache. Exclude them, but list them as checked.
    → **missing option**
    → Add these rows to the licence table. Evaluate a 3B-active MoE (Qwen3.6-35B-A3B) as the "GPU or large-RAM self-hoster" tier next to Qwen3.5-9B. Replace or supplement Granite 4.0 micro with Granite 4.2 3B/8B.

15. **No comparison of other cheap hosted APIs**
    → The brief says "local free models or cheap hosted ones, Claude Haiku first". The doc compares only Haiku 5.5 with local models. Hosted open-weight inference (for example, Qwen3.5/3.6 or Gemma 4 on OpenRouter, DeepInfra or Groq) would let self-hosters without a GPU run the same model family as dev. Other vendors' small models are also absent.
    → **missing option**
    → Add at least one line on hosted open-weight endpoints behind the same OpenAI-compatible interface (the planned provider interface already allows it), with prices researched or marked TODO. Haiku 5.5 remains the first choice; this is about completeness.

16. **"An RTX 4090 that finishes a 5-minute video in about 2 s does about $0.70/h of Haiku-equivalent work"** (lines 19, 270)
    → Arithmetic check: 3,600 s / 2 s = 1,800 videos/h × $0.000395 = $0.71/h. That is correct at **standard** prices, but the recommended prod path is Batch, which gives **$0.36/h**. The 2 s comes from llama.cpp batch-1 numbers. Red Hat's A100 test shows vLLM serving concurrent users at about 793 tok/s aggregate vs 41 tok/s for Ollama (https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking, read 2026-10-08), so a saturated GPU on vLLM would process many more videos per hour than the batch-1 figure implies.
    → **unsupported** (inconsistent basis)
    → Quote both $0.71/h (standard) and $0.36/h (Batch). State that the 2 s per video is single-stream, and that a batched vLLM server would raise the GPU's Haiku-equivalent value several-fold. That shifts the break-even, which stays open (question 8).

17. **"Videos without speech (fine-tuned): F1 15.5, vs about 42 with speech. Successes rely on on-screen text. Music videos fail."** (line 186; also line 30)
    → Table A.12 covers 190 validation videos with no ASR: Chapter-Llama F1 15.5, Vid2Seq 12.6. The 42.6 is the score for **all** 300 validation videos, not a with-speech subset. Text: speechless videos with OCR text give "satisfactory chaptering"; speechless videos without on-screen text (e.g. only music) are "inferior, though still acceptable". Failure cases come from "very similar backgrounds across frames". (https://arxiv.org/html/2504.00072v1, read 2026-10-08)
    → **minor** (overstated)
    → Say "vs 42.6 on the full validation set (indicative only)" and "music-only videos are weaker" instead of "fail". Add n = 190.

18. **Input ablation table "(zero-shot) speech only 22.7 / captions only 12.6 / both 29.9"** (lines 179–184, 30, 244)
    → The numbers are correct, but they come from Table 2, a validation ablation (300 videos). The paper's fine-tuned row of the same table is 38.5 / 39.1 / 42.6, where captions alone almost match speech alone.
    → **minor**
    → Label the table as the validation subset. Optionally add the fine-tuned row: it shows that caption-only weakness is largely a zero-shot effect, which matters for the no-speech path.

19. **"Real creators chapter at roughly 2-minute granularity. A 5-minute video at that density has only about 2 chapters"** (line 229)
    → VidChapters-7M: average video 1,354 s, 8.3 chapters, adjacent starts 142.0 s apart (https://arxiv.org/html/2309.13952, read 2026-10-08). These are dataset averages dominated by ~22-minute videos. The paper's numbers do not say that density is constant with length.
    → **unsupported** (extrapolation)
    → Mark it as (judgement): chapter density on short videos is unknown, and shorter videos may be chaptered more densely. The 120 s threshold is already flagged as judgement, which is fine.

20. **"Disable it with `enable_thinking: False`"** (Qwen3.5 row, line 111)
    → Qwen3.5-4B card: on OpenAI-compatible servers, pass `chat_template_kwargs: {"enable_thinking": false}`. The bare `"enable_thinking": False` is the Alibaba Model Studio form. The card also states that Qwen3.5 does **not** support the `/think` and `/nothink` soft switches. (https://huggingface.co/Qwen/Qwen3.5-4B, read 2026-10-08)
    → **minor**
    → Give the exact form per runtime: `chat_template_kwargs` for vLLM, SGLang and llama-server, and `think: false` for Ollama. Note that the soft switches do not work. Also note that **SmolLM3-3B has extended thinking on by default** (card), which the SmolLM3 row omits. **Qwen3-4B-Instruct-2507 is non-thinking only** (card), which makes it a simpler drop-in for latency-sensitive use.

21. **"Qwen3.5 small (0.8B, 2B, 4B, 9B; ~Mar 2026)"** (line 111)
    → HF repos were created 2026-02-27/28. The secondary source says the release was 2026-03-02. The 4B card's citation says February 2026.
    → **minor**
    → "late Feb / early Mar 2026" is fine. No change needed beyond citing the HF dates.

22. **Speaking rate "150 wpm … attributed to NCVS" [S6]** (line 74)
    → VirtualSpeech quotes NCVS at "about 150 wpm", but its own conversational range is 120–150 wpm and it gives 150–160 wpm for podcasters (https://virtualspeech.com/blog/average-speaking-rate-words-per-minute, read 2026-10-08).
    → **minor**
    → Optionally mention the 150–160 wpm podcaster figure as a better proxy for talking-head UGC. It supports the 200 wpm high case. No change to the arithmetic is needed.

## Verified as correct

- Model ID `claude-haiku-5-5`, released 2026-10-07, retirement not sooner than 2027-10-07, 1M context, 128K max output (300K on Batch with beta header), text and image input (Haiku 5.5 overview page; models overview).
- All Haiku 5.5 prices for ≤100k and >100k prompts (input, output, 5m/1h cache write, cache read, Batch $0.05/$0.25 and $0.25/$1.25), Haiku 4.5 prices, the 50% Batch discount, and that Batch and caching stack (pricing page).
- Adaptive thinking on by default. Default effort `medium` (models overview, Haiku page, effort page). Non-default `temperature`/`top_p`/`top_k` return a 400 error.
- Tokenizer: about 30% more tokens than Haiku 4.5. 1M tokens ≈ 555k words on the current tokenizer vs 750k earlier, which gives 1.80 and 1.33 tokens/word. The FAQ's "1 token ≈ 0.75 words" is quoted correctly.
- Structured outputs: `claude-haiku-5-5` supported, `output_config.format`, the guarantee quote, the exceptions (refusal, `max_tokens`, enum/const capitalisation), unsupported min/max, length and array constraints (`minItems` only 0 or 1), 400 error on unsupported features, grammar cache 24 h from last use, limits of 20 strict tools / 24 optional parameters / 180 s compile timeout, and that changing `output_config.format` invalidates the prompt cache (structured-outputs page; note that the prompt-caching page's invalidation table does not list it).
- Cost arithmetic: Scenario A $0.00474/h ($0.00237 Batch, $0.000395 per video). B $0.01344/h ($0.00672, $0.00112). C $0.00236 ($0.0012). Caching ≈ $0.00086/h ≈ 18%. Haiku 4.5 ≈ $0.036/h. 1M videos ≈ $395 / $198 (A) and $1,120 / $560 (B). 2,450 input tokens per 5-minute video. 720 timestamps/h and 1,800 labels/h.
- Local timing: M1 Pro 9.2 + 8.2 s, T4 2.0 + 6.5 s, 4090 0.2 + 1.6 s, EPYC 10.8 s, VPS 94 s. All llama.cpp scoreboard numbers match (M1 117.96/14.15, M1 Pro 266.25/36.41, M4 Pro 439.78/50.74, M4 Max 885.68/83.06, 4090 11,992.7/186.2, A100 4,849.5/190.9, T4 1,219.1/46.4, 4060 Ti 3,394.6/63.9; non-FA rows).
- Leaseweb: 2× EPYC 9334, 24 threads, DeepSeek-R1-0528-Qwen3-8B Q4 at 27.8 tok/s, Llama-2-7B TTFT 4.8 s. Red Hat: A100 40 GB, vLLM about 793 vs Ollama about 41 tok/s, Ollama "primarily designed for single-user scenarios".
- Chapter-Llama: CVPR 2025 (CVF open access), authors. Zero-shot 8B All 29.5/6.2/30.7, Short 29.9/7.1/34.5, Medium 30.6. Proprietary on a 10% subset: 31.2 / 37.6 / 40.2 / 42.2. Fine-tuned 45.3. Short vs medium F1 similar.
- VidChapters-7M: 817K videos, 1,354 s average, 8.3 chapters, 142.0 s spacing, 97.3% with ASR (so 2.7% without).
- YouTube: first timestamp 00:00, at least three ascending timestamps, minimum 10 s each, and no video-length rule stated.
- Xu et al.: 19 SLMs, 2,000 news samples, Phi3-Mini and Llama3.2-3B "comparable to those of 70B LLMs", more concise, simple prompts better. JSONSchemaBench: 10K schemas, the six named frameworks, the compliance quote.
- llama.cpp: subset of JSON Schema, "skipped silently", nested `$ref` and `prefixItems` broken, schema not injected into the prompt. Ollama `format` takes a JSON schema (blog dated 2024-12-06). vLLM: xgrammar or guidance backends, `response_format` json_schema.
- Licences: Qwen3-4B-Instruct-2507 Apache-2.0 with 262k context. Qwen3.5-4B Apache-2.0, vision and video input, 262k context, thinking on by default. Gemma 4 Apache-2.0 with the "first in the Gemmaverse" quote (blog 2026-04-02). Phi-4-mini-instruct MIT, 3.8B, 128K. SmolLM3-3B Apache-2.0, 64k trained and 128k via YaRN. Granite 4.0 micro Apache-2.0, 3B, 128K, lists summarization. Ministral 3 8B Apache-2.0, 8.4B + 0.4B vision, 256k. Llama 3.2 and Llama 4 AUP EU multimodal clause with end-user exemption (both verified verbatim). AUP incorporated by reference into the licence.
- "Llama 4.5" remains unverified: the meta-llama HF org has no model newer than April 2025 (HF API, 2026-10-08), and the only source is the secondary report.
