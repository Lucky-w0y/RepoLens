import os
import datetime
import traceback
import json
import yaml
import shutil
import subprocess
from pathlib import Path

from minisweagent import package_dir
from minisweagent.agents.default import DefaultAgent
from minisweagent.environments.local import LocalEnvironment
from minisweagent import global_config_dir
from minisweagent.config import builtin_config_dir, get_config_path
from minisweagent.models import get_model
from minisweagent.run.utils.save import save_traj
from minisweagent.utils.log import logger

PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_NAME = "gpt-4o"
VERSION_ID = f"concerns_{MODEL_NAME}"

WORKSPACE_DIR = f"{PROJECT_ROOT}/workspace/{VERSION_ID}/App_work" # Your working dir for running agent locally, App_clean will be copied to here
os.makedirs(WORKSPACE_DIR, exist_ok=True)
JSON_OUTPUT_FILE = f"{PROJECT_ROOT}/output_{VERSION_ID}.json" # Your output json file path
TRAJECTORY_DIR = f"{PROJECT_ROOT}/trajectory" # Your trajectory dir


CONCERN_DIR = f"{PROJECT_ROOT}/../../../dataset/concerns" # concern dir
CONCERN_FILE_NAME = "__sorted_concern_list_4o-mini_emb_llm.json" # concern json file name
ISSUES_DIR = f"{PROJECT_ROOT}/../../../dataset/issues" # issue dataset dir path which contains all issue folders
ISSUE_IDS_FILE = f"{PROJECT_ROOT}/../../../dataset/issue_ids.txt" # issue id list file path which contains all issue ids for processing
SOURCE_DIR = f"{PROJECT_ROOT}/../../../dataset/App_clean" # Your clean app path
CONFIG_FILE = f"{PROJECT_ROOT}/config.toml" # Your config file path

COUNT_LIMIT = 216 # limit the number of json item in JSON_OUTPUT_FILE
MAX_ITERATION = 30  # max interaction turns for each issue

