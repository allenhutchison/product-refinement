"""Prompt templates for engineering todo documents."""

# Define dependencies for this document type
# Format: List of dictionaries with source document type, field to extract, and placeholder in prompt
DEPENDENCIES = [
    {
        "source_type": "product_requirements",  # The document type we depend on
        "source_field": "specification",        # The field we need from that document
        "placeholder": "spec"                   # The placeholder in our prompt(s)
    }
]
