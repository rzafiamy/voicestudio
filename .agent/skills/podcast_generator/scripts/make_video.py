#!/usr/bin/env python3
"""
make_video.py — Assemble a podcast video from a cover image + audio file.
Usage:
    python make_video.py --project podcasts/YYYYMMDD_HHMMSS_Title
                         --cover   /path/to/cover.png
"""
import argparse
import subprocess
import sys
from pathlib import Path


def get_audio_duration(audio_path: Path) -> float:
    result = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path)
    ])
    return float(result.decode().strip())


def make_video(project_dir: Path, cover_image: Path):
    audio_path  = project_dir / "audio_final.wav"
    assets_dir  = project_dir / "assets"
    output_video = assets_dir / "podcast_video.mp4"

    assets_dir.mkdir(exist_ok=True)

    if not audio_path.exists():
        print(f"❌ Audio file not found: {audio_path}")
        sys.exit(1)
    if not cover_image.exists():
        print(f"❌ Cover image not found: {cover_image}")
        sys.exit(1)

    duration = get_audio_duration(audio_path)
    print(f"🎬 Audio duration: {duration:.1f}s ({duration/60:.2f} min)")
    print(f"🖼️  Cover image:   {cover_image}")
    print(f"📁 Output:         {output_video}")

    # Build video with a subtle Ken-Burns zoom on the cover image
    # zoompan filter: slow zoom from 1.0→1.05 over the whole duration
    fps = 25

    cmd = [
        "ffmpeg", "-y",
        # Static image loop
        "-loop", "1",
        "-framerate", str(fps),
        "-i", str(cover_image),
        # Audio
        "-i", str(audio_path),
        # Scale preserving aspect ratio, then pad to 1920x1080 with black bars
        "-vf", (
            "scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black"
        ),
        # Encoding
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        # Trim to exact audio duration
        "-t", str(duration),
        "-shortest",
        str(output_video)
    ]

    print("⚙️  Running ffmpeg …")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("❌ ffmpeg failed:")
        print(result.stderr[-3000:])
        sys.exit(1)

    size_mb = output_video.stat().st_size / 1_048_576
    print(f"✅ Video created: {output_video}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Assemble podcast video from image + audio.")
    parser.add_argument("--project", required=True, help="Path to the podcast project folder")
    parser.add_argument("--cover",   required=True, help="Path to the cover image (PNG/JPG)")
    args = parser.parse_args()

    make_video(Path(args.project), Path(args.cover))
