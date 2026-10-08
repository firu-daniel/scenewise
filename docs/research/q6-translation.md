# Q6: Subtitles in other languages (roadmap item 5)

Research only. Building multi-language subtitles is out of scope. All sources were read on 2026-10-08 (revision r2, same day, after the final review round; sources renumbered in r1, S35–S39 added in r2, see the Sources list).

## Summary and recommendation

**Recommendation: DEFER (unchanged after reviews r1 and r2).** When the item is picked up, the default path is **Whisper (source-language transcript with timings) → LLM translation with context → original cue timings kept**. Use Claude Haiku 5.5 (`claude-haiku-5-5`) as the hosted option and a local commercially clean model (Qwen3, Gemma 4, or Seed-X, whose OpenMDW-1.0 licence is now confirmed permissive [S36]) as the free option. Reasons:

1. **Whisper cannot do it alone.** Whisper's translate task only produces English. The paper describes only "X→en" data and evaluation [S1], and the repo documents only "translate speech into English" and says `turbo` "is not trained for translation tasks" [S2]. Two speech models narrow the gap but do not close it. NVIDIA Canary-1b-v2 (CC-BY-4.0) translates speech En→24 and 24→En European languages, with segment-level timestamps [S23]. Gemma 4 E2B/E4B/12B do "speech-to-translated-text", but audio is capped at 30 s and no timestamps are documented [S19]. For any other pair, a text-MT step is still needed.
2. **The best-known dedicated MT models cannot be used commercially.** NLLB-200 weights are CC-BY-NC-4.0, and the code is MIT [S3][S4]. SeamlessM4T v2 is the same: weights CC-BY-NC-4.0, code MIT [S6][S7]. TowerInstruct and Tower+ [S12][S13] and Aya Expanse [S14] are NC. Hunyuan-MT-7B and the newer HY-MT1.5 (1.8B/7B) licences exclude the EU, UK and South Korea [S24][S37]. Expause is a commercial consumer, so all of these are ruled out.
3. **Commercially clean options exist but have no quality evidence for our domain.** MADLAD-400 (Apache-2.0) [S8][S9], Opus-MT (CC-BY-4.0) [S11], Seed-X (OpenMDW-1.0) [S25][S36], Canary (CC-BY-4.0) [S23] and Apache-2.0 LLMs [S17][S19] are usable or likely usable. Their published results are general-domain benchmarks: FLORES/WMT/FLEURS/CoVoST, or short Tatoeba sentences for Opus-MT, which its README says are "too optimistic" for realistic data [S11]. None covers short, informal, user-generated speech. MADLAD's card says it has not been assessed for production or for specific domains [S8].
4. **Hosted LLM cost is negligible.** Haiku 5.5 costs about $0.015–0.034 per target language per video-hour without thinking (derivation below). The legacy Haiku 4.5 costs about $0.11–0.25. Character-priced MT APIs come to about $1.1–1.5 per hour, roughly 30–100× Haiku 5.5. Cost does not block this. The blockers are product priority, the target-language list, and an evaluation set.
5. Translating cue by cue loses context. Translating with context needs cue IDs to round-trip reliably (see Notes). That is design work worth doing only when the item is actually scheduled.

## Options table

