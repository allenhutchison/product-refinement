"""Command line interface for the product refinement tool."""
import logging
import os
import sys
from typing import Dict, List, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..ai.service import AIService
from ..utils.config import Config
from ..utils.display import (
    display_banner,
    display_error,
    display_info,
    display_success,
    display_warning,
    format_spec_as_markdown,
    ask_user
)
from ..utils.storage import SpecificationManager
from ..utils.validation import Validator, ValidationError

console = Console()

def initialize_logging(config: Config) -> None:
    """Initialize logging configuration."""
    # Create log directory if it doesn't exist
    os.makedirs(config.LOG_DIR, exist_ok=True)
    
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(config.LOG_DIR, 'product_refinement.log')),
            logging.StreamHandler(sys.stdout)
        ]
    )

def create_spec(config: Config) -> None:
    """Create a new product specification."""
    display_banner("Create New Product Specification")
    
    # Get product description
    while True:
        try:
            description = ask_user("\nPlease describe your product idea:")
            Validator.not_empty(description)
            break
        except ValidationError as e:
            display_error(str(e))
    
    # Initialize AI service
    ai_service = AIService(config)
    
    # Generate initial specification
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Generating initial specification...", total=None)
        initial_spec = ai_service.generate_initial_spec(description)
    
    if initial_spec.startswith("Error"):
        display_error("Failed to generate initial specification.")
        return
    
    # Display initial specification
    console.print("\n📝 Initial Specification:")
    console.print(format_spec_as_markdown(initial_spec))
    
    # Refine specification through questions
    spec = initial_spec
    answered_questions = []
    
    while True:
        # Format answered questions for the prompt
        answered_questions_text = "\n".join([
            f"Q: {q['question']}\nA: {q['answer']}"
            for q in answered_questions
        ])
        
        # Get follow-up questions
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Generating follow-up questions...", total=None)
            questions = ai_service.get_follow_up_questions(spec, answered_questions_text)
        
        if not questions:
            break
        
        # Ask each question
        for question in questions:
            display_info(f"\n📋 Section: {question['section']}")
            while True:
                answer = ask_user(f"{question['question']} (type 'skip' to skip, 'done' to finish)")
                
                if answer.lower() == 'done':
                    questions = []  # Clear remaining questions
                    break
                elif answer.lower() == 'skip':
                    break
                
                try:
                    Validator.not_empty(answer)
                    answered_questions.append({
                        'section': question['section'],
                        'question': question['question'],
                        'answer': answer
                    })
                    break
                except ValidationError as e:
                    display_error(str(e))
        
        if not questions:  # User typed 'done' or no more questions
            break
        
        # Update specification with answers
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            progress.add_task(description="Updating specification...", total=None)
            spec = ai_service.finalize_spec(spec)
        
        # Display updated specification
        console.print("\n📝 Updated Specification:")
        console.print(format_spec_as_markdown(spec))
    
    # Get project name suggestion
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Suggesting project name...", total=None)
        project_name = ai_service.suggest_project_name(spec)
    
    # Save specification
    try:
        spec_manager = SpecificationManager(config)
        spec_manager.save_specification(project_name, spec)
        display_success(f"\n✅ Specification saved as '{project_name}'")
    except Exception as e:
        display_error(f"Failed to save specification: {str(e)}")

def list_specs(config: Config) -> None:
    """List all saved specifications."""
    display_banner("Saved Specifications")
    
    try:
        spec_manager = SpecificationManager(config)
        specs = spec_manager.list_specifications()
        
        if not specs:
            display_info("No specifications found.")
            return
        
        for project_dir, versions in specs.items():
            console.print(f"\n📁 {project_dir}")
            for version in versions:
                console.print(
                    f"  └─ {version.formatted_timestamp} - "
                    f"v{version.version} - {version.filename}"
                )
    except Exception as e:
        display_error(f"Failed to list specifications: {str(e)}")

def edit_spec(config: Config, spec_path: str) -> None:
    """Edit an existing specification."""
    display_banner("Edit Specification")
    
    try:
        spec_manager = SpecificationManager(config)
        spec_data = spec_manager.load_specification(spec_path)
        
        if not spec_data:
            display_error(f"Specification not found: {spec_path}")
            return
        
        # Display current specification
        console.print("\n📝 Current Specification:")
        console.print(format_spec_as_markdown(spec_data['specification']))
        
        # Initialize AI service
        ai_service = AIService(config)
        
        # Start refinement process
        spec = spec_data['specification']
        answered_questions = []
        
        while True:
            # Format answered questions for the prompt
            answered_questions_text = "\n".join([
                f"Q: {q['question']}\nA: {q['answer']}"
                for q in answered_questions
            ])
            
            # Get follow-up questions
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="Generating follow-up questions...", total=None)
                questions = ai_service.get_follow_up_questions(spec, answered_questions_text)
            
            if not questions:
                break
            
            # Ask each question
            for question in questions:
                display_info(f"\n📋 Section: {question['section']}")
                while True:
                    answer = ask_user(f"{question['question']} (type 'skip' to skip, 'done' to finish)")
                    
                    if answer.lower() == 'done':
                        questions = []  # Clear remaining questions
                        break
                    elif answer.lower() == 'skip':
                        break
                    
                    try:
                        Validator.not_empty(answer)
                        answered_questions.append({
                            'section': question['section'],
                            'question': question['question'],
                            'answer': answer
                        })
                        break
                    except ValidationError as e:
                        display_error(str(e))
            
            if not questions:  # User typed 'done' or no more questions
                break
            
            # Update specification with answers
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="Updating specification...", total=None)
                spec = ai_service.finalize_spec(spec)
            
            # Display updated specification
            console.print("\n📝 Updated Specification:")
            console.print(format_spec_as_markdown(spec))
        
        # Save updated specification
        try:
            spec_manager.save_specification(spec_data['product_name'], spec)
            display_success(f"\n✅ Specification updated successfully")
        except Exception as e:
            display_error(f"Failed to save specification: {str(e)}")
            
    except Exception as e:
        display_error(f"Failed to edit specification: {str(e)}")

@click.group()
@click.option('--model', help='AI model to use')
@click.option('--log-level', help='Logging level (DEBUG, INFO, WARNING, ERROR)')
@click.pass_context
def cli(ctx: click.Context, model: Optional[str], log_level: Optional[str]) -> None:
    """Product Refinement Tool - Generate and refine product specifications using AI."""
    # Initialize configuration
    config = Config()
    
    # Override settings from command line
    if model:
        config.MODEL_NAME = model
    if log_level:
        config.LOG_LEVEL = getattr(logging, log_level.upper())
    
    # Initialize logging
    initialize_logging(config)
    
    # Store config in context
    ctx.obj = config

@cli.command()
@click.pass_obj
def create(config: Config) -> None:
    """Create a new product specification."""
    create_spec(config)

@cli.command()
@click.pass_obj
def list(config: Config) -> None:
    """List all saved specifications."""
    list_specs(config)

@cli.command()
@click.argument('spec_path')
@click.pass_obj
def edit(config: Config, spec_path: str) -> None:
    """Edit an existing specification."""
    edit_spec(config, spec_path)

if __name__ == '__main__':
    cli() 