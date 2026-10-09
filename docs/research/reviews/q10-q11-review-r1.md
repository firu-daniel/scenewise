# Review r1: q10-pyav-ffmpeg-licence.md and q11-asr-without-pyav.md

Reviewer: fresh review agent (did not write either file). Date: 2026-10-08. Neither reviewed file was edited.

What was re-opened:
- **Wheel.** `av-19.0.1-cp312-abi3-manylinux_2_28_x86_64.whl` was downloaded to the scratchpad (`review-q10/`). It was unzipped and inspected with `unzip -l`, `strings` and `objdump -p`. It was not installed.
- **PyAV and pyav-ffmpeg on GitHub (`gh api`).**
  - pyav-ffmpeg: `patches/ffmpeg.patch`, `scripts/build-ffmpeg.py`, README, release `9.0.2-1`, and the commit history of the patch file.
  - PyAV: tag `v19.0.1` and `scripts/ffmpeg-latest.json`.
  - PR #967 comment 1789524823, and issue #2270 with all its comments.
- **FFmpeg licence sources.** FFmpeg's `configure` licence logic at n8.0. The FFmpeg legal page.
- **Ubuntu ffmpeg.** `debian/rules` and `debian/copyright` from the `ubuntu/noble` branch on Launchpad. The Launchpad `getPublishedSources` API.
- **Licence texts and FAQs.** The GPL FAQ, GPLv2, GPLv3, and the ASF GPL-compatibility page.
- **Package metadata.** PyPI JSON for faster-whisper, sherpa-onnx, onnx-asr, onnxruntime, numpy and speechbrain.
- **Upstream source.**
  - faster-whisper `v1.2.1`: `__init__.py`, `audio.py` and `transcribe.py`.
  - sherpa-onnx `v1.13.8`: `offline-whisper-model.cc`, `spoken-language-identification-whisper-impl.h`, `.h`, and the pybind file.
  - The onnx-asr 0.12.0 wheel.
- **Hugging Face API** for `onnx-community/whisper-tiny`, `onnx-community/whisper-base`, `openai/whisper-tiny` and `csukuangfj/sherpa-onnx-whisper-tiny`. Silero `hubconf.py` at v6.2.
- **Local re-runs (`review-q11/`).**
  - A uv 0.12.23 relock of a scratch copy of `pyproject.toml` and `uv.lock`, with faster-whisper moved to `asr-whisper`.
  - An independent re-implementation of the ORT Whisper-tiny LID adapter. It was run next to faster-whisper 1.2.1 (`--no-deps` + ctranslate2 4.8.2, with an `av` stub) on macOS `say` clips, digital silence, and Gaussian noise (σ 0.05, seeds 0–2).

Severity counts: wrong 4 · unsupported 2 · missing 3 · design concern 3 · minor 8 (20 findings in total).

## A. What checked out

### q10

- **Wheel identity.** The sha256 `1bea5b61…4170` matches `uv.lock`. The lock has 18 wheels plus the sdist, uploaded 2026-10-03.
- **`av.libs/` contents** are exactly as listed, including `libx264-d6533a8d.so.165` and `libx265-eebb7db1.so.217`. `libavcodec` `NEEDED`s both.
- **Licence files and SBOM.**
  - `licenses/` has only `LICENSE.txt` (BSD-3-Clause) and `AUTHORS.rst`.
  - `License-Expression: BSD-3-Clause`.
  - The SBOM lists only av, libXau, libdrm and libxcb×4.
- **Embedded configure line** is verbatim as quoted, with no `--enable-gpl` and no `--enable-nonfree`.
- **Licence strings and banners.**
  - The embedded strings read `LGPL version 3 or later`.
  - The x265 banner is present.
  - The LAME strings are inside libavcodec.
- **pyav-ffmpeg build.**
  - `patches/ffmpeg.patch` removes `libx264`/`libx265` from `EXTERNAL_LIBRARY_GPL_LIST` and adds them to `EXTERNAL_LIBRARY_VERSION3_LIST`.
  - `build-ffmpeg.py` passes `--enable-version3`, adds x265 always and x264 except on 32-bit ARM, and never passes `--enable-gpl`.
  - Release `9.0.2-1` was published 2026-09-19 with 14 binary tarballs and no source tarball.
  - The README's versions are as quoted, with gnutls, nettle and unistring on Linux only.
