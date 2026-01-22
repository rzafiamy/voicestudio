import argparse
import sys
from pathlib import Path
import torch
import soundfile as sf
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.traceback import install

# Install rich traceback handler for nicer error messages
install()

# Initialize Rich Console
console = Console()

def parse_args():
    parser = argparse.ArgumentParser(description="Run Qwen3 TTS Inference with Rich CLI")
    
    parser.add_argument(
        "--text", 
        nargs="+", 
        required=True, 
        help="Text to generate speech for. Can provide multiple text strings for batch processing."
    )
    
    parser.add_argument(
        "--speaker", 
        nargs="+", 
        required=True, 
        help="Speaker name(s). If one is provided, it applies to all texts."
    )
    
    parser.add_argument(
        "--language", 
        nargs="+", 
        default=["Auto"], 
        help="Language(s). Default is 'Auto'. If one is provided, it applies to all texts."
    )
    
    parser.add_argument(
        "--instruct", 
        nargs="+", 
        default=[""], 
        help="Instruction text(s) for style/emotion. Default is empty. If one is provided, it applies to all texts."
    )
    
    parser.add_argument(
        "--output", 
        nargs="+", 
        default=["output_{}.wav"], 
        help="Output filename(s). Use '{}' as a placeholder for index if providing a single template."
    )
    
    parser.add_argument(
        "--model-path", 
        type=str, 
        default="Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", 
        help="Path to the model or HuggingFace model ID."
    )
    
    return parser.parse_args()

def broadcast_arg(arg_list, target_length, arg_name):
    """
    Broadcasts a list to the target length.
    If list has 1 item, repeats it.
    If list has target_length items, returns as is.
    Otherwise, raises ValueError.
    """
    if len(arg_list) == 1:
        return arg_list * target_length
    elif len(arg_list) == target_length:
        return arg_list
    else:
        # Special case for defaults that might be passed as single-item lists by argparse default
        if len(arg_list) == 0:
             # Should not happen with nargs='+' unless empty list passed explicitly somehow?
             # For defaults like ["Auto"], it falls into len=1 bucket.
             return [None] * target_length 
        
        console.print(f"[bold red]Error:[/bold red] Argument [cyan]--{arg_name}[/cyan] has {len(arg_list)} items, but expected {target_length} (matching --text).")
        sys.exit(1)

def main():
    args = parse_args()
    
    num_texts = len(args.text)
    console.print(Panel(f"Starting Inference for [bold green]{num_texts}[/bold green] item(s)", title="Qwen3 TTS CLI"))

    # Validate and broadcast arguments
    speakers = broadcast_arg(args.speaker, num_texts, "speaker")
    languages = broadcast_arg(args.language, num_texts, "language")
    instructs = broadcast_arg(args.instruct, num_texts, "instruct")
    
    # Handle output filenames
    outputs = args.output
    if len(outputs) == 1 and "{}" in outputs[0]:
        # Template provided
        outputs = [outputs[0].format(i+1) for i in range(num_texts)]
    elif len(outputs) == 1 and num_texts > 1:
        # Single filename provided for multiple outputs - might be ambiguous, but let's append index
        base = Path(outputs[0])
        outputs = [f"{base.stem}_{i+1}{base.suffix}" for i in range(num_texts)]
    elif len(outputs) != num_texts:
         console.print(f"[bold red]Error:[/bold red] Argument [cyan]--output[/cyan] has {len(outputs)} items, but expected {num_texts}.")
         sys.exit(1)

    # Load Model
    try:
        # Conditional import check or just try/except
        try:
            from qwen_tts import Qwen3TTSModel
        except ImportError:
            console.print("[bold red]Error:[/bold red] Could not import 'qwen_tts'. Make sure it is installed or in the python path.")
            sys.exit(1)

        with console.status("[bold blue]Loading Qwen3TTSModel...[/bold blue]"):
            model = Qwen3TTSModel.from_pretrained(
                args.model_path,
                device_map="cuda:0",
                dtype=torch.bfloat16,
                #attn_implementation="flash_attention_2",
            )
        console.print(f"[bold green]✓[/bold green] Model loaded from {args.model_path}")

    except Exception as e:
        console.print(f"[bold red]Failed to load model:[/bold red] {e}")
        sys.exit(1)

    # Generate
    try:
        with console.status("[bold yellow]Generating audio...[/bold yellow]"):
            # Prepare batch arguments
            # Note: generate_custom_voice takes lists for batch inference
            wavs, sr = model.generate_custom_voice(
                text=args.text,
                language=languages,
                speaker=speakers,
                instruct=instructs,
            )
        
        console.print(f"[bold green]✓[/bold green] Generation complete. Sample rate: {sr}")

    except Exception as e:
        console.print(f"[bold red]Generation failed:[/bold red] {e}")
        sys.exit(1)

    # Save outputs
    for i, (wav, filename) in enumerate(zip(wavs, outputs)):
        try:
            sf.write(filename, wav, sr)
            console.print(f"  [green]Saved[/green] -> [bold]{filename}[/bold]")
        except Exception as e:
            console.print(f"  [red]Failed to save {filename}:[/red] {e}")

    console.print(Panel("[bold green]All tasks finished successfully![/bold green]", border_style="green"))

if __name__ == "__main__":
    main()
