"""Storage utilities for managing product specifications."""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from .config import Config
from .types import SpecificationData, SpecificationVersion

class SpecificationManager:
    """Manages saving and loading of product specifications."""
    
    def __init__(self, config: Config):
        """Initialize the specification manager."""
        self.config = config
        os.makedirs(self.config.SPECS_DIR, exist_ok=True)
    
    def _get_spec_path(self, project_name: str) -> str:
        """
        Get the path for a new specification file.
        
        Args:
            project_name (str): Name of the project
            
        Returns:
            str: Path to save the specification
        """
        # Create project directory
        project_dir = os.path.join(
            self.config.SPECS_DIR,
            project_name.lower().replace(' ', '_')
        )
        os.makedirs(project_dir, exist_ok=True)
        
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
        
        return os.path.join(project_dir, filename)
    
    def save_specification(self, project_name: str, specification: str) -> None:
        """
        Save a product specification to file.
        
        Args:
            project_name (str): Name of the project
            specification (str): The specification text to save
            
        Raises:
            IOError: If the specification cannot be saved
        """
        spec_path = self._get_spec_path(project_name)
        
        # Create specification data
        timestamp = datetime.now()
        spec_dict: SpecificationData = {
            'version': int(spec_path.split('_v')[-1].split('.')[0]),
            'timestamp': timestamp.timestamp(),
            'formatted_timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'product_name': project_name,
            'specification': specification
        }
        
        try:
            with open(spec_path, 'w') as f:
                json.dump(spec_dict, f, indent=2)
            logging.info(f"Saved specification to {spec_path}")
        except IOError as e:
            logging.error(f"Failed to save specification: {e}")
            raise
    
    def list_specifications(self) -> Dict[str, List[SpecificationVersion]]:
        """
        List all saved specifications.
        
        Returns:
            Dict[str, List[SpecificationVersion]]: Dictionary mapping project directories
                to lists of specification versions
        """
        specs: Dict[str, List[SpecificationVersion]] = {}
        
        try:
            # List all project directories
            for project_dir in os.listdir(self.config.SPECS_DIR):
                dir_path = os.path.join(self.config.SPECS_DIR, project_dir)
                if not os.path.isdir(dir_path):
                    continue
                
                # List specification files in the project directory
                spec_files = []
                for filename in os.listdir(dir_path):
                    if not filename.endswith('.json'):
                        continue
                        
                    file_path = os.path.join(dir_path, filename)
                    try:
                        with open(file_path, 'r') as f:
                            spec_data = json.load(f)
                            
                        spec_files.append(SpecificationVersion(
                            filename=filename,
                            version=spec_data['version'],
                            timestamp=spec_data['timestamp'],
                            formatted_timestamp=spec_data['formatted_timestamp'],
                            product_name=spec_data['product_name']
                        ))
                    except (json.JSONDecodeError, KeyError) as e:
                        logging.warning(f"Failed to read specification {file_path}: {e}")
                
                if spec_files:
                    # Sort by version number
                    spec_files.sort(key=lambda x: x.version)
                    specs[project_dir] = spec_files
                    
        except Exception as e:
            logging.error(f"Failed to list specifications: {e}")
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
        full_path = os.path.join(self.config.SPECS_DIR, spec_path)
        
        try:
            with open(full_path, 'r') as f:
                spec_data: SpecificationData = json.load(f)
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