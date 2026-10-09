#!/usr/bin/env bash
# Assert the accelerator routing and the PyAV-free default extras ARCHITECTURE.md §12 relies on,
# from uv.lock alone.
set -euo pipefail
reqs() { uv export --locked --no-dev --no-hashes --no-annotate --quiet "$@"; }
need() { grep -qE "$2" <<<"$1" || { echo "FAIL: $3"; exit 1; }; }

cpu=$(reqs --extra torch-cpu)
gpu=$(reqs --extra torch-cu130)
asr=$(reqs --extra service --extra asr)
img_cpu=$(reqs --extra service --extra asr --extra llm-anthropic --extra vision --extra gcs --extra torch-cpu)
img_gpu=$(reqs --extra service --extra asr --extra llm-anthropic --extra vision --extra gcs --extra torch-cu130)
fallback=$(reqs --extra asr-whisper)

need "$cpu" "^torch==[^ ]+\+cpu ; sys_platform == 'linux'"       "torch-cpu: torch not from pytorch-cpu"
need "$cpu" "^torchvision==[^ ]+\+cpu ; sys_platform == 'linux'" "torch-cpu: torchvision not from pytorch-cpu"
need "$gpu" "^torch==[^ ]+\+cu130"                                "torch-cu130: torch not from pytorch-cu130"
need "$gpu" "^torchvision==[^ ]+\+cu130"                          "torch-cu130: torchvision not from pytorch-cu130"
if grep -qE "^(torch|torchvision)==" <<<"$asr"; then echo "FAIL: asr pulls torch"; exit 1; fi
if grep -qE "^onnxruntime-gpu==" <<<"$asr"; then echo "FAIL: asr pulls onnxruntime-gpu"; exit 1; fi
need "$asr" "^sherpa-onnx-core=="                                 "asr: sherpa-onnx-core missing from the lock"
# U16, q10/q11: PyAV (GPL x264/x265) only through the opt-in asr-whisper extra.
for set in asr img_cpu img_gpu; do
  if grep -qE "^(av|ctranslate2|faster-whisper)==" <<<"${!set}"; then
    echo "FAIL: $set pulls av, ctranslate2 or faster-whisper (only asr-whisper may, U16)"; exit 1
  fi
done
need "$fallback" "^faster-whisper=="                              "asr-whisper: faster-whisper missing"
echo "lock routing ok"
