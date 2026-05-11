#!/usr/bin/env python3
"""
make_podcast_clone.py — Multi-speaker voice-cloning podcast generator.

Uses the Qwen3-TTS Base model with reference wav files to clone real voices
for each speaker instead of predefined CustomVoice speakers.

Usage:
    python make_podcast_clone.py \
        --script podcasts/ai_security_oss_script.txt \
        --title  "The_Signal_OSS_Security" \
        --voice-map "Matthew:podcasts/voices/yt-matthew-us.wav,Sam:podcasts/voices/yt-sam-witteveen.wav"
"""

import os
import sys
import json
import argparse
import subprocess
import time
from pathlib import Path

# ── Make sure the project root is on PYTHONPATH so we can import engine ──────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)          # engine resolves "storage/" relative to cwd

from engine import StudioEngine


# ─────────────────────────────────────────────────────────────────────────────
# Voice profile registry
# Each profile carries the path to the reference wav and an optional ref_text.
# ref_text can be empty — the engine will use x_vector_only mode in that case.
# ─────────────────────────────────────────────────────────────────────────────
VOICE_PROFILES = {
    "Matthew": {
        "ref_audio": "podcasts/voices/yt-matthew-us.wav",
        "ref_text": "",   # x_vector_only — no transcript needed
    },
    "Sam": {
        "ref_audio": "podcasts/voices/yt-sam-witteveen.wav",
        "ref_text": "",
    },
    "Aria": {
        "ref_audio": "podcasts/voices/yt-diary-ceo.wav",
        "ref_text": "",
    },
}


def parse_dialogue(text: str) -> list[dict]:
    """Parse 'Speaker: text' formatted dialogue."""
    lines = text.strip().splitlines()
    segments = []
    for line in lines:
        if ":" in line:
            speaker, utterance = line.split(":", 1)
            utterance = utterance.strip()
            if utterance:
                segments.append({"speaker": speaker.strip(), "text": utterance})
    return segments


def build_voice_map(voice_map_str: str) -> dict:
    """Parse --voice-map CLI argument: 'Name:path,Name2:path2' """
    mapping = {}
    if not voice_map_str:
        return mapping
    for item in voice_map_str.split(","):
        if ":" in item:
            name, path = item.split(":", 1)
            mapping[name.strip()] = path.strip()
    return mapping