CONFIG_PATH = f"{PROJECT_ROOT}/config.yaml"
def get_task_concern_instruction(instance_id, concerns) -> str:
    issue_data_path = os.path.join(ISSUES_DIR, f"{instance_id}/issue_data.json")
    with open(issue_data_path, 'r', encoding='utf-8') as file:
         instance = json.load(file)
    instruction = f"""
<issue_title>
{instance['title']}
</issue_title>

<issue_body>
{instance['issue_repo_steps']}
</issue_body>

<concern_list>
{concerns}
</concern_list>

<instructions>
# Task Instructions

## Overview
You're a software engineer interacting continuously with a computer by submitting commands.
Your task is specifically to localize the specific files and functions that need modification or contain key information to resolve the issue.
I have provided you with the issue title, issue body, and a concern_list.

IMPORTANT: This is an interactive process where you will think and issue ONE command, see its result, then think and issue your next command.

For each response:
1. Include a THOUGHT section explaining your reasoning and what you're trying to accomplish
   - Explicitly mention how the concern_list influences your reasoning about the root cause
   - Refer to related_functions in concerns when deciding which files/functions to investigate
2. Provide exactly ONE bash command to execute

## Important Boundaries
- DO NOT MODIFY Code: Regular source code files, tests and configuration files (pyproject.toml, setup.cfg, etc.) in `{WORKSPACE_DIR}`

## Concern Guidances
Each **Concern** is a cohesive set of functionalities in code that are conceptually related to a specific term (entity, object, or domain concept) and potentially related to the issue.
  - These functionalities may be scattered across different parts of the codebase, but together they are concerned with a single responsibility or area of interest.
  - A Concern can be composed of atomic operations and low-level de tails, which, when aggregated, form a higher-level functional semantics or business logic tied to that term.

Each concern in the list is an object with the following structure:
  - concern_summary: a description of the concern, summarizing the functional semantics or business logic it represents.
  - related_functions: a list of functions related to this concern, where each item contains:
    - function_name: the name of the function.
    - file_path: the file path where the function is located.

You MUST carefully analyze these concerns to:
1. Infer the possible root cause of the issue
2. Prioritize which parts of the repository to investigate first
3. Use related_functions in each concern as entry points for exploration
4. Guide your localization of relevant files/functions

## Recommended Workflow
1. Analyze the provided concerns, including all related functions, to hypothesize the issue's root cause. For comprehensive coverage, also identify additional plausible files and functions from the broader codebase. To maximize precision, prioritize the most likely root-cause files or functions by placing them at the very top of your candidate list. 
2. Create a script to reproduce the issue.
3. Construct two ranked lists (10 files and 10 functions) that are most likely related to the issue. Ensure the top-ranked item in each list corresponds to the most probable root cause, while every entry in the lists represents a plausible root cause candidate to maximize recall.
4. give your final output and write the output in `{WORKSPACE_DIR}/result.json`.
   - The JSON object MUST contain the following two keys, each mapping to an ARRAY of strings. All file paths MUST be relative to the project root and NOT start with `./`.
      - "file_list": A list of relative file paths.
      - "function_list": Fully-qualified names of functions (e.g. `src/module/file.py:ClassName.method` or `src/module/file.py:function_name`).
   - Order the items in each list by importance, from most to least important.
   - Provide exactly 10 items in each list.
   - Do NOT include any other text, explanation, or conversation in your final response.Only the JSON object.
 
### Example:
 ```json
 {{
   "file_list": [
     "src/helpers/math_helpers.py",
     "src/services/payment_service.py"
   ],
   "function_list": [
     "src/helpers/math_helpers.py:MathUtils.calculate_sum",
     "src/services/payment_service.py:PaymentService.process"
   ]
 }}
 ```

## Command Execution Rules
Before executing commands, you should cd to the working directory: {WORKSPACE_DIR}.
You are operating in an environment where
1. You write a single command
2. The system executes that command in a subshell
3. You see the result
4. You write your next command

Each response should include:
1. A **THOUGHT** section where you explain your reasoning and plan
2. A single bash code block with your command

Format your responses like this:

<format_example>
THOUGHT: Here I explain my reasoning process, analysis of the current situation,
and what I'm trying to accomplish with the command below.

```bash
your_command_here
```
</format_example>

Commands must be specified in a single bash code block:

```bash
your_command_here
```

**CRITICAL REQUIREMENTS:**
- Your response SHOULD include a THOUGHT section explaining your reasoning
- Your response MUST include EXACTLY ONE bash code block
- This bash block MUST contain EXACTLY ONE command (or a set of commands connected with && or ||)
- If you include zero or multiple bash blocks, or no command at all, YOUR RESPONSE WILL FAIL
- Do NOT try to run multiple independent commands in separate blocks in one response
- Directory or environment variable changes are not persistent. Every action is executed in a new subshell.

Example of a CORRECT response:
<example_response>
THOUGHT: I need to understand the structure of the repository first. Let me check what files are in the current directory to get a better understanding of the codebase.

```bash
ls -la
```
</example_response>

Example of a CORRECT response:
<example_response>
THOUGHT: I have identified a code concern that may be related to the issue. I'll review the associated files and functions to gain a clearer understanding of the functionality.

```bash
cat file.txt
```
</example_response>

Example of an INCORRECT response:
<example_response>
THOUGHT: I need to examine the codebase and then look at a specific file. I'll run multiple commands to do this.

```bash
ls -la
```

Now I'll read the file:

```bash
cat file.txt
```
</example_response>

If you need to run multiple commands, either:
1. Combine them in one block using && or ||
```bash
command1 && command2 || echo "Error occurred"
```

1. Wait for the first command to complete, see its output, then issue the next command in your following response.

## Environment Details
- You have a full Linux shell environment
- Always use non-interactive flags (-y, -f) for commands
- Avoid interactive tools like vi, nano, or any that require user input
- If a command isn't available, you can install it

## Useful Command Examples

### Create a new file:
```bash
cat <<'EOF' > newfile.py
import numpy as np
hello = "world"
print(hello)
EOF
```

### Edit files with sed:
```bash
# Replace all occurrences
sed -i 's/old_string/new_string/g' filename.py

# Replace only first occurrence
sed -i 's/old_string/new_string/' filename.py

# Replace first occurrence on line 1
sed -i '1s/old_string/new_string/' filename.py

# Replace all occurrences in lines 1-10
sed -i '1,10s/old_string/new_string/g' filename.py
```

### View file content:
```bash
# View specific lines with numbers
nl -ba filename.py | sed -n '10,20p'
```

### Any other command you want to run
```bash
anything
```

## Submission
**When you've write your final result to {WORKSPACE_DIR}/result.json**
issue exactly the following command:

```bash
echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
```

This command will submit your work.
You cannot continue working in any way on this task after submitting.
</instructions>
<IMPORTANT!>
You SHOULD NEVER attempt to browse the web.
You SHOULD ONLY interact with the environment provided to you AND NEVER ASK FOR HUMAN HELP.
Don't include any lambda functions!
</IMPORTANT!>
"""
    return instruction