- **PyAV tag.** `v19.0.1` is commit `52e6691c82`, and `ffmpeg-latest.json` points at `9.0.2-1`.
- **Maintainer quotes.**
  - The PR #967 quote is verbatim (WyattBlue, 2023-11-01).
  - The issue #2270 quotes are verbatim. The issue was opened and closed on 2026-06-01.
- **FFmpeg legal page.** "If those parts get used the GPL applies to all of FFmpeg" is verbatim. Checklist item 18 ("notably libx264") is verbatim.
- **Ubuntu ffmpeg.**
  - `debian/rules`: the "compatible with effective licensing of GPLv2+" comment is there, as are `--enable-gpl`, x265 and gnutls in the shared CONFIG, x264 in the non-restricted-arch branch, and `--enable-version3` in the extra flavour. No nonfree flag appears.
  - `debian/copyright`: the quotes are verbatim.
  - The version `7:6.1.1-3ubuntu5` (Release pocket, 2024-04-06) is correct.
- **FSF, ASF and GPL text quotes** are all verbatim: #MereAggregation "almost surely" and "pipes, sockets…", #UnreleasedMods, ASF "can therefore be included in GPLv3 projects" and "never considered … compatible with GPL version 2", GPLv2 §3(c) noncommercial, and GPLv3 §0 "Mere interaction…".

### q11

- **faster-whisper 1.2.1.**
  - It is the latest release, and `requires_dist` has `av>=11` with no marker.
  - `__init__.py` line 1 is `from faster_whisper.audio import decode_audio`, and `audio.py` line 15 is `import av`.
  - `detect_language` defaults to `language_detection_threshold=0.5` and 1 segment, and runs `pad_or_trim` on the features.
- **sherpa-onnx 1.13.8 SLID.**
  - The pybind docstring reads "A string representing the identified language code", and `Compute(OfflineStream*) -> std::string` takes one stream.
  - `DetectLanguage` keeps the arg-max of the raw logits over the language ids, with no softmax.
  - An unknown id returns `""`.
  - The claim "no score, no batch" is **confirmed**.
- **onnx-asr 0.12.0.** `recognize_batch` runs `_decoding(encoding, detect_lang_input, 3)[:, 1]` when no `language` is given. The result is not returned or scored, so "no LID API" is **confirmed**. `WhisperPreprocessorNumpy` pads the audio to 30 s before the mel.
- **`onnx-community/whisper-tiny`.**
  - The sha is `ff4177021cc41f7db950912b73ea4fdf7d01d8e7` (2025-06-19). There is no licence field, and the card says only `base_model: openai/whisper-tiny`.
  - The int8 files are 10,124,977 and 30,461,071 bytes. Their sha256 values match q11 §2.3, and the downloaded files hash identically.
  - `generation_config.json` has 99 `lang_to_id` entries (ids 50259–50357), `decoder_start_token_id` 50258, and `is_multilingual: true`.
- **Other model repos.**
  - `openai/whisper-tiny` is sha `169d4a43`, tagged `apache-2.0`.
  - `onnx-community/whisper-base` is sha `1846881b`.
  - `csukuangfj/sherpa-onnx-whisper-tiny` is sha `65176e2d`, with int8 files of 12.9 MB and 89.9 MB.
- **Other packages.** speechbrain 1.1.1 needs `torch>=2.1.0` and `torchaudio>=2.1.0`. Silero v6.2's `hubconf.py` defines only `silero_vad`.
- **uv resolution (re-run).**
  - `uv lock` resolves 130 packages.
  - The `service + asr` export is the identical 29-package list, with no `av`.
  - The `-cpu` image set has no `av`, `faster-whisper` or `ctranslate2`. The reviewer also checked the `-cuda` set (`torch-cu130`), which q11 did not, and it has none of them either.
  - `uv pip compile --extra asr --universal -p 3.12` gives 23 packages and no `av`.
  - `uv tree --invert --package av` gives `av ← faster-whisper ← scenewise (extra: asr-whisper)`.