def generate_podcast(script_text: str,
                     title: str = "Untitled_Podcast",
                     voice_map_override: dict = None,
                     max_duration_sec: int = 600):

    # ── Load Base model ───────────────────────────────────────────────────────
    engine = StudioEngine()
    base_model_path = str((PROJECT_ROOT / "models" / "Qwen3-TTS-12Hz-1.7B-Base").resolve())
    if not Path(base_model_path).exists():
        # Fallback to any discovered Base model
        for m in engine.discover_local_models():
            if "Base" in m:
                base_model_path = str((PROJECT_ROOT / m).resolve()) if not Path(m).is_absolute() else m
                break
    print(f"🤖 Loading Base model: {base_model_path}")
    engine.load_model(base_model_path)

    # ── Merge voice profiles with CLI overrides ───────────────────────────────
    profiles = dict(VOICE_PROFILES)
    if voice_map_override:
        for name, path in voice_map_override.items():
            abs_path = str((PROJECT_ROOT / path).resolve()) if not Path(path).is_absolute() else path
            profiles[name] = {"ref_audio": abs_path, "ref_text": ""}

    # ── Project directory setup ───────────────────────────────────────────────
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() else "_" for c in title)
    project_dir = PROJECT_ROOT / "podcasts" / f"{timestamp}_{safe_title}"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "segments").mkdir(exist_ok=True)
    (project_dir / "assets").mkdir(exist_ok=True)

    # Save script
    (project_dir / "script.txt").write_text(script_text)

    segments = parse_dialogue(script_text)
    print(f"🎙️  Project  : {project_dir}")
    print(f"🎙️  Segments : {len(segments)}")

    temp_files = []
    unknown_speakers = set()

    try:
        for i, seg in enumerate(segments):
            speaker = seg["speaker"]
            profile = profiles.get(speaker)

            if profile is None:
                unknown_speakers.add(speaker)
                print(f"  ⚠️  [{i+1}/{len(segments)}] Unknown speaker '{speaker}' — skipping.")
                continue

            ref_audio = profile["ref_audio"]
            # Make absolute if relative
            if not Path(ref_audio).is_absolute():
                ref_audio = str((PROJECT_ROOT / ref_audio).resolve())

            if not Path(ref_audio).exists():
                print(f"  ❌ [{i+1}/{len(segments)}] Reference audio not found: {ref_audio}")
                continue

            print(f"  [{i+1}/{len(segments)}] Cloning '{speaker}' → {Path(ref_audio).name}")
            meta = engine.generate(
                text=seg["text"],
                language="Auto",
                ref_audio_path=ref_audio,
                ref_text=profile.get("ref_text", ""),
            )

            if meta:
                src = PROJECT_ROOT / "storage" / meta["filename"]
                dst = project_dir / "segments" / f"seg_{i+1:03d}_{speaker}.wav"
                os.rename(src, dst)
                temp_files.append(dst)

    except Exception as e:
        print(f"❌ Generation error: {e}")
        raise

    if unknown_speakers:
        print(f"\n⚠️  Unrecognised speakers (no audio generated): {unknown_speakers}")

    if not temp_files:
        print("❌ No audio segments generated. Aborting.")
        return None

    # ── Concatenate with ffmpeg ───────────────────────────────────────────────
    list_file = project_dir / "concat_list.txt"
    with open(list_file, "w") as f:
        for tf in temp_files:
            f.write(f"file 'segments/{tf.name}'\n")

    output_audio = project_dir / "audio_final.wav"
    print(f"\n🔗 Concatenating {len(temp_files)} segments → {output_audio.name} …")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", list_file.name, "-c", "copy", output_audio.name],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    list_file.unlink()

    # ── Duration check ────────────────────────────────────────────────────────
    probe = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(output_audio)
    ])
    duration = float(probe.decode().strip())

    if duration > max_duration_sec:
        print(f"⚠️  Duration {duration/60:.1f} min exceeds limit of {max_duration_sec/60:.0f} min")

    # ── Metadata ──────────────────────────────────────────────────────────────
    metadata = {
        "title": title,
        "timestamp": timestamp,
        "duration": round(duration, 2),
        "segments_count": len(temp_files),
        "model": engine.model_name,
        "mode": "voice_clone",
        "voices": {name: profile["ref_audio"] for name, profile in profiles.items()},
    }
    with open(project_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n✅ Podcast complete!")
    print(f"   Audio   : {output_audio}")
    print(f"   Duration: {duration/60:.2f} minutes")
    print(f"   Assets  : {project_dir / 'assets'}/ (place cover image here for video)")
    return project_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Voice-cloning multi-speaker podcast generator")
    parser.add_argument("--script",    required=True, help="Path to dialogue script file")
    parser.add_argument("--title",     default="New_Podcast", help="Podcast title (used in folder name)")
    parser.add_argument("--voice-map", default="", dest="voice_map",
                        help="Override voice profiles: 'Name:path/to/ref.wav,...'")
    parser.add_argument("--limit",     type=int, default=600, help="Max duration warning threshold (seconds)")
    args = parser.parse_args()

    script_path = Path(args.script)
    if script_path.exists():
        script_text = script_path.read_text()
    else:
        print(f"❌ Script file not found: {args.script}")
        sys.exit(1)

    vm_override = build_voice_map(args.voice_map)
    result = generate_podcast(script_text, args.title, vm_override, args.limit)
    if result is None:
        sys.exit(1)
