"""Command line interface for the product refinement tool."""
import logging
import os
import sys
import json
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
    
    # Set httpx logger to WARNING level to suppress INFO messages
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
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
                    f"  └─ {version['formatted_timestamp']} - "
                    f"v{version['version']} - {version['filename']}"
                )
    except Exception as e:
        display_error(f"Failed to list specifications: {str(e)}")

def edit_spec(config: Config, spec_path: Optional[str] = None) -> None:
    """Edit an existing specification."""
    display_banner("Edit Specification")
    
    try:
        spec_manager = SpecificationManager(config)
        specs = spec_manager.list_specifications()
        
        if not specs:
            display_info("No specifications found.")
            return
        
        # If no spec_path provided, show selection menu
        if not spec_path:
            # Create a flat list of all specifications with their paths
            all_specs = []
            for project_dir, versions in specs.items():
                for version in versions:
                    all_specs.append({
                        'path': os.path.join(project_dir, version['filename']),
                        'project': project_dir,
                        'version': version
                    })
            
            if not all_specs:
                display_info("No specifications found.")
                return
            
            # Display numbered list of specifications
            console.print("\nAvailable specifications:")
            for i, spec in enumerate(all_specs, 1):
                console.print(
                    f"{i}. {spec['project']} - "
                    f"v{spec['version']['version']} "
                    f"({spec['version']['formatted_timestamp']})"
                )
            
            # Get user selection
            while True:
                try:
                    selection = ask_user("\nEnter the number of the specification to edit (or 'q' to quit):")
                    if selection.lower() == 'q':
                        return
                    
                    index = int(selection) - 1
                    if 0 <= index < len(all_specs):
                        spec_path = all_specs[index]['path']
                        break
                    else:
                        display_error("Invalid selection. Please try again.")
                except ValueError:
                    display_error("Please enter a valid number.")
        
        else:
            # Check if spec_path is a directory (project name)
            full_dir_path = os.path.join(config.SPECS_DIR, spec_path)
            if os.path.isdir(full_dir_path) and spec_path in specs:
                # Select the most recent version from the directory
                versions = specs[spec_path]
                if versions:
                    # Sort by version number (descending) and take the first one
                    latest_version = sorted(versions, key=lambda v: v['version'], reverse=True)[0]
                    spec_path = os.path.join(full_dir_path, latest_version['filename'])
                    display_info(f"Using latest version: {latest_version['filename']}")
                else:
                    display_error(f"No specification files found in project: {spec_path}")
                    return
        
        # Load and display the specification
        spec_data = spec_manager.load_specification(spec_path)
        if not spec_data:
            display_error(f"Specification not found: {spec_path}")
            return
        
        # Show preview
        console.print("\n📝 Current Specification:")
        console.print(format_spec_as_markdown(spec_data['specification']))
        
        # Ask for confirmation
        if not ask_user("\nWould you like to edit this specification? (yes/no)").lower().startswith('y'):
            display_info("Edit cancelled.")
            return
        
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
            
            # Ask if user wants to continue refining
            if not ask_user("\nWould you like to continue refining? (yes/no)").lower().startswith('y'):
                break
        
        # Show final preview and ask for confirmation
        console.print("\n📝 Final Specification:")
        console.print(format_spec_as_markdown(spec))
        
        if ask_user("\nWould you like to save these changes? (yes/no)").lower().startswith('y'):
            try:
                spec_manager.save_specification(spec_data['product_name'], spec)
                display_success(f"\n✅ Specification updated successfully")
            except Exception as e:
                display_error(f"Failed to save specification: {str(e)}")
        else:
            display_info("Changes not saved.")
            
    except Exception as e:
        display_error(f"Failed to edit specification: {str(e)}")

