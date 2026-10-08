# Q3: Summaries and chapters (roadmap item 2)

Research only. All sources were read on 2026-10-08 (revision r2 after reviews `reviews/q3-review-r1.md` and `reviews/q3-review-r2.md`; every source re-opened 2026-10-08). Figures marked **(estimate)** or **(judgement)** are mine, not from a source. Source tags like [S3] point to the Sources list at the end.

## Summary and recommendation

**Recommendation**

- **Prod (Expause): Claude Haiku 5.5 (`claude-haiku-5-5`)**, called **synchronously** (Messages API) for fresh uploads. Use the Message Batches API only for backfills and re-processing. Make the mode a per-operator config switch.
  - Use structured outputs (`output_config.format` with a JSON schema) [S4].
  - Send **both** `thinking: {"type": "disabled"}` **and** `output_config.effort: "low"`. Haiku 5.5 thinks adaptively by default at effort `medium`; `low` effort alone reduces but does not guarantee zero thinking; `disabled` is allowed at `high` effort or below [S35][S5a]. Thinking tokens are billed as output and count toward `max_tokens` [S36].
  - End `messages` with a user turn (assistant prefill returns an error on Haiku 5.5) and select content blocks by `type`, not position [S5a].
  - Expected cost: about **$0.0047 per video-hour synchronous** ($0.00040 per 5-minute video), vs $0.0024 with Batch (estimate, arithmetic below). At 1M five-minute videos per month that is about **$395 vs $198**, a difference of about $200/month.
- **Dev, and the CPU default for self-hosters: Qwen3.5-4B (Apache-2.0)**, run locally through Ollama or llama.cpp with a JSON-schema-constrained output and thinking off [S10][S24][S25]. It needs no API key and costs nothing per call.
  - **When frame labels are passed and the host has a GPU or ≥ 24 GB RAM/VRAM, prefer Qwen3.5-9B, or the 3B-active MoE Qwen3.6-35B-A3B** (both Apache-2.0) [S38][S42]. Chapter-Llama's size ablation shows a 3B model gains nothing from captions while 8B gains about 4 F1 (see Quality) [S14].
  - Escalation: Gemma 4 12B / 26B A4B (Apache-2.0) or Qwen3.8-27B (Apache-2.0) on vLLM [S11][S12][S38][S27].
- **Keep one provider interface** (prompt, schema, validator) with three backends: Anthropic, a local runtime, and any OpenAI-compatible hosted open-weight endpoint (e.g. OpenRouter) for self-hosters without a GPU. A Python validator enforces the chapter rules that no backend's schema can express.

**Why**

1. **Haiku cost is negligible, so latency decides Batch vs synchronous.** At 150 wpm, one hour of speech is about 16k Haiku 5.5 tokens. Haiku 5.5 costs $0.10 in / $0.50 out per MTok; Batch is 50% off [S1][S2]. Batch results arrive "within 1 hour" for most batches but can take up to 24 h, and requests not processed in 24 h expire and must be resubmitted [S37]. A summary that appears hours after upload is likely unacceptable for a user-video app (judgement; product owner to confirm), and the saving is about $0.0002 per video. A GPU is only cheaper if kept saturated: a single-stream RTX 4090 finishing a 5-minute video in about 2 s does about $0.71/h of Haiku-equivalent work at standard prices ($0.36/h at Batch prices); a batched vLLM server would do several times more (estimate, see Local runtimes).
2. **Small local models are credible but measurably weaker at chaptering.**
   - Zero-shot Llama-3.1-8B scores 29.5 F1 on VidChapters-7M chaptering. On a different 10% subset, GPT-4o-mini scores 31.2, GPT-4o 37.6 and Gemini-2.0-Flash 40.2 [S14].
   - Size ablation (fine-tuned, 300 validation videos): speech only 1B 23.5, 3B 35.2, 8B 38.5; **speech + captions 1B 24.6, 3B 34.7, 8B 42.6** [S14]. With captions, the 3B-to-8B gap is about 8 F1, not 3.
   - Small models (Phi-3-mini, Llama-3.2-3B) match 70B models on news summarisation [S15].
   - No published summarisation or chaptering benchmark for Haiku 5.5 was found. It was released 2026-10-07 [S3].
3. **Structured output is solved on all backends.** Anthropic uses constrained decoding, with exceptions for refusals, `max_tokens` and enum casing [S4]. llama.cpp, Ollama and vLLM all do grammar- or schema-constrained decoding [S24][S26][S27].
   - Anthropic rejects numeric, length and most array constraints [S4]. llama.cpp supports integer `minimum`/`maximum` (not `number`) and compiles `minItems`/`maxItems` and `minLength`/`maxLength` into repetition bounds [S24]. Cross-field rules (first at 0, ascending, at least 10 s apart, within duration) need the Python validator on every backend.
4. **Gate by length.** YouTube's rules imply that chapters only make sense for videos of at least 30 s with at least 3 chapters of at least 10 s each [S16]. VidChapters chapters average 142 s apart in ~22-minute videos [S17].
   - **(judgement)** Emit chapters only for videos of at least 2 minutes with at least 3 valid chapters.
   - **(judgement)** Emit a summary only when the transcript has at least about 40 words, or when visual labels are rich enough.
5. **Frame labels: yes, as a secondary, clearly marked input.** Zero-shot, speech plus captions beats speech alone (F1 29.9 vs 22.7; captions alone 12.6) on a 300-video validation set [S14]. Speechless videos are hard (F1 15.5 fine-tuned, n = 190) [S14].
   - For no-speech videos, emit a short visual description, flagged `basis: "visual"`, and no chapters unless at least 3 distinct scenes exist.

## Haiku pricing and cost per video-hour

### Current model and prices (Claude API, first-party)

| Item | Claude Haiku 5.5 (prompt ≤100k tokens) | Haiku 5.5 (prompt >100k) | Claude Haiku 4.5 (previous) |
|---|---|---|---|
| Model ID | `claude-haiku-5-5` [S2][S3] | same | `claude-haiku-4-5` [S2] |
| Base input | $0.10 / MTok [S1] | $0.50 [S1] | $1.00 [S1] |
| Output | $0.50 / MTok [S1] | $2.50 [S1] | $5.00 [S1] |
| 5-minute cache write | $0.125 [S1] | $0.625 [S1] | $1.25 [S1] |
| 1-hour cache write | $0.20 [S1] | $1.00 [S1] | $2.00 [S1] |
| Cache read | $0.01 [S1] | $0.05 [S1] | $0.10 [S1] |
| Batch input / output | $0.05 / $0.25 [S1] | $0.25 / $1.25 [S1] | $0.50 / $2.50 [S1] |

**Other facts about Haiku 5.5**

- Released 2026-10-07. Retirement is not sooner than 2027-10-07.
- 1M-token context, 128K max output. Input is text and images.
- Adaptive thinking is on by default, with default effort `medium` [S3][S35].
- Non-default `temperature`, `top_p` or `top_k` returns a 400 error [S3].

**Thinking and effort (verified on [S35], [S5a], [S36])**

