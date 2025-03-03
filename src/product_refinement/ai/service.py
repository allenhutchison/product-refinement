"""AI service for generating and refining product specifications."""
import functools
import hashlib
import json
import logging
import os
import pickle
import sys
import time
from typing import Dict, List, Optional, Any

import llm

from ..utils.config import Config
from ..utils.display import ask_user
from ..utils.types import Question

class AIService:
    """Service for interacting with AI models."""
    
    def __init__(self, config: Config):
        """Initialize the AI service with configuration."""
        self.config = config
        self.llm = None  # Lazy initialization
        self._load_prompts()
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.config.CACHE_DIR, exist_ok=True)
    
    def _load_prompts(self) -> None:
        """Load all prompts from files."""
        try:
            self.initial_prompt = self._load_prompt_file("initial.txt")
            self.refinement_prompt = self._load_prompt_file("refinement.txt")
            self.final_refinement_prompt = self._load_prompt_file("final_refinement.txt")
            self.todo_prompt = self._load_prompt_file("todo.txt")
        except ValueError as e:
            logging.error(f"Error loading prompts: {str(e)}")
            sys.exit(1)
    
    def _load_prompt_file(self, prompt_file: str) -> str:
        """
        Load a prompt from a file in the prompts directory.
        
        Args:
            prompt_file (str): Name of the prompt file to load
            
        Returns:
            str: Content of the prompt file
            
        Raises:
            ValueError: If the prompt file cannot be loaded
        """
        prompt_path = os.path.join(self.config.PROMPT_DIR, prompt_file)
        try:
            with open(prompt_path, "r") as f:
                return f.read().strip()
        except IOError as e:
            raise ValueError(f"Failed to load prompt file {prompt_file}: {str(e)}")
    
    def get_cache_key(self, method_name: str, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key based on method name and arguments."""
        # Create a string representation of the arguments
        args_str = str(args) + str(sorted(kwargs.items()))
        
        # Add model name to make cache key model-specific
        model_key = f"{self.config.MODEL_NAME}:{args_str}"
        
        # Create a hash of the arguments
        key = hashlib.md5(f"{method_name}:{model_key}".encode()).hexdigest()
        return key
    
    def get_cached_response(self, cache_key: str) -> Optional[str]:
        """Try to get a cached response."""
        cache_file = os.path.join(self.config.CACHE_DIR, cache_key)
        
        if os.path.exists(cache_file):
            # Check if cache has expired
            if time.time() - os.path.getmtime(cache_file) > self.config.CACHE_EXPIRY:
                logging.debug(f"Cache expired for key {cache_key}")
                return None
                
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)
                    logging.debug(f"Cache hit for key {cache_key}")
                    return cached_data
            except Exception as e:
                logging.warning(f"Error reading cache: {e}")
                
        return None
    
    def save_to_cache(self, cache_key: str, data: Any) -> None:
        """Save response to cache."""
        cache_file = os.path.join(self.config.CACHE_DIR, cache_key)
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(data, f)
            logging.debug(f"Saved to cache: {cache_key}")
        except Exception as e:
            logging.warning(f"Error saving to cache: {e}")
    
    def cached_ai_call(method):
        """Decorator to cache AI calls."""
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            # Generate cache key
            cache_key = self.get_cache_key(method.__name__, *args, **kwargs)
            
            # Try to get cached response
            cached_response = self.get_cached_response(cache_key)
            if cached_response is not None:
                return cached_response
            
            # Call original method if no cache hit
            result = method(self, *args, **kwargs)
            
            # Save result to cache
            self.save_to_cache(cache_key, result)
            
            return result
        return wrapper
    
    def _get_model(self, max_retries: int = 3, retry_delay: float = 2.0):
        """Get the AI model with retry logic."""
        if self.llm is not None:
            return self.llm
            
        import importlib.util
        
        if importlib.util.find_spec("llm") is None:
            error_msg = "Error: The 'llm' package is not installed. Please install it with 'pip install llm'."
            logging.error(error_msg)
            print(error_msg)
            return None
            
        import llm
        
        for attempt in range(max_retries):
            try:
                self.llm = llm.get_model(self.config.MODEL_NAME)
                return self.llm
            except ConnectionError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logging.warning(f"Connection error: {e}. Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                else:
                    logging.error(f"Failed to connect to AI model after {max_retries} attempts: {e}")
                    print(f"Error: Could not connect to the AI model. Please check your internet connection.")
                    return None
            except Exception as e:
                logging.error(f"Error getting AI model: {e}")
                print(f"Error: Could not load the AI model '{self.config.MODEL_NAME}'. Try using a different model.")
                return None
        
        return None

    def ask(self, prompt: str, model_name: Optional[str] = None, stream: bool = True, show_response: bool = True) -> str:
        """
        Calls the AI model using the llm library.

        Args:
            prompt (str): The input prompt to the AI model.
            model_name (str, optional): The name of the model to use. If None, uses the default from config.
            stream (bool): Whether to stream the response.
            show_response (bool): Whether to print the response when not streaming.

        Returns:
            str: The full AI-generated response.
        """
        # Set model name if provided, otherwise use default
        if model_name:
            current_model_name = self.config.MODEL_NAME
            self.config.MODEL_NAME = model_name
            self.llm = None  # Reset to force reload with new model
        
        try:
            # Get the model
            model = self._get_model()
            if not model:
                return "ERROR: Could not access the AI model."
            
            # Generate the response
            if stream:
                print(f"\n🤖 AI Response (Streaming with {self.config.MODEL_NAME})...")
                response_text = ""
                # Stream the response as it's generated
                for chunk in model.prompt(prompt):
                    print(chunk, end="", flush=True)
                    response_text += chunk
                print("\n")
                return response_text.strip()
            else:
                # For non-streaming responses, ensure we get the complete response
                response = model.prompt(prompt)
                response_text = response.text()
                
                # Log the raw response for debugging
                logging.debug(f"Raw model response: {response_text}")
                
                # Clean up the response
                response_text = response_text.strip()
                
                # For JSON responses, ensure we have complete JSON
                if response_text.startswith("{"):
                    # Find the last closing brace
                    last_brace = response_text.rfind("}")
                    if last_brace != -1:
                        response_text = response_text[:last_brace + 1]
                    else:
                        logging.warning("Response appears to be JSON but is incomplete")
                
                if show_response:
                    print(f"\n🤖 AI Response (Using {self.config.MODEL_NAME})...")
                    print(response_text)
                    print("\n")
                else:
                    print(f"\n🤖 Processing AI response (Using {self.config.MODEL_NAME})...")
                
                return response_text
                
        except Exception as e:
            logging.error(f"Error calling AI model: {str(e)}")
            return f"ERROR: Problem with the AI model response. {str(e)}"
        finally:
            # Restore original model name if it was changed
            if model_name:
                self.config.MODEL_NAME = current_model_name
                self.llm = None  # Reset to force reload with original model

    @cached_ai_call
    def generate_initial_spec(self, description: str) -> str:
        """
        Generate an initial product specification using AI.
        
        Args:
            description (str): Brief description of the product
            
        Returns:
            str: Initial product specification
        """
        prompt = self.initial_prompt + f"\n\nProduct description: {description}"
        response = self.ask(prompt, stream=False, show_response=False)
        
        if response.startswith("ERROR:"):
            print(f"\n⚠️ {response}")
            user_choice = ask_user("Would you like to try again with a different model? (yes/no)")
            if user_choice.lower().startswith('y'):
                model_name = ask_user("Please enter the model name to try:")
                print(f"\n🔄 Retrying with {model_name}...")
                response = self.ask(prompt, model_name=model_name, stream=False, show_response=False)
            else:
                print("\n⚠️ Continuing with empty specification. You may need to add more details manually.")
                return "Error occurred during generation. Please add specification details manually."
        
        return response
    
    def _extract_questions_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        Fallback method to extract questions from text if JSON parsing fails.
        
        Args:
            text (str): The text to extract questions from
            
        Returns:
            List[Dict[str, str]]: List of extracted questions
        """
        questions = []
        
        # Simple heuristic: look for lines that might contain questions
        lines = text.split('\n')
        current_section = "General"
        
        for line in lines:
            line = line.strip()
            
            # Try to identify section headers
            if line.endswith(':') and not line.startswith('"') and len(line) < 50:
                current_section = line.rstrip(':').strip()
                continue
            
            # Clean up JSON-like text
            if line.startswith('"question":'):
                line = line.replace('"question":', '').strip()
                if line.startswith('"') and line.endswith('"'):
                    line = line[1:-1]  # Remove quotes
            
            # Look for question marks
            if '?' in line and len(line) > 10:
                # Clean up any remaining JSON artifacts
                line = line.strip('",')
                questions.append({
                    'section': current_section,
                    'question': line
                })
                
        logging.info(f"Extracted {len(questions)} questions using fallback method")
        return questions[:1]  # Return at most one question to avoid flooding the user
    
    @cached_ai_call
    def get_follow_up_questions(self, spec: str, answered_questions_text: str) -> List[Question]:
        """
        Get follow-up questions about the specification from the AI.
        
        Args:
            spec (str): The current specification
            answered_questions_text (str): Text describing previously answered questions
            
        Returns:
            List[Question]: List of questions with 'section' and 'question' keys
        """
        refinement_prompt = self.refinement_prompt.format(
            spec=spec,
            answered_questions=answered_questions_text
        )
        response = self.ask(refinement_prompt, stream=False, show_response=False)
        
        if response.startswith("ERROR:"):
            logging.error(f"Error in get_follow_up_questions: {response}")
            # Return an empty array to prevent further errors
            return []
        
        # Parse the JSON response
        try:
            questions = json.loads(response)
            if not isinstance(questions, list):
                logging.error("AI response is not a JSON array")
                return []
                
            # Validate each question has the expected fields
            valid_questions = []
            for question in questions:
                if isinstance(question, dict) and 'section' in question and 'question' in question:
                    valid_questions.append(question)
                else:
                    logging.warning(f"Skipping invalid question format: {question}")
                    
            return valid_questions
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse AI response as JSON: {e}")
            # Try to extract questions if JSON parsing failed
            return self._extract_questions_from_text(response)
    
    @cached_ai_call
    def finalize_spec(self, spec: str) -> str:
        """
        Generate the final well-structured product specification using AI.
        
        Args:
            spec (str): The refined product specification
            
        Returns:
            str: The finalized product specification
        """
        final_prompt = self.final_refinement_prompt.format(spec=spec)
        response = self.ask(final_prompt, stream=False, show_response=False)
        
        if response.startswith("ERROR:"):
            print(f"\n⚠️ {response}")
            print("\n⚠️ Unable to finalize the specification. Returning the unfinalized version.")
            return spec
        
        return response
    
    @cached_ai_call
    def suggest_project_name(self, spec: str) -> str:
        """
        Get an AI suggestion for a project name based on the specification.
        
        Args:
            spec (str): The product specification
            
        Returns:
            str: The suggested project name
        """
        prompt = """
        Based on this product specification, suggest a concise, memorable project name.
        Return ONLY the suggested name, nothing else.
        
        Specification:
        {spec}
        """.format(spec=spec)
        
        response = self.ask(prompt, stream=False, show_response=True)
        
        if response.startswith("ERROR:"):
            print(f"\n⚠️ {response}")
            return "untitled_project"
        
        return response.strip()

    @cached_ai_call
    def generate_todo_list(self, spec: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate an engineering todo list from a specification.
        
        Args:
            spec (str): The product specification
            
        Returns:
            Dict[str, List[Dict[str, Any]]]: The generated todo list with tasks
        """
        # Use a direct approach instead of trying to get valid JSON from the model
        # Define sections we want to generate tasks for
        sections = [
            "Architecture", 
            "Core Features", 
            "Infrastructure", 
            "Testing", 
            "Documentation",
            "Security",
            "Performance"
        ]
        
        tasks = []
        
        # Generate tasks for each section separately
        for section in sections:
            prompt = f"""
            You are a technical lead creating an engineering todo list for a product.
            For the '{section}' section only, create 2-3 focused tasks based on this specification:
            
            {spec}
            
            For each task, provide:
            1. A brief title (one line)
            2. Complexity (Low/Medium/High)
            3. Dependencies (if any)
            4. A detailed description (2-3 sentences)
            5. Technical notes (1-2 sentences)
            6. Testing notes (1-2 sentences)
            
            Format your response as a clean simple list with clear sections. Do not include any explanations or formatting beyond the task details.
            """
            
            response = self.ask(prompt, stream=False, show_response=False)
            
            if response.startswith("ERROR:"):
                logging.error(f"Error generating tasks for section {section}: {response}")
                continue
                
            # Parse the response into task objects manually
            task_blocks = self._parse_tasks_from_text(response, section)
            tasks.extend(task_blocks)
            
        return {"tasks": tasks}
        
    def _parse_tasks_from_text(self, text: str, section: str) -> List[Dict[str, Any]]:
        """
        Parse tasks from the AI-generated text.
        
        Args:
            text (str): The AI-generated text
            section (str): The section these tasks belong to
            
        Returns:
            List[Dict[str, Any]]: List of parsed tasks
        """
        tasks = []
        
        # Split text by double newlines to separate tasks
        blocks = text.split("\n\n")
        
        current_task = {"section": section}
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
                
            # Check if this block is a new task (starts with a number or has "Task" in the first line)
            if block[0].isdigit() or "Task" in block.split("\n")[0]:
                # If we have a task in progress, save it and start a new one
                if "title" in current_task:
                    tasks.append(current_task)
                current_task = {"section": section}
                
                # The first line is the title
                lines = block.split("\n")
                title_line = lines[0]
                # Remove any numbering or "Task:" prefix
                title = title_line.strip()
                if ":" in title:
                    title = title.split(":", 1)[1].strip()
                elif "." in title and title.split(".", 1)[0].isdigit():
                    title = title.split(".", 1)[1].strip()
                    
                current_task["title"] = title
                
                # Process the rest of the lines
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Look for complexity, dependencies, etc.
                    if "complexity" in line.lower():
                        complexity = line.split(":", 1)[1].strip() if ":" in line else "Medium"
                        current_task["complexity"] = complexity
                    elif "dependencies" in line.lower():
                        deps = line.split(":", 1)[1].strip() if ":" in line else ""
                        current_task["dependencies"] = [d.strip() for d in deps.split(",") if d.strip()]
                    elif "description" in line.lower():
                        desc = line.split(":", 1)[1].strip() if ":" in line else line
                        current_task["description"] = desc
                    elif "technical" in line.lower() and "notes" in line.lower():
                        tech = line.split(":", 1)[1].strip() if ":" in line else line
                        current_task["technical_notes"] = tech
                    elif "testing" in line.lower() and "notes" in line.lower():
                        test = line.split(":", 1)[1].strip() if ":" in line else line
                        current_task["testing_notes"] = test
            elif "title" in current_task:
                # This is a continuation of a field from the current task
                if "complexity" in block.lower():
                    complexity = block.split(":", 1)[1].strip() if ":" in block else "Medium"
                    current_task["complexity"] = complexity
                elif "dependencies" in block.lower():
                    deps = block.split(":", 1)[1].strip() if ":" in block else ""
                    current_task["dependencies"] = [d.strip() for d in deps.split(",") if d.strip()]
                elif "description" in block.lower():
                    desc = block.split(":", 1)[1].strip() if ":" in block else block
                    current_task["description"] = desc
                elif "technical" in block.lower() and "notes" in block.lower():
                    tech = block.split(":", 1)[1].strip() if ":" in block else block
                    current_task["technical_notes"] = tech
                elif "testing" in block.lower() and "notes" in block.lower():
                    test = block.split(":", 1)[1].strip() if ":" in block else block
                    current_task["testing_notes"] = test
                else:
                    # If we can't identify the field, assume it's a description
                    current_task["description"] = current_task.get("description", "") + "\n" + block
        
        # Add the last task if there is one
        if "title" in current_task:
            tasks.append(current_task)
            
        # Ensure all tasks have the required fields
        for task in tasks:
            task.setdefault("title", "Untitled Task")
            task.setdefault("complexity", "Medium")
            task.setdefault("dependencies", [])
            task.setdefault("description", "No description provided.")
            task.setdefault("technical_notes", "")
            task.setdefault("testing_notes", "")
            
        return tasks 