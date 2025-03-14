"""Command line interface for the product refinement tool."""
import logging
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

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

def get_available_document_types(config: Config) -> List[Tuple[str, str]]:
    """
    Get a list of available document types from the prompts directory.
    
    Args:
        config (Config): The configuration object
        
    Returns:
        List[Tuple[str, str]]: List of tuples with (doc_type, display_name)
    """
    doc_types = []
    
    try:
        # List all directories in the prompts directory
        prompt_dir = config.PROMPT_DIR
        for item in os.listdir(prompt_dir):
            potential_doc_type_dir = os.path.join(prompt_dir, item)
            
            # Check if it's a directory and has the necessary files
            if (os.path.isdir(potential_doc_type_dir) and 
                not item.startswith('__') and 
                os.path.exists(os.path.join(potential_doc_type_dir, "initial.txt"))):
                # Create a display name by replacing underscores with spaces and capitalizing
                display_name = item.replace('_', ' ').title()
                doc_types.append((item, display_name))
    except Exception as e:
        logging.error(f"Error scanning for document types: {e}")
        
    return sorted(doc_types)

def prompt_for_document_type(config: Config) -> str:
    """
    Prompt the user to select a document type from available options.
    
    Args:
        config (Config): The configuration object
        
    Returns:
        str: The selected document type
        
    Raises:
        click.Abort: If the user cancels the selection
    """
    doc_types = get_available_document_types(config)
    
    if not doc_types:
        display_error("No document types available in the prompts directory.")
        raise click.Abort()
    
    # Display options in a table
    table = Table(title="Available Document Types", show_header=False)
    table.add_column("#", style="cyan")
    table.add_column("Document Type", style="green")
    table.add_column("Description", style="yellow")
    
    for i, (doc_type, display_name) in enumerate(doc_types, 1):
        # Get description from the first line of the __init__.py docstring if available
        description = "No description available"
        init_file = os.path.join(config.PROMPT_DIR, doc_type, "__init__.py")
        if os.path.exists(init_file):
            try:
                with open(init_file, 'r') as f:
                    content = f.read()
                    if '"""' in content:
                        description = content.split('"""')[1].strip().split('\n')[0]
            except Exception:
                pass
        
        table.add_row(str(i), display_name, description)
    
    console.print(table)
    
    # Get user selection
    while True:
        try:
            selection = ask_user("\nSelect a document type (number) or 'q' to quit: ")
            if selection.lower() == 'q':
                raise click.Abort()
            
            index = int(selection) - 1
            if 0 <= index < len(doc_types):
                return doc_types[index][0]  # Return the doc_type (not display name)
            
            display_error(f"Invalid selection. Please enter a number between 1 and {len(doc_types)}.")
        except ValueError:
            display_error("Please enter a valid number.")

def create_spec(config: Config) -> None:
    """Create a new product specification."""
    # If document type not specified in config, prompt for it
    if not hasattr(config, 'DOCUMENT_TYPE_SELECTED') or not config.DOCUMENT_TYPE_SELECTED:
        try:
            config.DOCUMENT_TYPE = prompt_for_document_type(config)
        except click.Abort:
            return
    
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
            specs = spec_manager.list_specifications(doc_type=source_type)
            
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
                # Customize prompt based on document type
                if config.DOCUMENT_TYPE == "idea":
                    prompt_text = "\nPlease describe your idea:"
                elif config.DOCUMENT_TYPE == "product_requirements":
                    prompt_text = "\nPlease describe your product:"
                else:
                    prompt_text = f"\nPlease describe your {config.DOCUMENT_TYPE.replace('_', ' ')}:"
                    
                description = ask_user(prompt_text)
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
        display_error("Failed to generate initial document.")
        return
    
    # Display initial specification
    console.print(f"\n📝 Initial {config.DOCUMENT_TYPE.replace('_', ' ').title()}:")
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
            progress.add_task(description="Updating document...", total=None)
            spec = ai_service.finalize_spec(spec)
        
        # Display updated specification
        console.print(f"\n📝 Updated {config.DOCUMENT_TYPE.replace('_', ' ').title()}:")
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
        spec_manager.save_specification(project_name, spec, config.DOCUMENT_TYPE)
        display_success(f"\n✅ {config.DOCUMENT_TYPE.replace('_', ' ').title()} saved as '{project_name}'")
    except Exception as e:
        display_error(f"Failed to save document: {str(e)}")

