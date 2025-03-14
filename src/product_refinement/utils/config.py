"""Configuration settings for the product refinement system."""
import os

class Config:
    """Application configuration settings."""
    MODEL_NAME: str = "gemini-2.0-flash"  # Default model
    LOG_LEVEL: str = "INFO"  # Default log level
    
    # Get the project root directory (2 levels up from this file)
    _PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Default directories within the project
    PROMPT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    
    # User's home directory for data storage
    _USER_HOME: str = os.path.expanduser("~")
    _DATA_ROOT: str = os.path.join(_USER_HOME, "product_refinement")
    
    # Store all data files in the user's home directory for easier access and separation from source code
    SPECS_DIR: str = _DATA_ROOT
    CACHE_DIR: str = os.path.join(_DATA_ROOT, "cache")
    LOG_DIR: str = os.path.join(_DATA_ROOT, "logs")
    
    CACHE_EXPIRY: int = 60 * 60 * 24 * 7  # 1 week in seconds
    DOCUMENT_TYPE: str = "product_requirements"  # Default document type
    
    def __init__(self):
        """Initialize config with defaults and ensure directories exist."""
        # Create necessary directories
        for directory in [self.SPECS_DIR, self.CACHE_DIR, self.LOG_DIR]:
            os.makedirs(directory, exist_ok=True)
    
    @classmethod
    def from_args(cls, args):
        """Initialize config from command line args."""
        config = cls()
        if hasattr(args, 'model') and args.model:
            config.MODEL_NAME = args.model
        if hasattr(args, 'log_level') and args.log_level:
            config.LOG_LEVEL = args.log_level
        if hasattr(args, 'doc_type') and args.doc_type:
            config.DOCUMENT_TYPE = args.doc_type
        return config