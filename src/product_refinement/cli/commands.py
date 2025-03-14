"""Command line interface for the product refinement tool."""
import logging
import os
import sys
import json
from datetime import datetime
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
    display_banner(f"Create New {config.DOCUMENT_TYPE.replace('_', ' ').title()}")
    
    # Initialize AI service
    ai_service = AIService(config)
    
    # Check for dependencies
    dependencies = ai_service.get_document_dependencies()
    dependency_values = {}
    
    if dependencies:
        display_info("\nThis document type has dependencies:")
        
        for dep in dependencies:
            source_type = dep["source_type"]
            source_field = dep["source_field"]
            placeholder = dep["placeholder"]
            
            display_info(f"• Requires {source_field} from {source_type}")
            
            # We need to get the source document
            spec_manager = SpecificationManager(config)
            specs = spec_manager.list_specifications()
            
            if not specs:
                display_error(f"No specifications found. Please create a {source_type} document first.")
                return
                
            # Create a flat list of all specifications
            all_specs = []
            for project_dir, versions in specs.items():
                for version in versions:
                    all_specs.append({
                        'path': os.path.join(project_dir, version['filename']),
                        'project': project_dir,
                        'version': version
                    })
            
            # Display numbered list of specifications
            console.print("\nSelect a source document:")
            for i, spec in enumerate(all_specs, 1):
                console.print(
                    f"{i}. {spec['project']} - "
                    f"v{spec['version']['version']} "
                    f"({spec['version']['formatted_timestamp']})"
                )
            
            # Get user selection
            while True:
                try:
                    selection = ask_user("\nEnter the number of the source document (or 'q' to quit):")
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
            
            # Load the selected specification
            spec_data = spec_manager.load_specification(spec_path)
            if not spec_data:
                display_error(f"Specification not found: {spec_path}")
                return
                
            # Extract the required field
            if source_field not in spec_data:
                display_error(f"Field '{source_field}' not found in the selected specification.")
                return
                
            # Add to dependency values
            dependency_values[placeholder] = spec_data[source_field]
    
    # Get product description if needed (for document types without dependencies)
    description = ""
    if not dependencies:
        while True:
            try:
                description = ask_user("\nPlease describe your product idea:")
                Validator.not_empty(description)
                break
            except ValidationError as e:
                display_error(str(e))
    
    # Generate initial specification
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Generating initial document...", total=None)
        initial_spec = ai_service.generate_initial_spec(description, dependency_values)
    
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
    """List all saved specifications organized by project."""
    display_banner("All Projects")
    
    try:
        spec_manager = SpecificationManager(config)
        specs_by_project = spec_manager.list_specifications()
        
        if not specs_by_project:
            display_info("No documents found.")
            return
        
        # Display documents by project
        for project_name, doc_types in specs_by_project.items():
            # Format the project name nicely for display
            pretty_project = project_name.replace('_', ' ').title()
            console.print(f"\n[bold blue]== Project: {pretty_project} ==[/bold blue]")
            
            # For each document type in this project
            for doc_type, specs in doc_types.items():
                # Format document type for display
                pretty_doc_type = doc_type.replace('_', ' ').title()
                console.print(f"\n[bold cyan]{pretty_doc_type} Documents:[/bold cyan]")
                
                # List specifications for this document type
                for spec in specs:
                    console.print(
                        f"  • {spec['formatted_timestamp']} - "
                        f"v{spec['version']} - {spec['filename']}"
                    )
    except Exception as e:
        display_error(f"Failed to list documents: {str(e)}")

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
    
    # Save the original document type
    original_doc_type = config.DOCUMENT_TYPE
    
    # Get available specifications - we need to look for product_requirements
    # rather than using the current document type
    config.DOCUMENT_TYPE = "product_requirements"
    all_specs_by_project = spec_manager.list_specifications()
    
    # Create a flattened list of product requirement specs from all projects
    all_req_specs = []
    for project_name, doc_types in all_specs_by_project.items():
        if "product_requirements" in doc_types:
            for spec in doc_types["product_requirements"]:
                # Build full path for each spec
                spec_full_path = os.path.join(
                    config.SPECS_DIR, 
                    project_name, 
                    "product_requirements",
                    spec["filename"]
                )
                all_req_specs.append({
                    'path': spec_full_path,
                    'name': project_name.replace('_', ' ').title(),
                    'version': spec['version'],
                    'date': spec['formatted_timestamp'],
                    'project_dir': project_name
                })
    
    if not all_req_specs:
        print("No specifications found. Please create a specification first.")
        config.DOCUMENT_TYPE = original_doc_type
        return
    
    # If spec_path is not provided, show a list of available specs
    if not spec_path:
        print("\nAvailable specifications:")
        for i, spec in enumerate(all_req_specs, 1):
            print(f"{i}. {spec['name']} - v{spec['version']} ({spec['date']})")
        
        # Ask user to select a specification
        spec_choice = input("\nEnter the number of the specification to generate todo list from (or 'q' to quit): ")
        if spec_choice.lower() == 'q':
            config.DOCUMENT_TYPE = original_doc_type
            return
        
        try:
            spec_idx = int(spec_choice) - 1
            if spec_idx < 0 or spec_idx >= len(all_req_specs):
                print("Invalid selection.")
                config.DOCUMENT_TYPE = original_doc_type
                return
                
            selected_spec = all_req_specs[spec_idx]
            spec_path = selected_spec['path']
            selected_project_dir = selected_spec['project_dir']
        except ValueError:
            print("Invalid selection. Please enter a number.")
            config.DOCUMENT_TYPE = original_doc_type
            return
    else:
        # If spec_path is provided but doesn't contain the full path, try to find it
        if not os.path.isabs(spec_path) and not os.path.exists(spec_path):
            # Try finding it in the new project-first structure
            found = False
            selected_project_dir = None
            
            for spec in all_req_specs:
                if spec_path in spec['path'] or os.path.basename(spec_path) == os.path.basename(spec['path']):
                    spec_path = spec['path']
                    selected_project_dir = spec['project_dir']
                    found = True
                    break
                    
            if not found:
                potential_path = os.path.join(config.SPECS_DIR, spec_path)
                if os.path.exists(potential_path):
                    spec_path = potential_path
                    # Try to extract the project name from the path
                    parts = os.path.normpath(spec_path).split(os.sep)
                    if len(parts) >= 2:
                        # Path structure should be project/doc_type/filename
                        selected_project_dir = parts[-3]
                    else:
                        selected_project_dir = "unknown"
    
    # Validate the provided spec_path
    if not os.path.exists(spec_path):
        print(f"Specification file not found: {spec_path}")
        config.DOCUMENT_TYPE = original_doc_type
        return
    
    # Load the specification
    try:
        with open(spec_path, 'r') as f:
            spec_data = json.load(f)
            if isinstance(spec_data, dict) and 'specification' in spec_data:
                spec_content = spec_data['specification']
                if 'product_name' in spec_data:
                    project_name = spec_data['product_name']
                    selected_project_dir = project_name.lower().replace(' ', '_')
            else:
                spec_content = json.dumps(spec_data)  # Fallback if not in expected format
    except Exception as e:
        print(f"Error loading specification: {e}")
        config.DOCUMENT_TYPE = original_doc_type
        return
    
    # Set document type to engineering_todo for generating todo list
    config.DOCUMENT_TYPE = "engineering_todo"
    
    # Initialize AI service with engineering_todo document type
    ai_service = AIService(config)
    
    try:
        # Generate todo list
        todo_list = ai_service.generate_todo_list(spec_content)
        
        # Restore original document type
        config.DOCUMENT_TYPE = original_doc_type
        
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
            # Create engineering_todo directory in the project folder
            if selected_project_dir:
                # Get project name from the directory name
                project_name = selected_project_dir.replace('_', ' ').title()
                
                # Get the appropriate directory for the todo list
                todo_dir = os.path.join(
                    config.SPECS_DIR,
                    selected_project_dir,
                    "engineering_todo"
                )
                os.makedirs(todo_dir, exist_ok=True)
                
                # Create filename with version number
                spec_filename = os.path.basename(spec_path)
                spec_basename = os.path.splitext(spec_filename)[0]
                todo_filename = f"{spec_basename}_todo.json"
                todo_path = os.path.join(todo_dir, todo_filename)
                
                try:
                    # Add metadata to the todo list
                    todo_list["project_name"] = project_name
                    todo_list["doc_type"] = "engineering_todo"
                    todo_list["generated_from"] = spec_path
                    todo_list["timestamp"] = datetime.now().timestamp()
                    todo_list["formatted_timestamp"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    with open(todo_path, 'w') as f:
                        json.dump(todo_list, f, indent=2)
                    print(f"\nTodo list saved to: {todo_path}")
                except Exception as e:
                    print(f"Error saving todo list: {e}")
            else:
                print("Error: Cannot determine project directory for saving todo list")
    
    except Exception as e:
        print(f"✗ Failed to generate todo list: {str(e)}")
        # Make sure to restore original document type in case of error
        config.DOCUMENT_TYPE = original_doc_type

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
@click.option('--project', help='Filter by project name')
@click.option('--doc-type', help='Filter by document type')
@click.pass_obj
def list(config: Config, project: Optional[str] = None, doc_type: Optional[str] = None) -> None:
    """List all saved documents, optionally filtered by project or document type."""
    if doc_type:
        config.DOCUMENT_TYPE = doc_type
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