def list_specs(config: Config, project: Optional[str] = None, doc_type: Optional[str] = None) -> None:
    """List all saved specifications organized by project."""
    display_banner("All Projects")
    
    try:
        spec_manager = SpecificationManager(config)
        
        # If doc_type is not provided and not selected, list all types
        selected_doc_type = doc_type or getattr(config, 'DOCUMENT_TYPE_SELECTED', None)
        specs_by_project = spec_manager.list_specifications(project, selected_doc_type)
        
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
    display_banner("Edit Document")
    
    try:
        spec_manager = SpecificationManager(config)
        
        # If document type not specified in config and no path is provided,
        # let the user select which document type to view
        selected_doc_type = None
        if not spec_path and (not hasattr(config, 'DOCUMENT_TYPE_SELECTED') or not config.DOCUMENT_TYPE_SELECTED):
            try:
                # Get list of document types that have saved documents
                available_types = []
                all_specs = spec_manager.list_specifications()
                
                for project_dir, doc_types in all_specs.items():
                    for doc_type in doc_types.keys():
                        if doc_type not in [t[0] for t in available_types]:
                            display_name = doc_type.replace('_', ' ').title()
                            available_types.append((doc_type, display_name))
                
                if not available_types:
                    display_info("No documents found.")
                    return
                
                # Display options
                console.print("\nSelect document type to edit:")
                for i, (doc_type, display_name) in enumerate(available_types, 1):
                    console.print(f"{i}. {display_name}")
                
                # Get user selection
                while True:
                    try:
                        selection = ask_user("\nEnter the number of the document type (or 'q' to quit): ")
                        if selection.lower() == 'q':
                            return
                        
                        index = int(selection) - 1
                        if 0 <= index < len(available_types):
                            selected_doc_type = available_types[index][0]
                            config.DOCUMENT_TYPE = selected_doc_type
                            break
                        
                        display_error(f"Invalid selection. Please enter a number between 1 and {len(available_types)}.")
                    except ValueError:
                        display_error("Please enter a valid number.")
            except click.Abort:
                return
        else:
            # Use the selected document type from config if available
            selected_doc_type = getattr(config, 'DOCUMENT_TYPE_SELECTED', None)
        
        # Get specifications based on selected document type
        specs = spec_manager.list_specifications(doc_type=selected_doc_type)
        
        if not specs:
            display_info(f"No {'documents' if not selected_doc_type else selected_doc_type.replace('_', ' ')} found.")
            return
        
        # If no spec_path provided, show selection menu
        if not spec_path:
            # Create a flat list of all specifications with their paths
            all_specs = []
            for project_dir, doc_types in specs.items():
                if selected_doc_type:
                    # If document type is selected, only show that type
                    if selected_doc_type in doc_types:
                        for spec in doc_types[selected_doc_type]:
                            doc_type_name = selected_doc_type.replace('_', ' ').title()
                            all_specs.append({
                                'path': os.path.join(project_dir, selected_doc_type, spec['filename']),
                                'project': project_dir,
                                'version': spec,
                                'doc_type': selected_doc_type,
                                'display_name': f"{project_dir.replace('_', ' ').title()} - {doc_type_name} v{spec['version']}"
                            })
                else:
                    # If no document type selected, show all
                    for doc_type, specs_list in doc_types.items():
                        for spec in specs_list:
                            doc_type_name = doc_type.replace('_', ' ').title()
                            all_specs.append({
                                'path': os.path.join(project_dir, doc_type, spec['filename']),
                                'project': project_dir,
                                'version': spec,
                                'doc_type': doc_type,
                                'display_name': f"{project_dir.replace('_', ' ').title()} - {doc_type_name} v{spec['version']}"
                            })
            
            if not all_specs:
                display_info("No documents found.")
                return
            
            # Sort by project name and then by timestamp (newest first)
            all_specs.sort(key=lambda x: (x['project'], -x['version'].get('timestamp', 0)))
            
            # Display numbered list of specifications
            console.print("\nAvailable documents:")
            for i, spec in enumerate(all_specs, 1):
                console.print(
                    f"{i}. {spec['display_name']} "
                    f"({spec['version'].get('formatted_timestamp', 'Unknown date')})"
                )
            
            # Get user selection
            while True:
                try:
                    selection = ask_user("\nEnter the number of the document to edit (or 'q' to quit):")
                    if selection.lower() == 'q':
                        return
                    
                    index = int(selection) - 1
                    if 0 <= index < len(all_specs):
                        spec_path = all_specs[index]['path']
                        # Set the document type for the editing session
                        config.DOCUMENT_TYPE = all_specs[index]['doc_type']
                        break
                    else:
                        display_error("Invalid selection. Please try again.")
                except ValueError:
                    display_error("Please enter a valid number.")
        
        else:
            # Check if spec_path is a directory (project name)
            full_dir_path = os.path.join(config.SPECS_DIR, spec_path)
            if os.path.isdir(full_dir_path) and spec_path in specs:
                # If document type is selected, use that
                if selected_doc_type and selected_doc_type in specs[spec_path]:
                    versions = specs[spec_path][selected_doc_type]
                    doc_type = selected_doc_type
                else:
                    # Otherwise, use the first available document type
                    doc_type, versions = next(iter(specs[spec_path].items()))
                
                if versions:
                    # Sort by version number (descending) and take the first one
                    latest_version = sorted(versions, key=lambda v: v['version'], reverse=True)[0]
                    spec_path = os.path.join(full_dir_path, doc_type, latest_version['filename'])
                    config.DOCUMENT_TYPE = doc_type
                    display_info(f"Using latest version: {latest_version['filename']}")
                else:
                    display_error(f"No document files found in project: {spec_path}")
                    return
        
        # Load and display the specification
        spec_data = spec_manager.load_specification(spec_path)
        if not spec_data:
            display_error(f"Document not found: {spec_path}")
            return
        
        # Show preview
        doc_type_display = spec_data.get('doc_type', config.DOCUMENT_TYPE).replace('_', ' ').title()
        console.print(f"\n📝 Current {doc_type_display}:")
        console.print(format_spec_as_markdown(spec_data['specification']))
        
        # Ask for confirmation
        if not ask_user("\nWould you like to edit this document? (yes/no)").lower().startswith('y'):
            display_info("Edit cancelled.")
            return
        
        # Initialize AI service with the correct document type
        config.DOCUMENT_TYPE = spec_data.get('doc_type', config.DOCUMENT_TYPE)
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
                progress.add_task(description="Updating document...", total=None)
                spec = ai_service.finalize_spec(spec)
            
            # Display updated specification
            console.print(f"\n📝 Updated {doc_type_display}:")
            console.print(format_spec_as_markdown(spec))
            
            # Ask if user wants to continue refining
            if not ask_user("\nWould you like to continue refining? (yes/no)").lower().startswith('y'):
                break
        
        # Show final preview and ask for confirmation
        console.print(f"\n📝 Final {doc_type_display}:")
        console.print(format_spec_as_markdown(spec))
        
        if ask_user("\nWould you like to save these changes? (yes/no)").lower().startswith('y'):
            try:
                spec_manager.save_specification(spec_data['product_name'], spec, config.DOCUMENT_TYPE)
                display_success(f"\n✅ Document updated successfully")
            except Exception as e:
                display_error(f"Failed to save document: {str(e)}")
        else:
            display_info("Changes not saved.")
            
    except Exception as e:
        display_error(f"Failed to edit document: {str(e)}")

