# Review r2 (final round): q3-summaries-chapters.md

Reviewer: a fresh review agent that did not write or previously review the file. All sources were re-opened on 2026-10-08.
Severity scale: **wrong** (the source contradicts the claim), **unsupported** (the source does not back the claim as written, or a material caveat is missing), **missing option**, **minor**.

## Round-1 resolution check

All 22 round-1 findings are resolved correctly. Each fix was checked against its source:

- **#1:** `disabled` + `low`. The Effort page's Haiku 5.5 section says: "You can also send `thinking: {"type": "disabled"}` at `high` effort or below. At `xhigh` or `max`, it returns a 400 error". It also says: "Effort is a behavioral signal, not a strict token budget". With `disabled`, a per-message `output_config.effort` change returns a 400 error.
- **#2:** llama.cpp. The README says integer-only `minimum`/`maximum`, gives length and item bounds in its example, says unsupported features are "skipped silently", calls nested `$ref` and `prefixItems` broken, and says the schema is "not injected into the prompt".
- **#3, #17, #18:** Chapter-Llama. Table 2 is 22.7/12.6/29.9 zero-shot and 38.5/39.1/42.6 fine-tuned. Table A.8 is 23.5/35.2/38.5/39.8 speech only and 24.6/34.7/42.6 speech plus captions. Table A.12 is n = 190, 15.5 vs Vid2Seq 12.6. The OCR, music-video and similar-background wording matches.
- **#4, #5:** Batch. The source says "most batches completing within 1 hour", "expire if processing does not complete within 24 hours", "may see more requests expiring", expired requests are "not billed", cache hits run "30% to 98%", and it suggests the 1-hour cache.
- **#6–#9:** 512 and 4,096 tokens confirmed. Thinking tokens are billed as output. The What's-new page lists refusal without server-side fallback, the prefill error, thinking-first blocks, thinking omitted by default, and "a small limit can stop after a `thinking` block".
- **#10, #14, #21:** The Hugging Face API matches every licence and date given. Qwen3.5-0.8B/2B are dated 2026-02-28, 4B/9B 2026-02-27, 35B-A3B 2026-02-24, Qwen3.6-35B-A3B 2026-04-15 and Qwen3.8-27B 2026-08-05; all are `apache-2.0`. Qwen3.8-Flash-Next is `other`/`qwen-community-1.0`. Qwen2.5-3B is `other`/`qwen-research`. Granite 4.2 3B/8B are `apache-2.0` and the GGUF exists. Ministral-3-3B-2512 is `apache-2.0`. FrogNano is `mit` in the metadata, while the card's table says "Apache License 2.0". LFM2.5 is `other`/`lfm1.0`.
- **#11:** Gemma 4 12B was created 2026-05-23. Context is 128K for E2B/E4B and 256K for the others. Audio is on E2B, E4B and 12B only. All models take video as frames.
- **#12, #13, #15, #16, #19, #20, #22:** The fixes are as described in the resolution table.

**Arithmetic, all re-done and correct:**

- Scenario A: 29,400 × $0.10/M + 3,600 × $0.50/M = $0.00474/h. That is $0.000395 per video, $395 per 1M videos synchronous and $197.50 (≈ $198) with Batch. The difference is $197.50 (≈ $200), or ≈ $0.0002 per video.
- Scenario B: $0.01344/h, $1,120 per 1M videos.
- Scenario C: $0.00236/h.
- Caching: $0.000864/h, which is 18.2%.
- Haiku 4.5: ≈ $0.036/h.
- RTX 4090: 1,800 × $0.000395 = $0.711/h, or $0.356/h at Batch prices.
- vLLM vs Ollama: 793/41 = 19.3×.
- Chapter-Llama gaps: 42.6 − 34.7 = 7.9 and 42.6 − 38.5 = 4.1.
- OpenRouter column: $0.00348, $0.00266, $0.00330, $0.00373, $0.00801 and $0.02168 per hour. All match the table.

