import argparse
import json
import logging
import os
from datetime import datetime
import sys

import openai
from dotenv import load_dotenv

# Add command line argument parsing
parser = argparse.ArgumentParser(description='AI-Powered Product Specification Generator')
parser.add_argument('--log-level', 
                   default='INFO',
                   choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                   help='Set the logging level')
args = parser.parse_args()

# Configure logging with command line argument
logging.basicConfig(level=getattr(logging, args.log_level))

# Suppress httpx logs (used by OpenAI client)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Load environment variables from .env file
load_dotenv()

# Allow dynamic model selection
MODEL_NAME = "gpt-4"  

# Get OpenAI API Key from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set. Please check your .env file.")

# Initialize the OpenAI client
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def load_prompt(prompt_file):
    """Load a prompt from a file in the prompts directory."""
    prompt_path = os.path.join("prompts", prompt_file)
    try:
        with open(prompt_path, "r") as f:
            return f.read().strip()
    except IOError as e:
        raise ValueError(f"Failed to load prompt file {prompt_file}: {str(e)}")

# Load prompts from files
try:
    AI_INITIAL_PROMPT = load_prompt("initial.txt")
    AI_REFINEMENT_PROMPT = load_prompt("refinement.txt")
    AI_FINAL_REFINEMENT_PROMPT = load_prompt("final_refinement.txt")
except ValueError as e:
    print(f"Error loading prompts: {str(e)}")
    sys.exit(1)

def ask_ai(prompt, model_name="gpt-4", stream=True):
    """
    Calls the OpenAI API to interact with an AI model.

    - If `stream=True`, prints the response as it arrives.
    - Otherwise, waits for the full response.

    Args:
        prompt (str): The input prompt to the AI model.
        model_name (str): The name of the model to use.
        stream (bool): Whether to stream the response.

    Returns:
        str: The full AI-generated response.
    """
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "system", "content": prompt}],
        stream=stream
    )

    if stream:
        print("\n🤖 AI Response (Streaming)...\n")
        response_text = ""
        for chunk in response:
            text = chunk.choices[0].delta.content or ""
            print(text, end="", flush=True)  # Print each chunk in real-time
            response_text += text  # Append to the full response
        print("\n")  # Ensure we move to a new line after streaming
        return response_text.strip()
    else:
        return response.choices[0].message.content.strip()

def ask_user(question):
    """Prompt user for input and return response."""
    response = input(f"\n{question}\n> ")
    return response.strip()

def generate_initial_spec(description):
    """Generate an initial product specification using AI."""
    print("\n🚀 Generating an initial specification draft...")
    prompt = AI_INITIAL_PROMPT + f"\n\nProduct description: {description}"
    return ask_ai(prompt, stream=True)  # Streaming enabled

def refine_spec(spec):
    """Iteratively refine the product specification, asking questions one at a time."""
    # Track answered questions and their responses
    answered_questions = []
    
    while True:
        print("\n🔍 AI is identifying missing sections...")
        # Format answered questions for the prompt
        answered_questions_text = "\n".join([
            f"Section: {q['section']}\nQuestion: {q['question']}\nAnswer: {q['answer']}"
            for q in answered_questions
        ]) if answered_questions else "No questions answered yet."
        
        refinement_prompt = AI_REFINEMENT_PROMPT.format(
            spec=spec,
            answered_questions=answered_questions_text
        )
        follow_up_questions = ask_ai(refinement_prompt, stream=False)  # No streaming for structured data

        try:
            # Add debug logging
            logging.debug("AI Response: %s", follow_up_questions)
            
            # Try to clean the response if it contains markdown code blocks
            if "```json" in follow_up_questions:
                follow_up_questions = follow_up_questions.split("```json")[1].split("```")[0].strip()
            elif "```" in follow_up_questions:
                follow_up_questions = follow_up_questions.split("```")[1].strip()

            questions = json.loads(follow_up_questions)  # Parse JSON response
            
            # Validate the structure
            if not isinstance(questions, list):
                raise ValueError("Response is not a JSON array")
            
            for item in questions:
                if not isinstance(item, dict):
                    raise ValueError("Array contains non-object items")
                if "section" not in item or "question" not in item:
                    raise ValueError("Missing required fields in question object")

        except (json.JSONDecodeError, ValueError) as e:
            print(f"\n⚠️ Error parsing AI response: {str(e)}")
            print("Trying again...")
            continue

        if not questions:
            print("\n✅ The specification is complete!")
            break  # Exit loop when no missing sections remain

        for item in questions:
            section = item["section"]
            question = item["question"]

            print(f"\n📌 Refining section: **{section}**")
            print(f"🤖 AI Suggestion: {question}")
            
            user_input = ask_user("\nProvide your answer (or type 'skip' to move on, 'done' to finish refinements).")

            if user_input.lower() == "done":
                print("\n✅ Exiting refinements early.")
                return spec  # Exit immediately

            if user_input.lower() == "skip":
                print("⏭️ Skipping this question.")
                continue  # Move to the next question

            # Store the answered question and response
            answered_questions.append({
                "section": section,
                "question": question,
                "answer": user_input
            })

            # Update the spec with user's response
            spec += f"\n\n**{section}:** {question}\n{user_input}"

        print("\n🔄 Refinement round complete. Checking for further missing details...")

    return spec

