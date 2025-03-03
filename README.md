# Product Refinement Tool

A command-line tool for generating and refining product specifications using AI. This tool helps product managers, developers, and stakeholders create detailed, well-structured product specifications through an interactive process.

## Features

- Generate initial product specifications from brief descriptions
- Refine specifications through AI-guided questions
- Save and manage multiple versions of specifications
- Beautiful command-line interface with progress indicators
- Markdown formatting for better readability
- Caching of AI responses for better performance
- Comprehensive error handling and logging

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/product-refinement.git
cd product-refinement
```

2. Install the package:
```bash
pip install -e .
```

## Usage

The tool provides several commands for managing product specifications:

### Create a New Specification

```bash
refine create
```

This will start an interactive process where you:
1. Enter a brief description of your product
2. Review the initial specification
3. Answer follow-up questions to refine the specification
4. Save the final specification

### List Saved Specifications

```bash
refine list
```

Shows all saved specifications with their versions and timestamps.

### Edit an Existing Specification

```bash
refine edit <spec-path>
```

Opens an existing specification for further refinement.

### Command Line Options

- `--model`: Specify which AI model to use
- `--log-level`: Set logging level (DEBUG, INFO, WARNING, ERROR)

Example:
```bash
refine --model gpt-4 --log-level DEBUG create
```

## Configuration

The tool uses the following configuration settings:

- `MODEL_NAME`: The AI model to use (default: gpt-4)
- `LOG_LEVEL`: Logging level (default: INFO)
- `CACHE_DIR`: Directory for caching AI responses
- `LOG_DIR`: Directory for log files
- `SPECS_DIR`: Directory for saved specifications
- `PROMPT_DIR`: Directory for prompt templates
- `CACHE_EXPIRY`: Time in seconds before cache entries expire

## Project Structure

```
product_refinement/
├── __init__.py
├── __main__.py
├── ai/
│   ├── __init__.py
│   └── service.py
├── cli/
│   ├── __init__.py
│   └── commands.py
├── prompts/
│   ├── initial.txt
│   ├── refinement.txt
│   └── final_refinement.txt
└── utils/
    ├── __init__.py
    ├── config.py
    ├── display.py
    ├── storage.py
    ├── types.py
    └── validation.py
```

## Development

1. Set up a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install development dependencies:
```bash
pip install -e ".[dev]"
```

3. Run tests:
```bash
pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