- **Feature parity.** The reviewer independently re-implemented the log-mel described in step 1 of §2.3. It matched `pad_or_trim(FeatureExtractor()(a)[:, :3000])` **exactly (max |Δ| 0.0)** on speech, silence and noise.
- **Language-token handling is sound.** The adapter gathers the 99 `lang_to_id` logits after a single decoder step from SOT 50258, then takes the softmax. This reproduced CT2 on speech within 0.005 (en 0.9978 vs 0.9967).
- **CT2 reproduction.** CT2 silence is `cy 0.2823`, the same as q11 and q2. CT2 noise at seed 0 is `nn 0.5523`, the same as q11.
- **Timing.** The "about 2× faster" claim is reproduced: CT2 takes 0.29–0.30 s per window and ORT 0.12–0.16 s.
- **Adapter size.** The reviewer's whole script (mel, model, softmax and harness) is 69 non-blank lines, so "about 70 lines of adapter" is credible.

## B. Findings

### Wrong

1. **Claim (q10 §1 recommendation, §2.8, §3 item 1):** "treat the bundled FFmpeg stack as GPL (GPLv2-or-later, which allows GPLv3)". §1(b) and §3 item 2 base the obligations on GPLv2 §3(a)/(b)/(c).
   - **Source:**
     - The wheel's own configure line contains `--enable-version3`, verified in the wheel.
     - FFmpeg `configure` (n8.0, lines 4596–4605): `enabled version3 && { enabled gpl && enable gplv3 || enable lgplv3; }`, and then `license="GPL version 3 or later"` for gpl+version3.
     - The patch moves x264/x265 into `EXTERNAL_LIBRARY_VERSION3_LIST`, and that list is exactly what forces `--enable-version3`.
     - The libav* code is therefore taken under LGPLv3+. LGPLv3 cannot be combined under GPLv2-only. The only licence the FFmpeg+x264/x265 combination can be distributed under is **GPL-3.0-or-later**.
     - An unpatched build with the same flags would print "GPL version 3 or later".
     - This also makes the maintainer's "LGPLv2.1 or later … OR GPLv2 or later" description inconsistent with the build he ships. q10 does not point that out.
   - **Severity:** wrong.
   - **Correction:**
     - State that the effective licence of the bundled stack is GPL-3.0-or-later.
     - In §3 item 1, list FFmpeg-in-wheel as GPL-3.0-or-later.
     - Base the source obligation on GPLv3 §6(a)–(d). §6(b) is the written offer for ≥3 years. §6(c) covers passing on the offer, "occasionally and noncommercially". §6(d) is equivalent access from a network server. GPLv2 §3 should be secondary at most.
     - The Apache-2.0 compatibility conclusion in §1(a) is unaffected, because Apache-2.0 is GPLv3-compatible.

2. **Claim (q10 §2.3):** "`patches/ffmpeg.patch` … removes `libx264` and `libx265` from `EXTERNAL_LIBRARY_GPL_LIST` and adds them to `EXTERNAL_LIBRARY_VERSION3_LIST`. The commit that did this, `dc9ee64dff` (2025-06-27)…"
   - **Source:** `gh api …/commits/dc9ee64dff` (the patch diff) and the commit history of `patches/ffmpeg.patch`.
     - `dc9ee64dff` removed them from the GPL list but added them to the general **`EXTERNAL_LIBRARY_LIST`**, which made them LGPL-compatible without version3.
     - The move into `EXTERNAL_LIBRARY_VERSION3_LIST` arrived in **`9e70d98192` (2025-08-23, "ffmpeg 8.0")**.
     - `598dea363c` refreshed it for FFmpeg 9.0, as q10 says.
   - **Severity:** wrong (the attribution only; the current patch content is described correctly).
   - **Correction:** "Introduced in `dc9ee64dff` (2025-06-27, `GPLv3 OR "LGPLv3 + Exceptions"`) as a move to the general external-library list. Moved into the version3 list in `9e70d98192` (2025-08-23). Refreshed for 9.0 in `598dea363c`."

