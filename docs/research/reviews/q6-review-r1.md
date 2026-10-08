# Review r1: q6-translation.md

Reviewer: fresh review agent (did not write the file). Every source was re-opened on 2026-10-08 unless noted. The reviewed file was not edited.

Severity counts: wrong 2 · unsupported 3 · missing option 5 · minor 8 (18 findings in total).

## Findings

1. **S19 attribution and quote.** The doc says: "Karakanta et al. note that reusing source segmentation for the target 'can be suboptimal' and propose projecting timestamps onto target blocks [S19]."
   → The arXiv 2209.13192 PDF (https://arxiv.org/pdf/2209.13192, read 2026-10-08) is by **Papi, Gaido, Karakanta, Cettolo, Negri, Turchi**. Papi is first author and Karakanta is third. The §3.3 text reads: imposing the caption segmentation on the subtitle side "could be a sub-optimal solution. For this reason, we introduce a caption-subtitle alignment module that projects the source timestamps to the target blocks". It then lists three methods: BWP, LEV and SEM. The substance is right, but the attribution and the quote are wrong. The source list title for S19 is correct.
   → **wrong**
   → Fix: change it to "Papi et al." and quote "could be a sub-optimal solution". Optionally name the three projection methods (block-wise, Levenshtein, semantic).

2. **The Haiku 5.5 cost uses the old-tokenizer ratio.** The doc says 12k tokens per hour, from "1 token ≈ 0.75 English words [S18]", applied to both Haiku models. It then adds, as a side note, "4.7+ models use a new tokenizer with about 30% more tokens".
   → The pricing page (https://platform.claude.com/docs/en/about-claude/pricing, read 2026-10-08) says: "Claude 4.7 and later models … use a newer tokenizer … approximately 30% more tokens". The Haiku 5.5 page (https://platform.claude.com/docs/en/models/haiku-5-5/overview, read 2026-10-08) says it "uses the same newer tokenizer as Claude 4.7 and later models, so the same text counts as approximately 30% more tokens than on Claude Haiku 4.5". The models overview says 1M tokens ≈ 555k words on the current tokenizer, against 750k on the old one. The 0.75 ratio therefore applies only to Haiku 4.5.
   → Re-done arithmetic for Haiku 5.5 with the doc's own assumptions:
     - 9k words / 0.555 ≈ 16.2k tokens, then ×2 for SRT, then ×1.5 for overlap ≈ 49k input tokens, which costs $0.0049.
     - Output of 49k–97k tokens at $0.50/MTok costs $0.024–0.049.
     - The total is about **$0.03–0.05**, not $0.02–0.04.

     The Haiku 4.5 figure checks out: 36k × $1/M = $0.036; 36–72k × $5/M = $0.18–0.36; the total is $0.216–0.396, which matches the doc's $0.22–0.40.
   → **wrong** (low impact: the conclusion that cost is negligible still holds)
   → Fix: apply the 1.3–1.35× factor to Haiku 5.5. Change the summary range to "$0.03–0.40".

3. **Thinking tokens are left out of the cost estimate.** The doc says nothing about them.
   → On the Haiku 5.5 page (same URL, read 2026-10-08), the "Good to know" section says: "Adaptive thinking is on by default. Control thinking depth with the effort parameter". The models overview lists the default effort as `medium`. Thinking output is billed as output tokens, so output could be well above the 36–72k assumed.
   → **unsupported**
   → Fix: state that the estimate assumes low effort or thinking turned off. Add thinking-token overhead to open question 5. Also note that Haiku 5.5 rejects non-default `temperature`, `top_p` and `top_k` with a 400 error (same page). This matters if someone plans to set temperature 0 for deterministic MT.

4. **Haiku model IDs and dates are missing.** The doc names "Haiku 5.5" and "Haiku 4.5" but gives no model IDs or release status.
   → The models overview (https://platform.claude.com/docs/en/about-claude/models/overview, read 2026-10-08) and the Haiku 5.5 page give:
     - Haiku 5.5: API ID `claude-haiku-5-5` (Bedrock: `anthropic.claude-haiku-5-5`). Released **2026-10-07**, the day before the doc. Retirement not sooner than 2027-10-07. 1M context, 128K max output.
     - Haiku 4.5: listed under "Legacy models (still available)".
   → **minor**
   → Fix: add the ID `claude-haiku-5-5` and the release date. Mark Haiku 4.5 as legacy, so the $0.22–0.40 figure is a fallback rather than the default.

5. **Haiku 5.5 has a second price tier above 100k tokens.** The doc says "$0.10 in / $0.50 out per MTok (prompts ≤100k)" but does not say what happens above that.
   → The pricing page lists $0.50 in / $2.50 out per MTok for prompts over 100,000 tokens, and $0.25 / $1.25 on Batch. The long-context section says Haiku 5.5 is the exception to flat 1M-context pricing.
   → **minor**
   → Fix: state that one call must stay under 100k prompt tokens or cost 5× more. This argues for chunking by cue window rather than sending the whole transcript in one call. Expause's short videos are unaffected.

6. **The output-token assumption has no basis.** The doc says "I assume 36k–72k output tokens, because non-Latin scripts tokenize worse."
   → No source is given. The context overlap (1.5×) inflates input only, not output. If the output is JSON with cue IDs and no timestamps, the base is about 12–16k tokens, so 36–72k means a 2–6× expansion. That fits for some scripts, but no figure supports it. This mainly inflates the Haiku 4.5 number.
   → **unsupported**
   → Fix: show the derivation (cue IDs only, about 1.2× for IDs, then a script expansion factor per language). Alternatively, label 36–72k explicitly as a conservative upper bound.

7. **"Cost per video is a fraction of a cent"** is not true for every model.
   → No Expause video-length figure is cited, and none exists in /Users/daniel/scenewise/docs. At the Haiku 4.5 upper bound ($0.40 per hour, about $0.0067 per minute), a 3-minute video costs about $0.02. The claim holds for Haiku 5.5 (under $0.001 per minute, even after finding 2) and for Haiku 4.5 only below about 1.5 minutes.
   → **unsupported**
   → Fix: state the assumed video length, or limit the claim to Haiku 5.5.

8. **The commercial status of TranslateGemma is framed too cautiously.** The doc says: "Commercial status needs legal reading (open question)."
   → The Gemma Terms (https://ai.google.dev/gemma/terms, last modified 2026-04-01, read 2026-10-08) include TranslateGemma in the Appendix. §2.2 grants rights to use, reproduce, modify and distribute, and the terms contain no non-commercial clause. The obligations are §3.1 (pass the §3.2 use restrictions downstream as enforceable terms, and ship the Gemma notice) and §3.2 (the Prohibited Use Policy). The page also states that Gemma 4 is excluded: "For Gemma 4 terms, see the Gemma 4 license".
   → **minor**
   → Fix: say "commercial use is not prohibited; open question is whether the §3.1 pass-through + Prohibited Use Policy are acceptable for an OSS Apache/MIT project".

9. **Gemma 4 sizes are vague.** The doc says "Edge sizes up to 31B [S16]."
   → The blog post (S16, dated **2026-04-02**, read 2026-10-08) says only "from edge devices to 31B parameters". The HF card (https://huggingface.co/google/gemma-4-E4B-it, read 2026-10-08) lists E2B, E4B, 12B, 26B A4B (MoE) and 31B, pre-trained on 140+ languages with out-of-the-box support for 35+. Context is 128K on E4B.
   → **minor**
   → Fix: list the actual sizes and the language counts. Cite the HF card.

10. **Missing option: Gemma 4 speech-to-translated-text.**
    → The Gemma 4 E4B card (same URL, read 2026-10-08) says audio input on E2B, E4B and 12B supports "speech-to-translated-text translation across multiple languages". Audio is capped at 30 s. The card reports CoVoST 35.54 for E4B. The licence is Apache-2.0. The model could translate a short Expause clip directly, without Whisper, but cue timings would have to come from Whisper anyway. The doc marks Gemma 4 quality as "Not checked" even though the card has a CoVoST number.
    → **missing option**
    → Fix: add it as an option with the 30 s limit and the CoVoST figure, and note that it gives no timestamps.

11. **Missing option: NVIDIA Canary-1b-v2.**
    → The card (https://huggingface.co/nvidia/canary-1b-v2, read 2026-10-08) gives:
      - Licence: **CC-BY-4.0**, "ready for commercial and non-commercial use".
      - Size: about 1B parameters. Released 2025-08-14.
      - Tasks: ASR plus speech translation **En→24 and 24→En** (25 European languages), with segment-level timestamps for translation.
      - En→X FLEURS: COMET 84.56, BLEU 29.4.

    This weakens the doc's point 1 ("Any other target language needs a separate text-MT step") for English-source audio into European targets.
    → **missing option**
    → Fix: add a table row and qualify point 1.

12. **Missing option (to be ruled out): Tencent Hunyuan-MT-7B.**
    → The card (https://huggingface.co/tencent/Hunyuan-MT-7B, read 2026-10-08) reports 33 languages, a release on 2025-09-01, and "first place in 30 out of the 31" WMT25 categories it entered. The licence (https://huggingface.co/tencent/Hunyuan-MT-7B/raw/main/License.txt) is the Tencent Hunyuan Community License: "DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM AND SOUTH KOREA", with a threshold at 100M MAU.
    → **missing option**
    → Fix: add it as "not usable (territorial exclusion)". It is a strong, well-known MT model that readers will ask about.

13. **Missing option: ByteDance Seed-X-PPO-7B.**
    → The card (https://huggingface.co/ByteDance-Seed/Seed-X-PPO-7B, read 2026-10-08) gives an **OpenMDW** licence, 28 languages and a paper dated 2025-07-18. It claims to be "on par with or outperforming … Gemini-2.5, Claude-3.5, and GPT-4" on FLORES-200 and WMT-25.
    → **missing option**
    → Fix: add it with "licence OpenMDW (verify permissiveness)". It is a dedicated MT LLM that may be commercially clean.

14. **Missing option: hosted MT APIs and other cheap hosted LLMs.**
    → DeepL API, Google Cloud Translation and other low-cost hosted LLMs are not mentioned. Haiku-first is the project's stance, but a research doc should say why dedicated MT APIs were excluded (for example, no cue-ID or context control, or character-based pricing). I did not price them in this review.
    → **missing option**
    → Fix: add one line or row, with the reason they are excluded or deferred.

15. **The NLLB row is incomplete.** The doc lists only the "600M distilled card" and the MoE paper.
    → The card (https://huggingface.co/facebook/nllb-200-distilled-600M, read 2026-10-08) also says the model was "trained with input lengths not exceeding 512 tokens", "is not intended to be used for document translation", and is general-domain. These caveats directly support the doc's argument against context translation for seq2seq models. The other NLLB checkpoints (1.3B, 3.3B dense; 54.5B MoE) come from my own knowledge and were not re-sourced here.
    → **minor**
    → Fix: add the 512-token and no-document-translation caveats. Optionally list the other checkpoint sizes.

16. **Opus-MT's quality evidence is mischaracterised.** Summary point 3 lumps Opus-MT into "published results are general-domain or news (FLORES/WMT)" and the table says "one model per language pair".
    → The README (https://github.com/Helsinki-NLP/Opus-MT, read 2026-10-08) says the evaluations mostly use short **Tatoeba** sentences, which may overstate quality on realistic data. Some pairs also have WMT scores. The README also links multilingual models (OPUS-100).
    → **minor**
    → Fix: mention Tatoeba and its caveat, and note that multilingual Opus-MT models exist.

17. **The Omnilingual MT follow-up is unverified.** The doc says "OMT-LLaMA is built on LLaMA 3 [S17a]".
    → S17a (https://slator.com/?p=112857) returned **HTTP 403** on 2026-10-08, so I could not re-verify it. A search summary agrees on the LLaMA 3 base. The Meta publication page (https://ai.meta.com/research/publications/omnilingual-mt-machine-translation-for-1600-languages/, dated 2026-03-17) links **no weights or code**. The arXiv entry was last revised as v3 on 2026-05-07.
    → **minor**
    → Fix: add the Meta page as a source showing that no weights were linked as of 2026-10-08. Keep open question 2.

18. **Source labels are confusing.** [S10a] is the MADLAD paper, but [S10] and [S11] are Tower models.
    → **minor**
    → Fix: renumber, for example by giving MADLAD's paper its own S-number next to S7 and S8.

## Verified as correct

- Whisper: the README says "Whisper's code and model weights are released under the MIT License", "the `turbo` model is not trained for translation tasks", and "translate non-English speech into English". The paper describes only X→en data (125k h) and X→en CoVoST2/FLEURS evaluation. (S1, S2)
- NLLB-200: the card licence is CC-BY-NC-4.0. The quote "research model and is not released for production deployment" is exact. The card lists BLEU/spBLEU/chrF++. The fairseq nllb README says "NLLB code and fairseq(-py) is MIT-licensed" and "All models are licensed under CC-BY-NC 4.0". The abstract supports "44% BLEU relative to the previous state-of-the-art", MoE and Flores-200 (the baseline is unnamed in the abstract). (S3, S4, S9)
- SeamlessM4T v2: the weights are CC-BY-NC-4.0 and the code is MIT. The model table lists 2.3B. "nearly 100 languages" is quoted correctly, and S2TT and T2TT are both listed. The card has no BLEU numbers. (S5, S6)
- MADLAD-400:
  - Apache-2.0, T5 encoder-decoder, `<2xx>` target tag.
  - Sizes 3B, 7.2B and 10.7B. The 3B model has an 11.8 GB original file and a 1.65 GB `model-q4k.gguf`.
  - The card says "evaluate on only 204", "not been assessed for production usecases" and "not meant to work on domain-specific models out-of-the box".
  - The paper abstract says "competitive with models that are significantly larger". (S7, S8, S10a)
- TowerInstruct-7B-v0.2: CC-BY-NC-4.0, 10 languages, built on Llama 2. Tower+ 9B: the text says CC-BY-NC-4.0 and the tag says cc-by-nc-sa-4.0. The quote "one of the best multilingual LLMs under 10B parameters" is exact and backed only by a chart. (S10, S11)
- Aya Expanse 8B: CC-BY-NC plus the Cohere AUP, 23 languages, and a 32B variant exists. (S12)
- Opus-MT: the code is MIT and the models are CC-BY 4.0. (S13)
- TranslateGemma:
  - Gemma licence. The card lists 5B for the 4B model.
  - 55 languages and a "Total input context of 2K tokens".
  - WMT24++ MetricX 5.32 / 3.60 / 3.09 and COMET 81.6 / 83.5 / 84.4 are exact.
  - The tech report is dated 2026-01-13 and the InfoQ article 2026-01-28. (S14)
- The Gemma Terms are dated 2026-04-01. (S14a)
- Gemma 4 is Apache-2.0 and "the first in the Gemmaverse … OSI-approved Apache 2.0 license". The post is dated 2026-04-02 even though the URL path says 2026/03. (S16)
- Qwen3-8B: Apache-2.0, 8.2B parameters, "100+ languages and dialects" with translation listed as a strength, and no translation numbers. (S15)
- Omnilingual MT: 1B–8B models, 1,600+ languages, "match or exceed … 70B LLM baseline", no licence in the abstract, submitted 2026-03-17. Omnilingual ASR is reported as Apache-2.0. (S17, S17a second link)
- Haiku prices: Haiku 5.5 is $0.10 / $0.50 for prompts up to 100k and Haiku 4.5 is $1 / $5. Batch is 50% off (Haiku 5.5 batch $0.05 / $0.25; Haiku 4.5 batch $0.50 / $2.50). The ratio "1 token ≈ … 0.75 words in English" is on the page. The 30% tokenizer note is correct. (S18)
- Haiku 4.5 arithmetic: $0.22–0.40 per video-hour is correct under the doc's assumptions. The Batch-halving claim is correct.
- SBAAM (arXiv 2405.10741): Gaido is first author and the paper is at ACL 2024. The abstract names three subtasks: translation, segmentation into subtitles, and timestamp prediction. (S20)
- Papi et al. 2209.10608: the authors are Papi, Karakanta, Negri and Turchi. The paper evaluates with Sigma and CPL, with a 42 CPL limit. (S21)