def finalize_spec(spec):
    """Generate the final well-structured product specification using AI."""
    print("\n📌 Finalizing the specification with AI...")
    final_prompt = AI_FINAL_REFINEMENT_PROMPT.format(spec=spec)
    return ask_ai(final_prompt, stream=True)  # Streaming enabled

def get_project_dir(product_name):
    """
    Get the directory path for a project, creating it if it doesn't exist.
    
    Args:
        product_name (str): Name of the product/project
        
    Returns:
        str: Path to the project directory
    """
    # Convert product name to a valid directory name
    dir_name = "".join(c.lower() for c in product_name if c.isalnum())
    project_dir = os.path.join("specs", dir_name)
    os.makedirs(project_dir, exist_ok=True)
    return project_dir

def get_next_version(project_dir):
    """
    Get the next version number for a project.
    
    Args:
        project_dir (str): Path to the project directory
        
    Returns:
        int: Next version number
    """
    versions = [0]  # Start with 0 if no versions exist
    for filename in os.listdir(project_dir):
        if filename.endswith(".json"):
            try:
                version = int(filename.split("_v")[1].split(".")[0])
                versions.append(version)
            except (IndexError, ValueError):
                continue
    return max(versions) + 1

def format_timestamp(timestamp_str):
    """
    Format a timestamp string into a human-readable format.
    
    Args:
        timestamp_str (str): Timestamp in format "YYYYMMDD_HHMMSS"
        
    Returns:
        str: Formatted date and time (e.g., "2024-03-20 15:30:45")
    """
    try:
        dt = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return timestamp_str