def get_all_json_data():
    """
    read all data in `JSON_OUTPUT_FILE`
    """
    try:
        with open(JSON_OUTPUT_FILE, 'r', encoding='utf-8') as f:
            all_data = json.load(f)
        if not isinstance(all_data, list):
            all_data = [all_data]
    except (FileNotFoundError, json.JSONDecodeError):
        all_data = []
    return all_data

def complete_status(all_data):
    """
    if an item in all_data has no 'status' field but has 'file_list' or 'function_list' or 'class_list', set its 'status' to 0
    0: success
    1: fail
    """
    for item in all_data:
        if 'status' not in item and ('file_list' in item or 'function_list' in item or 'class_list' in item):
            item['status'] = 0

def write_error_json(session_id, instance_id, used_turns):
    """
    write failure json to JSON_OUTPUT_FILE
    """
    json_data = {}
    json_data["session_id"] = session_id
    json_data["issue_id"] = instance_id
    json_data["status"] = 1 # failure
    json_data['used_turns'] = used_turns

    all_data = get_all_json_data()
    complete_status(all_data)
    all_data.append(json_data)

    with open(JSON_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2)

def write_json(json_data, trajectory_id, used_turn, instance_id):
    """
    write json_data to JSON_OUTPUT_FILE
    if json_data is None, write failure json to JSON_OUTPUT_FILE
    """

    if json_data:
        json_data["session_id"] = trajectory_id
        json_data["issue_id"] = instance_id
        json_data["status"] = 0
        json_data['used_turns'] = used_turn
        try:
            # append new data
            all_data = get_all_json_data()
            complete_status(all_data)
            all_data.append(json_data)
            with open(JSON_OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, indent=2)
        except Exception as e:
            print(e)
    else:
        try:
            write_error_json(trajectory_id, instance_id, used_turn)
        except Exception as e:
            print(e)

