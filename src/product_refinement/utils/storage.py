"""Storage utilities for managing product specifications."""
import json
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any

from .config import Config
from .types import SpecificationData, SpecificationVersion

class SpecificationManager:
    """Manages saving and loading of product specifications."""
    
    def __init__(self, config: Config):
        """Initialize the specification manager."""
        self.config = config
        # Create specs directory if it doesn't exist
        os.makedirs(self.config.SPECS_DIR, exist_ok=True)
        logging.info(f"Specifications will be saved in: {self.config.SPECS_DIR}")
        
        # Handle legacy files
        self._handle_legacy_specifications()
    
    def _handle_legacy_specifications(self):
        """Detect and handle specifications created before the project-first structure."""
        # Check for files in the old structure
        legacy_files = []
        
        # Case 1: Files directly in the specs directory
        if os.path.exists(self.config.SPECS_DIR):
            for item in os.listdir(self.config.SPECS_DIR):
                full_path = os.path.join(self.config.SPECS_DIR, item)
                
                # Direct JSON files
                if os.path.isfile(full_path) and item.endswith('.json'):
                    legacy_files.append(full_path)
                    
                # Case 2: Document type directories with project subdirectories
                elif os.path.isdir(full_path):
                    # Check if this directory matches a document type
                    if item in ['product_requirements', 'engineering_todo'] or os.path.exists(os.path.join(self.config.PROMPT_DIR, item)):
                        # This is a document-type directory from the old structure
                        for project in os.listdir(full_path):
                            project_dir = os.path.join(full_path, project)
                            if os.path.isdir(project_dir):
                                # Find all JSON files in the project directory
                                for filename in os.listdir(project_dir):
                                    if filename.endswith('.json'):
                                        file_path = os.path.join(project_dir, filename)
                                        legacy_files.append((file_path, item, project))  # Save doc_type and project info
        
        if legacy_files:
            logging.info(f"Found legacy specification files to migrate to project-first structure")
            
            for file_info in legacy_files:
                if isinstance(file_info, tuple):
                    file_path, doc_type, project_dirname = file_info
                else:
                    file_path = file_info
                    doc_type = None
                    project_dirname = None
                    
                try:
                    # Load the specification
                    with open(file_path, 'r') as f:
                        spec_data = json.load(f)
                    
                    # Determine document type
                    if doc_type is None:
                        # Try to infer from filename or content
                        filename = os.path.basename(file_path)
                        if "_todo" in filename:
                            doc_type = 'engineering_todo'
                        else:
                            doc_type = spec_data.get('doc_type', 'product_requirements')
                    
                    # Update doc_type in the data
                    spec_data['doc_type'] = doc_type
                    
                    # Get or infer project name
                    project_name = spec_data.get('product_name', 'unknown')
                    if project_dirname:
                        # Use the directory name as it might be more reliable
                        project_dirname_clean = project_dirname.replace('_', ' ')
                        if project_name == 'unknown':
                            project_name = project_dirname_clean
                    
                    # Create new file structure:
                    # ~/product_refinement/[project_name]/[doc_type]/[filename]
                    project_dir = os.path.join(
                        self.config.SPECS_DIR,
                        project_name.lower().replace(' ', '_')
                    )
                    os.makedirs(project_dir, exist_ok=True)
                    
                    doc_type_dir = os.path.join(project_dir, doc_type)
                    os.makedirs(doc_type_dir, exist_ok=True)
                    
                    # Create new file path
                    filename = os.path.basename(file_path)
                    new_file_path = os.path.join(doc_type_dir, filename)
                    
                    # If target doesn't exist or is different, save the updated specification
                    if not os.path.exists(new_file_path) or file_path != new_file_path:
                        with open(new_file_path, 'w') as f:
                            json.dump(spec_data, f, indent=2)
                        logging.info(f"Migrated specification from {file_path} to {new_file_path}")
                        
                        # Only note removal for files that aren't in the same location
                        if os.path.exists(new_file_path) and file_path != new_file_path:
                            # Note that the original can be removed
                            logging.info(f"You can safely remove the original file: {file_path}")
                    
                except Exception as e:
                    logging.warning(f"Failed to migrate specification {file_path}: {e}")
    
    def _get_project_dir(self, project_name: str) -> str:
        """
        Get the directory for a specific project.
        
        Args:
            project_name (str): Name of the project
            
        Returns:
            str: Path to the project directory
        """
        project_dir = os.path.join(
            self.config.SPECS_DIR,
            project_name.lower().replace(' ', '_')
        )
        os.makedirs(project_dir, exist_ok=True)
        return project_dir
    
    def _get_doc_type_dir(self, project_name: str, doc_type: str = None) -> str:
        """
        Get the directory for a document type within a project.
        
        Args:
            project_name (str): Name of the project
            doc_type (str, optional): Document type. If None, uses the config default.
            
        Returns:
            str: Path to the document type directory within the project
        """
        if doc_type is None:
            doc_type = self.config.DOCUMENT_TYPE
            
        project_dir = self._get_project_dir(project_name)
        doc_type_dir = os.path.join(project_dir, doc_type)
        os.makedirs(doc_type_dir, exist_ok=True)
        return doc_type_dir
    
    def _get_spec_path(self, project_name: str, doc_type: str = None) -> str:
        """
        Get the path for a new specification file.
        
        Args:
            project_name (str): Name of the project
            doc_type (str, optional): Document type. If None, uses the config default.
            
        Returns:
            str: Path to save the specification
        """
        # Get appropriate document type directory within the project
        doc_type_dir = self._get_doc_type_dir(project_name, doc_type)
        
        # Get existing versions for this document type in the project
        existing_files = [
            f for f in os.listdir(doc_type_dir)
            if f.endswith('.json') and not f.endswith('_todo.json')
        ]
        
        # Calculate next version number
        version = 1
        if existing_files:
            versions = [
                int(f.split('_v')[1].split('.')[0])
                for f in existing_files
                if '_v' in f
            ]
            if versions:
                version = max(versions) + 1
        
        # Generate filename with timestamp and version
        timestamp = datetime.now()
        formatted_timestamp = timestamp.strftime('%Y%m%d_%H%M%S')
        filename = f"{project_name.lower().replace(' ', '_')}_v{version}.json"
        
        spec_path = os.path.join(doc_type_dir, filename)
        logging.debug(f"Generated specification path: {spec_path}")
        return spec_path
    
    def save_specification(self, project_name: str, specification: str, doc_type: str = None) -> str:
        """
        Save a product specification to file.
        
        Args:
            project_name (str): Name of the project
            specification (str): The specification text to save
            doc_type (str, optional): Document type. If None, uses the config default.
            
        Returns:
            str: Path where specification was saved
            
        Raises:
            IOError: If the specification cannot be saved
        """
        if doc_type is None:
            doc_type = self.config.DOCUMENT_TYPE
            
        spec_path = self._get_spec_path(project_name, doc_type)
        
        # Create specification data
        timestamp = datetime.now()
        spec_dict: SpecificationData = {
            'version': int(spec_path.split('_v')[-1].split('.')[0]),
            'timestamp': timestamp.timestamp(),
            'formatted_timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'product_name': project_name,
            'specification': specification,
            'doc_type': doc_type
        }
        
        try:
            with open(spec_path, 'w') as f:
                json.dump(spec_dict, f, indent=2)
            logging.info(f"Saved specification to {spec_path}")
            return spec_path
        except IOError as e:
            logging.error(f"Failed to save specification: {e}")
            raise
    
    def list_specifications(self, project_name: str = None, doc_type: str = None) -> Dict:
        """
        List specifications, filtered by project and/or document type.
        
        Args:
            project_name (str, optional): Filter by project name.
            doc_type (str, optional): Filter by document type.
        
        Returns:
            Dict: Nested dictionary organized by project and document type
        """
        result = {}
        
        # Get all projects
        try:
            for project_dir in os.listdir(self.config.SPECS_DIR):
                project_path = os.path.join(self.config.SPECS_DIR, project_dir)
                
                # Skip non-directories and system directories
                if not os.path.isdir(project_path) or project_dir.startswith('.') or project_dir.startswith('__'):
                    continue
                    
                # Filter by project name if specified
                if project_name and project_dir != project_name.lower().replace(' ', '_'):
                    continue
                
                project_specs = {}
                
                # Look for document type folders in this project
                for doc_type_dir in os.listdir(project_path):
                    doc_type_path = os.path.join(project_path, doc_type_dir)
                    
                    # Skip non-directories and system directories
                    if not os.path.isdir(doc_type_path) or doc_type_dir.startswith('.') or doc_type_dir.startswith('__'):
                        continue
                    
                    # Filter by document type if specified
                    if doc_type and doc_type_dir != doc_type:
                        continue
                    
                    # List specification files in this document type
                    spec_files = []
                    for filename in os.listdir(doc_type_path):
                        # Only include JSON files
                        if not filename.endswith('.json'):
                            continue
                        
                        # Special handling for todo files - only include them for engineering_todo document type
                        if filename.endswith('_todo.json') and doc_type_dir != 'engineering_todo':
                            continue
                            
                        file_path = os.path.join(doc_type_path, filename)
                        try:
                            with open(file_path, 'r') as f:
                                spec_data = json.load(f)
                                
                            spec_files.append({
                                'filename': filename,
                                'path': os.path.join(project_dir, doc_type_dir, filename),
                                'version': spec_data.get('version', 1),
                                'timestamp': spec_data.get('timestamp', 0),
                                'formatted_timestamp': spec_data.get('formatted_timestamp', 'Unknown date'),
                                'product_name': spec_data.get('product_name', project_dir.replace('_', ' ')),
                                'doc_type': doc_type_dir  # Use directory name for clarity
                            })
                        except (json.JSONDecodeError, KeyError) as e:
                            logging.warning(f"Failed to read specification {file_path}: {e}")
                    
                    # Only add document types that have specifications
                    if spec_files:
                        # Sort by version number
                        spec_files.sort(key=lambda x: x.get('timestamp', 0))
                        project_specs[doc_type_dir] = spec_files
                
                # Only add projects with specifications
                if project_specs:
                    result[project_dir] = project_specs
            
            # For specific document type queries, simplify the result structure
            if doc_type and len(result) == 1:
                project = next(iter(result))
                if doc_type in result[project]:
                    return result[project][doc_type]
        except Exception as e:
            logging.error(f"Failed to list specifications: {e}")
            raise
                
        return result
    
    def load_specification(self, spec_path: str) -> Optional[SpecificationData]:
        """
        Load a specification from file.
        
        Args:
            spec_path (str): Path to the specification file
            
        Returns:
            Optional[SpecificationData]: The loaded specification data, or None if not found
            
        Raises:
            IOError: If the specification cannot be loaded
        """
        # If path is relative to SPECS_DIR, make it absolute
        if not os.path.isabs(spec_path):
            full_path = os.path.join(self.config.SPECS_DIR, spec_path)
        else:
            full_path = spec_path
        
        try:
            with open(full_path, 'r') as f:
                spec_data = json.load(f)
                
            # Add the doc_type if it's not already there
            if 'doc_type' not in spec_data:
                # Try to infer document type from the path
                path_parts = os.path.normpath(full_path).split(os.sep)
                
                # In the project-first structure, doc_type is the directory before the file
                if len(path_parts) >= 2:
                    spec_data['doc_type'] = path_parts[-2]
                else:
                    spec_data['doc_type'] = self.config.DOCUMENT_TYPE
            
            return spec_data
        except FileNotFoundError:
            logging.error(f"Specification not found: {spec_path}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse specification {spec_path}: {e}")
            raise IOError(f"Failed to parse specification: {e}")
        except Exception as e:
            logging.error(f"Failed to load specification {spec_path}: {e}")
            raise