# AI-Powered Product Specification Generator

A powerful tool that uses AI to help you create detailed, comprehensive product specifications with minimal effort.

## Features

- Generate initial product specifications from a brief description
- Iteratively refine specifications through AI-guided questioning
- Track answered questions to prevent duplicates
- Save specifications in both Markdown and JSON formats
- Version control for specifications
- Support for multiple AI models (OpenAI, Anthropic Claude, and Google Gemini)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/product-refinement.git
   cd product-refinement
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Copy the example environment file and add your API keys:
   ```
   cp .env.example .env
   ```
   Then edit the `.env` file to add your API keys for the models you plan to use.

## Usage

Run the script with:

```
python spec.py
```

### Command Line Options

- `--model`: Select the AI model to use (default: gpt-4-turbo)
  - OpenAI models: gpt-4, gpt-4-turbo, gpt-4o, gpt-4o-mini, gpt-3.5-turbo
  - OpenAI "o" models: o1 (alias for gpt-4o), o1-mini (alias for gpt-4o-mini), o3 (alias for gpt-4o-2024-05-13)
  - Anthropic models: claude-3-opus, claude-3-sonnet, claude-3-haiku
  - Google models: gemini-1.5-pro, gemini-1.5-flash, gemini-1.0-pro
- `--log-level`: Set the logging level (default: INFO)
  - Available options: DEBUG, INFO, WARNING, ERROR, CRITICAL

Example:
```
python spec.py --model claude-3-opus --log-level WARNING
```

## Workflow

1. Choose to create a new specification or load an existing one
2. For new specifications, provide a brief product description
3. The AI generates an initial draft specification
4. The AI suggests follow-up questions to refine the specification
5. Answer the questions or skip them as needed
6. When complete, the AI generates a final, polished specification
7. The specification is saved with version control

## Model Recommendations

### OpenAI Models
- **GPT-4 Turbo** (default): Good balance of capability and cost
- **GPT-4o** (or o1): Faster response times with similar quality to GPT-4 Turbo
- **GPT-4o-mini** (or o1-mini): More economical option with good capabilities
- **o3**: Latest version of GPT-4o with improved capabilities

### Anthropic Models
- **Claude-3-Opus**: Highest quality specifications with excellent technical detail
- **Claude-3-Sonnet**: Good balance of quality and cost
- **Claude-3-Haiku**: Fastest Claude model, good for quick iterations

### Google Models
- **Gemini-1.5-Pro**: Google's most capable model, good for detailed specifications
- **Gemini-1.5-Flash**: Faster version with good capabilities
- **Gemini-1.0-Pro**: More economical option

## Customizing Prompts

All prompts are stored in the `prompts/` directory:
- `initial.txt`: Prompt for generating the initial specification
- `refinement.txt`: Prompt for generating follow-up questions
- `final_refinement.txt`: Prompt for generating the final specification

You can edit these files to customize the AI's behavior and the structure of your specifications.

## License

[MIT License](LICENSE)
