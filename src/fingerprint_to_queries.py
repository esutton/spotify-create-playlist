"""Generate track query list from an MP3 radio-capture using audio fingerprinting.

This script:
- Splits a (long) MP3 radio capture into candidate tracks using silence detection (pydub).
- For each segment it computes an audio fingerprint (Chromaprint / fpcalc via pyacoustid)
  and looks up metadata with the AcoustID web service (requires ACOUSTID_API_KEY env var).
- Falls back to embedded tags (mutagen) or to a heuristic filename when lookup fails.
- Writes a one-track-per-line text file (default: `queries.txt`) suitable as input to
  `create_playlist.create_playlist_and_add_tracks` (each line is a search query like
  "Song Title - Artist").

Requirements
------------
- Python packages: pydub, pyacoustid (import name: acoustid), mutagen
  Install: pip install pydub pyacoustid mutagen
- System: chromaprint's `fpcalc` must be installed and on PATH.
  On macOS: brew install chromaprint

Usage example
-------------
python src/fingerprint_to_queries.py radio_capture.mp3 --output queries.txt

If you do not have an AcoustID API key, the script will attempt to use embedded tags
and then fall back to a generic query string per segment.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from typing import List, Optional, Tuple

try:
    from pydub import AudioSegment, silence
except Exception as e:
    raise ImportError("pydub is required. Install with `pip install pydub`") from e

try:
    import acoustid
except Exception:
    acoustid = None  # optional; we'll handle missing library/API key gracefully

try:
    from mutagen import File as MutagenFile
except Exception:
    MutagenFile = None

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def split_on_silence(audio: AudioSegment, min_silence_len: int = 1200, silence_thresh: int = -40,
                     keep_silence: int = 300) -> List[AudioSegment]:
    """Split an AudioSegment into chunks by detected silence.

    Returns a list of AudioSegment objects representing non-silent regions.
    """
    non_silent_ranges = silence.detect_nonsilent(audio, min_silence_len=min_silence_len,
                                                 silence_thresh=silence_thresh)
    segments: List[AudioSegment] = []
    for start, end in non_silent_ranges:
        # optionally keep a little silence at edges to avoid chopping words
        s = max(0, start - keep_silence)
        e = min(len(audio), end + keep_silence)
        segments.append(audio[s:e])
    return segments


def fingerprint_and_lookup(segment_path: str, acoustid_key: Optional[str]) -> Optional[Tuple[str, str]]:
    """Return (title, artist) from fingerprint lookup or None on failure.

    Uses pyacoustid (chromaprint). acoustid_key may be None to skip lookup.
    """
    if acoustid is None or acoustid_key is None:
        return None

    try:
        duration, fp = acoustid.fingerprint_file(segment_path)
    except Exception as e:
        logger.debug("Fingerprinting failed: %s", e)
        return None

    try:
        results = acoustid.lookup(acoustid_key, fp, duration)
    except Exception as e:
        logger.debug("AcoustID lookup failed: %s", e)
        return None

    # results is a tuple (status, list) in some versions; normalize
    try:
        # pyacoustid.lookup returns a list of result dicts or a tuple
        candidates = results[1] if isinstance(results, tuple) and len(results) > 1 else results
    except Exception:
        candidates = results

    # Try to extract artist/title from the best candidate
    try:
        for r in candidates:
            recordings = r.get("recordings") or []
            if recordings:
                rec = recordings[0]
                title = rec.get("title")
                artists = rec.get("artists") or []
                artist = artists[0].get("name") if artists else None
                if title:
                    return title, artist or ""
    except Exception:
        pass

    return None


def read_tags(path: str) -> Optional[Tuple[str, str]]:
    if MutagenFile is None:
        return None
    try:
        m = MutagenFile(path)
        if not m or not getattr(m, "tags", None):
            return None
        # common ID3 tags
        title = None
        artist = None
        tags = m.tags
        # ID3v2
        if "TIT2" in tags:
            title = str(tags.get("TIT2"))
        if "TPE1" in tags:
            artist = str(tags.get("TPE1"))
        # fallbacks
        if not title:
            title = tags.get("title") or tags.get("TIT2")
        if not artist:
            artist = tags.get("artist") or tags.get("TPE1")
        # normalize
        if isinstance(title, list):
            title = title[0]
        if isinstance(artist, list):
            artist = artist[0]
        if title:
            return str(title), str(artist) if artist else ""
    except Exception:
        return None


def make_query_from_metadata(meta: Optional[Tuple[str, str]], index: int) -> str:
    if meta and meta[0]:
        title, artist = meta
        if artist:
            return f"{title} - {artist}"
        return title
    return f"Unknown Track {index + 1}"


def process_file(input_path: str, output_path: str, acoustid_key: Optional[str],
                 min_silence_len: int = 1200, silence_thresh: int = -40, keep_silence: int = 300) -> List[str]:
    audio = AudioSegment.from_file(input_path)
    logger.info("Loaded audio (duration: %.1f sec)", len(audio) / 1000.0)

    segments = split_on_silence(audio, min_silence_len=min_silence_len,
                                silence_thresh=silence_thresh, keep_silence=keep_silence)

    if not segments:
        # No silence-based splits found -> treat whole file as one segment
        segments = [audio]

    queries: List[str] = []
    temp_files: List[str] = []
    try:
        for i, seg in enumerate(segments):
            logger.info("Processing segment %d/%d (%.1f sec)", i + 1, len(segments), len(seg) / 1000.0)
            # export to temporary WAV for fingerprinting
            tf = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            temp_files.append(tf.name)
            tf.close()
            seg.export(tf.name, format="wav")

            # Try fingerprint lookup
            meta = None
            if acoustid_key:
                meta = fingerprint_and_lookup(tf.name, acoustid_key)

            # If lookup fails, try embedded tags
            if not meta:
                tag_meta = read_tags(input_path) if i == 0 else None
                if tag_meta:
                    meta = tag_meta

            q = make_query_from_metadata(meta, i)
            logger.info("  -> Query: %s", q)
            queries.append(q)

    finally:
        # cleanup temp files
        for p in temp_files:
            try:
                os.unlink(p)
            except Exception:
                pass

    # write output
    with open(output_path, "w", encoding="utf-8") as fh:
        for q in queries:
            fh.write(q + "\n")

    logger.info("Wrote %d queries to %s", len(queries), output_path)
    return queries


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create track query list from an MP3 radio capture using audio fingerprinting")
    p.add_argument("input", help="Input audio file (mp3) containing radio capture")
    p.add_argument("--output", "-o", default="queries.txt", help="Output queries file (one per line)")
    p.add_argument("--acoustid-key", default=os.getenv("ACOUSTID_API_KEY"), help="AcoustID API key (or set ACOUSTID_API_KEY env var)")
    p.add_argument("--min-silence-ms", type=int, default=1200, help="Minimum silence length (ms) to split tracks")
    p.add_argument("--silence-thresh-db", type=int, default=-40, help="Silence threshold in dBFS (negative number)")
    p.add_argument("--keep-silence-ms", type=int, default=300, help="Amount of silence to keep at edges (ms)")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(list(argv) if argv is not None else None)
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    if not os.path.exists(args.input):
        logger.error("Input file not found: %s", args.input)
        return 2

    queries = process_file(args.input, args.output, args.acoustid_key,
                           min_silence_len=args.min_silence_ms,
                           silence_thresh=args.silence_thresh_db,
                           keep_silence=args.keep_silence_ms)

    for q in queries:
        print(q)

    return 0


if __name__ == "__main__":
    sys.exit(main())
