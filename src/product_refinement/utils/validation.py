"""Validation utilities for user input."""
import re
from typing import Optional, List

class ValidationError(Exception):
    """Exception raised for validation errors."""
    pass

class Validator:
    """Validation utilities for user input."""
    
    @staticmethod
    def not_empty(value: str, message: str = "Input cannot be empty") -> str:
        """Validate that input is not empty."""
        if not value or value.strip() == "":
            raise ValidationError(message)
        return value.strip()
    
    @staticmethod
    def min_length(value: str, min_len: int, message: Optional[str] = None) -> str:
        """Validate that input has at least min_len characters."""
        if len(value.strip()) < min_len:
            msg = message or f"Input must be at least {min_len} characters"
            raise ValidationError(msg)
        return value.strip()
    
    @staticmethod
    def max_length(value: str, max_len: int, message: Optional[str] = None) -> str:
        """Validate that input has at most max_len characters."""
        if len(value.strip()) > max_len:
            msg = message or f"Input must be at most {max_len} characters"
            raise ValidationError(msg)
        return value.strip()
    
    @staticmethod
    def is_int(value: str, message: str = "Input must be an integer") -> int:
        """Validate that input is an integer."""
        try:
            return int(value.strip())
        except ValueError:
            raise ValidationError(message)
    
    @staticmethod
    def is_float(value: str, message: str = "Input must be a number") -> float:
        """Validate that input is a float."""
        try:
            return float(value.strip())
        except ValueError:
            raise ValidationError(message)
    
    @staticmethod
    def matches_pattern(value: str, pattern: str, message: str = "Input format is invalid") -> str:
        """Validate that input matches a regex pattern."""
        if not re.match(pattern, value.strip()):
            raise ValidationError(message)
        return value.strip()
    
    @staticmethod
    def is_valid_filename(value: str, message: str = "Invalid filename") -> str:
        """Validate that input is a valid filename."""
        # Remove common invalid characters
        value = value.strip()
        if not value or re.search(r'[\\/:*?"<>|]', value):
            raise ValidationError(message)
        return value
    
    @staticmethod
    def is_yes_no(value: str, message: str = "Please enter 'yes' or 'no'") -> bool:
        """Validate that input is a yes/no response and return bool."""
        value = value.strip().lower()
        if value in ('y', 'yes', 'true', '1'):
            return True
        if value in ('n', 'no', 'false', '0'):
            return False
        raise ValidationError(message)
    
    @staticmethod
    def in_choices(value: str, choices: List[str], message: Optional[str] = None) -> str:
        """Validate that input is one of the available choices."""
        value = value.strip().lower()
        choices_lower = [c.lower() for c in choices]
        
        if value not in choices_lower:
            msg = message or f"Input must be one of: {', '.join(choices)}"
            raise ValidationError(msg)
        
        # Return the original case version
        return choices[choices_lower.index(value)] 