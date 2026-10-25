import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# 1. Load environment variables
load_dotenv()
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in environment or .env file.")

# 2. Initialize Groq client
client = Groq(api_key=api_key)
grokmodel = "openai/gpt-oss-120b"

BASE_DIR = Path(__file__).resolve().parent
IGNORED_DIRS = {".git", ".venv", "venv", "__pycache__", ".vscode", ".idea", "bin", "obj"}

# Determine workspace directory
candidate_subdirs = [
    d for d in BASE_DIR.iterdir()
    if d.is_dir() and d.name not in IGNORED_DIRS and any(list(d.glob("*.java")) + list(d.glob("*.cpp")))
]
WORKSPACE_DIR = candidate_subdirs[0] if candidate_subdirs else BASE_DIR

# Track if fix was applied
fix_applied = False


# ==========================================
# Tool 1: search_files
# ==========================================
def search_files(directory=".", extension=None):
    """
    Lists paths of source files in the workspace directory.
    """
    target_dir = (WORKSPACE_DIR / directory).resolve()
    print(f"\n[TOOL CALLED] search_files(directory='{directory}', extension='{extension}')")
    
    found_files = []
    if target_dir.exists() and target_dir.is_dir():
        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
            for file in files:
                if file.startswith("."):
                    continue
                if extension:
                    if file.endswith(extension):
                        rel_path = os.path.relpath(os.path.join(root, file), WORKSPACE_DIR)
                        found_files.append(rel_path.replace("\\", "/"))
                else:
                    if file.endswith((".java", ".cpp", ".py", ".c", ".h")):
                        rel_path = os.path.relpath(os.path.join(root, file), WORKSPACE_DIR)
                        found_files.append(rel_path.replace("\\", "/"))
    
    result = {"files": found_files, "total": len(found_files)}
    print(f"[TOOL RESULT] Found {len(found_files)} source file(s): {found_files}")
    return json.dumps(result)


# ==========================================
# Tool 2: search_in_file
# ==========================================
def search_in_file(file_path, query=None):
    """
    Reads a file and returns its lines with line numbers.
    """
    target_path = (WORKSPACE_DIR / file_path).resolve()
    print(f"\n[TOOL CALLED] search_in_file(file_path='{file_path}', query='{query}')")
    
    if not target_path.exists():
        err_msg = f"Error: File '{file_path}' does not exist in workspace."
        print(f"[TOOL RESULT] {err_msg}")
        return json.dumps({"error": err_msg})
    
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        all_lines = [{"line_number": i, "content": line.rstrip("\r\n")} for i, line in enumerate(lines, start=1)]
        
        if query and str(query).lower() not in {"none", "", "all"}:
            filtered = [item for item in all_lines if str(query).lower() in item["content"].lower()]
            if filtered:
                print(f"[TOOL RESULT] Found {len(filtered)} line(s) matching '{query}' in '{file_path}'.")
                return json.dumps({"file": file_path, "total_lines": len(lines), "matches": filtered})
            else:
                print(f"[TOOL RESULT] No direct match for '{query}'. Returning full file with line numbers.")
                return json.dumps({
                    "file": file_path,
                    "note": f"No direct match for '{query}'. Full file content provided below with line numbers.",
                    "total_lines": len(lines),
                    "matches": all_lines
                })
        
        print(f"[TOOL RESULT] Returned all {len(all_lines)} line(s) with line numbers from '{file_path}'.")
        return json.dumps({"file": file_path, "total_lines": len(lines), "matches": all_lines})
    except Exception as e:
        err_msg = f"Error reading file: {str(e)}"
        print(f"[TOOL RESULT] {err_msg}")
        return json.dumps({"error": err_msg})