| Option | Licence (commercial?) | Size | Quality evidence | Notes |
|---|---|---|---|---|
| Whisper `translate` | MIT, code and weights [S2] | tiny to large | X→en only [S1] | `turbo` not trained for translation [S2]. Cannot produce non-English targets. |
| **Canary-1b-v2** (NVIDIA, 2025-08-14) | **CC-BY-4.0**, "ready for commercial and non-commercial use" [S23] | 978M [S23] | En→X FLEURS (24 languages): COMET 84.56, BLEU 29.4 [S23] | Speech→text: En→24 and 24→En, 25 European languages only. Segment-level timestamps for translation [S23]. |
| **Gemma 4 speech translation** (E2B/E4B/12B) | **Apache-2.0** [S19] | E4B is 4.5B effective (8B with embeddings) [S19] | CoVoST 35.54 (E4B) [S19] | Audio capped at **30 s**. No timestamps documented, so Whisper is still needed for timings [S19]. |
| NLLB-200 | Weights **CC-BY-NC-4.0**, code **MIT** [S3][S4]. **Not commercial.** | 600M distilled card [S3]. Paper uses MoE [S5] | +44% BLEU relative to the previous SOTA on FLORES-200 [S5] | "Research model… not released for production deployment". Trained on inputs of at most 512 tokens and "not intended to be used for document translation" [S3]. |
| SeamlessM4T v2 | Weights **CC-BY-NC-4.0**, code MIT [S6][S7]. **Not commercial.** | 2.3B [S6] | No numbers on the card | S2TT and T2TT in "nearly 100 languages" [S7]. |
| MADLAD-400 MT | **Apache-2.0** [S8][S9] | 3B, 7.2B, 10.7B [S9]. 3B is 11.8 GB in F32, 1.65 GB as GGUF q4k [S8] | "Competitive with models that are significantly larger" [S10]. Evaluated on 204 of 400+ languages [S8] | T5 seq2seq with a `<2xx>` tag. Sentence-level. Not assessed for production or domain [S8]. |
| Opus-MT (Marian) | Models **CC-BY-4.0**, code MIT [S11] | Small, mostly one model per pair. Separate multilingual OPUS-100 models are linked [S11] | Mostly short **Tatoeba** sentences, "too optimistic" for realistic data [S11] | Many pair models to manage. |
| **Seed-X-PPO-7B** (ByteDance, Jul 2025) | **OpenMDW-1.0** (repo LICENSE, read first-hand) [S36]. MIT-like: "permission is hereby granted, free of charge, to deal in the Model Materials without restriction". On redistribution, keep a copy of the agreement and all notices. Rights terminate if you bring a patent suit. No restrictions on outputs, no AUP, no field-of-use limit. AS-IS, and the user is "SOLELY RESPONSIBLE FOR… CLEARING RIGHTS OF OTHER PERSONS" [S36][S26]. **Commercial use allowed.** | 7B in the name; HF metadata shows about 8B params [S25] | Claims "on par with or outperforming" Gemini-2.5, Claude-3.5 and GPT-4 on FLORES-200 and WMT-25 (self-reported). The card itself gives no scores; numbers are in the tech report, arXiv 2507.13618 [S25] | 28 languages [S25]. Strongest *self-reported* claims among the clean candidates (unverified). Translation-only: "We don't have any chat template", no multi-round prompts, a target-language tag (e.g. `<de>`) ends the prompt, and the authors advise against unofficial quantised builds [S25]. So cue-ID JSON is unlikely to round-trip; expect sentence/segment prompts. |
| **Hunyuan-MT-7B** (Tencent, 2025-09-01) and **HY-MT1.5 1.8B/7B** (Tencent, 2025-12-30) | Tencent Hunyuan / Tencent HY Community Licence: "DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA" (same wording in both) [S24][S37]. Separate licence needed above 100M MAU, measured "on the … version release date" (a snapshot, not an ongoing threshold). §5(b): Outputs may not be used "to improve any other AI model". The Exhibit A AUP can be updated by Tencent [S24]. **Not usable.** | 7B; HY-MT1.5 1.8B (edge) and 7B [S37] | Hunyuan-MT-7B: "First place in 30 out of the 31" WMT25 categories it entered (self-reported) [S24]. HY-MT1.5: not checked | 33 languages [S24][S37]. Both ruled out by the territorial exclusion. |
| TowerInstruct 7B v0.2 / Tower+ 9B | **CC-BY-NC-4.0** (Tower+ also tags cc-by-nc-sa) [S12][S13]. **Not commercial.** | 7B / 9B | Tower+: "one of the best multilingual LLMs under 10B" (chart only) [S13] | 10 languages (v0.2) [S12]. |
| Aya Expanse 8B/32B | **CC-BY-NC** plus Cohere AUP [S14]. **Not commercial.** | 8B, 32B | No numbers checked | 23 languages [S14]. |
| TranslateGemma 4B/12B/27B (Jan 2026) | Gemma Terms of Use. The model is listed in its Appendix, and the terms contain **no non-commercial clause**. §3.1 requires passing the §3.2 use restrictions and the Prohibited Use Policy downstream, giving recipients a copy of the Agreement, marking modified files and shipping a Notice file. §3.2 lets Google "restrict (remotely or otherwise) usage" it reasonably believes violates the terms [S16] | 4B (5B listed), 12B, 27B [S15] | WMT24++ (55 languages): COMET 81.6 / 83.5 / 84.4, MetricX 5.32 / 3.60 / 3.09 [S15] | **2K-token input context** [S15]. |
| Meta Omnilingual MT (OMT-LLaMA 1–8B; Mar 2026) | **Unknown.** The Meta page (2026-03-17) links no weights, code or licence [S21] | 1B–8B [S20] | 1B–8B models "match or exceed" a 70B baseline [S20] | 1,600+ languages. Reported to be built on LLaMA 3, but S22 returned HTTP 403 on re-check, so this is unverified. |
| Qwen3-8B | **Apache-2.0** [S17] | 8.2B | Card claims translation strength, 100+ languages, with no numbers [S17] | A general chat LLM, so cue-ID JSON and context prompts are possible in principle (not tested). |
| Gemma 4 (text) | **Apache-2.0** [S18][S19]. The Gemma Terms exclude Gemma 4 [S16] | E2B, E4B, 12B, 26B A4B (MoE), 31B [S19] | No text-MT numbers checked | Pre-trained on 140+ languages, 35+ supported out of the box. 128K context on the small models [S19]. |
| **Claude Haiku 5.5** `claude-haiku-5-5` (released 2026-10-07) | Commercial API | n/a | No MT benchmark checked (open question) | $0.10 in / $0.50 out per MTok for prompts ≤100k tokens. **$0.50 / $2.50 above 100k.** Batch is 50% off [S27]. New tokenizer: about 30% more tokens than Haiku 4.5. Adaptive thinking is on by default at effort `medium`. Thinking can be turned off with `thinking: {type: "disabled"}` at effort `high` or below; at `xhigh`/`max` that returns a 400 error [S35]. A non-default `temperature`, `top_p` or `top_k` returns a 400 error [S28][S29]. |
| Claude Haiku 4.5 (legacy) | Commercial API | n/a | Not checked | $1 / $5 per MTok [S27]. Listed under "Legacy models (still available)" [S29]. Fallback only. |
| DeepL API / Google Cloud Translation | Commercial APIs | n/a | Not checked | Priced per character. Google (read first-hand): NMT costs $20 per M characters, with the first 500k a month free as a $10 credit that is listed under NMT only, so Translation LLM has no free tier. Translation LLM costs $10 in + $10 out per M characters, "cost equivalent with NMT"; Adaptive translation (LLM) costs $25 + $25 [S30]. DeepL Growth (secondary sources only; DeepL's API price tab renders client-side): $32.50 a month including 1M characters (about 18 video-hours), then $27.50 per extra M, capped at 50M a month [S31][S38][S39]. Below about 18 h a month the marginal DeepL cost is $0 and the cost is the fixed fee; the $1.49/h figure is the overage rate. An AWS Marketplace annual listing shows $25/M. DeepL's legacy API Free/Pro plans are reported closed to new signups as of mid-2026 [S31]. **Deferred:** about 30–100× Haiku 5.5's cost (Google 32–72×, DeepL 44–99×), and cue-ID and context control was not checked. |

### Cost per video-hour, per target language (estimate; the inputs are assumptions)

Assumptions (not sourced):
- About 150 words per minute of speech, so 9,000 words per hour.
- SRT cue IDs and timestamps double the input.
- A context overlap of 1.5× applies to input only.
- The output is JSON with cue IDs and no timestamps, so translated text ×1.2.
- A script/length expansion of 1×–3× for the target language is an **unsourced upper-bound band**.
- The words→tokens (step 1) and words→characters (step 8, 6 chars/word) conversions are independent rough assumptions. At the pricing page's "1 token is approximately 4 characters" [S27], 54k characters would be 13.5k Haiku 4.5 tokens rather than 12k, a ~12% gap that does not change any conclusion.

1. **Tokens per hour of source text.**
   - Haiku 4.5: 9,000 ÷ 0.75 words per token = **12,000** [S27].
   - Haiku 5.5: 9,000 ÷ 0.555 = **16,200**, because 1M tokens ≈ 555k words on the new tokenizer [S29].
2. **Input.**
   - Haiku 4.5: 12,000 × 2 × 1.5 = **36,000**.
   - Haiku 5.5: 16,200 × 2 × 1.5 = **48,600**.
3. **Output.**
   - Haiku 4.5: 12,000 × 1.2 × (1–3) = **14,400–43,200**.
   - Haiku 5.5: 16,200 × 1.2 × (1–3) = **19,400–58,300**.
4. **Haiku 5.5.**
   - Input: 48,600 × $0.10/M = $0.0049.
   - Output: 19,400–58,300 × $0.50/M = $0.0097–0.0292.
   - **Total ≈ $0.015–0.034 per hour.**
5. **Haiku 4.5.**
   - Input: 36,000 × $1/M = $0.036.
   - Output: 14,400–43,200 × $5/M = $0.072–0.216.
   - **Total ≈ $0.11–0.25 per hour.**
6. **Thinking.** The figures above assume thinking adds nothing. Thinking tokens are "billed as output tokens, even when the thinking text isn't returned" [S35]. On Haiku 5.5, thinking can be disabled at effort `high` or below [S35], so the no-thinking figures are directly achievable. If thinking is left on and doubles the output, the Haiku 5.5 upper bound becomes 0.0049 + 2 × 0.0292 ≈ **$0.063**. The Batch API halves every figure [S27].
7. **Prompt tier.** One hour is about 48.6k input tokens, which stays under the 100k tier. Inputs above about 2 hours, or large context windows, must be chunked, or the price is 5× higher [S27].
8. **Character-priced MT APIs.** About 6 characters per word is assumed, giving 54,000 characters per hour.
   - Google NMT: 54k × $20/M = $1.08.
   - Google Translation LLM: 54k × $10/M in + about 54k × $10/M out ≈ $1.08.
   - DeepL: 54k × $27.50/M ≈ $1.49, plus the monthly fee.
9. **Per video.** No Expause video-length figure exists in the docs, so assume 3 minutes for illustration.
   - Haiku 5.5: $0.034 ÷ 20 ≈ $0.0017, a fraction of a cent.
   - Haiku 4.5: $0.25 ÷ 20 ≈ $0.013.

## Notes (subtitle-specific)

- **Cue-by-cue translation** keeps timing trivially, because there is a 1:1 cue mapping. It loses cross-cue context such as pronouns, gender agreement and sentences split across cues. Sentence-level seq2seq models (MADLAD, Opus-MT, NLLB with its 512-token training limit [S3]) force this mode or a sentence-merge step.
- **Context translation** (an LLM with a window of N cues, stable cue IDs and JSON output) improves fluency. It can merge, split or drop cues, so we must validate that every input ID comes back. Papi et al. say imposing source segmentation on the target "could be a sub-optimal solution" and project source timestamps onto target blocks with three methods: block-wise, Levenshtein and semantic [S32]. SBAAM treats translation, segmentation and timestamping as three subtasks [S33].
- **Reading speed and line length (CPS/CPL)** change with the target language. Translated cues can break limits that the source met. Papi et al. evaluate segmentation with Sigma and CPL (42-character limit) [S34].
- **Thinking off and JSON:** the docs warn that "With thinking off, the model can skip a tool call it needs when you also request JSON output" [S35]. If cue-ID JSON is returned via a tool, test with thinking off and at low effort before choosing the cheaper setting.
- **Determinism:** Haiku 5.5 does not allow `temperature: 0` (it returns a 400 error, "regardless of whether thinking is used") [S28][S35]. Reproducibility has to come from validation, not sampling settings.
- TranslateGemma's 2K-token input [S15] and Gemma 4's 30 s audio cap [S19] limit how much context fits in one call.
- Expause content is short and informal, often with slang or code-switching. None of the benchmarks above cover this domain.

## Open questions

1. **Decision for the user: is TranslateGemma acceptable?** Commercial use is not prohibited, but §3.1 requires passing the §3.2 restrictions and the Prohibited Use Policy downstream, giving recipients a copy of the Agreement, marking modified files and shipping a Notice; §3.2 lets Google restrict usage "remotely or otherwise"; §4.5 allows termination for breach [S16]. *For:* strong WMT24++ numbers [S15] and no fee. *Against:* non-OSI terms with a remote-restriction right in an Apache/MIT project, and a 2K-token input that limits context; Apache-2.0 Gemma 4 / Qwen3 and OpenMDW Seed-X avoid all of this.
2. Were Meta Omnilingual MT weights released, and under what licence? None were linked as of 2026-10-08 [S21].
3. *Closed in r2.* Seed-X ships under OpenMDW-1.0: commercial use allowed; obligations are keeping the agreement copy and notices on redistribution, plus patent termination; the user carries rights clearance [S36]. (OpenMDW 1.1 exists, updated 2026-05-27, but Seed-X's repo pins 1.0.)
4. How do Seed-X, MADLAD-400, Opus-MT and Canary compare with Haiku 5.5 and Qwen3 on chrF/COMET for Expause's target languages and content? No head-to-head numbers were found.
5. Which target languages does Expause need? If they are English↔European only, Canary-1b-v2 could replace Whisper plus MT [S23].
6. What are Haiku 5.5's real output and thinking-token counts per target script, at effort `low`? (Whether thinking can be disabled is answered: yes, at effort `high` or below [S35].) **Decision for the user when the item is scheduled:** run with thinking *off* (cheapest, matches the $0.015–0.034 figures, but the docs warn JSON tool calls can be skipped) or *on at low effort* (more reliable cue-ID JSON, up to about 2× output cost). Only a pilot on real cues can settle this.
7. Should translation run on Whisper's source transcript or on an English pivot? Is pivot error compounding acceptable?
8. What is the typical length of an Expause video? It is needed to turn the per-hour figures into per-video figures.
9. Do the DeepL and Google APIs support context or glossary inputs that would preserve cue IDs? Google's prices are now confirmed first-hand [S30]. DeepL's API prices could not be read first-party (client-rendered tab); the $32.50 / $27.50 figures rest on two secondary sources [S31][S39] and conflict with a $25/M AWS Marketplace annual listing. Re-check on deepl.com when signed in, if DeepL is ever reconsidered.

## Sources (all read 2026-10-08)

- [S1] Radford et al., Whisper paper, arXiv 2212.04356v1, https://arxiv.org/html/2212.04356v1
- [S2] openai/whisper README, https://github.com/openai/whisper
- [S3] facebook/nllb-200-distilled-600M card, https://huggingface.co/facebook/nllb-200-distilled-600M
- [S4] fairseq `nllb` branch README, https://github.com/facebookresearch/fairseq/tree/nllb
- [S5] NLLB Team, "No Language Left Behind", arXiv 2207.04672, https://arxiv.org/abs/2207.04672
- [S6] facebook/seamless-m4t-v2-large card, https://huggingface.co/facebook/seamless-m4t-v2-large
- [S7] facebookresearch/seamless_communication README, https://github.com/facebookresearch/seamless_communication
- [S8] google/madlad400-3b-mt card, https://huggingface.co/google/madlad400-3b-mt
- [S9] google/madlad400-10b-mt card, https://huggingface.co/google/madlad400-10b-mt
- [S10] Kudugunta et al., MADLAD-400, arXiv 2309.04662, https://arxiv.org/abs/2309.04662
- [S11] Helsinki-NLP/Opus-MT README, https://github.com/Helsinki-NLP/Opus-MT
- [S12] Unbabel/TowerInstruct-7B-v0.2 card, https://huggingface.co/Unbabel/TowerInstruct-7B-v0.2
- [S13] Unbabel/Tower-Plus-9B card, https://huggingface.co/Unbabel/Tower-Plus-9B
- [S14] CohereLabs/aya-expanse-8b card, https://huggingface.co/CohereLabs/aya-expanse-8b
- [S15] google/translategemma-4b-it card, https://huggingface.co/google/translategemma-4b-it ; coverage: https://infoq.com/news/2026/01/google-translategemma-models
- [S16] Gemma Terms of Use (last modified 2026-04-01), https://ai.google.dev/gemma/terms
- [S17] Qwen/Qwen3-8B card, https://huggingface.co/Qwen/Qwen3-8B
- [S18] Google Open Source Blog, "Gemma 4: Expanding the Gemmaverse with Apache 2.0" (2026-04-02), https://opensource.googleblog.com/2026/03/gemma-4-expanding-the-gemmaverse-with-apache-20.html
- [S19] google/gemma-4-E4B-it card, https://huggingface.co/google/gemma-4-E4B-it
- [S20] Omnilingual MT, arXiv 2603.16309, https://arxiv.org/abs/2603.16309
- [S21] Meta publication page, Omnilingual MT (2026-03-17), https://ai.meta.com/research/publications/omnilingual-mt-machine-translation-for-1600-languages/
- [S22] Slator coverage, https://slator.com/?p=112857 (HTTP 403 on 2026-10-08) ; Omnilingual ASR Apache-2.0 report, https://www.opensourceforu.com/2025/11/metas-omnilingual-asr-brings-1600-languages-to-open-source-speech-ai/
- [S23] nvidia/canary-1b-v2 card, https://huggingface.co/nvidia/canary-1b-v2
- [S24] tencent/Hunyuan-MT-7B card, https://huggingface.co/tencent/Hunyuan-MT-7B ; licence: https://huggingface.co/tencent/Hunyuan-MT-7B/raw/main/License.txt
- [S25] ByteDance-Seed/Seed-X-PPO-7B card, https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B
- [S26] Linux Foundation, "Why We Built the OpenMDW License" (2025-07-02), https://huggingface.co/blog/linuxfoundation/openmdw
- [S27] Anthropic pricing page, https://platform.claude.com/docs/en/about-claude/pricing
- [S28] Claude Haiku 5.5 overview, https://platform.claude.com/docs/en/models/haiku-5-5/overview
- [S29] Anthropic models overview, https://platform.claude.com/docs/en/about-claude/models/overview
- [S30] Google Cloud Translation pricing, https://cloud.google.com/translate/pricing (read first-hand via plain HTTP GET, 2026-10-08)
- [S31] SimpleLocalize, "How much does AI translation cost? DeepL, Google Translate, OpenAI compared (2026)", 2026-06-03 (secondary), https://simplelocalize.io/blog/posts/ai-machine-translation-cost-comparison/
- [S32] Papi, Gaido, Karakanta, Cettolo, Negri, Turchi, "Direct Speech Translation for Automatic Subtitling", arXiv 2209.13192, https://arxiv.org/pdf/2209.13192
- [S33] Gaido et al., SBAAM, arXiv 2405.10741, https://arxiv.org/pdf/2405.10741v1
- [S34] Papi et al., "Dodging the Data Bottleneck", arXiv 2209.10608, https://arxiv.org/abs/2209.10608v2
- [S35] Anthropic, "Thinking", https://platform.claude.com/docs/en/build-with-claude/thinking
- [S36] Seed-X repo LICENSE (OpenMDW-1.0), https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B/raw/main/LICENSE ; licence index: https://openmdw.ai/license
- [S37] Tencent HY Community Licence for HY-MT1.5, https://huggingface.co/tencent/HY-MT1.5-1.8B/raw/main/License.txt ; tech report arXiv 2512.24092
- [S38] DeepL support, "Usage count and billing in DeepL API", https://support.deepl.com/hc/en-us/articles/360020685720 (first-party: 1M characters included monthly on Growth, 50M cap; no USD prices)
- [S39] flexprice.io pricing index, DeepL (secondary, search excerpt dated 2026-09-22), https://flexprice.io/pricing-index/deepl-translator ; conflicting: AWS Marketplace annual Growth listing ($25/M), https://aws.amazon.com/marketplace/pp/prodview-2fii5e2hmuneo

## Review round 1 — resolution

Every finding was re-checked on 2026-10-08. Old source labels are mapped to new ones in the Sources list.

1. **Fixed.** Attribution changed to Papi et al. and the quote corrected to "could be a sub-optimal solution". The three methods are named. Author order checked on https://arxiv.org/abs/2209.13192 [S32].
2. **Fixed.** Haiku 5.5 now uses 0.555 words per token [S29] and the "approximately 30% more tokens" note [S27][S28]. The arithmetic was redone. The new range ($0.015–0.034) is lower than the reviewer's $0.03–0.05, because finding 6 also changed the output model.
3. **Fixed.** The default adaptive thinking (effort `medium`) and the 400 error on a non-default `temperature`/`top_p`/`top_k` were confirmed [S28][S29]. A thinking sensitivity was added (step 6), along with a Determinism note and open question 6.
4. **Fixed.** Added the ID `claude-haiku-5-5`, the 2026-10-07 release date and Haiku 4.5's legacy status [S28][S29].
5. **Fixed.** Added the >100k tier ($0.50 / $2.50) and a chunking note [S27].
6. **Fixed.** The output is now derived as JSON text ×1.2 × 1–3 expansion, with the band labelled an unsourced upper bound. Overlap is applied to input only.
7. **Fixed.** A 3-minute video is stated as an assumption, and the per-video figures are split by model. Open question 8 was added.
8. **Fixed.** The text now says the terms have no non-commercial clause, gives the §3.1/§3.2 obligations, and notes that Gemma 4 is excluded [S16].
9. **Fixed.** Exact Gemma 4 sizes, language counts and context added from the HF card [S19].
10. **Fixed.** Added a Gemma 4 speech-translation row: 30 s cap, CoVoST 35.54, no timestamps [S19]. Summary point 1 was qualified.
11. **Fixed.** Added a Canary-1b-v2 row: CC-BY-4.0, 978M, En↔24, segment timestamps, COMET 84.56 / BLEU 29.4 [S23]. Summary point 1 was qualified.
12. **Fixed.** Added Hunyuan-MT-7B as not usable, because of the EU/UK/KR exclusion and the 100M MAU clause [S24].
13. **Fixed.** Added Seed-X-PPO-7B. OpenMDW was checked via the LF post [S26]. The full licence text is still an open question (open question 3).
14. **Fixed.** Added DeepL and Google rows with per-character prices and the reason they are deferred. Caveat: the official pricing pages did not render, so the figures come from a search excerpt of Google's page [S30] and a 2026-06-03 secondary source [S31]. Open question 9 was added.
15. **Fixed.** Added the 512-token and no-document-translation caveats [S3]. The other checkpoint sizes were not added, because they could not be sourced here.
16. **Fixed, with a correction to the review.** The Tatoeba caveat was added. The README does not call its own models multilingual. It *links* to separate OPUS-100 multilingual models, and the table now says that [S11].
17. **Fixed.** Added the Meta page (no weights, code or licence linked) as S21. The LLaMA 3 base is marked unverified because of the 403 error. Open question 2 was kept.
18. **Fixed.** All sources renumbered sequentially. The MADLAD paper is now S10, next to S8 and S9.

No findings were rejected. The recommendation is unchanged: **DEFER**. Canary and Seed-X add clean options but do not remove the blockers (target-language list, domain evaluation set, priority), and the corrected cost is still negligible.

## Review round 2 — resolution

Final round. Every finding was re-checked against its source on 2026-10-08 before it was applied.

1. **Fixed.** The multiple is now "about 30–100×" (Google 32–72×, DeepL 44–99×), recomputed from the doc's own $1.08–1.49 and $0.015–0.034 figures. The summary now states the multiple too.
2. **Fixed.** Read the Seed-X repo LICENSE first-hand: OpenMDW-1.0, with the grant, redistribution, patent-termination, outputs, AS-IS and rights-clearance clauses as quoted [S36]. The Seed-X row, summary and recommendation were updated, the "once its licence is checked" hedge dropped, and open question 3 closed.
3. **Fixed.** The Thinking page confirms Haiku 5.5 accepts `thinking: {type: "disabled"}` at effort `high` or below (400 at `xhigh`/`max`) and warns that with thinking off the model can skip a needed tool call when JSON output is also requested [S35]. Added to the Haiku 5.5 row, cost step 6, a new Notes bullet and open question 6, which is now a decision (thinking off vs low effort) for the user.
4. **Fixed.** "Billed as output tokens" now quoted and cited to the Thinking page [S35] in step 6.
5. **Fixed.** Google pricing re-read first-hand (plain HTTP GET works). S30 caveat replaced; no free tier on Translation LLM and the Adaptive $25 + $25 rate added; Google dropped from open question 9.
6. **Fixed, partly.** DeepL is still secondary-only. Added the first-party DeepL support article (1M characters included, 50M cap) [S38], flexprice.io as a second secondary source [S39], the Free/Pro discontinuation [S31], the ~18 h included-volume note, and a conflicting $25/M AWS Marketplace annual listing found during re-verification. Open question 9 keeps the DeepL re-check.
7. **Fixed.** Added MAU-at-release-date, §5(b) no-improving-other-models and the updatable AUP to the Hunyuan row [S24].
8. **Fixed.** HY-MT1.5 1.8B/7B (2025-12-30) added to the Hunyuan row: same Tencent HY licence, same EU/UK/KR exclusion and MAU clause, not usable [S37].
9. **Fixed.** The §3.2 remote-restriction right, §3.1 copy-of-Agreement and modified-file marking duties, and §4.5 termination were added to the TranslateGemma row and open question 1, which is now phrased as a decision for the user with both sides.
10. **Fixed.** "Likely the strongest" softened to "strongest self-reported claims among the clean candidates (unverified)". Added: no scores on the card (numbers in arXiv 2507.13618), no chat template, single-turn, target-language tag, no unofficial quantisation, about 8B params. Noted cue-ID JSON is unlikely to round-trip. Also softened the Qwen3 "Handles cue-ID JSON" note to "possible in principle (not tested)" for consistency.
11. **Fixed.** Added an assumption stating the token and character conversions are independent rough assumptions, with the ~12% gap quantified; no figures changed.

No findings were rejected. The recommendation is unchanged: **DEFER**. Unsettled items are left as user decisions in open questions 1, 6 and 9.