- "Effort is a behavioral signal, not a strict token budget. At lower effort levels, Claude still thinks on sufficiently difficult problems" [S35]. So `low` effort alone does not guarantee zero thinking tokens.
- Haiku 5.5: "You can also send `thinking: {"type": "disabled"}` at `high` effort or below. At `xhigh` or `max`, it returns a 400 error" [S35][S5a]. Sending `disabled` together with `effort: "low"` is therefore allowed. With `disabled`, effort cannot be changed mid-conversation via per-message `output_config` [S35] (irrelevant for single-turn calls).
- Effort also affects the response text itself ("affects all tokens"), so `low` helps keep output terse [S35].
- Thinking tokens "are billed as output tokens, even when the thinking text isn't returned to you, and they count toward `max_tokens`" [S36]. With thinking on, a small `max_tokens` "can stop after a `thinking` block and before any text" [S5a], giving `stop_reason: "max_tokens"` and invalid JSON.

**Breaking changes relevant to the implementation [S5a]**

- Assistant message prefill returns an error: end `messages` with a user turn. (Prefilling `{` to force JSON is not possible; use structured outputs.)
- Responses can begin with `thinking` blocks: select content blocks by `type`, not `content[0]`.
- Thinking text is omitted by default.
- Safety classifiers can decline a request: handle `stop_reason: "refusal"`; server-side fallback isn't available.

**Tokenizer and stacking**

- Haiku 5.5 uses the newer tokenizer, which produces about 30% more tokens than Haiku 4.5 for the same text [S3][S5a].
- Batch and caching discounts stack [S1][S37].

**Prompt caching**

- Minimum cacheable prefix: **512 tokens for Haiku 5.5, 4,096 tokens for Haiku 4.5** [S5]. The 800-token fixed prefix therefore caches on 5.5 but would not cache at all on 4.5.
- Changing `output_config.format` invalidates the cache [S4].
- With Batch, cache hits are "best-effort", typically "30% to 98%", and Anthropic suggests the 1-hour cache duration because batches can exceed 5 minutes [S37].

**Structured outputs**

- Supported on `claude-haiku-5-5` [S4].
- Guarantees: "Structured outputs guarantee schema-compliant responses through constrained decoding." The exceptions are refusals, `max_tokens` cut-offs, and enum capitalisation [S4].
- Unsupported in the schema: numeric constraints (`minimum`/`maximum`, `multipleOf`), `minLength`/`maxLength`, and array constraints beyond `minItems` 0 or 1 [S4].
- The first use of a schema adds grammar-compile latency. Compiled grammars are cached for 24 h [S4].

### Batch vs synchronous for Expause

| | Synchronous Messages API | Message Batches API |
|---|---|---|
| Latency | Seconds per video (estimate) | "most batches completing within 1 hour"; up to 24 h; slower under demand, with more requests expiring [S37] |
| Failure mode | Normal retries | Requests not processed within 24 h come back `expired` (not billed) and must be resubmitted [S37] |
| Cost, Scenario A | $0.0047 / video-hour, $0.00040 / video | $0.0024 / video-hour, $0.00020 / video |
| Cost at 1M videos / month (A) | ~$395 | ~$198 |
| Prompt caching | Warm while traffic is steady (5-min TTL) | Best-effort, 30–98% hit rate; 1-hour cache recommended [S37] |

**Recommendation for Expause (judgement):** synchronous for every fresh upload, so the summary is ready when the video is processed. The Batch saving is about $200 per million videos, which does not justify hours of delay. Use Batch for backfills (re-summarising the existing catalogue, prompt or model upgrades). Expose `summaries.anthropic_mode: sync | batch` in scenewise config. If the product owner decides summaries can appear later (e.g. only in a digest), switch to Batch.

### Tokens per hour of speech

- **Speaking rate**
  - About 150 wpm is the commonly quoted conversational rate, attributed to the National Center for Voice and Speech (secondary citation). The same page gives 120–150 wpm for conversation and 150–160 wpm for radio hosts and podcasters, a better proxy for talking-head UGC [S6].
  - In Switchboard telephone conversations, the turn-wise rate is 164 wpm, the overall rate 196 wpm, and the rate excluding silence 236 wpm [S7].
  - I use **150 wpm (base)** and **200 wpm (high)**. Short-form creators may talk fast, and some videos are silent.
- **Tokens per word**
  - Anthropic says 1M tokens is roughly 555k words on the current tokenizer, which Haiku 5.5 uses. That is **1.80 tokens per word**. Earlier models fit about 750k words, or 1.33 tokens per word [S8][S3].
  - The pricing FAQ's "1 token ≈ 0.75 words" is the old-tokenizer figure [S1].
- **Transcript tokens per hour**
  - Base: 150 wpm × 60 = 9,000 words × 1.80 = **16,200 tokens**.
  - High: 200 wpm × 60 = 12,000 words × 1.80 = **21,600 tokens**.
- **Timestamps (estimate).** Chapters need timed text. Assume one `[mm:ss]` marker per ~5 s of speech, at about 5 tokens each: 720 × 5 = **3,600 tokens per hour**.
- **Fixed prompt (estimate).** Instructions plus the JSON schema come to about 800 tokens per request. Expause videos average 5 minutes, so an hour of content is about 12 requests: 12 × 800 = **9,600 tokens per hour**.
- **Output per video (estimate)**
  - Summary of about 80 words ≈ 145 tokens.
  - 3–5 chapters × about 26 tokens (title of about 6 words, a start time, JSON keys) ≈ 130 tokens.
  - JSON overhead ≈ 25 tokens.
  - Total ≈ **300 tokens per video**, or 3,600 per hour.
- **Thinking (estimate).** 0 only with `thinking: {"type": "disabled"}` [S35]. At `low` effort with adaptive thinking, usually small but not guaranteed zero. Allow up to about 1,000 tokens per video in the high scenario.
- **Frame labels as input (estimate).** One label line every 2 s (e.g. `[01:04] person, dog, beach, text:"SALE"`) at about 12 tokens is 1,800 × 12 = **21,600 tokens per hour**.

### Arithmetic (Haiku 5.5, ≤100k-token prompts, which every 5-minute video is)

| Scenario | Input tokens/hour | Output tokens/hour | Cost/hour (standard) | Cost/hour (Batch, −50%) | Per 5-min video (standard) |
|---|---|---|---|---|---|
| **A. Base**: 150 wpm, transcript plus timestamps, thinking disabled | 16,200 + 3,600 + 9,600 = **29,400** → × $0.10/M = $0.00294 | 12 × 300 = **3,600** → × $0.50/M = $0.00180 | **$0.0047** | **$0.0024** | $0.00040 |
| **B. High**: 200 wpm, plus frame labels, plus 1,000 thinking tokens per video | 21,600 + 3,600 + 21,600 + 9,600 = **56,400** → $0.00564 | 12 × 1,300 = **15,600** → $0.00780 | **$0.0134** | **$0.0067** | $0.00112 |
| **C. One 60-minute video** (Scenario A text, one request) | 16,200 + 3,600 + 800 = 20,600 → $0.00206 | about 600 (more chapters) → $0.00030 | **$0.0024** | $0.0012 | n/a |