# ==========================================
# Tool 3: replace_in_file
# ==========================================
def replace_in_file(file_path, target=None, replacement="", line_number=None):
    """
    Replaces a target line/string or replaces a specific line number with the replacement line.
    """
    global fix_applied
    target_path = (WORKSPACE_DIR / file_path).resolve()
    print(f"\n[TOOL CALLED] replace_in_file(file_path='{file_path}', line_number={line_number}, target='{target}', replacement='{replacement}')")
    
    if not target_path.exists():
        err_msg = f"Error: File '{file_path}' does not exist."
        print(f"[TOOL RESULT] {err_msg}")
        return json.dumps({"error": err_msg})
    
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Method 1: Replace by line number if provided
        if line_number is not None:
            lines = content.splitlines(keepends=True)
            idx = int(line_number) - 1
            if 0 <= idx < len(lines):
                old_line = lines[idx]
                newline_char = "\n" if not replacement.endswith("\n") else ""
                lines[idx] = replacement + newline_char
                new_content = "".join(lines)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                fix_applied = True
                msg = f"Successfully replaced line {line_number}: '{old_line.strip()}' -> '{replacement.strip()}'"
                print(f"[TOOL RESULT] {msg}")
                return json.dumps({"success": True, "message": msg})
            else:
                err_msg = f"Line number {line_number} is out of range (1 to {len(lines)})."
                print(f"[TOOL RESULT] {err_msg}")
                return json.dumps({"error": err_msg})

        # Method 2: Replace by target string
        if target:
            if target not in content:
                matched = False
                lines = content.splitlines(keepends=True)
                for i, line in enumerate(lines):
                    if target.strip() in line:
                        lines[i] = replacement + ("\n" if not replacement.endswith("\n") else "")
                        matched = True
                        break
                if matched:
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write("".join(lines))
                    fix_applied = True
                    msg = f"Successfully replaced line containing '{target.strip()}' with '{replacement.strip()}'"
                    print(f"[TOOL RESULT] {msg}")
                    return json.dumps({"success": True, "message": msg})
                else:
                    err_msg = f"Target text '{target}' not found in '{file_path}'."
                    print(f"[TOOL RESULT] {err_msg}")
                    return json.dumps({"error": err_msg})
            
            new_content = content.replace(target, replacement, 1)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            fix_applied = True
            msg = f"Successfully replaced '{target.strip()}' with '{replacement.strip()}' in '{file_path}'"
            print(f"[TOOL RESULT] {msg}")
            return json.dumps({"success": True, "message": msg})
        
        return json.dumps({"error": "Either target string or line_number must be provided."})
    except Exception as e:
        err_msg = f"Error writing file: {str(e)}"
        print(f"[TOOL RESULT] {err_msg}")
        return json.dumps({"error": err_msg})


# ==========================================
# Tool Definitions for Groq Function Calling
# ==========================================
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Lists paths of source files in the workspace (e.g. .java files).",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory to search in, defaults to '.'",
                        "default": "."
                    },
                    "extension": {
                        "type": "string",
                        "description": "Optional file extension filter, e.g., '.java'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_file",
            "description": "Reads a file and returns its lines with line numbers. Can optionally filter by keyword query to find bug-related lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path of the file to inspect."
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional keyword or method name to search for."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "replace_in_file",
            "description": "Replaces a specific line (by line number) or target code snippet with a replacement line to fix the bug.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file to modify."
                    },
                    "line_number": {
                        "type": "integer",
                        "description": "The 1-based line number to replace."
                    },
                    "target": {
                        "type": "string",
                        "description": "The exact line or snippet to be replaced."
                    },
                    "replacement": {
                        "type": "string",
                        "description": "The new replacement code line."
                    }
                },
                "required": ["file_path", "replacement"]
            }
        }
    }
]


def execute_tool(tool_name, arguments_json):
    """Parses tool arguments and calls the corresponding Python function."""
    try:
        args = json.loads(arguments_json) if isinstance(arguments_json, str) else arguments_json
    except Exception:
        args = {}

    if tool_name == "search_files":
        return search_files(
            directory=args.get("directory", "."),
            extension=args.get("extension")
        )
    elif tool_name == "search_in_file":
        return search_in_file(
            file_path=args.get("file_path", ""),
            query=args.get("query")
        )
    elif tool_name == "replace_in_file":
        return replace_in_file(
            file_path=args.get("file_path", ""),
            target=args.get("target"),
            replacement=args.get("replacement", ""),
            line_number=args.get("line_number")
        )
    else:
        err = f"Unknown tool: {tool_name}"
        print(f"[ERROR] {err}")
        return json.dumps({"error": err})