def save_specification(spec, product_name=None):
    """Save the specification to files in both Markdown and JSON formats."""
    if not product_name:
        try:
            product_name = spec.split("Product Name:")[1].split("\n")[0].strip()
        except IndexError:
            product_name = "unnamed_project"
    
    project_dir = get_project_dir(product_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version = get_next_version(project_dir)
    
    # Create filenames with version numbers
    base_filename = f"spec_v{version}"
    
    # Add timestamp to the specification content
    formatted_timestamp = format_timestamp(timestamp)
    spec_with_metadata = f"Version: {version}\nLast Updated: {formatted_timestamp}\n\n{spec}"
    
    # Save Markdown version
    md_filename = os.path.join(project_dir, f"{base_filename}.md")
    with open(md_filename, "w") as f:
        f.write(spec_with_metadata)
    
    # Convert to JSON structure
    spec_dict = {
        "version": version,
        "timestamp": timestamp,
        "formatted_timestamp": formatted_timestamp,
        "product_name": product_name,
        "specification": spec_with_metadata
    }
    
    # Save JSON version
    json_filename = os.path.join(project_dir, f"{base_filename}.json")
    with open(json_filename, "w") as f:
        json.dump(spec_dict, f, indent=2, ensure_ascii=False)
    
    print(f"\n📁 Specification v{version} saved to project '{product_name}':")
    print(f"   - Markdown: {md_filename}")
    print(f"   - JSON: {json_filename}")
    print(f"   - Last Updated: {formatted_timestamp}")

def list_specifications():
    """List all available specifications grouped by project."""
    if not os.path.exists("specs"):
        return {}
    
    projects = {}
    for project_dir in os.listdir("specs"):
        project_path = os.path.join("specs", project_dir)
        if not os.path.isdir(project_path):
            continue
        
        specs = []
        for filename in os.listdir(project_path):
            if filename.endswith(".json"):
                filepath = os.path.join(project_path, filename)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                        specs.append((
                            filename,
                            data.get("version", 0),
                            data.get("timestamp", "Unknown"),
                            data.get("formatted_timestamp", format_timestamp(data.get("timestamp", "Unknown"))),
                            data.get("product_name", project_dir)
                        ))
                except (json.JSONDecodeError, IOError):
                    continue
        
        if specs:
            specs.sort(key=lambda x: x[1], reverse=True)
            projects[project_dir] = specs
    
    return projects

def load_specification(filename):
    """
    Load a specification from a JSON file.
    
    Args:
        filename (str): Name of the JSON file to load
        
    Returns:
        tuple: (specification_text, project_name)
    """
    filepath = os.path.join("specs", filename)
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            return data.get("specification", ""), data.get("product_name")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading specification: {e}")
        return None, None

def choose_specification():
    """Allow user to choose between creating a new specification or loading an existing one."""
    print("\n📝 Welcome to the AI-Powered Product Specification Generator!")
    print("\nWhat would you like to do?")
    print("1. Create a new specification")
    print("2. Load and refine an existing specification")
    
    while True:
        choice = ask_user("Enter your choice (1 or 2):").strip()
        if choice == "1":
            return True, None
        elif choice == "2":
            projects = list_specifications()
            if not projects:
                print("\n⚠️ No existing specifications found.")
                return True, None
            
            print("\nAvailable projects:")
            project_list = list(projects.items())
            for i, (project_dir, specs) in enumerate(project_list, 1):
                latest_spec = specs[0]  # First spec is the newest
                print(f"{i}. {latest_spec[4]} (latest: v{latest_spec[1]}, updated: {latest_spec[3]})")
            
            while True:
                project_choice = ask_user("Enter the project number to load (or 'new' for a new spec):").strip()
                if project_choice.lower() == "new":
                    return True, None
                
                try:
                    project_index = int(project_choice) - 1
                    if 0 <= project_index < len(project_list):
                        project_dir, specs = project_list[project_index]
                        
                        print(f"\nVersion history for {specs[0][4]}:")
                        for i, (filename, version, _, formatted_timestamp, _) in enumerate(specs, 1):
                            print(f"{i}. Version {version} (created: {formatted_timestamp})")
                        
                        version_choice = ask_user("Enter the version number to load (or 'latest' for the latest version):").strip()
                        spec_index = 0  # Default to latest
                        
                        if version_choice.lower() != "latest":
                            try:
                                spec_index = int(version_choice) - 1
                                if not (0 <= spec_index < len(specs)):
                                    raise ValueError()
                            except ValueError:
                                print("Invalid version number. Using latest version.")
                        
                        filename = specs[spec_index][0]
                        spec, project_name = load_specification(os.path.join(project_dir, filename))
                        if spec:
                            return False, (spec, project_name)
                except ValueError:
                    pass
                print("Invalid choice. Please try again.")
        else:
            print("Invalid choice. Please enter 1 or 2.")

def suggest_project_name(spec):
    """Get an AI suggestion for the project name based on the specification."""
    prompt = """
    Based on this product specification, suggest a concise, memorable project name.
    Return ONLY the suggested name, nothing else.
    
    Specification:
    {spec}
    """.format(spec=spec)
    
    suggested_name = ask_ai(prompt, stream=False).strip()
    
    print(f"\n🤖 Suggested project name: {suggested_name}")
    
    # Ask user if they want to use the suggested name
    choice = ask_user("Would you like to use this name? (yes/no)").lower()
    if choice.startswith('y'):
        return suggested_name
    
    # If user doesn't like the suggestion, ask for their preferred name
    return ask_user("Please enter your preferred project name:")

if __name__ == "__main__":
    is_new, loaded_spec = choose_specification()
    project_name = None
    
    if is_new:
        product_description = ask_user("Describe your product in a few sentences:")
        spec = generate_initial_spec(product_description)
        print("\n📄 Initial Specification Draft:\n", spec)
    else:
        spec, project_name = loaded_spec  # Now returns both spec and name
        print("\n📄 Loaded Specification:\n", spec)
    
    updated_spec = refine_spec(spec)
    final_spec = finalize_spec(updated_spec)
    print("\n✅ FINAL PRODUCT SPECIFICATION:\n", final_spec)
    
    # Only suggest name for new specs
    if is_new:
        project_name = suggest_project_name(final_spec)
    
    save_specification(final_spec, project_name)
