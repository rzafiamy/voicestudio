import os
import sys
import json
import argparse
import subprocess
import time
from pathlib import Path
from engine import StudioEngine

def parse_dialogue(text):
    """
    Parses dialogue in format:
    Speaker Name: Dialogue text
    """
    lines = text.strip().split('\n')
    segments = []
    for line in lines:
        if ':' in line:
            parts = line.split(':', 1)
            segments.append({
                "speaker": parts[0].strip(),
                "text": parts[1].strip()
            })
    return segments

def generate_podcast(script_text, title="Untitled Podcast", max_duration_sec=300):
    engine = StudioEngine()
    # Resolve to absolute path — HuggingFace hub rejects paths starting with "./"
    _default_model = os.getenv("DEFAULT_MODEL", "models/Qwen3-TTS-12Hz-1.7B-CustomVoice")
    _project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
    model_path = str((_project_root / _default_model).resolve())
    engine.load_model(model_path)
    
    # Setup Directory Structure
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    safe_title = "".join([c if c.isalnum() else "_" for c in title])
    project_dir = Path("podcasts") / f"{timestamp}_{safe_title}"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    segments_dir = project_dir / "segments"
    segments_dir.mkdir(exist_ok=True)
    
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    # Save Script
    script_path = project_dir / "script.txt"
    with open(script_path, "w") as f:
        f.write(script_text)
    
    segments = parse_dialogue(script_text)
    temp_files = []
    
    print(f"🎙️ Project: {project_dir}")
    print(f"🎙️ Starting podcast generation ({len(segments)} segments)...")
    
    speaker_map = {
        "Host": "Ryan",
        "Guest": "Vivian",
        "Ryan": "Ryan",
        "Vivian": "Vivian",
        "Aiden": "Aiden",
        "Serena": "Serena"
    }

    try:
        for i, seg in enumerate(segments):
            speaker = speaker_map.get(seg['speaker'], "Ryan")
            print(f"  [{i+1}/{len(segments)}] Generating {seg['speaker']} ({speaker})...")
            
            meta = engine.generate(
                text=seg['text'],
                speaker=speaker,
                language="Auto"
            )
            
            if meta:
                # Move generated wav to project segments
                src = Path("storage") / meta['filename']
                dst = segments_dir / f"seg_{i+1:03d}_{speaker}.wav"
                os.rename(src, dst)
                temp_files.append(dst)
            
        if not temp_files:
            print("❌ No audio generated.")
            return

        # Concatenate using ffmpeg
        list_file = project_dir / "concat_list.txt"
        with open(list_file, "w") as f:
            for tf in temp_files:
                f.write(f"file 'segments/{tf.name}'\n")
        
        output_audio = project_dir / "audio_final.wav"
        print(f"🔗 Concatenating into {output_audio.name}...")
        
        # We run ffmpeg from the project directory
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", list_file.name, "-c", "copy", output_audio.name
        ], cwd=project_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        os.remove(list_file)
        
        # Check duration
        duration_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(output_audio)]
        duration = float(subprocess.check_output(duration_cmd).decode().strip())
        
        # Save project metadata
        with open(project_dir / "metadata.json", "w") as f:
            json.dump({
                "title": title,
                "timestamp": timestamp,
                "duration": duration,
                "segments_count": len(segments),
                "model": engine.model_name
            }, f, indent=2)

        print(f"✅ Podcast complete!")
        print(f"   Audio:  {output_audio}")
        print(f"   Script: {script_path}")
        print(f"   Assets: {assets_dir}/ (Generated images & video should go here)")
        print(f"   Duration: {duration/60:.2f} minutes.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=str, required=True, help="Path to script or raw text")
    parser.add_argument("--title", type=str, default="New Podcast")
    parser.add_argument("--limit", type=int, default=300)
    args = parser.parse_args()
    
    script_content = ""
    if os.path.exists(args.script):
        with open(args.script, "r") as f:
            script_content = f.read()
    else:
        script_content = args.script
        
    generate_podcast(script_content, args.title, args.limit)
