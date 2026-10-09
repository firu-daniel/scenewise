#!/usr/bin/env bash
# Download the pinned model files used by the q11 scripts and verify their sha256.
# Usage: ./fetch_models.sh MODEL_DIR [--with-fp16] [--with-ct2]
#   default:     onnx-community/whisper-tiny fp32 encoder + decoder (the q11 choice) and the int8 pair (round 0, for
#                the comparison), generation_config.json, added_tokens.json, Silero VAD v6.2 ONNX
#   --with-fp16: also the fp16 encoder (lid_eval.py's fp16/int8 variant)
#   --with-ct2:  also Systran/faster-whisper-tiny (CTranslate2, for ct2_reference.py)
# Licences: OpenAI Whisper weights are MIT (github.com/openai/whisper README). The onnx-community repo states no
# licence of its own (card: base_model openai/whisper-tiny); the openai/whisper-tiny HF card is tagged apache-2.0.
# Systran/faster-whisper-tiny is tagged MIT. Silero VAD is MIT.
set -euo pipefail
dir=${1:?MODEL_DIR}; shift || true
with_ct2=0; with_fp16=0
for a in "$@"; do case $a in --with-ct2) with_ct2=1;; --with-fp16) with_fp16=1;; *) echo "unknown $a"; exit 2;; esac; done
WT=https://huggingface.co/onnx-community/whisper-tiny/resolve/ff4177021cc41f7db950912b73ea4fdf7d01d8e7
CT=https://huggingface.co/Systran/faster-whisper-tiny/resolve/d90ca5fe260221311c53c58e660288d3deb8d356
SV=https://raw.githubusercontent.com/snakers4/silero-vad/be95df9152c0d7618fa1edfeb296fc3dae32376f/src/silero_vad/data/silero_vad.onnx
get() {  # url dest sha256
  mkdir -p "$(dirname "$2")"
  [ -f "$2" ] || curl -fsSL -o "$2" "$1"
  echo "$3  $2" | shasum -a 256 -c -
}
get $WT/onnx/encoder_model_int8.onnx "$dir/wt/onnx/encoder_model_int8.onnx" 03ff3c99ce804f79a42afd6212c9492eb75e55625926de66f8fc192e9567d336
get $WT/onnx/decoder_model_int8.onnx "$dir/wt/onnx/decoder_model_int8.onnx" 2a160a2a5ccf901f83aa4d4ceec580a269bd2cec582871e0816e98c610594f12
get $WT/generation_config.json "$dir/wt/generation_config.json" f5c67e5a4f7102f8cb4d058bc95da276bbc19eeec997267c3bb0f25ef68facd1
get $WT/added_tokens.json "$dir/wt/added_tokens.json" 9715fd2243b6f06a5858b5e32950d2853f73dd5bc201aafcf76f5082a2d8acd1
get $SV "$dir/silero_vad.onnx" 1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3
get $WT/onnx/encoder_model.onnx "$dir/wt/onnx/encoder_model.onnx" 6642befb640f950d4a8cbbd17834d59e7e75f575b81ccf213e06b050623ab1dd
get $WT/onnx/decoder_model.onnx "$dir/wt/onnx/decoder_model.onnx" ab79e3f2a9a3d98f159f853a3172120a38af7eb5f7863d706aa7d39c228f009e
if [ $with_fp16 = 1 ]; then
  get $WT/onnx/encoder_model_fp16.onnx "$dir/wt/onnx/encoder_model_fp16.onnx" fc4bf9f3fadc450b128c3ef0711a4e61a55797447b6a700abe7fb97d9f549518
fi
if [ $with_ct2 = 1 ]; then
  get $CT/model.bin "$dir/fwt/model.bin" dcb76c6586fc06cbdac6dd21f14cfd129cc4cdd9dce19bf4ffa62e59cbe6e6d1
  get $CT/config.json "$dir/fwt/config.json" a73a28cdfe1c43ccc7202fa333d1f89c202477271407ae9a7f19afa52039cac8
  get $CT/tokenizer.json "$dir/fwt/tokenizer.json" fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab
  get $CT/vocabulary.txt "$dir/fwt/vocabulary.txt" 34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913
fi
