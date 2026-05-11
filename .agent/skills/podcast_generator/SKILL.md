---
name: podcast_generator
description: Combine LLMs (Gemini Nano) and Makix CLI to generate complete 5-minute podcasts with multiple speakers.
---

# Podcast Generator Skill

This skill allows you to automate the creation of a multi-speaker podcast. It integrates local LLMs for script generation, the Makix Studio CLI for high-quality TTS, and Linux audio tools (`ffmpeg`) for post-production.

## Workflow

1.  **Script Generation**: Use an LLM (e.g., Gemini Nano) to generate a dialogue script.
2.  **Audio Synthesis**: The orchestrator script calls the Makix CLI for each dialogue segment.
3.  **Concatenation**: Standard Linux tools (`ffmpeg`) join segments into a seamless podcast.
4.  **Duration Control**: Ensures the podcast stays within the 5-minute limit (~750-900 words).
5.  **Project Organization**: Assets are automatically structured into a dedicated project folder.

## Usage Instructions

### Step 1: Generate the Script
Ask the LLM to generate a script in the following format:
```text
Host: Welcome to today's tech briefing! I'm Ryan.
Guest: And I'm Vivian. Today we're talking about local AI.
Host: It's an exciting time for on-device models...
```
*Tip: To hit the 5-minute mark, target approximately 800 words.*

### Step 2: Run the Orchestrator
Use the provided `make_podcast.py` script to generate the project.

```bash
python .agent/skills/podcast_generator/scripts/make_podcast.py \
    --script "my_podcast_script.txt" \
    --title "Local_AI_Discussion" \
    --limit 300
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
| **Safety Limit** | Warns if the generated audio exceeds the 5-minute threshold. |

## Linux Toolkit Integration
The skill relies on the following standard tools:
- `ffmpeg`: For concatenating audio segments.
- `ffprobe`: For duration verification.
- `cat/sed/grep`: (Internal) For script parsing and cleanup.

## Best Practices
- **Parallelism**: The `StudioEngine` processes segment-by-segment to manage VRAM effectively.
- **Natural Pauses**: A 0.1s silence is added between segments for natural pacing.
- **Visuals**: Use the `generate_image` tool to create covers or video frames and save them in the project's `assets/` folder.
- **Video Assembly**: Once audio and images are ready, use `ffmpeg` to combine them into a final `.mp4` video inside the `assets/` directory.

## Example Command (Single Line)
```bash
python .agent/skills/podcast_generator/scripts/make_podcast.py --script "$(cat script.txt)" --title "Daily_Update"
```