# ==========================================
# Coding Agent Execution Loop
# ==========================================
def run_attempt(bug_description, code_files, attempt_num, max_attempts=3):
    """
    Executes a full solving attempt using tool calls.
    Allows multiple tool steps (inspect -> replace) within the attempt.
    """
    global fix_applied
    fix_applied = False

    files_list_str = ", ".join(code_files)
    system_prompt = (
        "You are an expert autonomous coding agent that fixes simple bugs in software projects.\n"
        f"Project Workspace Directory: {WORKSPACE_DIR}\n"
        f"Available Source Files: {files_list_str}\n\n"
        "You have access to 3 tools:\n"
        "1. search_files: list files in the project.\n"
        "2. search_in_file: inspect a file and get exact line numbers.\n"
        "3. replace_in_file: replace an incorrect line or target snippet with the corrected line.\n\n"
        "Instructions:\n"
        f"- The user's code files are: {files_list_str}.\n"
        "- Step 1: Use search_in_file to inspect the relevant file and find the exact line number of the bug.\n"
        "- Step 2: Use replace_in_file immediately to fix the bug in the file.\n"
        "- Do not just talk or say what you plan to do; call replace_in_file to make the actual modification!\n"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Fix this bug: {bug_description}"}
    ]

    # Allow up to 5 steps inside this attempt to investigate and apply the fix
    MAX_STEPS_PER_ATTEMPT = 5
    for step in range(1, MAX_STEPS_PER_ATTEMPT + 1):
        try:
            response = client.chat.completions.create(
                model=grokmodel,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.1
            )
        except Exception as e:
            print(f"[ERROR] Groq API call failed: {e}")
            return False

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        # Case 1: LLM wants to call tools
        if tool_calls:
            messages.append(response_message)
            for call in tool_calls:
                fn_name = call.function.name
                fn_args = call.function.arguments
                tool_output = execute_tool(fn_name, fn_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": tool_output
                })

            # If replace_in_file was executed successfully, we succeeded!
            if fix_applied:
                return True

        # Case 2: LLM returned text
        else:
            final_text = response_message.content or ""
            messages.append({"role": "assistant", "content": final_text})
            if fix_applied:
                print(f"\nAgent Summary: {final_text}")
                return True
            else:
                # LLM didn't call tools yet, prompt it to use tools
                messages.append({
                    "role": "user",
                    "content": "Please inspect the file using search_in_file and apply the fix using replace_in_file."
                })

    return fix_applied


def solve_bug(bug_description, max_retries=3):
    global fix_applied
    code_files = [
        f for f in os.listdir(WORKSPACE_DIR)
        if f.endswith((".java", ".cpp", ".py", ".c", ".h"))
        and not f.startswith(".")
        and f not in {"main.py", "agent.py"}
    ]

    for attempt in range(1, max_retries + 1):
        print(f"\n>>> [Attempt {attempt} of {max_retries}] Contacting Groq LLM...")
        success = run_attempt(bug_description, code_files, attempt, max_retries)
        if success:
            print("\n" + "=" * 60)
            print(" [SUCCESS] Bug solved successfully! (File modifications applied)")
            print("=" * 60 + "\n")
            return True
        else:
            if attempt < max_retries:
                print(f"[WARNING] Attempt {attempt} did not resolve the bug. Retrying...")

    print("\n" + "!" * 60)
    print(" [FAILURE] Cannot solve the bug inside the limit of 3 retries.")
    print("!" * 60 + "\n")
    return False


# ==========================================
# CLI Entry Point
# ==========================================
def main():
    code_files = [
        f for f in os.listdir(WORKSPACE_DIR)
        if f.endswith((".java", ".cpp", ".py", ".c", ".h"))
        and not f.startswith(".")
        and f not in {"main.py", "agent.py"}
    ]
    if not code_files:
        code_files = [f for f in os.listdir(WORKSPACE_DIR) if not f.startswith(".") and f not in IGNORED_DIRS]

    print("=" * 60)
    print("MINI CODING AGENT")
    print("=" * 60)
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"Files    : {', '.join(code_files)}")
    print()

    if len(sys.argv) > 1:
        bug = " ".join(sys.argv[1:])
        print(f"Describe the bug in simple English: {bug}")
    else:
        try:
            bug = input("Describe the bug in simple English: ").strip()
        except EOFError:
            bug = ""

    if not bug:
        print("No bug description provided. Exiting.")
        return

    solve_bug(bug, max_retries=3)


if __name__ == "__main__":
    main()
