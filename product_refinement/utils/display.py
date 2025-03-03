"""Display utilities for the command line interface."""
from typing import Any

# Add colorful output and progress indicators
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.markdown import Markdown
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

def format_spec_as_markdown(spec: str) -> Any:
    """Format specification as markdown if rich is available."""
    if RICH_AVAILABLE:
        return Markdown(spec)
    return spec

def display_banner(title: str) -> None:
    """Display a banner with the title."""
    if RICH_AVAILABLE:
        console.print(Panel(f"[bold]{title}[/bold]", border_style="blue"))
    else:
        print("\n" + "=" * 80)
        print(f" {title} ".center(80))
        print("=" * 80)

def ask_user(prompt: str) -> str:
    """Ask user for input with enhanced UI if available."""
    if RICH_AVAILABLE:
        return Prompt.ask(f"[bold cyan]{prompt}[/bold cyan]")
    else:
        return input(f"{prompt} ")

def display_success(message: str) -> None:
    """Display a success message."""
    if RICH_AVAILABLE:
        console.print(f"[bold green]✓[/bold green] {message}")
    else:
        print(f"✓ {message}")

def display_error(message: str) -> None:
    """Display an error message."""
    if RICH_AVAILABLE:
        console.print(f"[bold red]✗[/bold red] {message}")
    else:
        print(f"✗ {message}")

def display_warning(message: str) -> None:
    """Display a warning message."""
    if RICH_AVAILABLE:
        console.print(f"[bold yellow]⚠[/bold yellow] {message}")
    else:
        print(f"⚠ {message}")

def display_info(message: str) -> None:
    """Display an informational message."""
    if RICH_AVAILABLE:
        console.print(f"[bold blue]ℹ[/bold blue] {message}")
    else:
        print(f"ℹ {message}")

class DummyProgress:
    """Dummy progress class for when rich is not available."""
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def start(self):
        print("Processing...")
    
    def stop(self):
        pass 