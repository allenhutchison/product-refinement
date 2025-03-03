"""Configuration settings for the product refinement system."""
import os

class Config:
    """Application configuration settings."""
    MODEL_NAME: str = "gemini-2.0-flash"  # Default model
    LOG_LEVEL: str = "INFO"  # Default log level
    PROMPT_DIR: str = "prompts"
    SPECS_DIR: str = "specs"
    CACHE_DIR: str = os.path.expanduser("~/.cache/product_refinement")
    CACHE_EXPIRY: int = 60 * 60 * 24 * 7  # 1 week in seconds
    
    @classmethod
    def from_args(cls, args):
        """Initialize config from command line args."""
        config = cls()
        config.MODEL_NAME = args.model
        config.LOG_LEVEL = args.log_level
        return config 