**OpenRouter prices** (https://openrouter.ai/api/v1/models, 2026-10-08) match exactly:

| Model | $/MTok in / out |
|---|---|
| Haiku 5.5 | 0.10 / 0.50 (`:batch` 0.05 / 0.25) |
| Qwen3.5-9B | 0.10 / 0.15 |
| Granite 4.2 8B | 0.06 / 0.25 |
| Ministral 3B 2512 | 0.10 / 0.10 |
| Gemma 4 26B A4B | 0.09 / 0.30 (a `:free` variant exists) |
| Qwen3.5/3.6-35B-A3B | 0.15 / 1.00 |
| Qwen3.8-27B | 0.425 / 2.55 |
| Gemini 2.5 Flash-Lite | 0.10 / 0.40 |
| GPT-5-nano | 0.05 / 0.40 |

**EU territorial check:** nothing recommended carries an EU restriction.

- Haiku 5.5: the Claude API lists EU member states, and "Services in the EU are provided by Anthropic Ireland Limited" (https://www.anthropic.com/supported-countries, 2026-10-08).
- Qwen3.5/3.6/3.8, Gemma 4, Granite 4.2 and Ministral 3 are all plain Apache-2.0, with no AUP carve-out found on the cards.
- The only EU carve-outs are the Llama multimodal ones, and the file correctly excludes Llama from the defaults.

## Findings

1. **Claim:** "Hosted open-weight models are in the same cost range as Haiku 5.5 (all well under $0.01 per video-hour)." (Cheap hosted section, Conclusion)
   - **Source:** the file's own table, with prices from OpenRouter's models API (https://openrouter.ai/api/v1/models, 2026-10-08). Qwen3.8-27B is $0.425/$2.55, which gives 29,400 × 0.425e-6 + 3,600 × 2.55e-6 = **$0.0217 per video-hour**, more than 2× the stated ceiling and 4.6× Haiku 5.5. Qwen3.5/3.6-35B-A3B is $0.0080, which is not "well under" $0.01 and is 1.7× Haiku.
   - **Severity:** wrong
   - **Correction:** Write "between about 0.6× and 4.6× Haiku 5.5 ($0.0027–$0.0217 per video-hour). Only Granite 4.2 8B, Ministral 3B and Qwen3.5-9B are cheaper than Haiku 5.5 at standard prices, and none is cheaper than Haiku Batch ($0.0024)."

2. **Claim:** "Scenario A per hour uses the Haiku token counts (29,400 in, 3,600 out) as a rough upper bound, since Qwen/Gemma tokenizers differ (estimate)."
   - **Source:** Several of the listed hosted models think by default:
     - Qwen3.5 and Qwen3.6: "operate in thinking mode by default" (https://huggingface.co/Qwen/Qwen3.6-35B-A3B, 2026-10-08).
     - Qwen3.8-27B: "Thinking mode is on by default", and `preserve_thinking` is also on by default (https://huggingface.co/Qwen/Qwen3.8-27B, 2026-10-08).
     - Granite 4.2: "full thinking (default), non-thinking, and low-effort" (https://huggingface.co/ibm-granite/granite-4.2-8b, 2026-10-08).

     No source is given for the claim that Haiku's tokenizer counts an upper bound for these models.
   - **Severity:** unsupported
   - **Correction:** State that the bound holds only when thinking is disabled at the hosted provider (OpenRouter's `reasoning` setting or the provider's `chat_template_kwargs`). Otherwise output tokens, and cost, can be several times higher. That makes Qwen3.8-27B and the 35B-A3B rows worse still. Mark the tokenizer comparison as (judgement).

3. **Claim:** Granite 4.2 row: "Granite 4.2 3B / 8B (2026-08-07) | Apache-2.0 | … Not evaluated here." It is also listed among the defaults in the licence Conclusion and in the hosted table.
   - **Source:** The Granite 4.2 3B and 8B cards (https://huggingface.co/ibm-granite/granite-4.2-3b and https://huggingface.co/ibm-granite/granite-4.2-8b, 2026-10-08) say "Release Date: August 25, 2026" and "Reasoning Mode: Built-in `<think>` … full thinking (default)". They give 128K native context, extensible to 512K. Both are post-trained from the Granite-4.1 base. 2026-08-07 is only the Hugging Face repo creation date.
   - **Severity:** minor
   - **Correction:** Give the release date as 2026-08-25 (repo created 2026-08-07). Add "thinking on by default; switch to non-thinking mode" and the 128K context. The thinking default matters for both latency and hosted cost (see finding 2).

4. **Claim:** Qwen3.8-27B row: "Dense, GPU tier." It is also an escalation option in the Recommendation, "on vLLM".
   - **Source:** The Qwen3.8-27B card (https://huggingface.co/Qwen/Qwen3.8-27B, 2026-10-08) calls it a "native vision-language model". It says "Thinking mode is on by default", and that `preserve_thinking` is enabled by default. The off switch is `chat_template_kwargs: {"enable_thinking": false}`, or plain `enable_thinking` on Qwen Cloud.
   - **Severity:** minor
   - **Correction:** Add "thinking on by default (disable as for Qwen3.5); vision-language; 262k context". The file's Thinking bullet under Local runtimes names only Qwen3.5/3.6; extend it to Qwen3.8 and Granite 4.2.

5. **Claim:** "With Batch … the recommended 1-hour write costs $0.20/MTok (2× input)."
   - **Source:** The Pricing page (https://platform.claude.com/docs/en/about-claude/pricing, 2026-10-08) says: "These multipliers stack with other pricing modifiers, including the Batch API discount". Under Batch, a Haiku 5.5 1-hour write therefore costs 2 × $0.05 = **$0.10/MTok**, and a cache read costs $0.005.
   - **Severity:** minor (the 2× ratio and the conclusion are unchanged)
   - **Correction:** Write "$0.10/MTok at Batch prices (2× the Batch input rate)".

6. **Claim:** Refusals: "a hosted or local open-weight model can act as the client-side fallback" (Arithmetic section, open question 7).
   - **Source:** Refusals and fallback (https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback, 2026-10-08) makes several relevant points:
     - "You can usually still get an answer by sending the same request to another Claude model." Client-side fallback through the SDK middleware works on any platform.
     - "Claude Haiku 5.5 has no server-side fallback: with `fallbacks: "default"`, a declined request stays declined, and a list of fallback models returns a 400 error."
     - "The `fallbacks` parameter is not supported on the Message Batches API."
     - "A Claude Haiku 5.5 refusal carries no fallback credit."
     - Refusals before any output are billed in the `bio`, `frontier_llm` and `reasoning_extraction` categories, and are free in the others.
     - The safety-classifier list names Fable, Opus 5/5.5, Sonnet 5.5 and Haiku 5.5. It does not name Haiku 4.5.
   - **Severity:** missing option
   - **Correction:** Add a client-side retry on another Claude model as an option. Claude Haiku 4.5 is not in the classifier list, but it costs 10× and is the same vendor; the SDK middleware can do the retry. Note that a retry after a Haiku 5.5 refusal gets no fallback credit. Note too that `fallbacks` must not be sent in Batch items. Keep the open-weight fallback as the alternative.

7. **Claim:** Open question 9: "Which OpenRouter providers support `response_format` json_schema and a thinking-off switch for Qwen3.5/3.6? Not checked per provider." The hosted table also mentions the Gemma `:free` variant without a caveat.
   - **Source:** The OpenRouter models API (https://openrouter.ai/api/v1/models, 2026-10-08) lists `structured_outputs` and `response_format` in `supported_parameters` for these models:
     - qwen3.5-9b, qwen3.5/3.6-35b-a3b and qwen3.8-27b
     - granite-4.2-8b and ministral-3b-2512
     - gemma-4-26b-a4b-it

     The **`:free` Gemma variant lacks `structured_outputs`**. This is model-level metadata, not per-provider.
   - **Severity:** minor
   - **Correction:** Record that structured outputs are advertised at model level for every listed model except the `:free` Gemma variant, which scenewise should not use. Per-provider support and the thinking-off switch stay open. OpenRouter's `provider.require_parameters` can enforce the per-provider part.

8. **Claim:** Recommendation: "prefer Qwen3.5-9B, or the 3B-active MoE Qwen3.6-35B-A3B … when … ≥ ~24 GB RAM". The licence table says "needs ~20+ GB RAM/VRAM at Q4 (estimate)".
   - **Source:** The Qwen3.6-35B-A3B card (2026-10-08) says "35B in total and 3B activated", with a vision encoder. 35B × ~4.5 bits ≈ 19.7 GB for the weights alone. The KV cache and the OS come on top, so ~24 GB is the realistic host figure.
   - **Severity:** minor (two inconsistent figures)
   - **Correction:** Use one figure: "≈ 20 GB weights at Q4_K_M; plan for ≥ 24 GB host RAM/VRAM (estimate)".

## Verified as correct (new or changed claims)

- **Haiku 5.5 settings and breaking changes.** Defaults are adaptive thinking and effort `medium`. `disabled` is allowed at `high` or below, and gives a 400 error at `xhigh`/`max`. "Affects all tokens" and "behavioral signal" are quoted correctly. The other breaking changes are confirmed: the prefill error, thinking-first blocks, thinking omitted by default, `stop_reason: "refusal"` with no server-side fallback, the `max_tokens`/thinking interaction, the 400 error on sampling parameters, and ~30% more tokens. Release is 2026-10-07, with retirement no sooner than 2027-10-07. Input is text and images.
- **Sync vs Batch.** Every Batch latency and expiry claim, the "not billed" status for expired requests, the 30–98% cache-hit range and the 1-hour suggestion match the source. The synchronous recommendation is a judgement and is labelled as one.
- **llama.cpp schema support**, as stated in the resolution of round-1 #2.
- **Chapter-Llama.** All numbers and caveats are correct.
- **New models and licences.** All are correct per the HF API and the cards. FrogNano is a "repository-level coding agent derived from Qwen/Qwen3.5-4B", "not designed or evaluated as a general-purpose assistant", and takes text-only input for its evaluated use. Ministral 3 3B has a 3.4B language model plus a 0.4B vision encoder, 256k context and Apache-2.0.
- **Ollama.** `think: false` means "request no thinking output, if the model permits it".
