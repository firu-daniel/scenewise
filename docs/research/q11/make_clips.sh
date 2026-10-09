#!/usr/bin/env bash
# Generate the speech clips used by the q11 scripts with macOS `say` (16 kHz mono s16le WAV).
# Usage: ./make_clips.sh AUDIO_DIR      (macOS only; voices Samantha en_US, Anna de_DE, Thomas fr_FR)
# Silence, white noise (seeds 0-2), a synthetic music bed and noisy-speech mixes are made in Python by clips.py.
set -euo pipefail
out=${1:?AUDIO_DIR}; mkdir -p "$out"
s() { say -v "$1" --file-format=WAVE --data-format=LEI16@16000 -o "$out/$2.wav" "$3"; }
s Samantha en "The quarterly report is ready. Please review the figures before Thursday's meeting and send me your comments."
s Anna de "Der Quartalsbericht ist fertig. Bitte prüfen Sie die Zahlen vor der Besprechung am Donnerstag und schicken Sie mir Ihre Kommentare."
s Thomas fr "Le rapport trimestriel est prêt. Merci de vérifier les chiffres avant la réunion de jeudi."
for f in en de fr; do printf '%s ' "$f"; afinfo "$out/$f.wav" | grep -E 'estimated duration' ; done
