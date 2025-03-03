"""Configuration settings for the product refinement system."""
import os

class Config:
    """Application configuration settings."""
    MODEL_NAME: str = "gemini-2.0-flash"  # Default model
    LOG_LEVEL: str = "INFO"  # Default log level
    PROMPT_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
    SPECS_DIR: str = os.path.expanduser("~/product_refinement/specs")
    CACHE_DIR: str = os.path.expanduser("~/.cache/product_refinement")
    LOG_DIR: str = os.path.expanduser("~/product_refinement/logs")
    CACHE_EXPIRY: int = 60 * 60 * 24 * 7  # 1 week in seconds
    
    @classmethod
    def from_args(cls, args):
        """Initialize config from command line args."""
        config = cls()
        if hasattr(args, 'model') and args.model:
            config.MODEL_NAME = args.model
        if hasattr(args, 'log_level') and args.log_level:
            config.LOG_LEVEL = args.log_level
        return config 