def generate_todo(config: Config, spec_path: Optional[str] = None) -> None:
    """
    Generate an engineering todo list from a product specification.
    
    Args:
        config (Config): The configuration object
        spec_path (Optional[str]): Path to the specification file
    """
    display_banner("Generate Engineering Todo List")
    
    # Define ANSI color codes for console output
    class COLORS:
        RESET = "\033[0m"
        BOLD = "\033[1m"
        BLUE = "\033[94m"
        GREEN = "\033[92m"
        YELLOW = "\033[93m"
        CYAN = "\033[96m"
        RED = "\033[91m"
    
    # Initialize logging
    initialize_logging(config)
    
    # Initialize spec manager
    spec_manager = SpecificationManager(config)
    
    # Get available specifications
    specs = spec_manager.list_specifications()
    
    if not specs:
        print("No specifications found. Please create a specification first.")
        return
    
    # If spec_path is not provided, show a list of available specs
    if not spec_path:
        # Create a flat list of all specifications with their paths
        all_specs = []
        for project_dir, versions in specs.items():
            for version in versions:
                # Construct the full path to the specification file
                full_path = os.path.join(config.SPECS_DIR, project_dir, version['filename'])
                all_specs.append({
                    'path': full_path,
                    'name': os.path.basename(project_dir),
                    'version': version['version'],
                    'date': version['formatted_timestamp']
                })
        
        print("\nAvailable specifications:")
        for i, spec in enumerate(all_specs, 1):
            print(f"{i}. {spec['name']} - v{spec['version']} ({spec['date']})")
        
        # Ask user to select a specification
        spec_choice = input("\nEnter the number of the specification to generate todo list from (or 'q' to quit):: ")
        if spec_choice.lower() == 'q':
            return
        
        try:
            spec_idx = int(spec_choice) - 1
            if spec_idx < 0 or spec_idx >= len(all_specs):
                print("Invalid selection.")
                return
                
            selected_spec = all_specs[spec_idx]
            spec_path = selected_spec['path']
        except ValueError:
            print("Invalid selection. Please enter a number.")
            return
    else:
        # If spec_path is provided but doesn't contain the full path, append the config.SPECS_DIR
        if not os.path.isabs(spec_path) and not os.path.exists(spec_path):
            potential_path = os.path.join(config.SPECS_DIR, spec_path)
            if os.path.exists(potential_path):
                spec_path = potential_path
    
    # Validate the provided spec_path
    if not os.path.exists(spec_path):
        print(f"Specification file not found: {spec_path}")
        return
    
    # Load the specification
    try:
        with open(spec_path, 'r') as f:
            spec_data = json.load(f)
            if isinstance(spec_data, dict) and 'specification' in spec_data:
                spec_content = spec_data['specification']
            else:
                spec_content = json.dumps(spec_data)  # Fallback if not in expected format
    except Exception as e:
        print(f"Error loading specification: {e}")
        return
    
    # Initialize AI service
    ai_service = AIService(config)
    
    try:
        # Generate todo list
        todo_list = ai_service.generate_todo_list(spec_content)
        
        if not todo_list or not todo_list.get("tasks"):
            print("✗ Failed to generate todo list")
            return
        
        # Display the todo list
        tasks_by_section = {}
        for task in todo_list["tasks"]:
            section = task.get("section", "General")
            if section not in tasks_by_section:
                tasks_by_section[section] = []
            tasks_by_section[section].append(task)
        
        # Print the todo list
        for section, tasks in tasks_by_section.items():
            print(f"\n{COLORS.BOLD}{COLORS.BLUE}## {section}{COLORS.RESET}")
            for task in tasks:
                print(f"\n{COLORS.BOLD}{task.get('title', 'Untitled Task')}{COLORS.RESET}")
                print(f"{COLORS.YELLOW}Complexity: {task.get('complexity', 'Unknown')}{COLORS.RESET}")
                
                if task.get('dependencies'):
                    print(f"{COLORS.YELLOW}Dependencies: {', '.join(task.get('dependencies', []))}{COLORS.RESET}")
                
                if task.get('description'):
                    print(f"\n{task.get('description')}")
                
                if task.get('technical_notes'):
                    print(f"\n{COLORS.CYAN}Technical Notes:{COLORS.RESET}\n{task.get('technical_notes')}")
                
                if task.get('testing_notes'):
                    print(f"\n{COLORS.GREEN}Testing Notes:{COLORS.RESET}\n{task.get('testing_notes')}")
        
        # Ask if user wants to save the todo list
        save_choice = input("\nWould you like to save this todo list? (y/n): ")
        if save_choice.lower().startswith('y'):
            # Save in the same directory as the spec file
            spec_dir = os.path.dirname(spec_path)
            spec_name = os.path.basename(spec_path)
            todo_filename = os.path.splitext(spec_name)[0] + "_todo.json"
            todo_path = os.path.join(spec_dir, todo_filename)
            
            try:
                with open(todo_path, 'w') as f:
                    json.dump(todo_list, f, indent=2)
                print(f"\nTodo list saved to: {todo_path}")
            except Exception as e:
                print(f"Error saving todo list: {e}")
    
    except Exception as e:
        print(f"✗ Failed to generate todo list: {str(e)}")

@click.group()
@click.option('--model', help='AI model to use')
@click.option('--log-level', help='Logging level (DEBUG, INFO, WARNING, ERROR)')
@click.option('--doc-type', help='Document type to work with (e.g., product_requirements)')
@click.pass_context
def cli(ctx: click.Context, model: Optional[str], log_level: Optional[str], doc_type: Optional[str]) -> None:
    """Product Refinement Tool - Generate and refine product specifications using AI."""
    # Initialize configuration
    config = Config()
    
    # Override settings from command line
    if model:
        config.MODEL_NAME = model
    if log_level:
        config.LOG_LEVEL = getattr(logging, log_level.upper())
    if doc_type:
        config.DOCUMENT_TYPE = doc_type
    
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
@click.argument('spec_path', required=False)
@click.pass_obj
def edit(config: Config, spec_path: Optional[str]) -> None:
    """Edit an existing specification."""
    edit_spec(config, spec_path)

@cli.command()
@click.argument('spec_path', required=False)
@click.pass_obj
def todo(config: Config, spec_path: Optional[str]) -> None:
    """Generate an engineering todo list from a specification."""
    generate_todo(config, spec_path)

if __name__ == '__main__':
    cli()