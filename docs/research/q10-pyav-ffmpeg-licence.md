# q10 — Licence of the FFmpeg in PyAV's wheels, and of apt ffmpeg in the images

Research date: **2026-10-08**. Every source was read that day unless marked otherwise. This is research, not legal
advice. Points marked **[lawyer]** need a lawyer before a release that publishes images.

**Status (2026-10-08, after review round 1).** Superseded in part by q11 and by user decisions U16 and U17
(`user-decisions.md`):

- **U16.** faster-whisper moves to an opt-in `asr-whisper` extra and is left out of published images. The default
  `asr` extra has no PyAV; the language-ID gate uses an in-house onnxruntime Whisper-tiny adapter (q11). The PyAV
  analysis below (§2.1–§2.6, §2.8) and §3 in full therefore apply only to `asr-whisper` builds, which scenewise does
  not publish. Anyone who builds and distributes such an image takes them on.
- **U17.** Ubuntu's apt ffmpeg is used for development and CI. Whether published images use the Ubuntu build or an
  LGPL-only ffmpeg build is decided when the first published Dockerfile is written. §2.7, §3 and §5 give the inputs.

The `pyproject.toml` change that implements U16 is listed in q11 §4 and has not landed yet; the context paragraph
below describes the lock as it stands today.

Context: today the `asr` extra pins faster-whisper 1.2.1, which hard-requires `av>=11`. faster-whisper imports `av`
when the module loads, so PyAV and the FFmpeg libraries bundled with it are loaded into the service process. They are
never given input (q8c §1, §3). Separately, the `MediaTool` adapter runs the system `ffmpeg`/`ffprobe` as
subprocesses. In development and CI that is Ubuntu 24.04's apt package (U17).

## 1. Summary and recommendation

- **PyAV's own code is BSD-3-Clause.** That is the wheel's only licence file. **The wheel is not effectively BSD.**
  Every locked wheel bundles **libx265 (GPL-2.0-or-later)**, and every wheel except armv7l also bundles **libx264
  (GPL-2.0-or-later)**. libavcodec links them dynamically from `av.libs/`. Only the x86_64 wheel was inspected (§4
  question 7).
- **The bundled FFmpeg stack is effectively GPL-3.0-or-later.** The build calls itself "LGPL version 3 or later", but
  that label comes from a patched `configure`:
  - PyAV's build repo moves libx264/libx265 out of FFmpeg's GPL list and into its "version3" list
    (`patches/ffmpeg.patch`). Without the patch, enabling them would require `--enable-gpl`.
  - The build passes `--enable-version3`, so FFmpeg's own code is taken under **LGPLv3+**. In unpatched FFmpeg,
    `--enable-gpl` plus `--enable-version3` gives "GPL version 3 or later" (`configure`, n8.0, lines 4596–4603).
  - LGPLv3+ code combined with GPLv2+ x264/x265 can only be distributed under **GPLv3 or later**. LGPLv3 cannot be
    combined under GPLv2-only.
  - FFmpeg's legal page says that when GPL parts are used, "the GPL applies to all of FFmpeg", and that FFmpeg "is not
    available under any other licensing terms, especially not proprietary/commercial ones".
  - In 2023, PyAV's maintainer said the PyPI binaries are "GPLv3". In 2026 he described them as "'LGPLv2.1 or later +
    Commercial exceptions' OR 'GPLv2 or later'". That description does not match the build he ships: the libav* code
    is LGPLv3+, not LGPLv2.1+, and neither "GPLv2" nor a commercial exception can cover FFmpeg's own code. x264 and x265
    publish no royalty-free exception; each offers a **paid** commercial licence on request, which covers only x264 or
    x265.
- **(a) Compatibility with scenewise's Apache-2.0 code.** Apache-2.0 code can go into a GPLv3 combination (ASF), and
  GPLv3 is the only licence the bundled stack can be distributed under anyway. So the combination is licensable.
  scenewise's source repo contains no FFmpeg, so its Apache-2.0 licence is unaffected. The issue arises only when
  scenewise and the wheel are **distributed together and loaded into one process**, which after U16 means
  `asr-whisper` builds only. In the FSF's view, a shared address space "almost surely" makes one program. Whether a
  Python `import` of a dependency creates a combined work is a contested legal question **[lawyer]**.
- **(b) Shipping the wheel in a distributed image (`asr-whisper` builds only, after U16).** Permitted, with the
  obligations of GPLv3 (and LGPL for the LGPL libraries):
  - licence texts and notices (GPLv3 §4–§5);
  - the **Corresponding Source** of the GPL/LGPL parts, conveyed under GPLv3 §6. For an image pulled from a registry
    the natural route is **§6(d)**: offer equivalent access to the source "through the same place", or on another
    server "provided you maintain clear directions next to the object code", for as long as the image is offered.
    §6(b)'s 3-year written offer is written for object code "in, or embodied in, a physical product". §6(c), passing on
    an upstream offer, is allowed "only occasionally and noncommercially". GPLv2 §3 matters only for any component that
    is GPLv2-only; none was found in the PyAV stack.

  The wheel itself carries no FFmpeg, x264 or x265 licence text or source, so the distributor has to supply them.
  **Recommended** (not a licence term): do not describe such an image as Apache-2.0 only.