3. **Claim (q11 §3 table, ORT "faster-whisper padding" column, and "What this shows"):** non-speech ORT scores are "silence en 0.302 (nn 0.177, cy 0.119)" and "noise nn 0.385". The text adds that noise scored above 0.5 only "with faster-whisper itself … and with the audio-padded ORT variant". The recommended adapter variant is thereby implied to stay under 0.5.
   - **Source:** the reviewer's independent re-run (`review-q11/scripts/lid_check.py`, `lidlib.py`). Its features were identical to faster-whisper's (Δ 0.0), and it used the same onnx-community int8 files with the same sha256, with onnxruntime 1.30.0 and one thread.

     | Input | ORT, single window | ORT, batch of 4 | ORT, paired with one loud-noise window | CT2 |
     |---|---|---|---|---|
     | silence | en 0.291 (nn 0.192, cy 0.124) | en 0.282 | en 0.303 | — |
     | noise, seed 0 | nn 0.478 | nn 0.375 | nn 0.500 | nn 0.552 |
     | noise, seed 1 | nn 0.509 | — | — | 0.509 |
     | noise, seed 2 | nn 0.507 | — | — | 0.506 |

   - **Severity:** wrong. q11's ORT non-speech numbers cannot be reproduced as single-window results. They are consistent with a batched run (see finding 10). With the recommended padding, the ORT adapter **also** scores ≥ 0.5 on white noise for 2 of 3 seeds.
   - **Correction:**
     - Replace the ORT non-speech cells with single-window values, and state the batch composition used.
     - Say that both backends exceed 0.5 on white noise.
     - q11's own conclusion, that VAD-first protects the gate and the threshold does not, is strengthened. The sentence "Low scores on non-speech are not stable across builds" should become "not stable across builds **or across batch composition**".

4. **Claim (q11 §1, last bullet):** "Then the only GPL code left in an image is the apt `ffmpeg` CLI, run as a subprocess." q10's §5 effect note says the same: "Its §3 obligations shrink to the apt ffmpeg CLI for default images."
   - **Source:**
     - `debian/rules` (ubuntu/noble): `--enable-gpl` with `--enable-libx264`/`--enable-libx265` sits in the shared CONFIG. The apt `libavcodec60`/`libavfilter9` and the `libx264-164`/`libx265-199` packages that `ffmpeg` depends on are therefore GPL shared libraries in the image, not just the CLI.
     - Any Ubuntu 24.04 or CUDA-on-Ubuntu base image ships GPL packages anyway: bash (GPL-3+), coreutils, grep, tar, dpkg, and others.
   - **Severity:** wrong (overstated).
   - **Correction:**
     - "With `asr-whisper` absent, no GPL code is loaded into the scenewise process."
     - "The image still aggregates GPL packages: the base OS, plus apt ffmpeg and its libav*, x264 and x265 libraries. q10 §3 items 1, 2 (Ubuntu source packages) and 4 still apply to published images."
     - q10's U17 decision (Ubuntu vs LGPL-only ffmpeg in published images) does not remove the base-OS part.

### Unsupported

