"""Storage utilities for managing product specifications."""
import json
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

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
        
        # Create directories for each document type
        self._ensure_document_type_dirs()
        
        # Handle legacy files
        self._handle_legacy_specifications()
    
    def _ensure_document_type_dirs(self):
        """Create directories for known document types."""
        # Get a list of all document types from the prompts directory
        prompts_dir = self.config.PROMPT_DIR
        if os.path.exists(prompts_dir):
            for entry in os.listdir(prompts_dir):
                if os.path.isdir(os.path.join(prompts_dir, entry)) and not entry.startswith('__'):
                    doc_type_dir = os.path.join(self.config.SPECS_DIR, entry)
                    os.makedirs(doc_type_dir, exist_ok=True)
                    logging.debug(f"Ensured document type directory exists: {doc_type_dir}")
    
    def _handle_legacy_specifications(self):
        """Detect and handle specifications created before the multi-document type system."""
        # Check if there are any JSON files directly in the specs directory or in project subdirectories
        # that aren't inside a document type folder
        legacy_files = []
        
        # Look for direct JSON files in the specs directory
        if os.path.exists(self.config.SPECS_DIR):
            for item in os.listdir(self.config.SPECS_DIR):
                full_path = os.path.join(self.config.SPECS_DIR, item)
                
                # Case 1: JSON file directly in specs directory
                if os.path.isfile(full_path) and item.endswith('.json'):
                    legacy_files.append(full_path)
                    
                # Case 2: Project directory with JSON files (but not a document type directory)
                elif os.path.isdir(full_path) and not item.startswith('__'):
                    # Check if this is a document type directory by looking for initial.txt in prompts
                    prompt_dir = os.path.join(self.config.PROMPT_DIR, item)
                    if not os.path.exists(prompt_dir) or not os.path.isdir(prompt_dir):
                        # This is likely a project directory from the old structure
                        for sub_item in os.listdir(full_path):
                            sub_path = os.path.join(full_path, sub_item)
                            if os.path.isfile(sub_path) and sub_item.endswith('.json'):
                                legacy_files.append(sub_path)
        
        if legacy_files:
            logging.info(f"Found {len(legacy_files)} legacy specification files to migrate")
            
            # Create product_requirements and engineering_todo directories if they don't exist
            product_req_dir = os.path.join(self.config.SPECS_DIR, "product_requirements")
            engineering_todo_dir = os.path.join(self.config.SPECS_DIR, "engineering_todo")
            os.makedirs(product_req_dir, exist_ok=True)
            os.makedirs(engineering_todo_dir, exist_ok=True)
            
            for file_path in legacy_files:
                try:
                    # Load the specification
                    with open(file_path, 'r') as f:
                        spec_data = json.load(f)
                    
                    # Determine if this is a todo file by checking filename or content
                    filename = os.path.basename(file_path)
                    is_todo = "_todo" in filename
                    
                    # Add doc_type field if missing
                    if 'doc_type' not in spec_data:
                        spec_data['doc_type'] = 'engineering_todo' if is_todo else 'product_requirements'
                    
                    # Create the appropriate folder structure
                    project_name = spec_data.get('product_name', 'unknown')
                    
                    # Choose the appropriate directory based on the doc_type
                    if spec_data['doc_type'] == 'engineering_todo' or is_todo:
                        base_dir = engineering_todo_dir
                        spec_data['doc_type'] = 'engineering_todo'  # Ensure doc_type matches directory
                    else:
                        base_dir = product_req_dir
                        spec_data['doc_type'] = 'product_requirements'  # Ensure doc_type matches directory
                    
                    project_dir = os.path.join(
                        base_dir,
                        project_name.lower().replace(' ', '_')
                    )
                    os.makedirs(project_dir, exist_ok=True)
                    
                    # Create new file path
                    filename = os.path.basename(file_path)
                    new_file_path = os.path.join(project_dir, filename)
                    
                    # If target doesn't exist or is different, save the updated specification
                    if not os.path.exists(new_file_path) or file_path != new_file_path:
                        with open(new_file_path, 'w') as f:
                            json.dump(spec_data, f, indent=2)
                        logging.info(f"Migrated specification from {file_path} to {new_file_path}")
                        
                        # Only remove the original file if it's in a different location and was successfully copied
                        if os.path.exists(new_file_path) and file_path != new_file_path:
                            # Keep the old files around for now, just log that they can be removed
                            logging.info(f"You can safely remove the original file: {file_path}")
                    
                except Exception as e:
                    logging.warning(f"Failed to migrate specification {file_path}: {e}")

    def _get_doc_type_dir(self, doc_type: str = None) -> str:
        """
        Get the directory for a specific document type.
        
        Args:
            doc_type (str, optional): Document type. If None, uses the config default.
            
        Returns:
            str: Path to the document type directory
        """
        if doc_type is None:
            doc_type = self.config.DOCUMENT_TYPE
            
        doc_type_dir = os.path.join(self.config.SPECS_DIR, doc_type)
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
        # Get appropriate document type directory
        doc_type_dir = self._get_doc_type_dir(doc_type)
        
        # Create project directory
        project_dir = os.path.join(
            doc_type_dir,
            project_name.lower().replace(' ', '_')
        )
        os.makedirs(project_dir, exist_ok=True)
        logging.debug(f"Created project directory: {project_dir}")
        
        # Get existing versions
        existing_files = [
            f for f in os.listdir(project_dir)
            if f.endswith('.json')
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
        
        spec_path = os.path.join(project_dir, filename)
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
        spec_path = self._get_spec_path(project_name, doc_type)
        
        # Create specification data
        timestamp = datetime.now()
        spec_dict: SpecificationData = {
            'version': int(spec_path.split('_v')[-1].split('.')[0]),
            'timestamp': timestamp.timestamp(),
            'formatted_timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'product_name': project_name,
            'specification': specification,
            'doc_type': doc_type or self.config.DOCUMENT_TYPE
        }
        
        try:
            with open(spec_path, 'w') as f:
                json.dump(spec_dict, f, indent=2)
            logging.info(f"Saved specification to {spec_path}")
            return spec_path
        except IOError as e:
            logging.error(f"Failed to save specification: {e}")
            raise
    
    def list_specifications(self, doc_type: str = None) -> Dict[str, Dict[str, List[SpecificationVersion]]]:
        """
        List specifications for a specific document type or all document types.
        
        Args:
            doc_type (str, optional): Document type to list. If None, lists all document types.
        
        Returns:
            Dict: When doc_type is None, returns {doc_type: {project: [versions]}}
                 When doc_type is specified, returns {project: [versions]}
        """
        if doc_type:
            # List specifications for a specific document type
            return self._list_specs_for_doc_type(doc_type)
        else:
            # List all document types
            specs_by_type = {}
            
            # Get all document type directories
            try:
                for entry in os.listdir(self.config.SPECS_DIR):
                    doc_type_path = os.path.join(self.config.SPECS_DIR, entry)
                    if os.path.isdir(doc_type_path) and not entry.startswith('__'):
                        doc_specs = self._list_specs_for_doc_type(entry)
                        if doc_specs:  # Only add non-empty document types
                            specs_by_type[entry] = doc_specs
            except Exception as e:
                logging.error(f"Failed to list specifications: {e}")
                raise
                
            return specs_by_type
    
    def _list_specs_for_doc_type(self, doc_type: str) -> Dict[str, List[SpecificationVersion]]:
        """
        List specifications for a particular document type.
        
        Args:
            doc_type (str): Document type to list
            
        Returns:
            Dict[str, List[SpecificationVersion]]: Dictionary mapping project directories to lists of specification versions
        """
        specs = {}
        doc_type_dir = self._get_doc_type_dir(doc_type)
        
        try:
            # List all project directories
            if os.path.exists(doc_type_dir):
                for project_dir in os.listdir(doc_type_dir):
                    dir_path = os.path.join(doc_type_dir, project_dir)
                    if not os.path.isdir(dir_path):
                        continue
                    
                    # List specification files in the project directory
                    spec_files = []
                    for filename in os.listdir(dir_path):
                        # Skip files that aren't JSON or are todo list files
                        if not filename.endswith('.json') or filename.endswith('_todo.json'):
                            continue
                            
                        file_path = os.path.join(dir_path, filename)
                        try:
                            with open(file_path, 'r') as f:
                                spec_data = json.load(f)
                                
                            spec_files.append({
                                'filename': filename,
                                'version': spec_data['version'],
                                'timestamp': spec_data['timestamp'],
                                'formatted_timestamp': spec_data['formatted_timestamp'],
                                'product_name': spec_data['product_name'],
                                'doc_type': spec_data.get('doc_type', doc_type)  # Default to directory name if not stored
                            })
                        except (json.JSONDecodeError, KeyError) as e:
                            logging.warning(f"Failed to read specification {file_path}: {e}")
                    
                    if spec_files:
                        # Sort by version number
                        spec_files.sort(key=lambda x: x['version'])
                        specs[project_dir] = spec_files
        except Exception as e:
            logging.error(f"Failed to list specifications for {doc_type}: {e}")
            raise
                
        return specs
    
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
                spec_data: SpecificationData = json.load(f)
                
            # Add the doc_type if it's not already there
            if 'doc_type' not in spec_data:
                # Try to infer document type from the path
                path_parts = os.path.normpath(full_path).split(os.sep)
                specs_index = path_parts.index(os.path.basename(self.config.SPECS_DIR))
                if specs_index + 1 < len(path_parts):
                    spec_data['doc_type'] = path_parts[specs_index + 1]
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