- **Prompt caching** of the 800-token fixed prefix saves 800 × ($0.10 − $0.01)/M ≈ $0.00007 per video, or about $0.0009 per hour, about 18% of Scenario A, synchronous and only while traffic keeps the 5-minute cache warm (estimate). With Batch the hit rate is best-effort (30–98%) and the recommended 1-hour write costs $0.10/MTok at Batch prices (2× the Batch input rate; cache multipliers stack with the Batch discount, and a Batch cache read costs $0.005) [S1][S37], so the saving is smaller and uncertain (estimate).
- **Haiku 4.5 for comparison (estimate).** Token counts are about 1/1.3 of the above because of the old tokenizer, at 10× the price. Scenario A comes to about 22.6k in × $1 + 2.8k out × $5 ≈ **$0.036 per hour**. The 800-token prefix would not cache on 4.5 (4,096 minimum) [S5].
- **Scale (estimate).** 1M five-minute videos per month cost about $395 in Scenario A synchronous, or $198 with Batch. Scenario B costs about $1,120, or $560 with Batch.
- **Refusals.** Haiku 5.5 safety classifiers can return `stop_reason: "refusal"`, and "Server-side fallback isn't available" [S5a]. A refused response may not match the schema [S4]. This is relevant because Expause also sends moderation-flagged videos. Handle refusal as a distinct outcome. Two client-side retry options exist, both through the same provider interface:
  - **Retry on another Claude model.** Anthropic: "You can usually still get an answer by sending the same request to another Claude model"; the SDK refusal-fallback middleware does this "on any platform" [S43]. Claude Haiku 4.5 is the cheapest candidate and is not in the list of models with these safety classifiers [S43], but costs 10× Haiku 5.5 (≈ $0.036/video-hour) and is the same vendor. Caveats [S43]: "A Claude Haiku 5.5 refusal carries no fallback credit", so the retry writes the fallback model's cache at full price; refusals before any output are billed only in the `bio`, `frontier_llm` and `reasoning_extraction` categories; `fallbacks` must **not** be sent in Batch items (the item comes back errored), so refused Batch items are resubmitted on the fallback model as a new batch or direct requests; with Haiku 5.5, `fallbacks: "default"` leaves the request declined and a model list returns 400.
  - **Retry on a hosted or local open-weight model** (different vendor, cheaper, no Anthropic policy overlap).
  - This does **not** conflict with the rule against server-side fallbacks: Haiku 5.5 has no server-side fallback, so scenewise must never send `fallbacks`. Any retry is an explicit, client-side, operator-configured step (`summaries.refusal_fallback: none | claude:<model> | openweight:<backend>`), and every retry is logged with the refusal `stop_details.category` and the model that produced the final output (judgement).

## Cheap hosted open-weight endpoints (alternative to Haiku and to local inference)