5. **Claim (q11 §2.3, §3, [L1]):** "Prototype: 109 lines …; its features match … to 6e-6; its speech results match … within 0.005"; [L1] "scratch scripts `ort_whisper_lid.py`, `fw_compare.py`".
   - **Source:** the repository contains neither script. The numbers cannot be reproduced from the document alone. The reviewer re-derived the adapter independently: the feature and speech claims hold, but the non-speech claims do not (finding 3).
   - **Severity:** unsupported (as a citation), because the evidence is not preserved.
   - **Correction:**
     - Commit the prototype, or at minimum the parity check, as a test under `tests/`. The natural place is T3/T4, gated on the mirrored weights.
     - Alternatively, inline the ~70-line adapter in an appendix.
     - Record the noise RNG seed (q11's CT2 figure matches seed 0 of `np.random.default_rng`).

6. **Claim (q10 §1(c), §3 item 6):** "the FSF FAQ says internal use, including running a site, triggers no source release"; "Nothing to do for Expause's internal use".
   - **Source:** GPL FAQ #UnreleasedMods. It covers a company "running a modified version of a GPLed program on a web site", and its answer is the FSF's interpretation, not licence text. The FAQ also has "Does moving a copy to a majority-owned, and controlled, subsidiary constitute distribution?", which q10 does not consult. GPLv3 §0 "convey" is the operative text once finding 1 is applied.
   - **Severity:** unsupported as fact. It is legal opinion that is reasonable but not sourced as such.
   - **Correction:**
     - Mark §1(c) and §3 item 6 **[lawyer]**, as open question 5 already half does.
     - Cite GPLv3 §0 ("convey"; "Mere interaction … is not conveying") as the primary text and the FAQ as FSF interpretation.
     - Add the subsidiary FAQ entry as relevant if Expause's GCP project belongs to a different legal entity than the one building the images.

### Missing

7. **q10 §2.4–§2.5 omit FFmpeg's own statement against commercial terms.**
   - **Source:** ffmpeg.org/legal.html: "Note that FFmpeg is not available under any other licensing terms, especially not proprietary/commercial ones, not even in exchange for payment."
   - **Severity:** missing.
   - **Correction:** quote it in §2.5. It directly undercuts the maintainer's "LGPLv2.1 or later + Commercial exceptions" reading. Even a paid x264/x265 licence only covers x264/x265; FFmpeg's code stays LGPL/GPL. It also strengthens open question 2's answer ("no").

8. **The q10 status no longer matches U16/U17 or q11.**
   - **Source:** `docs/research/user-decisions.md`.
     - U16 (2026-10-08): faster-whisper moves to an opt-in `asr-whisper` extra and is "left out of published images".
     - U17 (2026-10-08): Ubuntu ffmpeg is used for dev/CI, and published images are decided later.
   - **What q10 still says:**
     - "Keep the stock wheel" in §1, as a recommendation for images.
     - Option C "Not possible without replacing Whisper LID (q8c §3)". q11 does exactly that.
   - **Severity:** missing (status note).
   - **Correction:** add a status line at the top of q10: "Superseded in part by q11 and U16: PyAV is present only in `asr-whisper` builds, which published images exclude. §3 applies in full to such builds; for default images see U17 and finding 4." Option C becomes "done (q11)".

9. **The pyproject lines that q11 §4 must change are not all listed.**
   - **Source:** `pyproject.toml`.
     - Line 249, deptry `DEP002` ignores: `"faster-whisper", … # item 1 (asr)`.
     - The import-linter forbidden list for `scenewise.service` names `ctranslate2` and `faster_whisper`.
     - The `asr` comment `# CPU only (q8c §3, D20, U4)`.
   - **Severity:** missing (minor).
   - **Correction:** in §4, list the DEP002 entry (it moves with `asr-whisper`), and keep the import-linter entries. Also note that the relock changes the `asr-whisper` optional-dependency group and `provides-extras` as well as the marker (see finding 17).

### Design concern

10. **Batch dimension and dynamic int8 quantization (q11 §1, §2.3 "with a real batch dimension"; "batch of 5: 0.73 s").**
    - **Source:**
      - The int8 encoder contains 18 `DynamicQuantizeLinear` nodes and 24 `MatMulInteger` nodes (counted in the ONNX file). ORT's `DynamicQuantizeLinear` computes **one scale/zero-point per tensor, across the whole batch**.
      - Measured (finding 3): the same 10 s noise window gives nn 0.478 alone, 0.375 in a batch of 4, and 0.500 next to a loud window. A speech window moves by 0.001–0.008.
      - A window's probability therefore depends on which other windows (from the same or another video) share its batch. Scores near the p ≥ 0.5 threshold can flip, and results are not reproducible per window.
    - **Severity:** design concern.
    - **Correction:** do one of the following, and add a test that a window's p is identical alone and in a batch:
      - run the LID encoder with batch = 1 per window (≈0.12–0.16 s each, still faster than CT2), and drop the "real batch dimension" claim; or
      - use the fp32 `encoder_model.onnx` (or fp16), keeping int8 for the decoder only, and re-measure; or
      - quantize statically (per-tensor static scales).

11. **The LID threshold rests on the backend that ships, and noise passes it (q11 §3, open question 3; q2 §4.4).**
    - **Source:** finding 3. White noise reaches p ≥ 0.5 on both CT2 and ORT for most seeds, so a VAD false positive on a noise or music bed passes the LID gate as "nn" or similar.
    - **Severity:** design concern (it extends q11's own finding).
    - **Correction:**
      - In addition to tuning the threshold, consider a minimum-coverage rule (≥ about 2 s of VAD speech, as q2 already states) combined with an **English-specific** check. The gate needs "is it English", not "is it any language". p(en) on noise was 0.13–0.17.
      - T3 should report p(en) on noise and music beds, not only the arg-max p.

12. **"Fallback opt-in" vs U4 (q11 §2.4, §5 last bullet, open question 1).**
    - **Source:**
      - U4: "faster-whisper + large-v3-turbo (MIT) stays the fallback back end".
      - U16 (2026-10-08) already confirms opt-in and exclusion from published images.
    - **Severity:** design concern (mild). There is no conflict with the letter of U4: the back end, its adapter and its config remain. But in every published image the fallback is unavailable, and `asr.backend = "faster-whisper"` fails at bootstrap. So U4's "fallback" holds only for self-built images. q11 still lists this as an open user decision, but U16 has already settled it.
    - **Correction:**
      - Cite U16 in q11 §5 and open question 1, and close that question.
      - State in ARCHITECTURE §12 and the README that the published images ship no fallback recogniser, and that adopters who need it build with `SCENEWISE_EXTRAS=asr-whisper` and take on q10 §3.
      - If an in-image fallback is ever required, q11's open question 2 (sherpa-onnx Whisper turbo with attention outputs) is the route.

### Minor

13. **q10 §2.5 checklist numbering.**
    - **Source:** legal.html has 18 items. q10 numbers them 1–10 with gaps silently merged. Its "7. host the source on the same server" is page item 8 ("Use tarball or a zip file" is item 7). Its "9. go through the checklist again" is page item 17.
    - **Correction:** use the page's numbers (1–6, 8, 9–11 attribution, 17, 18). That also keeps open question 3's "item 8" consistent.

14. **q10 §2.4, issue #2270 chronology.**
    - **Source:**
      - The redistributor's first question is dated **2026-09-12**.
      - The maintainer's pointers to `x265.org/#licensing` and to pyav-ffmpeg tag **`8.1.2-1`** (the tag for the asker's PyAV 18.1.0 wheel, not `9.0.2-1`) came at 2026-09-13 03:51.
      - The "implied … by your actions" answer came separately at 14:34, after a second question.
      - Also omitted: the 2026-06-01 maintainer comment "The `build-deps` script does enable GPL but that's what we test with, not what we ship with."
    - **Correction:** fix the dates and tag, and split the two replies.

15. **q10 §1, first bullet: "Every locked wheel except armv7l bundles libx264 and libx265".**
    - **Source:** the pyav-ffmpeg README: x265 4.3 is enabled on all platforms, and only x264 is skipped on armv7l.
    - **Correction:** "every locked wheel bundles GPL x265; all but armv7l also bundle x264". Only x86_64 was inspected (q10 open question 7).

16. **q10 open question 6 can be closed.**
    - **Source:** Launchpad `getPublishedSources` (ffmpeg, noble, `status=Published`) returns only `7:6.1.1-3ubuntu5` in the Release pocket as of 2026-10-08. There is no noble-updates or noble-security version.
    - **Correction:** close the question, keeping the advice to pin.

17. **q11 §3: "the only lock change is faster-whisper's marker".**
    - **Source:** reviewer's relock diff. It also adds an `asr-whisper` group to scenewise's `[package.optional-dependencies]` entry and `"asr-whisper"` to `provides-extras`.
    - **Correction:** reword to "no resolved version changes; only scenewise's own extras metadata changes".

18. **q10 §1(b) lists "no claim that the image as a whole is Apache-2.0 only" as a licence obligation.**
    - **Source:** no GPL, LGPL or Apache clause requires this. It is a misrepresentation-avoidance recommendation, and §3 item 3 is fine as a recommendation.
    - **Correction:** move it out of the obligations list or label it "recommended".

19. **q11 §1, §2.3: weights licence "MIT/Apache-2.0 weights".**
    - **Source:** the OpenAI README says MIT. The `openai/whisper-tiny` HF card is tagged apache-2.0. The onnx-community repo has no licence. These conflict.
    - **Correction:** name MIT (from OpenAI's repository) as the governing licence of the weights. Note the HF tag discrepancy, and credit the onnx-community conversion in NOTICE (as q11 §5 already proposes for q2 §5.3).

20. **q11 §2.3 adapter guard.**
    - **Source:** the correctness of the language-token handling depends on `generation_config.json` being from a multilingual export (`is_multilingual: true`, 99 ids). A future switch to `base` or `large-v3` (100 languages including `yue`) keeps working because the ids are read from the file. A `.en` export would silently return garbage.
    - **Correction:** have the adapter assert `is_multilingual` and `decoder_start_token_id == <|startoftranscript|>` at load. Pin the `generation_config.json` sha256 along with the two ONNX files.
