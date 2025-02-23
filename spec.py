import openai
import json
from datetime import datetime
import os
from dotenv import load_dotenv

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

# AI prompt templates
AI_INITIAL_PROMPT = """
You are an AI that helps users write product specifications. Given a brief product description, generate an initial structured product specification with these sections:
- **Product Name**
- **Objective**
- **Features**
- **Technical Specifications**
- **User Scenarios**

Ensure the format is clean and structured, with placeholders for missing information.
"""

AI_REFINEMENT_PROMPT = """
You are a JSON-focused AI assistant. Your task is to analyze this product specification and generate follow-up questions.

Here is the current product specification:
{spec}

You must respond with a JSON array of questions, following this exact format:
[
    {{
        "section": "Section Name",
        "question": "Your specific question about this section"
    }}
]

Requirements:
1. Response MUST be valid JSON
2. Response must ONLY contain the JSON array, no additional text
3. Each object in the array MUST have exactly two fields: "section" and "question"
4. Questions should be specific and actionable
5. Prioritize the most important questions first
6. Maximum 3 questions at a time

Example of valid response:
[
    {{
        "section": "Technical Architecture",
        "question": "What specific database technology will be used for storing user profiles?"
    }},
    {{
        "section": "Security",
        "question": "What authentication method will be implemented for user login?"
    }}
]
"""

AI_FINAL_REFINEMENT_PROMPT = """
Here is the current product specification:
{spec}

Now, using the provided responses, generate the final, well-structured specification.
"""

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
    while True:
        print("\n🔍 AI is identifying missing sections...")
        refinement_prompt = AI_REFINEMENT_PROMPT.format(spec=spec)
        follow_up_questions = ask_ai(refinement_prompt, stream=False)  # No streaming for structured data

        try:
            # Add debug logging
            print("\nDebug - AI Response:", follow_up_questions)
            
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
        str: The specification text
    """
    filepath = os.path.join("specs", filename)
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
            return data.get("specification", "")
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error loading specification: {e}")
        return None

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
                        spec = load_specification(os.path.join(project_dir, filename))
                        if spec:
                            return False, spec
                except ValueError:
                    pass
                print("Invalid choice. Please try again.")
        else:
            print("Invalid choice. Please enter 1 or 2.")

if __name__ == "__main__":
    # Choose whether to create new or load existing
    is_new, loaded_spec = choose_specification()
    
    if is_new:
        # Create new specification
        product_description = ask_user("Describe your product in a few sentences:")
        spec = generate_initial_spec(product_description)
        print("\n📄 Initial Specification Draft:\n", spec)
    else:
        # Use loaded specification
        spec = loaded_spec
        print("\n📄 Loaded Specification:\n", spec)
    
    # Continue with refinement
    updated_spec = refine_spec(spec)
    
    # Final AI-powered formatting
    final_spec = finalize_spec(updated_spec)
    
    # Display the final product specification
    print("\n✅ FINAL PRODUCT SPECIFICATION:\n", final_spec)
    
    # Save the specification
    save_specification(final_spec)
