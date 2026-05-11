---
name: podcast_generator
description: Combine LLMs (Gemini Nano) and Makix CLI to generate complete 5-minute podcasts with multiple speakers.
---

# Podcast Generator Skill

This skill allows you to automate the creation of a multi-speaker podcast. It integrates local LLMs for script generation, the Makix Studio CLI for high-quality TTS, and Linux audio tools (`ffmpeg`) for post-production.

## Workflow

1.  **Project Discovery**: Clarify if the podcast is a **Monologue** (solo deep dive), **Dialogue** (host + guest), or a **Panel** (multiple experts).
2.  **Voice Mapping**: Select appropriate reference voices (`.wav` clones) for each speaker's personality.
3.  **Script Generation**: Use an LLM to generate a script tailored to the chosen format (~150 words/min).
4.  **Audio Synthesis**: The orchestrator script calls the Makix CLI/Engine for each dialogue segment.
5.  **Concatenation**: Standard Linux tools (`ffmpeg`) join segments into a seamless podcast.
6.  **Duration Control**: Ensures the podcast stays within the requested limit (e.g., 6+ minutes).
7.  **Project Organization**: Assets are automatically structured into a dedicated project folder.

## Usage Instructions

### Step 1: Clarify Format & Voices
Before generating, always confirm:
- **Format**: Monologue, Dialogue (2 people), or Discussion (3+ people).
- **Voice Selection**: Choose specific `.wav` files from `podcasts/voices/` to match the speaker's role (e.g., use a deep, authoritative voice for a "Security Expert").

### Step 2: Generate the Script
Target ~150 words per minute of desired audio.
- For a **6-minute** podcast, target **900-1000 words**.
- Use the following format for multi-speaker scripts:
```text
Host: Welcome to today's tech briefing! I'm Ryan.
Guest: And I'm Vivian. Today we're talking about local AI.
```

### Step 3: Run the Orchestrator
Use `make_podcast_clone.py` for voice cloning:

```bash
./venv/bin/python .agent/skills/podcast_generator/scripts/make_podcast_clone.py \
    --script "my_script.txt" \
    --title "My_Podcast" \
    --voice-map "SpeakerName:path/to/voice.wav"
```

## Project Directory Structure
Every generation creates a new project folder in `podcasts/YYYYMMDD_HHMMSS_Title/`:

- **`script.txt`**: The original source dialogue.
- **`audio_final.wav`**: The complete, concatenated podcast file.
- **`metadata.json`**: Technical details (duration, segment count, model).
- **`segments/`**: Individual audio files for each line of dialogue.
- **`assets/`**: Dedicated folder for **images** and the **final video** file.

## Features & Parameters

| Feature | Description |
| :--- | :--- |
| **Speaker Mapping** | Automatically maps "Host" to Ryan and "Guest" to Vivian. |
| **Project Isolation** | Each podcast has its own self-contained directory. |
| **Auto-Concatenate** | Uses `ffmpeg` concat demuxer for zero-loss merging. |

## Linux Toolkit Integration
The skill relies on the following standard tools:
- `ffmpeg`: For concatenating audio segments.
- `ffprobe`: For duration verification.
- `cat/sed/grep`: (Internal) For script parsing and cleanup.

## Best Practices for Natural Dialogue

To make the podcast "attractive" and "human-like," follow these script-writing tips:
- **Interjections**: Use "Hmm," "Right," "Exactly," or "That's a great point" to simulate active listening.
- **Micro-Pauses**: Use ellipses (...) for natural hesitation.
- **Conversational Fillers**: Use "You know," "Actually," or "I mean" to avoid sounding like a lecture.
- **Emotional Variation**: Design the script so speakers react to each other's points with surprise or concern.
- **Parallelism**: The `StudioEngine` processes segment-by-segment to manage VRAM effectively.
- **Natural Pauses**: A 0.1s silence is added between segments for natural pacing.
- **Visuals**: Use the `generate_image` tool to create covers or video frames and save them in the project's `assets/` folder.
- **Visual Style**: Aim for a **"8-bit retro cartoon image illustration style"** for covers to maintain a unique, stylized brand identity unless otherwise specified.
- **Video Assembly**: Once audio and images are ready, use `make_video.py` to combine them into a final `.mp4`.

## Example Command (Single Line)
```bash
python .agent/skills/podcast_generator/scripts/make_podcast.py --script "$(cat script.txt)" --title "Daily_Update"
```