- **Ubuntu 24.04's apt ffmpeg is GPL-2.0-or-later.** It is built with `--enable-gpl`, and Debian's copyright file says
  "the resulting binaries are licensed under GPL v2+". It has no nonfree parts. Its `libavcodec60`, `libavfilter9` and
  other libav* packages, and the `libx264-164`/`libx265-199` packages they depend on, are GPL shared libraries in the
  image as well, not just the CLI. scenewise only runs the CLI as a subprocess, which in the FSF's view normally makes
  it a separate program, so shipping it in the image is "mere aggregation". The notice and source obligations still
  apply to these packages when images are distributed.
- **What GPL remains in a default published image (after U16).** With `asr-whisper` absent, **no GPL code is loaded
  into the scenewise process**. The image still **aggregates** GPL packages: the Ubuntu or CUDA-on-Ubuntu base OS
  (bash, coreutils, grep, tar, dpkg and others) and, under the Ubuntu option of U17, apt ffmpeg with its libav*, x264
  and x265 libraries. §3 items 1, 2 (Ubuntu source packages), 3 and 4 still apply to published images. An LGPL-only
  ffmpeg (U17's other option) removes the GPL ffmpeg packages but not the base-OS part.
- **(c) Commercial use by Expause: no licence here forbids it.** GPL, LGPL, BSD and Apache all allow commercial use.
  None of this is AGPL. Whether Expause's own deployment triggers source obligations is **[lawyer]**:
  - The operative text is GPLv3 §0: to "convey" is propagation "that enables other parties to make or receive copies",
    and "Mere interaction with a user through a computer network, with no transfer of a copy, is not conveying".
    GPLv3 §2 also allows conveying works to others "for the sole purpose of having them … provide you with facilities
    for running those works", if they run them "exclusively on your behalf".
  - The FSF's interpretation (GPL FAQ #UnreleasedMods): a company running a GPL program on its web site need not
    release the source. FAQ #DistributeSubsidiary: whether moving a copy to a majority-owned subsidiary is distribution
    "is a matter to be decided in each case under the copyright law of the appropriate jurisdiction". This matters if
    the Google Cloud project belongs to a different legal entity from the one that builds the images.
  - Reading these together, building and running images in Expause's own project, without handing copies to others,
    is probably not conveying. If Expause ships the image or the binaries to third parties (on-premises customers,
    partners), the obligations above fall on Expause.
- **Recommendation.**
  - **Default and published images:** use the default `asr` extra (no PyAV), per U16 and q11. PyAV and its GPL stack
    are not in the scenewise process.
  - **`asr-whisper` builds:** keep the stock wheel. Document in the README and the extra's comment that the extra
    brings GPL-3.0-or-later code (FFmpeg with x264/x265) into the process, and that whoever distributes such an image
    must meet §3 in full. scenewise does not publish such images.
  - **ffmpeg in published images (U17, open):** see §5 for the comparison. The Ubuntu build is the cheaper choice and
    leaves the image's GPL status unchanged, because the base OS is GPL-aggregated anyway. An LGPL-only build is worth
    its cost only if a consumer needs an image with no GPL ffmpeg in it.
  - **Every published image,** whichever ffmpeg it has: ship a third-party licence file, keep `/usr/share/doc`, attach
    a source bundle for the GPL/LGPL packages per image digest, and do not label the image Apache-2.0 only (§3).

## 2. Findings

### 2.1 What is locked

- `uv.lock`: `av` **19.0.1**, uploaded 2026-10-03. Its sdist plus 18 wheels cover two ABI families: `cp312-abi3` and
  free-threaded `cp314-cp314t`. Platforms: macOS 11 x86_64, macOS 14 arm64, manylinux_2_28 aarch64 and x86_64,
  manylinux_2_31 armv7l, musllinux_1_2 aarch64 and x86_64, and Windows amd64 and arm64. The Linux images use the
  manylinux_2_28 wheels.
- PyAV v19.0.1 (tag commit `52e6691c82`) has `scripts/ffmpeg-latest.json`, which points at **pyav-ffmpeg release
  `9.0.2-1`** (published 2026-09-19). That release is FFmpeg **9.0.2**.
- After U16 is implemented (q11 §4), `av` stays in the lock but only through `scenewise[asr-whisper]`.

### 2.2 Inspection of `av-19.0.1-cp312-abi3-manylinux_2_28_x86_64.whl`

The wheel's sha256 is `1bea5b61…4170`, which matches `uv.lock`. It was downloaded to the scratchpad and inspected with
`zipfile`, `strings` and `objdump`. It was not installed or imported.

- **Licence files.** `dist-info/licenses/` contains only `LICENSE.txt` (BSD-3-Clause text, "Copyright retained by
  original committers") and `AUTHORS.*`. `METADATA` says `License-Expression: BSD-3-Clause`. The wheel has **no
  FFmpeg, x264, x265, LAME, gnutls or other third-party licence text**, and no source offer.
- **SBOM.** `sboms/auditwheel.cdx.json` lists only av, libXau, libdrm and libxcb, taken from AlmaLinux 8 RPMs. It
  does not list the FFmpeg stack.
- **Bundled shared libraries in `av.libs/`:**
  - FFmpeg: libavcodec 63.1.102, libavformat, libavfilter, libavdevice, libavutil 61.1.102, libswresample and
    libswscale;
  - **libx264 (.so.165)** and **libx265 (.so.217)**;
  - libSvtAv1Enc 4.2.0, libdav1d, libvpx, libopus, libwebp, libwebpmux, libsharpyuv, libvmaf and libvpl;
  - libgnutls, libnettle, libhogweed, libgmp and libunistring;
  - libasound, libdrm, libxcb (four libraries) and libXau.

  LAME (`--enable-libmp3lame`) is compiled into libavcodec, because no separate `.so` exists and the libmp3lame
  strings are inside libavcodec. `objdump -p` shows that libavcodec `NEEDED`s `libx264-d6533a8d.so.165` and
  `libx265-eebb7db1.so.217`.
- **Embedded FFmpeg configure line** (identical in libavutil, libavcodec and libavformat):
  `--enable-version3 --enable-alsa --enable-gnutls --enable-libdav1d --enable-libmp3lame --enable-libopus
  --enable-libsvtav1 --enable-libvmaf --enable-libvpx --enable-libwebp --enable-libxcb --enable-zlib --enable-libx265
  --enable-libx264 --enable-nvenc --enable-nvdec --enable-amf --enable-libvpl …`. It has **no `--enable-gpl`** and no
  `--enable-nonfree`. It **does** have `--enable-version3`, which puts FFmpeg's own code under LGPLv3+ (§2.5).
- **Embedded licence strings:** `libavcodec license: LGPL version 3 or later`, and the same for libavutil and
  libavformat.
- **x264 and x265 banners** are present. x265's reads "Copyright 2013-2018 (c) Multicoreware, Inc".

I inspected only the x86_64 wheel. The pyav-ffmpeg README lists x264 "(except armv7l)" and x265 with no exception,
so x265 is in every wheel and x264 in all but armv7l.

### 2.3 How PyAV builds the bundled FFmpeg (PyAV-Org/pyav-ffmpeg)

- The README lists "FFmpeg 9.0.2 … for all platforms":
  - lamer 3.101.0 (a LAME fork), opus 1.6.1, dav1d 1.5.4, libsvtav1 4.2.0, vpx 1.17.0, png 1.6.58, webp 1.6.0 and
    libvmaf 3.2.1;
  - **x264 `b35605ace3ddf7c1a5d67a2eb553f034aef41d55` (except armv7l)** and **x265 4.3**;
  - on Linux only, gnutls 3.8.13, nettle 4.0 and unistring 1.4.2.
- `scripts/build-ffmpeg.py` passes `--enable-version3` and appends `--enable-libx265`, plus `--enable-libx264`
  except on 32-bit ARM. It never passes `--enable-gpl`.
- **`patches/ffmpeg.patch` edits FFmpeg's `configure`:** in its current form it removes `libx264` and `libx265` from
  `EXTERNAL_LIBRARY_GPL_LIST` and adds them to `EXTERNAL_LIBRARY_VERSION3_LIST`. History of the patch file
  (re-checked 2026-10-08 with `gh api`):
  - `dc9ee64dff` (2025-06-27, titled **`GPLv3 OR "LGPLv3 + Exceptions"`**) introduced the relabelling. It removed
    x264/x265 from the GPL list and added them to the general **`EXTERNAL_LIBRARY_LIST`**, which made them
    LGPL-compatible without even requiring version3.
  - `9e70d98192` (2025-08-23, "ffmpeg 8.0") moved them into **`EXTERNAL_LIBRARY_VERSION3_LIST`**.
  - `1e42248dfc` (2026-03-20, "Build FFmpeg 8.1") and `598dea363c` (2026-08-04, "FFmpeg 9.0") refreshed the patch.

  As a result, FFmpeg's built-in licence report says LGPLv3+ even though GPL libraries are linked.
- The repo also has a `build-deps` script. On issue #2270 the maintainer said it "does enable GPL but that's what we
  test with, not what we ship with".
- Release `9.0.2-1` publishes only binary tarballs, `ffmpeg-<platform>.tar.gz` for 14 platforms. No source tarball is
  attached. The sources are the upstream projects at the pinned versions, plus this repo's patches and scripts.

### 2.4 What the maintainers have said

- **PyAV PR #967, comment by WyattBlue (maintainer), 2023-11-01:** "Our binaries are GPLv3 in the PyPI release (with
  other compatible licenses for deps), but this git repo is BSD by itself".
- **PyAV issue #2270**, "The binary wheels released on PyPI are not actually licensed under the BSD-3-Clause license,
  but under the GPL". Opened 2026-06-01 and closed by the maintainer the same day. Comments:
  - 2026-06-01, maintainer: "The license is for the source code, not the binary wheels";
  - 2026-06-01, maintainer: "The current license PyAV binary wheels is not the "GPLv3", it is under "'LGPLv2.1 or
    later + Commercial exceptions' OR 'GPLv2 or later'"";
  - 2026-06-01, maintainer: "The `build-deps` script does enable GPL but that's what we test with, not what we ship
    with.";
  - 2026-09-12, a downstream redistributor of a Windows application asked for the terms and build materials of their
    exact wheel. On 2026-09-13 at 03:51 the maintainer replied with two links: x265.org's licensing section and the
    pyav-ffmpeg tag **`8.1.2-1`** (the tag for the asker's PyAV 18.1.0 wheel, not `9.0.2-1`);
  - 2026-09-13, after the redistributor said they could not find the commercial-exception terms, the maintainer
    replied at 14:34 that the exception is "implied — either by your actions (i.e. not sharing full source code, like
    the GPL requires) or you explicitly state the license you're choosing", and pointed to the x264/x265 repos and
    homepages.
- **What upstream says about x264 and x265:**
  - `x264.h` (GitHub mirror): GPL "version 2 … or (at your option) any later version". "This program is also
    available under a commercial proprietary license. For more information, contact us at licensing@x264.com".
    The videolan.org x264 page says the same ("also available under a commercial license", contact
    x264licensing@videolan.org).
  - `x265.h` and `COPYING` (Bitbucket `multicoreware/x265_git`): GPL v2 or later. "also available under a commercial
    proprietary license. … contact us at license @ x265.com".

  Neither publishes a royalty-free exception. A commercial licence is a separate contract with the copyright holder,
  and it covers only that holder's library. **Relying on an "implied" commercial exception is not supported by any
  source I found [lawyer].**
- **The maintainer's 2026 description does not match the build.** The shipped FFmpeg is configured with
  `--enable-version3`, so its own code is LGPLv3+, not "LGPLv2.1 or later". FFmpeg offers no commercial terms (§2.5),
  so a "commercial exception" could at most cover x264/x265, never the FFmpeg code linked with them. And the only
  licence under which LGPLv3+ FFmpeg and GPLv2+ x264/x265 can be combined is GPLv3+, not "GPLv2 or later".

### 2.5 FFmpeg's own position

From ffmpeg.org/legal.html:

- FFmpeg is LGPL 2.1+ with optional GPL v2+ parts, and "If those parts get used the GPL applies to all of FFmpeg".
- "Note that FFmpeg is not available under any other licensing terms, especially not proprietary/commercial ones, not
  even in exchange for payment." This rules out a commercial route for FFmpeg's own code. A paid x264/x265 licence
  would leave FFmpeg under LGPL/GPL.
- The LGPL compliance checklist has 18 items. Those relevant here, with the page's own numbers:
  1. compile without `--enable-gpl` and without `--enable-nonfree`;
  2. use dynamic linking;
  3. "Distribute the source code of FFmpeg, no matter if you modified it or not";
  4. the source must correspond exactly to the binaries;
  5. include the changes as a diff (`git diff > changes.diff`);
  6. explain how FFmpeg was compiled, for example the configure line;
  7. use a tarball or a zip file for the source;
  8. host the source on the same webserver as the binary;
  9–11. attribution ("This software uses code of FFmpeg …"), in the about box and in the EULA;
  17. go through the items again for each LGPL external library compiled in, "for example LAME";
  18. "Make sure your program is not using any GPL libraries (notably libx264)".

  The PyAV wheel fails item 18, so the LGPL route is not available for it as built.
- **How `configure` derives the licence** (FFmpeg `configure` at tag n8.0, lines 4596–4603):
  `enabled version3 && { enabled gpl && enable gplv3 || enable lgplv3; }`, then
  `license="GPL version 3 or later"` for gpl+version3 and `license="LGPL version 3 or later"` for lgplv3. Libraries in
  `EXTERNAL_LIBRARY_VERSION3_LIST` require `--enable-version3`. With the unpatched lists, the PyAV flags plus the
  `--enable-gpl` that x264/x265 would then demand give "GPL version 3 or later". That is the effective licence of the
  shipped stack.

### 2.6 Licences of the other bundled libraries

These come from upstream conventions. I did not re-read each licence file today, so check them when writing the
notice file:

- **LGPL:** gnutls (2.1+), alsa-lib (2.1+) and LAME/lamer.
- **Dual "LGPLv3+ or GPLv2+":** nettle/hogweed, gmp and libunistring.
- **Permissive:**
  - BSD: opus, dav1d, libvpx, libwebp, SVT-AV1 (BSD-3-Clause-Clear, plus the AOM patent licence) and libvmaf
    (BSD-2-Clause-Patent);
  - MIT/X11: libvpl, libxcb, libXau and libdrm.

These raise no extra issue beyond the notice and source obligations, and all of them can be combined under GPLv3. The
LGPL ones also need the relinking ability that dynamic `.so` files already provide.

### 2.7 Ubuntu 24.04 (noble) apt ffmpeg

- Package version: `7:6.1.1-3ubuntu5`, noble release pocket, published 2024-04-06 (FFmpeg 6.1.1). Launchpad's
  `getPublishedSources` (ffmpeg, noble, `status=Published`) returns only this version on 2026-10-08: there is **no
  noble-updates or noble-security version**.
- `debian/rules` on the `ubuntu/noble` branch:
  - the shared `CONFIG` has the comment "Most possible features, compatible with effective licensing of GPLv2+" and
    includes `--enable-gpl`, `--enable-libx265` and `--enable-gnutls`; `--enable-libx264` is added on the
    non-restricted architectures;
  - the "extra" flavour adds `--enable-version3` (GPLv3+) for `libavcodec-extra`/`libavfilter-extra`;
  - `--enable-nonfree` appears nowhere.
- `debian/copyright`: "For building the default Debian packages some of the GPL licensed files are used, so the
  resulting binaries are licensed under GPL v2+". The extra flavour is "effectively licensed under the GPL v3+".
  FFmpeg "can also be combined with non-free libraries … But this is not done for the Debian packages".
- `ffmpeg` depends on `libavcodec60`, `libavdevice60`, `libavfilter9`, `libavformat60`, `libavutil58` and others, and
  `libavcodec60` depends on `libx264-164` and `libx265-199` (packages.ubuntu.com). These GPL shared libraries are in
  any image that installs `ffmpeg`.
- Debian packages install their copyright files in `/usr/share/doc/<pkg>/copyright`. Images must not strip them, for
  example with `--path-exclude=/usr/share/doc/*`. Doing so removes the notices.
- The base image itself (Ubuntu 24.04, or NVIDIA's CUDA images built on it) already contains GPL packages such as
  bash (GPL-3+), coreutils, grep, tar and dpkg. Every published scenewise image therefore aggregates GPL software,
  whatever ffmpeg it uses.

### 2.8 GPL relationship: subprocess compared with import

The FSF FAQ, #MereAggregation, says where the line falls between "separate programs" and "one program with two parts"
"is a legal question, which ultimately judges will decide". It adds:

- "If modules are designed to run linked together in a shared address space, that almost surely means combining them
  into one program";
- "pipes, sockets and command-line arguments are communication mechanisms normally used between two separate
  programs".

Applied to scenewise:

- **ffmpeg CLI through a subprocess with argv and pipes:** separate program, aggregate. scenewise's code stays
  Apache-2.0 and is not affected.
- **`import av` through faster-whisper (`asr-whisper` builds only, after U16):** the same address space as scenewise's
  code. On the FSF's reading this is one combined program while it runs. A distributed image containing it should
  therefore satisfy **GPLv3** for the combination, which is the only licence the bundled stack allows (§2.5). Apache-2.0
  is GPLv3-compatible: "Apache 2 software can therefore be included in GPLv3 projects" (apache.org). It is not
  GPLv2-compatible: "the FSF has never considered the Apache License to be compatible with GPL version 2". That no
  longer matters here, because no GPLv2-only combination arises.
- **Never giving PyAV input does not change the linking analysis.** It is a security rule, not a licensing one.
  **[lawyer]**: whether loading an unused transitive Python dependency creates a derivative or combined work.

## 3. What scenewise must do

Obligations attach to **distribution** ("conveying", GPLv3 §0). scenewise's own git repo and its sdist/wheel do not
contain PyAV or FFmpeg, so they need nothing beyond the existing Apache-2.0 LICENSE and NOTICE. The obligations below
apply to **container images that scenewise publishes**, which q7 plans in CI ("building and publishing both image
variants"), and to anyone else who redistributes them. Items marked *(asr-whisper)* apply only to images built with
that extra, which scenewise does not publish (U16); they are kept so that the README can point self-builders at them.

1. **Notices (needed for every published image).** Add a third-party licence file for the images, for example
   `THIRD_PARTY_LICENSES` copied into the image, and point to it from NOTICE/README. It lists:
   - the apt ffmpeg packages, if U17 picks the Ubuntu build: ffmpeg and its libav* libraries (GPL-2.0-or-later, as
     built), x264 and x265 (GPL-2.0-or-later), with a pointer to `/usr/share/doc/*/copyright`; or the LGPL-only build,
     if U17 picks that, with its own configure line and licence;
   - a pointer to `/usr/share/doc/*/copyright` for the base-OS packages;
   - *(asr-whisper)* PyAV 19.0.1 (BSD-3-Clause); FFmpeg 9.0.2 as bundled by pyav-ffmpeg `9.0.2-1`, **GPL-3.0-or-later**
     because it is built with `--enable-version3` and with x264/x265, whatever its built-in "LGPL version 3 or later"
     string says; x264 `b35605ac…` and x265 4.3 (GPL-2.0-or-later, distributed under GPLv3 in this combination); LAME,
     gnutls, nettle, gmp, libunistring and alsa-lib (LGPL / dual); and the permissive libraries in §2.6.

   Include the full licence texts the listed components need (GPLv2, GPLv3, LGPLv2.1, LGPLv3, BSD/MIT). The PyAV wheel
   ships none of them.
2. **Corresponding source (needed when images are published).** For each published image digest, provide the complete
   corresponding source of the GPL/LGPL components.
   - Route: for images offered from a registry, GPLv3 §6(d) — equivalent access to the source from the same place,
     or from another server with "clear directions next to the object code", kept available for as long as the image
     is offered. For the GPLv2+ apt packages, GPLv2 §3(a) (source accompanying the binary) is met the same way when
     the source is published alongside the image. §6(c) / GPLv2 §3(c), passing on an upstream offer, is for
     noncommercial distribution only.
   - For the apt packages: the matching Ubuntu source packages (`apt-get source` at the pinned versions), including
     the base-OS GPL packages.
   - *(asr-whisper)* For PyAV: the av 19.0.1 sdist; the pyav-ffmpeg `9.0.2-1` tree with its patches and build scripts;
     the FFmpeg 9.0.2 source; x264 at `b35605ac…`; x265 4.3; and the LGPL libraries at the versions in §2.3.
   - A link to upstream GitHub tags or Ubuntu's archive alone may not meet §6(d)'s "you remain obligated to ensure that
     it is available" **[lawyer]**.
   - Practical form: a CI job that downloads these tarballs for the locked versions and attaches them to the GitHub
     release, or pushes them as an OCI artifact, next to each image digest.
3. **Labelling (recommended; not a licence term).** Do not label images `org.opencontainers.image.licenses=Apache-2.0`
   alone. State in the README that "scenewise source is Apache-2.0; container images include GPL-licensed components
   (the base OS and the ffmpeg CLI)". Use an SPDX expression or a pointer to the third-party file for the image label.
   For `asr-whisper`, add that the extra loads GPL-3.0-or-later code (FFmpeg with x264/x265) into the process.
4. **Keep Debian notices.** Do not strip `/usr/share/doc` from images.
5. **Ways to avoid GPL code.**
   - **Option A:** keep the stock wheel and do items 1–4 in full. Now applies to `asr-whisper` builds only.
   - **Option B:** build av from its sdist (`--no-binary av`) against an FFmpeg 9 built with pyav-ffmpeg's script but
     without x264/x265 and without the configure patch. The result is a genuinely LGPLv3 FFmpeg; LGPL source and notice
     duties remain. It needs a custom build step and a rebuild for every av or FFmpeg bump. Not needed after U16.
   - **Option C — done (q11, U16):** the default `asr` extra drops faster-whisper and PyAV, and Whisper LID moves to
     an in-house onnxruntime Whisper-tiny adapter. faster-whisper stays as the opt-in `asr-whisper` fallback.
   - **For the ffmpeg CLI (U17):** see §5.
   - Deleting `libx264`/`libx265` from `av.libs` is **not** an option. libavcodec `NEEDED`s them and would fail to
     load.
6. **Expause's internal use [lawyer].** Keep the notices in the image. Building and running images in Expause's own
   Google Cloud project, without handing copies to others, is probably not "conveying" under GPLv3 §0 and §2 (§1(c)).
   Confirm this, and confirm the position if the project belongs to a different legal entity from the one that builds
   the images (FAQ #DistributeSubsidiary), before relying on it.

## 4. Open questions

1. **[lawyer]** Does importing PyAV (unused) into scenewise's process make one GPL-covered combined work for
   distribution purposes, or is the wheel merely aggregated? After U16 this affects only `asr-whisper` builds.
2. **[lawyer]** pyav-ffmpeg's relabelling of x264/x265 as "version3", and the maintainer's "implied commercial
   exception": can a redistributor rely on it? No source found supports it, and FFmpeg's own legal page says FFmpeg is
   not available under commercial terms (§2.5). This research's answer is **no**; it treats the wheel as
   GPL-3.0-or-later.
3. **[lawyer]** Is a link to upstream tags and Ubuntu's archive enough to meet the source obligation for published
   images, or must scenewise host the tarballs itself (as FFmpeg's checklist item 8 suggests for LGPL, and as GPLv3
   §6(d)'s "remain obligated" implies)?
4. **[lawyer]** Patents: the images contain H.264/HEVC encoders (x264, x265 in apt ffmpeg; also in PyAV for
   `asr-whisper`). Copyright licences do not cover codec patent pools, and scenewise never encodes. Out of scope here.
5. **[lawyer]** Does Expause deploying the image into its own Google Cloud project, run by Google as infrastructure,
   count as "conveying" (GPLv3 §0, §2) or "distribution"? The FSF FAQ (#UnreleasedMods, #DistributeSubsidiary) suggests
   not, but this was not checked against EU law or Expause's entity structure.
6. *Closed.* No noble-updates or noble-security ffmpeg exists on 2026-10-08; `7:6.1.1-3ubuntu5` is the only published
   noble version. Still pin the exact version in the Dockerfile so the source bundle matches it.
7. Only the manylinux x86_64 wheel was inspected. Check the aarch64 wheel the same way if an `asr-whisper` arm64 image
   is ever built.
8. **U17 (user decision, deferred to the first published Dockerfile):** Ubuntu ffmpeg or an LGPL-only ffmpeg in
   published images. Inputs in §5.

## 5. Input to U17: ffmpeg in published images

| | Ubuntu apt ffmpeg (`7:6.1.1-3ubuntu5`) | LGPL-only ffmpeg build |
|---|---|---|
| Licence of the ffmpeg component | GPL-2.0-or-later (libav*, x264, x265) | LGPL (2.1+, or 3+ with `--enable-version3`), no x264/x265 |
| GPL still in the image | yes: base OS and ffmpeg | yes: base OS only |
| Effect on scenewise's code | none (subprocess, aggregate) | none |
| Notices | `/usr/share/doc` copyright files, kept | must be written for the build, plus FFmpeg checklist items 9–11 |
| Source bundle | Ubuntu source packages via `apt-get source` | FFmpeg source, configure line, diff, LGPL libraries (checklist items 3–8, 17) |
| Build cost | none; same package as dev/CI (U17) | a build stage per image variant and per FFmpeg bump; dev/CI and images diverge |
| Codecs scenewise needs (decode, probe, extract audio/frames) | all | needs checking against the media contract (q1) when the build is defined |

Recommendation for that decision: **the Ubuntu build**, unless a consumer of the published images requires an image
without GPL ffmpeg. The LGPL-only build does not make the image GPL-free, because the base OS is GPL-aggregated, and
it adds a source bundle scenewise would have to assemble itself instead of fetching from Ubuntu. Either way, §3 items
1–4 apply.

## 6. Sources (all read 2026-10-08)

- `uv.lock` in this repo: the `av` 19.0.1 entry with its wheel list and hashes.
- Wheel: https://files.pythonhosted.org/packages/c8/97/5fb45934ac64e8afc2c6869a7dcb8cb2af1ddab09a725367548856cbb59f/av-19.0.1-cp312-abi3-manylinux_2_28_x86_64.whl
  (sha256 `1bea5b6134209305199bce7627ac3d33964de2cf2b09c77d08e7f67cf8bd4170`). Its contents were inspected locally.
- PyAV `scripts/ffmpeg-latest.json` at tag v19.0.1: https://github.com/PyAV-Org/PyAV/blob/v19.0.1/scripts/ffmpeg-latest.json
- pyav-ffmpeg:
  - README: https://github.com/PyAV-Org/pyav-ffmpeg
  - `patches/ffmpeg.patch`: https://github.com/PyAV-Org/pyav-ffmpeg/blob/main/patches/ffmpeg.patch
  - commit history of the patch file: `gh api "repos/PyAV-Org/pyav-ffmpeg/commits?path=patches/ffmpeg.patch"`
  - commit `dc9ee64dff` (2025-06-27) "GPLv3 OR "LGPLv3 + Exceptions"": https://github.com/PyAV-Org/pyav-ffmpeg/commit/dc9ee64dff
  - commit `9e70d98192` (2025-08-23) "ffmpeg 8.0": https://github.com/PyAV-Org/pyav-ffmpeg/commit/9e70d98192
  - commit `598dea363c` (2026-08-04) "FFmpeg 9.0": https://github.com/PyAV-Org/pyav-ffmpeg/commit/598dea363c
  - `scripts/build-ffmpeg.py`: https://github.com/PyAV-Org/pyav-ffmpeg/blob/main/scripts/build-ffmpeg.py
  - release 9.0.2-1: https://github.com/PyAV-Org/pyav-ffmpeg/releases/tag/9.0.2-1
- PyAV issue #2270: https://github.com/PyAV-Org/PyAV/issues/2270 (comments of 2026-06-01, 2026-09-12 and 2026-09-13).
- PyAV PR #967, maintainer comment of 2023-11-01: https://github.com/PyAV-Org/PyAV/pull/967#issuecomment-1789524823
- PyAV installation docs: https://pyav.basswood.io/docs/stable/overview/installation.html. They say nothing about
  licensing, and describe building from the sdist against your own FFmpeg.
- FFmpeg legal page, "not available under any other licensing terms" and the 18-item LGPL checklist:
  https://ffmpeg.org/legal.html
- FFmpeg `configure` licence logic at n8.0 (lines 4596–4603): https://github.com/FFmpeg/FFmpeg/blob/n8.0/configure
- x264:
  - https://www.videolan.org/developers/x264.html
  - header: https://raw.githubusercontent.com/mirror/x264/master/x264.h
- x265:
  - https://bitbucket.org/multicoreware/x265_git/raw/master/source/x265.h
  - https://bitbucket.org/multicoreware/x265_git/raw/master/COPYING
  - x265.org returned HTTP 429 and was not read.
- Ubuntu ffmpeg:
  - `debian/rules`: https://git.launchpad.net/ubuntu/+source/ffmpeg/plain/debian/rules?h=ubuntu/noble
  - `debian/copyright`: https://git.launchpad.net/ubuntu/+source/ffmpeg/plain/debian/copyright?h=ubuntu/noble
  - version: https://packages.ubuntu.com/noble/ffmpeg and the Launchpad API `getPublishedSources` (status=Published)
  - dependencies: https://packages.ubuntu.com/noble/ffmpeg and https://packages.ubuntu.com/noble/libavcodec60
- GPL FAQ (#MereAggregation, #UnreleasedMods, #DistributeSubsidiary, #GPLRequireSourcePostedPublic,
  #NFUseGPLPlugins): https://www.gnu.org/licenses/gpl-faq.en.html
- GPLv3 §0 ("convey"), §2 (facilities for running "exclusively on your behalf"), §6(a)–(d):
  https://www.gnu.org/licenses/gpl-3.0.txt
- GPLv2 §3: https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
- Apache–GPL compatibility: https://www.apache.org/licenses/GPL-compatibility.html
- `docs/research/user-decisions.md` (U16, U17); q11 (`q11-asr-without-pyav.md`); q8c §1, §3, §6.3 item 21; q8a §9.1;
  q7 (image publishing in CI) in this repo.

## 7. Review round 1 — resolution

Review: `reviews/q10-q11-review-r1.md`. Each q10 finding was re-checked against its source on 2026-10-08 before the
edit.

| # | Finding | Re-check | Resolution |
|---|---|---|---|
| 1 | Stack is GPL-3.0-or-later (`--enable-version3`), so obligations come from GPLv3 §6, not GPLv2 §3 | Confirmed. FFmpeg `configure` n8.0 lines 4596–4603 read as quoted; the wheel's configure line has `--enable-version3`; GPLv3 §6(a)–(d) re-read | **Accepted.** §1, §2.2, §2.5, §2.8 and §3 items 1–2 now say GPL-3.0-or-later and base source duties on GPLv3 §6. Added that §6(a)/(b) are worded for physical products, so §6(d) is the route for a registry image. Added that the maintainer's 2026 description is inconsistent with the build (§2.4) |
| 2 | Patch history misattributed to `dc9ee64dff` | Confirmed with `gh api` commit history and diffs: `dc9ee64dff` added x264/x265 to `EXTERNAL_LIBRARY_LIST`; `9e70d98192` moved them to the version3 list | **Accepted.** §2.3 gives the full history (`dc9ee64dff`, `9e70d98192`, `1e42248dfc`, `598dea363c`) |
| 4 | "Only GPL left is the apt ffmpeg CLI" overstated | Confirmed. `ffmpeg` depends on libav* packages and `libavcodec60` on `libx264-164`/`libx265-199`; base OS has GPL packages. (q10 had no "§5 effect note"; the wording is fixed where it now appears) | **Accepted.** §1 "What GPL remains", §2.7 and §3 say no GPL is loaded into the process without `asr-whisper`, but the image still aggregates the base OS and apt ffmpeg with its libraries; U17's LGPL option does not remove the base-OS part |
| 6 | Internal-use claim stated as fact | Confirmed. #UnreleasedMods is FSF interpretation; #DistributeSubsidiary says it depends on jurisdiction; GPLv3 §0 and §2 re-read | **Accepted.** §1(c) and §3 item 6 marked **[lawyer]**, GPLv3 §0 (and §2) cited as primary text, FAQ as FSF interpretation, subsidiary entry added. §4 question 5 updated |
| 7 | FFmpeg's "not available under … commercial" statement missing | Confirmed verbatim on legal.html | **Accepted.** Quoted in §2.5; used in §1, §2.4 and §4 question 2 (answer: no) |
| 8 | Status does not reflect U16/U17 or q11 | Confirmed against `user-decisions.md` | **Accepted.** Status block at top; recommendation rewritten; Option C marked done; §5 added as input to U17; §4 question 8 records U17 as open |
| 13 | Checklist numbering | Confirmed: 18 items; "same webserver" is item 8, "tarball" item 7, "go through again" item 17 | **Accepted.** §2.5 uses the page's numbers |
| 14 | Issue #2270 chronology | Confirmed with `gh api`: question 2026-09-12; links (x265.org, tag `8.1.2-1`) 2026-09-13 03:51; "implied" reply 14:34; `build-deps` comment 2026-06-01 | **Accepted.** §2.4 corrected; `build-deps` comment added to §2.3–§2.4 |
| 15 | armv7l wheel still has x265 | Confirmed in the pyav-ffmpeg README | **Accepted.** §1 and §2.2 corrected |
| 16 | Open question 6 can be closed | Confirmed: Launchpad returns only `7:6.1.1-3ubuntu5` (Release, 2024-04-06) | **Accepted.** §2.7 and §4 question 6 closed, pin advice kept |
| 18 | "No Apache-2.0-only claim" is not a licence obligation | Agreed; no clause requires it | **Accepted.** Labelled "recommended; not a licence term" in §1(b) and §3 item 3 |

Findings 3, 5, 9–12, 17, 19 and 20 concern q11 and are not addressed here. Finding 12's point that published images
ship no fallback recogniser is reflected in §1 and §3 (U16).