Prices from the OpenRouter public models API, read 2026-10-08 [S39]. OpenRouter routes to third-party providers; prices change, and per-provider structured-output support varies. Scenario A per hour reuses the Haiku token counts (29,400 in, 3,600 out). Treating these as an upper bound is (judgement): no source compares the tokenizers. It holds **only with thinking disabled at the hosted provider** (OpenRouter's `reasoning` setting, or `chat_template_kwargs: {"enable_thinking": false}` where the provider passes it through). Qwen3.5/3.6 [S42], Qwen3.8-27B [S45] and Granite 4.2 [S44] think by default; with thinking on, output tokens and cost can be several times higher, which makes the Qwen3.8-27B and 35B-A3B rows worse still. OpenRouter lists `reasoning` among the supported parameters for every row except Ministral 3B (which has no thinking mode to switch) [S39].

| Model (licence) | $/MTok in / out | Scenario A $/video-hour (estimate) |
|---|---|---|
| Claude Haiku 5.5 (proprietary), for reference | 0.10 / 0.50 (Batch SKU 0.05 / 0.25) | 0.0047 |
| Qwen3.5-9B (Apache-2.0) | 0.10 / 0.15 | 0.0035 |
| Granite 4.2 8B (Apache-2.0) | 0.06 / 0.25 | 0.0027 |
| Ministral 3 3B 2512 (Apache-2.0) | 0.10 / 0.10 | 0.0033 |
| Gemma 4 26B A4B (Apache-2.0) | 0.09 / 0.30 (a rate-limited `:free` variant exists, but it lacks `structured_outputs`; do not use it) | 0.0037 |
| Qwen3.5-35B-A3B / Qwen3.6-35B-A3B (Apache-2.0) | 0.15 / 1.00 | 0.0080 |
| Qwen3.8-27B (Apache-2.0) | 0.425 / 2.55 | 0.0217 |

**Conclusion.** Hosted open-weight models cost between about 0.6× and 4.6× Haiku 5.5 ($0.0027–$0.0217 per video-hour, thinking off). Only Granite 4.2 8B, Ministral 3B and Qwen3.5-9B are cheaper than Haiku 5.5 at standard prices; Gemma 4 26B A4B is about 0.8× too ($0.0037), but no row is cheaper than Haiku Batch ($0.0024). The 35B-A3B models (1.7×) and Qwen3.8-27B (4.6×) cost more than Haiku 5.5. They are useful for (a) self-hosters with no GPU who want the same model family as the local dev path, and (b) a refusal fallback. They do not displace Haiku 5.5 as the first choice for Expause. Other vendors' small proprietary models (e.g. Gemini 2.5 Flash-Lite at $0.10 / $0.40, GPT-5-nano at $0.05 / $0.40 [S39]) are similar in price; they were not evaluated, and the brief puts Claude first.

## Local LLM licences

Licences verified per checkpoint via the Hugging Face model API (`https://huggingface.co/api/models/<id>`), read 2026-10-08 [S38], unless another source is given.

| Family / model | Licence | Commercial OK? | Restrictions / notes |
|---|---|---|---|
| **Qwen3** (e.g. Qwen3-4B-Instruct-2507) | Apache-2.0 [S9][S38] | Yes | 262k native context. **Non-thinking only**, so a simpler drop-in where latency matters [S9]. |
| **Qwen3.5** small (0.8B, 2B, 4B, 9B; HF repos created 2026-02-27/28) | Apache-2.0, each card verified [S38] | Yes | 4B is multimodal (image and video), 262k context. **Thinking is on by default** [S10]. Disable it with `chat_template_kwargs: {"enable_thinking": false}` on vLLM / SGLang / llama-server (OpenAI-compatible); bare `"enable_thinking": false` is the Alibaba Model Studio form; Qwen3.5 "does not officially support the soft switch … `/think` and `/nothink`" [S10]. On Ollama, send `think: false` on the native `/api/chat` [S40]. |
| **Qwen3.5-35B-A3B** (2026-02-24) / **Qwen3.6-35B-A3B** (2026-04-15) | Apache-2.0 [S38] | Yes | MoE, 35B total, 3B active; 262k context; thinking on by default [S42]. Generation speed near a 3B dense model, but ≈ 20 GB weights at Q4_K_M (35B × ~4.5 bits); plan for ≥ 24 GB host RAM/VRAM including KV cache and OS (estimate). Candidate "large-RAM or GPU" tier. |
| **Qwen3.8-27B** (2026-08-05) | Apache-2.0 [S38] | Yes | Dense, GPU tier. Native vision-language (images and video); 262k context. **Thinking on by default**, and `preserve_thinking` on by default; disable with `chat_template_kwargs: {"enable_thinking": false}` as for Qwen3.5 [S45]. |
| **Not permissive (checked):** Qwen2.5-3B-Instruct; Qwen3.8-Flash-Next (2026-08-24) | `other` / `qwen-research`; `other` / `qwen-community-1.0` [S38] | Check terms | Exclude from defaults. The licence is per checkpoint, so the rule "check each card" stays. |
| **Gemma 4** (E2B, E4B, 26B A4B, 31B: Apr 2026; 12B added May 2026) | Apache-2.0, "the first in the Gemmaverse… under the OSI-approved Apache 2.0 license" [S11][S12][S38] | Yes | E2B/E4B: 128K context. 12B, 26B A4B, 31B: 256K. All take text, image and video; audio on E2B, E4B and 12B [S12]. 12B is a natural step between Qwen3.5-9B and 26B. |
| **Gemma 3 and earlier** (incl. 3n) | Gemma Terms of Use (last modified 2026-04-01): distribution includes "providing or making Gemma or its functionality available as a hosted service via API, web access" (§1.1(b)); use restrictions must flow down as "an enforceable provision" (§3.1). Gemma 4 is under a separate licence [S13] | Yes, with flow-down use restrictions | Avoid. Gemma 4 removes the issue. |
| **Llama 3.2** (1B, 3B text; 11B, 90B vision) | Llama 3.2 Community License [S18] | Yes, with conditions | "Built with Llama" display and a licence copy are required **if you distribute or make available** the materials or a product containing them (§1.b.i); serving scenewise with Llama would trigger this. The "Llama…" naming rule applies only to a model you "create, train, fine tune, or otherwise improve" and distribute, so not to scenewise (no fine-tuning). The **700M MAU** test applies to MAU on the Llama 3.2 release date (2024-09-25), not an ongoing threshold (§2) [S18]. The AUP is incorporated. AUP: for **multimodal** Llama 3.2 models, Section 1(a) rights are not granted to EU-domiciled individuals or EU-headquartered companies; end users are exempt [S19]. |
| **Llama 4** (Scout 17B-16E, Maverick) | Llama 4 Community License [S20] | Yes, with conditions | Same MAU-at-release clause [S20]. The AUP's EU multimodal exclusion applies, and Llama 4 is natively multimodal, so an **EU-based licensee cannot use it** [S20][S21]. Not small. "Llama 4.5" remains unverified: only a secondary report [S22]. |
| **Phi-4-mini-instruct** (3.8B) | MIT [S23a] | Yes | 128K context. |
| **FrogNano-4B-2609** (Microsoft, 2026-09-17) | HF metadata `mit`, but the card's table says "Apache License 2.0" (both permissive; inconsistent) [S38][S41] | Yes | A **coding agent** fine-tuned from Qwen3.5-4B; "not designed or evaluated as a general-purpose assistant"; text only [S41]. Not suitable for summaries. Use Qwen3.5-4B instead. |
| **SmolLM3-3B** | Apache-2.0 [S23b] | Yes | 64k trained, 128k with YaRN. **Extended thinking on by default**; disable with `/no_think` in the system prompt or `enable_thinking=False` [S23b]. |
| **Granite 4.2 3B / 8B** (released 2026-08-25; HF repo created 2026-08-07) | Apache-2.0 [S38][S44] | Yes | 128K native context (extensible to 512K). **Thinking on by default** ("full thinking (default), non-thinking, and low-effort"); switch to non-thinking mode with `enable_thinking=False` [S44]. Supersedes Granite 4.0 micro (3B, Apache-2.0, lists summarisation, 128K [S23c]). Official GGUF published (`granite-4.2-3b-GGUF`) [S38]. Not evaluated here. |
| **Ministral 3 3B / 8B Instruct (2512)** | Apache-2.0 [S23d][S38] | Yes | 8B: 8.4B language model plus 0.4B vision encoder, 256k context [S23d]. 3B is the smaller sibling. |
| **LiquidAI LFM2.5** family | `other` / `lfm1.0` [S38] | Check terms | Not Apache. Excluded. |

**Conclusion.** For scenewise defaults, use only Apache-2.0 or MIT models: Qwen3/3.5/3.6/3.8 (checking each card), Gemma 4, Phi-4-mini, SmolLM3, Granite 4.2 and Ministral 3. Llama is usable but adds attribution and AUP obligations, plus an EU multimodal carve-out; do not make it the default.

## Local runtimes and speed

**Runtimes**

| Runtime | Python story | Structured output | Fit |
|---|---|---|---|
| **llama.cpp / llama-cpp-python** | `llama-cpp-python` bindings plus an OpenAI-compatible server [S25] | GBNF grammars. A *subset* of JSON Schema is converted to GBNF: integer `minimum`/`maximum` supported (not `number`), length and item bounds compile to repetitions; unsupported features are **skipped silently**. The schema is not injected into the prompt [S24] | CPU, Apple Metal, CUDA. Best for CPU-only self-hosters. |
| **Ollama** | HTTP API / Python client | `format` takes a JSON schema to constrain output (since Dec 2024) [S26]. `think: false` disables thinking where the model permits [S40] | Easiest dev setup. Single-user oriented [S28]. |
| **vLLM** | Python-native server | Structured outputs via xgrammar or guidance backends. `response_format` json_schema [S27] | GPU production serving with batching [S28]. |
| **transformers** | Native | Needs an add-on library (e.g. outlines). Not evaluated here | Slowest; reference only. Qwen3.5 cards point to `transformers serve` for light loads and to vLLM or SGLang for production [S10]. |

**Measured throughput.** These are proxies: the 7B numbers are Llama-2-7B Q4_0 from llama.cpp's own scoreboards. "PP" is prompt processing; "TG" is token generation.

| Hardware | Model | PP tok/s | TG tok/s | Source |
|---|---|---|---|---|
| Apple M1 (8-core GPU) | 7B Q4_0 | 118 | 14.2 | [S29] |
| Apple M1 Pro (16 GPU cores) | 7B Q4_0 | 266 | 36.4 | [S29] |
| Apple M4 Pro (20) | 7B Q4_0 | 440 | 50.7 | [S29] |
| Apple M4 Max (40) | 7B Q4_0 | 886 | 83.1 | [S29] |
| NVIDIA T4 | 7B Q4_0 | 1,219 | 46.4 | [S30] |
| RTX 4060 Ti 8 GB | 7B Q4_0 | 3,395 | 63.9 | [S30] |
| RTX 4090 | 7B Q4_0 | 11,993 | 186 | [S30] |
| A100 80 GB | 7B Q4_0 | 4,850 | 191 | [S30] |
| 2× EPYC 9334 (24 threads), CPU only | DeepSeek-R1-Qwen3-8B Q4_K_M | n/a (TTFT 4.8 s for Llama-2-7B) | 27.8 | [S31] |
| 4-core Xeon E5-2696 v4 VPS, CPU only | Llama 3.1 8B Q4_K_M | n/a | 3.2 (weak blog source, inconsistent figures) | [S32] |
| A100 40 GB, many concurrent users | Llama-3.1-8B FP16 | n/a | peak aggregate: **vLLM 793 tok/s vs Ollama 41 tok/s** | [S28] |

**Time per 5-minute video (estimate, single stream).** This assumes Scenario A: about 2,450 input tokens and 300 output tokens, with thinking off.

| Hardware | Time per video |
|---|---|
| M1 Pro | ≈ 9 s + 8 s ≈ **17 s** |
| T4 | ≈ 2 s + 6.5 s ≈ **9 s** |
| RTX 4090 | ≈ 0.2 s + 1.6 s ≈ **2 s** |
| EPYC | ≈ 11 s generation + prefill |
| 4-core VPS | ≈ **95 s of generation alone** + unmeasured prefill |

- **Haiku-equivalent value of a GPU (estimate).** Single-stream 4090: 3,600 s / 2 s = 1,800 videos/h × $0.000395 = **$0.71/h** at Haiku standard prices, **$0.36/h** at Batch prices. These are batch-1 llama.cpp numbers; vLLM with concurrent requests reached ~19× Ollama's aggregate throughput on an A100 [S28], so a saturated vLLM server would be worth several times more. The break-even against GPU rental stays open (question 6).
- **3–4B models.** Token generation is memory-bandwidth bound, so a ~3–4B Q4 model should run roughly 2× faster than 7–8B (inference from size, not measured). A 3B-active MoE (Qwen3.6-35B-A3B) should generate at a similar speed but needs the RAM for all 35B weights (inference). I found no primary benchmark for 3–4B on CPU (open question).
- **Thinking.** Qwen3.5/3.6, Qwen3.8-27B and Granite 4.2 all think by default; leaving it on would multiply output tokens and latency, locally and on hosted endpoints [S10][S42][S44][S45]. Always send the thinking-off switch.

## Quality and structured output

**Chaptering: Chapter-Llama, CVPR 2025 [S14]**

- **Task.** VidChapters-7M. The input is ASR speech plus frame captions with timestamps.
- **Zero-shot Llama-3.1-8B** (no fine-tuning, which matches our no-fine-tuning constraint), test set:

  | Videos | F1 | SODA | CIDEr |
  |---|---|---|---|
  | All | 29.5 | 6.2 | 30.7 |
  | Short (<15 min) | 29.9 | 7.1 | 34.5 |

- **Proprietary models, zero-shot,** on a random 10% of the test set (a different subset): GPT-4o-mini 31.2 F1, GPT-4o 37.6, Gemini-2.0-Flash 40.2, Gemini-1.5-Pro 42.2.
- **Fine-tuned Chapter-Llama:** 45.3 F1. Not applicable to us, but it shows the headroom.
- **Model size** (Table A.8; fine-tuned on 1k videos, evaluated on 300 validation videos):

  | Model | Speech only | Speech + captions |
  |---|---|---|
  | Llama-3.2-1B | 23.5 | 24.6 |
  | Llama-3.2-3B | 35.2 | 34.7 |
  | Llama-3.1-8B | 38.5 | 42.6 |
  | Llama-3.2-11B | 39.8 | n/a |

  **1B is too small. With speech only, 3B is close to 8B; with captions, 3B gains nothing and 8B gains ~4 F1, so the gap widens to ~8 F1.**
  - **What this means for the 4B default (judgement).** These are fine-tuned Llama numbers on 300 videos, not zero-shot Qwen, so they are indicative only. They suggest a ~3–4B model may not use frame labels well. Therefore: keep Qwen3.5-4B as the CPU default for speech-led videos; when frame labels are passed (which includes every no-speech video), prefer Qwen3.5-9B or Qwen3.6-35B-A3B if the hardware allows, or a hosted endpoint. Verify on the Expause eval set (open question 1).
- **Input ablation** (Table 2; 300 validation videos, fine-tuned rows trained on 1k videos):

  | Input | Zero-shot F1 | Fine-tuned F1 |
  |---|---|---|
  | Speech only | 22.7 | 38.5 |
  | Captions only | 12.6 | 39.1 |
  | Both | 29.9 | 42.6 |

  Caption-only weakness is largely a zero-shot effect: fine-tuned, captions alone match speech alone. This matters for the no-speech path, where we cannot fine-tune.
- **Videos without speech** (Table A.12, n = 190 validation videos, fine-tuned): Chapter-Llama F1 15.5 (Vid2Seq 12.6), vs 42.6 on the full 300-video validation set (indicative only). Speechless videos with OCR-readable text give satisfactory chapters; without text or speech results are "inferior but still acceptable"; failures come from music videos with very similar backgrounds across frames.
- **Interpretation.** Haiku-class models are not benchmarked here. Inferring from the GPT-4o-mini / Gemini-Flash tier, a current small hosted model should beat a local 8B zero-shot. That is unverified (open question).

**Summarisation**

- Xu et al. 2025 evaluated 19 small models on 2,000 news samples. Phi-3-mini and Llama-3.2-3B gave "results comparable to those of 70B LLMs" with more concise summaries [S15].
- Simple prompts work better than complex ones for small models [S15].
- These are news texts, not short, informal UGC transcripts. No domain evidence was found (open question).

**Structured output reliability**

- **Anthropic.** Constrained decoding is supported on Haiku 5.5 [S4].
  - Failure modes: `refusal`, `max_tokens`, enum casing.
  - Unsupported schema features return a 400 (no silent drop).
  - Limits: 20 strict tools, 24 optional parameters, 180 s compile timeout [S4].
- **llama.cpp.** JSON Schema subset → GBNF. Integer `minimum`/`maximum` and length/item bounds are honoured; unsupported features are dropped silently, and nested `$ref` and `prefixItems` are broken. The prompt must still describe the format [S24]. On this backend, `start_s` as `{"type": "integer", "minimum": 0}` and `chapters` with `minItems: 3` can be enforced at decode time — but a forced `minItems: 3` would make the model invent chapters on short videos, so apply it only when the length gate already allows chapters (judgement).
- **Ollama** constrains to a JSON schema via `format` [S26]. **vLLM** uses xgrammar or guidance [S27].
- **Benchmark coverage.** JSONSchemaBench (10K real schemas) evaluates Guidance, Outlines, llama.cpp, XGrammar, OpenAI and Gemini. Most "guarantee constraint compliance given a schema." I read the abstract only [S33].
- **Caveat.** Format restrictions can degrade reasoning [S34]. Keep the schema flat and small (summary string, chapters array of {start_s, title}, basis enum), and leave thinking off. The task is extractive, not reasoning-heavy.
- **Validator, required for all backends.** Anthropic's schema cannot express numeric bounds [S4], and no backend expresses cross-field rules [S24]. Python must check that:
  - the first chapter starts at 0;
  - start times are strictly ascending;
  - each chapter lasts at least 10 s;
  - there are at least 3 chapters;
  - every start time is within the video duration.

  Drop chapters, not the summary, when the validator fails.

## Minimum length

**Evidence**

- **YouTube manual chapters** [S16]:
  - The first timestamp must be 00:00.
  - At least **three timestamps** in ascending order.
  - Minimum chapter length is **10 seconds**.

  So a video under 30 s can never have valid chapters. YouTube's help page states no video-length rule for automatic chapters [S16].
- **VidChapters-7M** (817K user-chaptered YouTube videos) [S17]:
  - Average video is 1,354 s (about 22.6 min), with **8.3 chapters**.
  - Adjacent chapters are **142 s** apart on average.
  - 97.3% of videos have ASR.

  These are averages dominated by ~22-minute videos. **(judgement)** If creators chaptered short videos at the same ~2-minute density, a 5-minute video would have about 2 chapters, below YouTube's minimum of 3; but density on short videos is unknown and may well be higher.
- **Chapter-Llama:** F1 is similar for short (<15 min) and medium videos [S14]. No evidence exists for videos under 1–2 minutes (open question).

**Rules (judgement, to calibrate on Expause samples)**

| Output | Emit when | Otherwise |
|---|---|---|
| **Chapters** | Duration ≥ **120 s** and the validator passes (≥3 chapters, each ≥10 s, first at 0) | Omit (`chapters: []`). Do not pad. |
| **Summary from transcript** | Transcript ≥ **~40 words** (about 15 s of speech at 150 wpm) | Below that, a "summary" is just a paraphrase. Return the transcript-based one-liner, or fall through to the visual rule. |
| **Visual-only description** | No or very little speech, **and** labels cover ≥3 distinct scenes or there is on-screen text | Return `summary: null`. |

## Frame labels as input

| Pros | Cons |
|---|---|
| Zero-shot, speech plus captions beats speech alone for chaptering (F1 29.9 vs 22.7, 300 validation videos) [S14]. | Labels are nouns, not events. A model can invent a storyline from "person, beach, dog". Zero-shot, captions alone score 12.6 F1 [S14]. |
| It is the only signal for no-speech videos, which are probably a much larger share on Expause than the 2.7% in VidChapters [S17]. That share is unknown (open question). | It roughly doubles input tokens (Scenario B), though still about $0.01 per hour. |
| On-screen text (OCR) drives most no-speech successes [S14]. | A ~3B model gained nothing from captions in the size ablation (34.7 vs 35.2) [S14]; small local models may not benefit. |
| | Noisy or incorrect labels leak into the user-facing summary. Moderation labels must never appear in a summary. |

**Decision (judgement)**

- **Allow labels**, but pass them in a separate, explicitly marked block: `VISUAL LABELS (automatic, may be wrong)`.
- Prompt rules:
  - Prefer the transcript.
  - Never state a visual claim as fact unless several frames agree.
  - Exclude moderation and safety labels from summary input entirely.
- Add `basis: "speech" | "visual" | "both"` to the output, so Expause can label or suppress visual-only summaries.
- On local backends, route label-bearing requests to the larger tier (Qwen3.5-9B / Qwen3.6-35B-A3B) where available.
- **No-speech videos:**
  - Summary: a visual-only, one- or two-sentence description, flagged `basis: "visual"`. Return `null` when labels are sparse.
  - Chapters: none, unless scene-change detection yields at least 3 scenes of at least 10 s *and* the video is at least 120 s long.
- Haiku 5.5 accepts images [S3], so keyframes could replace labels. Image-token cost and the trade-off belong to the frame-label research question and were not evaluated here.

## Open questions

1. **Haiku 5.5 and local-model quality.** No published summarisation or chaptering numbers exist; the model is one day old [S3]. Run a 50–100-video Expause eval set comparing Haiku 5.5 (thinking disabled, effort low) against Qwen3.5-4B, Qwen3.5-9B and Qwen3.6-35B-A3B, **with and without frame labels**, to test whether the Chapter-Llama finding (3B gains nothing from captions) holds zero-shot for Qwen at 4B.
2. **Latency requirement.** Must summaries be available at upload-processing time, or can they appear hours later? This decides synchronous vs Batch for Expause (recommendation: synchronous). Product owner to confirm.
3. **Expause video mix.** What share of videos have no speech, and what is the duration distribution? This decides how often chapters and summaries are emitted, and how often the larger local tier is needed.
4. **Calibrate thresholds.** Do the 120 s (chapters) and 40 words (summary) thresholds hold on real Expause samples? Is a chapter even useful in a 5-minute short-video UI? The product owner should decide.
5. **Local throughput for 3–4B and 3B-active MoE models on CPU.** No good primary benchmark was found. Run `llama-bench` on the target self-host hardware for Qwen3.5-4B Q4_K_M and Qwen3.6-35B-A3B Q4_K_M at pp2048 and tg300.
6. **Self-hosted GPU price** for the break-even against Haiku ($0.71/h standard, $0.36/h Batch, for a single-stream 4090; several times higher for batched vLLM). GPU hourly prices were not researched here.
7. **Refusal rate and refusal fallback (user decision).** The refusal rate on moderation-flagged Expause content is unmeasured. Which client-side retry should be the Expause default? *For Claude Haiku 4.5:* same vendor, contract and EU entity, same prompt and structured-output path, not in the classifier list [S43]. *Against:* 10× the price with no fallback credit, the same vendor's policies may still decline, and it is a previous-generation model with its own retirement date. *For an open-weight fallback:* cheaper, independent of Anthropic's classifiers. *Against:* a second backend to run and evaluate, weaker chaptering, and the operator becomes responsible for what an unfiltered model says about flagged content. A third option is no retry (return no summary for refused videos). Measure the refusal rate in the open question 1 eval first.
8. **Is Expause, or any scenewise operator, EU-based?** If so, Llama multimodal models are excluded by the AUP [S19][S21]. Moot if we default to Apache-2.0 models.
9. **Hosted open-weight endpoints.** OpenRouter advertises `structured_outputs` and `response_format` at **model level** for every model in the hosted table except the Gemma `:free` variant [S39]. Still open: support **per provider** behind each model, and whether each provider honours the thinking-off switch. Set `provider.require_parameters: true` so OpenRouter routes only to providers that support every parameter sent; verify thinking-off by checking output token counts in a smoke test.

Closed in r1: Qwen licences per checkpoint (verified, see licence table [S38]); Haiku 5.5 512-token cache minimum (confirmed [S5]); thinking-off setting (`disabled` + `low` allowed [S35]); zero-shot size curve (still unknown, folded into question 1). Closed in r2: OpenRouter model-level structured-output support (see question 9).

## Review round 1 — resolution

Review: `reviews/q3-review-r1.md`. Each finding was re-checked against its source on 2026-10-08.

| # | Severity | Resolution |
|---|---|---|
| 1 | wrong | **Fixed.** Effort page confirms `low` is "not a strict token budget" and `disabled` is allowed at `high` or below on Haiku 5.5 [S35][S5a]. Recommendation now sends both; thinking-estimate line and open questions updated. |
| 2 | wrong | **Fixed.** llama.cpp README: integer `minimum`/`maximum` supported, not `number`; length/item bounds compile to repetitions [S24]. Text now distinguishes backends; validator still required for cross-field rules. |
| 3 | unsupported | **Fixed.** Table A.8 confirmed (speech+captions 3B 34.7, 8B 42.6) [S14]. Both rows reported; 4B default now limited to speech-led/CPU, larger tier when labels are passed. |
| 4 | missing option | **Fixed.** Batch latency (≤24 h, expiry) confirmed [S37]. Recommendation changed to synchronous for Expause, Batch for backfills; cost difference stated (~$0.0002/video, ~$200 per 1M videos). |
| 5 | unsupported | **Fixed.** Batch cache hit 30–98% and 1-hour cache suggestion added [S37]. |
| 6 | minor | **Fixed.** 512 (Haiku 5.5) and 4,096 (Haiku 4.5) confirmed on the prompt-caching page [S5]; open question closed. |
| 7 | minor | **Fixed.** Cited the Thinking page [S36]; added the `max_tokens` consequence [S5a]. |
| 8 | minor | **Fixed.** Refusal claim now cites What's new in Haiku 5.5 [S5a]; local skill file dropped. |
| 9 | missing option | **Fixed.** Prefill error, thinking-first blocks, omitted thinking text added [S5a]. |
| 10 | unsupported | **Fixed.** All Qwen3.5 sizes Apache-2.0 per HF API; Qwen2.5-3B `qwen-research`, Qwen3.8-Flash-Next `qwen-community-1.0` [S38]. Secondary [S10a] removed; open question closed. |
| 11 | minor | **Fixed.** 12B created 2026-05-23; 256K for 12B/26B/31B; video input; audio on E2B/E4B/12B [S12][S38]. |
| 12 | minor | **Fixed.** Cites primary Gemma Terms §1.1(b), §3.1 [S13]. |
| 13 | minor | **Fixed.** Distribution trigger, naming-rule scope and MAU-at-release-date added from licence text [S18]. |
| 14 | missing option | **Fixed.** Added Granite 4.2 3B/8B, Qwen3.5/3.6-35B-A3B, Qwen3.8-27B, Ministral 3 3B, FrogNano-4B, LFM2.5 (excluded), all verified on HF API [S38]. Added finding: FrogNano is a coding agent and its card's licence field says Apache-2.0 while HF metadata says MIT [S41], so it is listed but not recommended. |
| 15 | missing option | **Fixed.** New section with OpenRouter prices for hosted open-weight models [S39]. |
| 16 | unsupported | **Fixed.** Both $0.71/h and $0.36/h given; single-stream caveat and vLLM concurrency note added [S28]. |
| 17 | minor | **Fixed.** n = 190, "42.6 on full validation set (indicative)", music-video wording corrected per Table A.12 and text [S14]. |
| 18 | minor | **Fixed.** Table labelled as 300-video validation ablation; fine-tuned row added [S14]. |
| 19 | unsupported | **Fixed.** Chapter-density extrapolation marked (judgement) with the caveat [S17]. |
| 20 | minor | **Fixed.** Per-runtime thinking switch, no soft switches for Qwen3.5 [S10]; Ollama `think: false` [S40]; SmolLM3 thinking default [S23b]; Qwen3-4B-2507 non-thinking [S9]. |
| 21 | minor | **Fixed.** HF creation dates (2026-02-27/28) cited [S38]. |
| 22 | minor | **Fixed.** 120–150 conversational and 150–160 podcaster range added [S6]; arithmetic unchanged. |

No findings were rejected.

## Review round 2 — resolution

Review: `reviews/q3-review-r2.md` (final round). Each finding was re-checked against its source on 2026-10-08 (OpenRouter models API re-queried; Granite 4.2 8B, Qwen3.8-27B, Refusals and fallback, and Pricing pages re-opened).

| # | Severity | Resolution |
|---|---|---|
| 1 | wrong | **Fixed.** Conclusion now matches the table: 0.6×–4.6× Haiku 5.5 ($0.0027–$0.0217/video-hour); Granite 4.2 8B, Ministral 3B, Qwen3.5-9B (and Gemma 4 26B A4B) are cheaper than Haiku standard; none is cheaper than Haiku Batch ($0.0024) [S39]. |
| 2 | unsupported | **Fixed.** Token bound marked (judgement) and limited to provider-side thinking off; default-thinking models named [S42][S44][S45]; `reasoning` parameter availability per model noted [S39]. |
| 3 | minor | **Fixed.** Granite 4.2 release date 2026-08-25 (repo 2026-08-07), thinking on by default, 128K/512K context [S44]. |
| 4 | minor | **Fixed.** Qwen3.8-27B: vision-language, 262k context, thinking and `preserve_thinking` on by default, off switch [S45]. Thinking bullet in Local runtimes extended to Qwen3.8 and Granite 4.2. |
| 5 | minor | **Fixed.** Batch 1-hour write is $0.10/MTok (multipliers stack with the Batch discount) [S1]. |
| 6 | missing option | **Fixed.** Client-side retry on another Claude model (Haiku 4.5 via SDK middleware) added beside the open-weight option, with no-fallback-credit, refusal-billing and no-`fallbacks`-in-Batch caveats [S43]. Stated explicitly that this does not conflict with never sending `fallbacks`: the retry is client-side, opt-in and logged. Choice of default moved to open question 7 as a user decision. |
| 7 | minor | **Fixed.** Model-level `structured_outputs` recorded for all hosted rows except Gemma `:free` (marked do-not-use); per-provider support remains open with `provider.require_parameters` as the enforcement [S39]. |
| 8 | minor | **Fixed.** One figure throughout: ≈ 20 GB weights at Q4_K_M, plan for ≥ 24 GB host RAM/VRAM (estimate). |

No findings were rejected. Unsettled items are in Open questions 1–9; question 7 (refusal fallback) and question 2 (sync vs Batch) are user decisions.

## Sources

All sources were read on 2026-10-08.

- [S1] Anthropic, Pricing. Haiku 5.5 / 4.5 rates, Batch 50% off, caching multipliers, "1 token ≈ 0.75 words". https://platform.claude.com/docs/en/about-claude/pricing
- [S2] Anthropic, Models overview. `claude-haiku-5-5`, adaptive thinking, default effort `medium`, 1M context, 555k words per 1M tokens. https://platform.claude.com/docs/en/about-claude/models/overview
- [S3] Anthropic, Claude Haiku 5.5 model page. Released 2026-10-07, tokenizer, thinking default, sampling parameters, image input. https://platform.claude.com/docs/en/models/haiku-5-5/overview
- [S4] Anthropic, Structured outputs. Supported models incl. `claude-haiku-5-5`, constrained decoding, limitations. https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- [S5] Anthropic, Prompt caching (minimum cacheable length: 512 Haiku 5.5, 4,096 Haiku 4.5). https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- [S5a] Anthropic, What's new in Claude Haiku 5.5 (refusals without server-side fallback, prefill error, thinking-first blocks, thinking omitted by default, `disabled` at high effort or below, `max_tokens` and thinking). https://platform.claude.com/docs/en/models/haiku-5-5/whats-new-haiku-5-5
- [S6] VirtualSpeech, "Average Speaking Rate and Words per Minute" (NCVS 150 wpm; 120–150 conversation; 150–160 podcasters). https://virtualspeech.com/blog/average-speaking-rate-words-per-minute
- [S7] M. Liberman, Language Log, 2006-08-07 (Switchboard speaking rates). https://languagelog.ldc.upenn.edu/~myl/languagelog/archives/003423.html
- [S8] Same page as [S2] (words per token on the current vs earlier tokenizer).
- [S9] Qwen/Qwen3-4B-Instruct-2507 model card (Apache-2.0, non-thinking). https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- [S10] Qwen/Qwen3.5-4B model card (Apache-2.0, thinking default, `chat_template_kwargs`, no soft switch, runtimes). https://huggingface.co/Qwen/Qwen3.5-4B
- [S11] Google Open Source Blog, "Gemma 4: Expanding the Gemmaverse with Apache 2.0", 2026-04-02. https://opensource.googleblog.com/2026/03/gemma-4-expanding-the-gemmaverse-with-apache-20.html
- [S12] google/gemma-4-E4B-it model card (family context lengths and modalities). https://huggingface.co/google/gemma-4-E4B-it
- [S13] Google, Gemma Terms of Use (last modified 2026-04-01). https://ai.google.dev/gemma/terms
- [S14] Ventura, Yang, Schmid, Varol, "Chapter-Llama: Efficient Chaptering in Hour-Long Videos with LLMs", CVPR 2025, arXiv:2504.00072 (Tables 2, A.8, A.12). https://arxiv.org/html/2504.00072v1
- [S15] Xu et al., "Evaluating Small Language Models for News Summarization", arXiv:2502.00641 (Feb 2025). https://arxiv.org/abs/2502.00641
- [S16] YouTube Help, "Video chapters". https://support.google.com/youtube/answer/9884579
- [S17] Yang et al., "VidChapters-7M", arXiv:2309.13952. https://arxiv.org/html/2309.13952
- [S18] Llama 3.2 Community License (HF mirror; §1.b.i, §2). https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct/blob/main/LICENSE.txt
- [S19] Llama 3.2 Acceptable Use Policy (EU multimodal clause). https://github.com/meta-llama/llama-models/blob/main/models/llama3_2/USE_POLICY.md
- [S20] meta-llama/Llama-4-Scout-17B-16E-Instruct model card (Llama 4 Community License, 700M MAU). https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct
- [S21] Llama 4 Acceptable Use Policy (EU multimodal clause). https://github.com/meta-llama/llama-models/blob/main/models/llama4/USE_POLICY.md
- [S22] The Agent Report, "Meta Ships Llama 4.5" (unverified, secondary). https://the-agent-report.com/2026/06/meta-llama-4-5-open-weight-refresh/
- [S23a] microsoft/Phi-4-mini-instruct. https://huggingface.co/microsoft/Phi-4-mini-instruct
- [S23b] HuggingFaceTB/SmolLM3-3B (thinking on by default, `/no_think`). https://huggingface.co/HuggingFaceTB/SmolLM3-3B
- [S23c] ibm-granite/granite-4.0-micro. https://huggingface.co/ibm-granite/granite-4.0-micro
- [S23d] mistralai/Ministral-3-8B-Instruct-2512. https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512
- [S24] llama.cpp, grammars README (GBNF, JSON Schema subset, integer min/max, silent skipping). https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md
- [S25] llama-cpp-python docs (JSON schema mode, OpenAI-compatible server). https://llama-cpp-python.readthedocs.io/en/latest/
- [S26] Ollama blog, "Structured outputs", 2024-12-06. https://ollama.com/blog/structured-outputs
- [S27] vLLM docs, Structured outputs (xgrammar / guidance). https://docs.vllm.ai/en/latest/features/structured_outputs.html
- [S28] Red Hat Developers, "Ollama vs. vLLM: a deep dive into performance benchmarking", 2025-08-08 (updated 2026-07-13). https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking
- [S29] llama.cpp Discussion #4167, Apple Silicon performance (Llama-2-7B Q4_0, llama-bench). https://github.com/ggml-org/llama.cpp/discussions/4167
- [S30] llama.cpp Discussion #15013, NVIDIA CUDA performance (Llama-2-7B Q4_0). https://github.com/ggml-org/llama.cpp/discussions/15013
- [S31] Leaseweb, "AMD EPYC LLM Inference Benchmark", 2026-04-05. https://blog.leaseweb.com/2026/04/05/amd-epyc-llm-inference-benchmark-cpu-vs-gpu/
- [S32] DEV Community, "Running LLMs on CPU in 2026: real benchmarks from a 4-core Xeon server" (weak source). https://dev.to/manoir_yantai_f22f01340f0/-running-llms-on-cpu-in-2026-real-benchmarks-from-a-4-core-xeon-server-a-4-57c6
- [S33] Geng et al., "JSONSchemaBench", arXiv:2501.10868 (abstract only). https://arxiv.org/abs/2501.10868
- [S34] Tam et al., "Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of LLMs", arXiv:2408.02442. https://arxiv.org/abs/2408.02442
- [S35] Anthropic, Effort ("behavioral signal, not a strict token budget"; Haiku 5.5 default `medium`; `disabled` at `high` or below). https://platform.claude.com/docs/en/build-with-claude/effort
- [S36] Anthropic, Thinking (thinking tokens billed as output, count toward `max_tokens`). https://platform.claude.com/docs/en/build-with-claude/thinking
- [S37] Anthropic, Batch processing (most within 1 h, 24 h expiry, demand slowdowns, cache hits 30–98%, 1-hour cache suggestion). https://platform.claude.com/docs/en/build-with-claude/batch-processing
- [S38] Hugging Face model API, per-checkpoint licence and creation date: Qwen3.5-0.8B/2B/4B/9B/35B-A3B, Qwen3.6-35B-A3B, Qwen3.8-27B, Qwen3.8-Flash-Next, Qwen2.5-3B-Instruct, Qwen3-4B-Instruct-2507, granite-4.2-3b/8b/3b-GGUF, Ministral-3-3B-Instruct-2512, FrogNano-4B-2609, gemma-4-E4B/12B/26B-A4B-it, LFM2.5-1.2B-Instruct, SmolLM3-3B. https://huggingface.co/api/models/<id> (e.g. https://huggingface.co/api/models/Qwen/Qwen3.6-35B-A3B)
- [S39] OpenRouter public models API (prices per token). https://openrouter.ai/api/v1/models
- [S40] Ollama docs, Thinking (`think: false`). https://docs.ollama.com/capabilities/thinking
- [S41] microsoft/FrogNano-4B-2609 model card (coding agent derived from Qwen3.5-4B; licence field). https://huggingface.co/microsoft/FrogNano-4B-2609
- [S42] Qwen/Qwen3.6-35B-A3B model card (35B total / 3B active, 262k context, thinking by default). https://huggingface.co/Qwen/Qwen3.6-35B-A3B
- [S43] Anthropic, Refusals and fallback (retry on another Claude model, SDK refusal-fallback middleware, no Haiku 5.5 server-side fallback, `fallbacks` unsupported in Batch, no fallback credit for Haiku 5.5 refusals, refusal billing categories, classifier model list). https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback
- [S44] ibm-granite/granite-4.2-8b model card (release 2026-08-25, thinking on by default, 128K/512K context; 3B card identical on these points). https://huggingface.co/ibm-granite/granite-4.2-8b
- [S45] Qwen/Qwen3.8-27B model card (vision-language, thinking and `preserve_thinking` on by default, 262k context). https://huggingface.co/Qwen/Qwen3.8-27B
