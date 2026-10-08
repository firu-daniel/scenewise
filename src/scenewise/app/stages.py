"""One function per stage: fetch through a port, transform purely, return domain data.

The skeleton wires one stage, ``audio``: the normalised track itself. Captions,
summary, chapters, moderation and labels join with roadmap items 1-4.
"""

from pathlib import Path


def audio(track: Path) -> bytes:
    """The audio stage: the 16 kHz mono ``pcm_s16le`` WAV that ``MediaTool`` made."""
    return track.read_bytes()
