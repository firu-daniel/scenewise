#!/usr/bin/env bash
# Regenerate the committed media fixtures with ffmpeg's lavfi sources. Nothing is
# downloaded. Bytes differ between ffmpeg builds, so tests assert on decoded
# properties (duration, streams, sample format), never on fixture bytes.
#   tone.m4a     2 s 440 Hz sine, AAC, 44.1 kHz stereo (exercises resample + downmix)
#   clip.mp4     2 s testsrc2 video (160x120, 10 fps, H.264) with a 440 Hz AAC tone
#   silent.mp4   2 s testsrc2 video with no audio stream
set -euo pipefail
cd "$(dirname "$0")"
common=(-hide_banner -loglevel error -y)
out=(-map_metadata -1 -fflags +bitexact)
video=(-c:v libx264 -preset veryslow -crf 40 -pix_fmt yuv420p -flags:v +bitexact)
audio=(-c:a aac -b:a 32k -flags:a +bitexact)

ffmpeg "${common[@]}" -f lavfi -i "sine=frequency=440:duration=2:sample_rate=44100" \
  -ac 2 "${audio[@]}" "${out[@]}" tone.m4a
ffmpeg "${common[@]}" -f lavfi -i "testsrc2=size=160x120:rate=10:duration=2" \
  -f lavfi -i "sine=frequency=440:duration=2:sample_rate=44100" \
  "${video[@]}" "${audio[@]}" -shortest "${out[@]}" clip.mp4
ffmpeg "${common[@]}" -f lavfi -i "testsrc2=size=160x120:rate=10:duration=2" \
  "${video[@]}" -an "${out[@]}" silent.mp4
ls -l tone.m4a clip.mp4 silent.mp4