@click.group()
@click.option('--model', help='AI model to use')
@click.option('--log-level', help='Logging level (DEBUG, INFO, WARNING, ERROR)')
@click.option('--doc-type', help='Document type to work with (e.g., product_requirements, idea)')
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
        config.DOCUMENT_TYPE_SELECTED = True  # Flag that user explicitly selected a doc type
    
    # Initialize logging
    initialize_logging(config)
    
    # Store config in context
    ctx.obj = config

@cli.command()
@click.pass_obj
def create(config: Config) -> None:
    """Create a new document (idea, product requirements, etc.)."""
    create_spec(config)

@cli.command()
@click.option('--project', help='Filter by project name')
@click.option('--doc-type', help='Filter by document type')
@click.pass_obj
def list(config: Config, project: Optional[str] = None, doc_type: Optional[str] = None) -> None:
    """List all saved documents, optionally filtered by project or document type."""
    if doc_type:
        config.DOCUMENT_TYPE = doc_type
        config.DOCUMENT_TYPE_SELECTED = True
    list_specs(config, project, doc_type)

@cli.command()
@click.argument('spec_path', required=False)
@click.pass_obj
def edit(config: Config, spec_path: Optional[str]) -> None:
    """Edit an existing document."""
    edit_spec(config, spec_path)

if __name__ == '__main__':
    cli()