def main(instance_id):  
    concern_file_path = os.path.join(CONCERN_DIR, f"{instance_id}/{CONCERN_FILE_NAME}")
    with open(concern_file_path, 'r', encoding='utf-8') as file:
        concerns = json.load(file)
    try:
        assert(concerns)
    except Exception as e:
        print(e)
        return
    task_str = get_task_concern_instruction(instance_id, concerns)

    # set trajectory file name
    trajectory_id = f"issue_{instance_id}.log"

    config = yaml.safe_load(get_config_path(CONFIG_PATH).read_text())
    env = LocalEnvironment(**config.get("env", {}), cwd=WORKSPACE_DIR)
    model = get_model(MODEL_NAME, config.get("model", {}))

    model.config.model_kwargs['temperature'] = 0.0
    agent = DefaultAgent(
        model=model,
        env=env,
        **config.get("agent", {}),
    )
    exit_status, result, extra_info = None, None, None
    try:
        exit_status, result = agent.run(task_str)  # type: ignore[arg-type]
    except Exception as e:
        logger.error(f"Error running agent: {e}", exc_info=True)
        exit_status, result = type(e).__name__, str(e)
        extra_info = {"traceback": traceback.format_exc()}

    trajectory_path = Path(TRAJECTORY_DIR) / f"{trajectory_id}.json"
    save_traj(agent, trajectory_path, exit_status=exit_status, result=result, extra_info=extra_info)

    # 1. extract json data
    try:
        with open(WORKSPACE_DIR + '/result.json', 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    except Exception as e:
        print(e)
        json_data = None
    used_turns = agent.model.n_calls
    if json_data and "file_list" in json_data and "function_list" in json_data:
        write_json(json_data, trajectory_id, used_turns, instance_id)
    else:
        write_error_json(trajectory_id, instance_id, used_turns)
        # unexpected error, exit the pipeline
        if used_turns == 1:
            print('Only one turn used, likely an error occurred, exiting pipeline.')
            exit()
        return

# git checkout
def checkout(instance_id):
    # remove local workspace dir if exists
    workspace_dir = WORKSPACE_DIR
    if os.path.exists(workspace_dir):
        try:
            shutil.rmtree(workspace_dir)
        except Exception as e:
            subprocess.run(["rm", "-rf", workspace_dir])

    # copy clean source code to workspace dir
    source_dir = SOURCE_DIR
    try:
        shutil.copytree(source_dir, workspace_dir)
    except Exception as e:
        print(e)
        subprocess.run(["cp", "-r", source_dir, workspace_dir])

    try:
        os.chdir(workspace_dir)
    except Exception as e:
        print(e)

    # bug reproduction
    the_issue_dir = os.path.join(ISSUES_DIR, f"{instance_id}")
    # get commid id from issue folder
    commit_id_file = os.path.join(the_issue_dir, "commit_id.txt")
    with open(commit_id_file, 'r', encoding='utf-8') as file:
        commit_id = file.read().strip()

    # git checkout
    subprocess.run(["git", "checkout", commit_id])

    # git apply
    subprocess.run(["git", "apply", f"{the_issue_dir}/bug_reintroduce.patch"])

    # git commit
    subprocess.run(["git", "add", "."])
    subprocess.run(["git", "commit", "-m", f"Reproduce bug by applying {instance_id}.patch"])

def pipeline(instance_id):
    checkout(instance_id)
    main(instance_id)

if __name__ == '__main__':
    # 0. remove unexpected results in JSON_OUTPUT_FILE
    if os.path.exists(JSON_OUTPUT_FILE):
        with open(JSON_OUTPUT_FILE, 'r', encoding='utf-8') as f:
                output_data = json.load(f)
                if not isinstance(output_data, list):
                    output_data = [output_data]
        cleaned_data = []
        cleaned_count = 0
        # remove items with 'used_turns' <= 1 and 'status' != 0 which are likely unexpected results
        for item in output_data:
            if 'used_turns' in item and item['used_turns'] <= 1 and item['status'] != 0:
                cleaned_count += 1
                continue
            else:
                cleaned_data.append(item)
        cleaned_data.sort(key=lambda item: int(item['issue_id']))
        with open(JSON_OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, indent=4)

    # 1. read all processed issue IDs
    processed_issue_ids = set()
    try:
        with open(JSON_OUTPUT_FILE, 'r', encoding='utf-8') as f:
            output_data = json.load(f)
            if not isinstance(output_data, list):
                output_data = [output_data]
            for item in output_data:
                    if 'issue_id' in item:
                        processed_issue_ids.add(str(item['issue_id']))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
   
    count_limit = COUNT_LIMIT

    # 2. read all unprocessed issue IDs
    try:
        with open(ISSUE_IDS_FILE, 'r', encoding='utf-8') as f:
            all_instance_ids = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        all_instance_ids = []

    already_count = len(processed_issue_ids)
    # 3. run pipeline for each unprocessed issue ID
    for instance_id in all_instance_ids:
        if already_count >= count_limit: 
            print(f"have processed {already_count} issues, reach the limit, exit")
            break
        if instance_id in processed_issue_ids:
            print(f"skip processed issue: {instance_id}")
            continue

        pipeline(instance_id)
        already_count += 1