#!/usr/bin/env bash
# Assert the accelerator routing ARCHITECTURE.md §12 relies on, from uv.lock alone.
set -euo pipefail
reqs() { uv export --locked --no-dev --no-hashes --no-annotate --quiet "$@"; }
need() { grep -qE "$2" <<<"$1" || { echo "FAIL: $3"; exit 1; }; }

cpu=$(reqs --extra torch-cpu)
gpu=$(reqs --extra torch-cu130)
asr=$(reqs --extra service --extra asr)

need "$cpu" "^torch==[^ ]+\+cpu ; sys_platform == 'linux'"       "torch-cpu: torch not from pytorch-cpu"
need "$cpu" "^torchvision==[^ ]+\+cpu ; sys_platform == 'linux'" "torch-cpu: torchvision not from pytorch-cpu"
need "$gpu" "^torch==[^ ]+\+cu130"                                "torch-cu130: torch not from pytorch-cu130"
need "$gpu" "^torchvision==[^ ]+\+cu130"                          "torch-cu130: torchvision not from pytorch-cu130"
if grep -qE "^(torch|torchvision)==" <<<"$asr"; then echo "FAIL: asr pulls torch"; exit 1; fi
if grep -qE "^onnxruntime-gpu==" <<<"$asr"; then echo "FAIL: asr pulls onnxruntime-gpu"; exit 1; fi
need "$asr" "^sherpa-onnx-core=="                                 "asr: sherpa-onnx-core missing from the lock"
echo "lock routing ok"
