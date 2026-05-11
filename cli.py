import argparse
import os
import sys
import time
import threading
from pathlib import Path

import torch
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.layout import Layout
from rich.align import Align
from rich.text import Text
from rich import box

from engine import StudioEngine, CUSTOM_VOICES, SUPPORTED_LANGUAGES

console = Console()
engine = StudioEngine()

class StudioCLI:
    def __init__(self, args=None):
        self.engine = engine
        self.args = args
        self.running = True

    def clear(self):
        console.clear()

    def header(self):
        vram = self.engine.get_vram_status()
        vram_text = ""
        if vram:
            vram_gb = vram['reserved'] / 1024**3
            total_gb = vram['total'] / 1024**3
            vram_text = f"[bold magenta]VRAM:[/] {vram_gb:.1f}/{total_gb:.1f} GB ({vram['percentage']:.1f}%)"
        
        model_text = f"[bold cyan]Model:[/] {os.path.basename(self.engine.model_name or 'None')}"
        
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")
        grid.add_row(
            Text.from_markup(f"🎵 [bold gradient(from=blue, to=purple)]Makix Studio CLI[/] | {model_text}"),
            Text.from_markup(vram_text)
        )
        
        console.print(Panel(grid, style="blue", box=box.ROUNDED))

    def show_main_menu(self):
        table = Table(box=box.SIMPLE, show_header=False)
        table.add_column("Key", style="bold yellow")
        table.add_column("Action", style="white")
        
        table.add_row("1", "Generate Audio")
        table.add_row("2", "Switch Model")
        table.add_row("3", "View History")
        table.add_row("4", "System Info")
        table.add_row("q", "Quit")
        
        console.print(Panel(table, title="Main Menu", border_style="green", expand=False))

    def run(self):
        # If we have text in args, run direct mode
        if self.args and self.args.text:
            self.run_direct()
            return

        # Otherwise run interactive mode
        default_model = getattr(self.args, 'model', None) or os.getenv("DEFAULT_MODEL", "./Qwen3-TTS-12Hz-1.7B-CustomVoice")
        self.switch_model(default_model)

        while self.running:
            self.clear()
            self.header()
            self.show_main_menu()
            
            choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "q"], default="1")
            
            if choice == "1":
                self.generate_menu()
            elif choice == "2":
                self.switch_model_menu()
            elif choice == "3":
                self.history_menu()
            elif choice == "4":
                self.system_info()
            elif choice == "q":
                self.running = False

    def run_direct(self):
        """Non-interactive generation mode based on CLI arguments"""
        model_path = self.args.model or os.getenv("DEFAULT_MODEL", "./Qwen3-TTS-12Hz-1.7B-CustomVoice")
        
        with console.status(f"[cyan]Loading model {os.path.basename(model_path)}..."):
            self.engine.load_model(model_path)
            
        if not self.engine.model:
            console.print("[bold red]Failed to load model.[/]")
            return

        console.print(f"🚀 [bold green]Generating:[/] [white]{self.args.text[:50]}...[/]")
        
        try:
            meta = self.engine.generate(
                text=self.args.text,
                language=self.args.language or "Auto",
                speaker=self.args.speaker or "Ryan",
                instruct=self.args.instruct or "",
                ref_audio_path=self.args.ref_audio or "",
                ref_text=self.args.ref_text or ""
            )
            
            if meta:
                console.print(f"✅ [bold green]Done![/] File: [bold cyan]{meta['filename']}[/]")
                console.print(f"📊 Speed: {meta['chars_per_sec']:.2f} ch/s | RTF: {meta['rtf']:.2f}")
                
                if self.args.play:
                    os.system(f"ffplay -nodisp -autoexit storage/{meta['filename']} > /dev/null 2>&1 || aplay storage/{meta['filename']} > /dev/null 2>&1")
            else:
                console.print("[bold red]Generation failed.[/]")
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")

    def switch_model(self, model_path):
        def load_task(progress):
            task = progress.add_task("[cyan]Loading model...", total=100)
            
            thread = threading.Thread(target=self.engine.load_model, args=(model_path,), daemon=True)
            thread.start()
            
            while thread.is_alive() or self.engine.model_status["status"] != "ready":
                status = self.engine.model_status
                progress.update(task, completed=status["progress"], description=f"[cyan]{status['message']}")
                if status["status"] == "error":
                    console.print(f"[bold red]Error loading model: {status['last_error']}")
                    break
                time.sleep(0.1)
            
            progress.update(task, completed=100, description="[green]Model Ready!")
            time.sleep(0.5)

        with Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            load_task(progress)

    def switch_model_menu(self):
        self.clear()
        self.header()
        
        models = self.engine.discover_local_models()
        table = Table(title="Available Models", box=box.DOUBLE)
        table.add_column("#", justify="right", style="cyan", no_wrap=True)
        table.add_column("Model Path", style="magenta")
        
        for i, m in enumerate(models):
            table.add_row(str(i+1), m)
            
        console.print(table)
        
        choice = Prompt.ask("Select model # (or 'b' to go back)")
        if choice.lower() == 'b':
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                self.switch_model(models[idx])
        except ValueError:
            console.print("[red]Invalid selection[/]")
            time.sleep(1)

    def generate_menu(self):
        if not self.engine.model:
            console.print("[bold red]No model loaded! Please switch to a model first.[/]")
            time.sleep(2)
            return

        self.clear()
        self.header()
        
        console.print(f"[bold green]Mode: {self.engine.model_type}[/]")
        
        text = Prompt.ask("Enter text to synthesize")
        if not text:
            return

        language = Prompt.ask("Language", choices=SUPPORTED_LANGUAGES, default="Auto")
        
        speaker = "Vivian"
        instruct = ""
        ref_audio = ""
        ref_text = ""
        
        if self.engine.model_type == "CustomVoice":
            speakers = list(CUSTOM_VOICES.keys())
            speaker = Prompt.ask("Select Speaker", choices=speakers, default="Ryan")
            instruct = Prompt.ask("Voice Instruction (optional)", default="")
        elif self.engine.model_type == "VoiceDesign":
            instruct = Prompt.ask("Describe the voice (e.g. 'A high-pitched female voice, very excited')")
            if not instruct:
                console.print("[red]Instruction is required for VoiceDesign[/]")
                time.sleep(1)
                return
        elif self.engine.model_type == "Base":
            ref_audio = Prompt.ask("Path to reference audio file")
            ref_text = Prompt.ask("Reference text (optional, for better cloning)", default="")

        self.clear()
        self.header()
        console.print(Panel(text, title="Input Text", border_style="blue"))
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold yellow]Synthesizing audio..."),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task("synthesizing", total=None)
            try:
                meta = self.engine.generate(
                    text=text,
                    language=language,
                    speaker=speaker,
                    instruct=instruct,
                    ref_audio_path=ref_audio,
                    ref_text=ref_text
                )
                progress.stop()
                
                if meta:
                    console.print(f"\n[bold green]Success![/]")
                    console.print(f"File saved: [bold cyan]{meta['filename']}[/]")
                    console.print(f"Speed: [bold magenta]{meta['chars_per_sec']:.2f} ch/s[/] | RTF: [bold magenta]{meta['rtf']:.2f}[/]")
                    
                    if Confirm.ask("Do you want to play the audio? (requires 'ffplay' or 'aplay')"):
                        os.system(f"ffplay -nodisp -autoexit storage/{meta['filename']} > /dev/null 2>&1 || aplay storage/{meta['filename']} > /dev/null 2>&1")
                else:
                    console.print("[bold red]Failed to generate audio.[/]")
            except Exception as e:
                progress.stop()
                console.print(f"[bold red]Error during generation: {e}[/]")
        
        Prompt.ask("\nPress Enter to continue")

    def history_menu(self):
        self.clear()
        self.header()
        
        history = self.engine.get_history()
        if not history:
            console.print("[yellow]No history yet.[/]")
            Prompt.ask("Press Enter to continue")
            return
            
        table = Table(title="Recent Generations", box=box.MINIMAL_DOUBLE_HEAD)
        table.add_column("#", justify="right", style="cyan")
        table.add_column("Time", style="white")
        table.add_column("Text", style="green", max_width=40)
        table.add_column("Model", style="blue")
        table.add_column("File", style="magenta")
        
        for i, item in enumerate(history[:10]):
            ts = item.get('timestamp', '')
            table.add_row(
                str(i+1),
                ts,
                item.get('text', '')[:50] + "...",
                os.path.basename(item.get('model', 'Unknown')),
                item.get('filename', '')
            )
            
        console.print(table)
        
        choice = Prompt.ask("Enter # to play/view, or 'b' to go back")
        if choice.lower() == 'b':
            return
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(history):
                item = history[idx]
                console.print(Panel(item.get('text', ''), title="Full Text", border_style="green"))
                if Confirm.ask("Play this audio?"):
                    os.system(f"ffplay -nodisp -autoexit storage/{item['filename']} > /dev/null 2>&1 || aplay storage/{item['filename']} > /dev/null 2>&1")
        except:
            pass

    def system_info(self):
        self.clear()
        self.header()
        
        vram = self.engine.get_vram_status()
        
        info_table = Table(show_header=False, box=box.ROUNDED)
        info_table.add_row("CUDA Available", "[green]Yes" if torch.cuda.is_available() else "[red]No")
        if vram:
            info_table.add_row("GPU Device", vram['device'])
            info_table.add_row("VRAM Total", f"{vram['total'] / 1024**3:.2f} GB")
            info_table.add_row("VRAM Reserved", f"{vram['reserved'] / 1024**3:.2f} GB")
            info_table.add_row("VRAM Allocated", f"{vram['allocated'] / 1024**3:.2f} GB")
        
        info_table.add_row("Torch Compile", "[green]Enabled" if self.engine.use_compile else "[yellow]Disabled")
        info_table.add_row("4-bit Quantization", "[green]Enabled" if self.engine.load_in_4bit else "[yellow]Disabled")
        
        console.print(Panel(info_table, title="System Status", expand=False))
        Prompt.ask("Press Enter to continue")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    parser = argparse.ArgumentParser(description="Makix Studio CLI")
    parser.add_argument("--text", type=str, help="Text to synthesize (triggers non-interactive mode)")
    parser.add_argument("--model", type=str, help="Model path")
    parser.add_argument("--language", type=str, help="Language (Auto, Chinese, English, etc.)")
    parser.add_argument("--speaker", type=str, help="Speaker name (for CustomVoice mode)")
    parser.add_argument("--instruct", type=str, help="Voice instruction/description")
    parser.add_argument("--ref-audio", type=str, help="Path to reference audio for cloning")
    parser.add_argument("--ref-text", type=str, help="Reference text for cloning")
    parser.add_argument("--play", action="store_true", help="Play audio after generation")
    
    args = parser.parse_args()
    
    cli = StudioCLI(args)
    try:
        cli.run()
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user. Exiting...[/]")
        sys.exit(0)
