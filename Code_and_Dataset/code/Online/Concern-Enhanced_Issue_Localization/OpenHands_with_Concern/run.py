from math import log
import sys
import os
import argparse

import asyncio
import json
import os
from pathlib import Path
from typing import Callable, Protocol
import shutil
import subprocess
import datetime

# import openhands.agenthub  # noqa F401 (we import this to get the agents registered)
# import openhands.cli.suppress_warnings  # noqa: F401
from openhands.controller.agent import Agent
from openhands.controller.replay import ReplayManager
from openhands.controller.state.state import State
from openhands.core.config import (
    OpenHandsConfig,
    parse_arguments,
    setup_config_from_args,
)
from openhands.core.config.mcp_config import OpenHandsMCPConfigImpl
from openhands.core.logger import openhands_logger as logger
from openhands.core.loop import run_agent_until_done
from openhands.core.schema import AgentState
from openhands.core.setup import (
    create_agent,
    create_controller,
    create_memory,
    create_runtime,
    generate_sid,
    initialize_repository_for_runtime,
)
from openhands.events import EventSource, EventStreamSubscriber
from openhands.events.action import MessageAction, NullAction, AgentFinishAction
from openhands.events.action.action import Action
from openhands.events.event import Event
from openhands.events.observation import AgentStateChangedObservation
from openhands.io import read_input, read_task
from openhands.mcp import add_mcp_tools_to_agent
from openhands.memory.memory import Memory
from openhands.runtime.base import Runtime
from openhands.utils.async_utils import call_async_from_sync

PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_NAME = "gpt-4o"
VERSION_ID = f"concerns_{MODEL_NAME}"

WORKSPACE_DIR = f"{PROJECT_ROOT}/workspace/{VERSION_ID}/App_work" # Your working dir for running agent locally, App_clean will be copied to here
JSON_OUTPUT_FILE = f"{PROJECT_ROOT}/output_{VERSION_ID}.json" # Your output json file path
TRAJECTORY_DIR = f"{PROJECT_ROOT}/trajectory" # Your trajectory dir
os.makedirs(WORKSPACE_DIR, exist_ok=True)
os.makedirs(TRAJECTORY_DIR, exist_ok=True)


CONCERN_DIR = f"{PROJECT_ROOT}/../../../dataset/concerns" # concern dir
CONCERN_FILE_NAME = "__sorted_concern_list_4o-mini_emb_llm.json" # concern json file name
ISSUES_DIR = f"{PROJECT_ROOT}/../../../dataset/issues" # issue dataset dir path which contains all issue folders
ISSUE_IDS_FILE = f"{PROJECT_ROOT}/../../../dataset/issue_ids.txt" # issue id list file path which contains all issue ids for processing
SOURCE_DIR = f"{PROJECT_ROOT}/../../../dataset/App_clean" # Your clean app path
CONFIG_FILE = f"{PROJECT_ROOT}/config.toml" # Your config file path

COUNT_LIMIT = 216 # limit the number of json item in JSON_OUTPUT_FILE
MAX_ITERATION = 30  # max interaction turns for each issue

class FakeUserResponseFunc(Protocol):
    def __call__(
        self,
        state: State,
        encapsulate_solution: bool = False,
        try_parse: Callable[[Action | None], str] | None = None,
    ) -> str: ...

async def run_controller(
    config: OpenHandsConfig,
    initial_user_action: Action,
    sid: str | None = None,
    runtime: Runtime | None = None,
    agent: Agent | None = None,
    exit_on_message: bool = False,
    fake_user_response_fn: FakeUserResponseFunc | None = None,
    headless_mode: bool = True,
    memory: Memory | None = None,
    conversation_instructions: str | None = None,
) -> State | None:
    """Main coroutine to run the agent controller with task input flexibility.

    It's only used when you launch openhands backend directly via cmdline.

    Args:
        config: The app config.
        initial_user_action: An Action object containing initial user input
        sid: (optional) The session id. IMPORTANT: please don't set this unless you know what you're doing.
            Set it to incompatible value will cause unexpected behavior on RemoteRuntime.
        runtime: (optional) A runtime for the agent to run on.
        agent: (optional) A agent to run.
        exit_on_message: quit if agent asks for a message from user (optional)
        fake_user_response_fn: An optional function that receives the current state
            (could be None) and returns a fake user response.
        headless_mode: Whether the agent is run in headless mode.

    Returns:
        The final state of the agent, or None if an error occurred.

    Raises:
        AssertionError: If initial_user_action is not an Action instance.
        Exception: Various exceptions may be raised during execution and will be logged.

    Notes:
        - State persistence: If config.file_store is set, the agent's state will be
          saved between sessions.
        - Trajectories: If config.trajectories_path is set, execution history will be
          saved as JSON for analysis.
        - Budget control: Execution is limited by config.max_iterations and
          config.max_budget_per_task.

    Example:
        >>> config = load_openhands_config()
        >>> action = MessageAction(content="Write a hello world program")
        >>> state = await run_controller(config=config, initial_user_action=action)
    """
    sid = sid or generate_sid(config)

    if agent is None:
        agent = create_agent(config)

    # when the runtime is created, it will be connected and clone the selected repository
    repo_directory = None
    if runtime is None:
        runtime = create_runtime(
            config,
            sid=sid,
            headless_mode=headless_mode,
            agent=agent,
        )
        # Connect to the runtime
        call_async_from_sync(runtime.connect)

        # Initialize repository if needed
        if config.sandbox.selected_repo:
            repo_directory = initialize_repository_for_runtime(
                runtime,
                selected_repository=config.sandbox.selected_repo,
            )

    event_stream = runtime.event_stream

    # when memory is created, it will load the microagents from the selected repository
    if memory is None:
        memory = create_memory(
            runtime=runtime,
            event_stream=event_stream,
            sid=sid,
            selected_repository=config.sandbox.selected_repo,
            repo_directory=repo_directory,
            conversation_instructions=conversation_instructions,
        )

    # Add MCP tools to the agent
    if agent.config.enable_mcp:
        # Add OpenHands' MCP server by default
        _, openhands_mcp_stdio_servers = (
            OpenHandsMCPConfigImpl.create_default_mcp_server_config(
                config.mcp_host, config, None
            )
        )
        runtime.config.mcp.stdio_servers.extend(openhands_mcp_stdio_servers)

        await add_mcp_tools_to_agent(agent, runtime, memory)

    replay_events: list[Event] | None = None
    if config.replay_trajectory_path:
        logger.info('Trajectory replay is enabled')
        assert isinstance(initial_user_action, NullAction)
        replay_events, initial_user_action = load_replay_log(
            config.replay_trajectory_path
        )

    controller, initial_state = create_controller(
        agent, runtime, config, replay_events=replay_events
    )

    assert isinstance(initial_user_action, Action), (
        f'initial user actions must be an Action, got {type(initial_user_action)}'
    )
    logger.debug(
        f'Agent Controller Initialized: Running agent {agent.name}, model '
        f'{agent.llm.config.model}, with actions: {initial_user_action}'
    )

    # start event is a MessageAction with the task, either resumed or new
    if initial_state is not None and initial_state.last_error:
        # we're resuming the previous session
        event_stream.add_event(
            MessageAction(
                content=(
                    "Let's get back on track. If you experienced errors before, do "
                    'NOT resume your task. Ask me about it.'
                ),
            ),
            EventSource.USER,
        )
    else:
        # init with the provided actions
        event_stream.add_event(initial_user_action, EventSource.USER)

    def on_event(event: Event) -> None:
        if isinstance(event, AgentStateChangedObservation):
            if event.agent_state == AgentState.AWAITING_USER_INPUT:
                if exit_on_message:
                    message = '/exit'
                elif fake_user_response_fn is None:
                    message = read_input(config.cli_multiline_input)
                else:
                    message = fake_user_response_fn(controller.get_state())
                action = MessageAction(content=message)
                event_stream.add_event(action, EventSource.USER)

    event_stream.subscribe(EventStreamSubscriber.MAIN, on_event, sid)

    end_states = [
        AgentState.FINISHED,
        AgentState.REJECTED,
        AgentState.ERROR,
        AgentState.PAUSED,
        AgentState.STOPPED,
    ]

    try:
        await run_agent_until_done(controller, runtime, memory, end_states)
    except Exception as e:
        logger.error(f'Exception in main loop: {e}')

    # save session when we're about to close
    if config.file_store is not None and config.file_store != 'memory':
        end_state = controller.get_state()
        # NOTE: the saved state does not include delegates events
        end_state.save_to_session(
            event_stream.sid, event_stream.file_store, event_stream.user_id
        )

    await controller.close(set_stop_state=False)

    state = controller.get_state()

    # save trajectories if applicable
    if config.save_trajectory_path is not None:
        # if save_trajectory_path is a folder, use session id as file name
        if os.path.isdir(config.save_trajectory_path):
            file_path = os.path.join(config.save_trajectory_path, sid + '.json')
        else:
            file_path = config.save_trajectory_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        histories = controller.get_trajectory(config.save_screenshots_in_trajectory)
        with open(file_path, 'w') as f:  # noqa: ASYNC101
            json.dump(histories, f, indent=4)

    return state

def auto_continue_response(
    state: State,
    encapsulate_solution: bool = False,
    try_parse: Callable[[Action | None], str] | None = None,
) -> str:
    """Default function to generate user responses.
    Tell the agent to proceed without asking for more input, or finish the interaction.
    """
    message = (
        'Please continue on whatever approach you think is suitable.\n'
        'If you think you have solved the task, please finish the interaction.\n'
        'IMPORTANT: YOU SHOULD NEVER ASK FOR HUMAN RESPONSE.\n'
    )
    return message

def load_replay_log(trajectory_path: str) -> tuple[list[Event] | None, Action]:
    """
    Load trajectory from given path, serialize it to a list of events, and return
    two things:
    1) A list of events except the first action
    2) First action (user message, a.k.a. initial task)
    """
    try:
        path = Path(trajectory_path).resolve()

        if not path.exists():
            raise ValueError(f'Trajectory file not found: {path}')

        if not path.is_file():
            raise ValueError(f'Trajectory path is a directory, not a file: {path}')

        with open(path, 'r', encoding='utf-8') as file:
            events = ReplayManager.get_replay_events(json.load(file))
            assert isinstance(events[0], MessageAction)
            return events[1:], events[0]
    except json.JSONDecodeError as e:
        raise ValueError(f'Invalid JSON format in {trajectory_path}: {e}')

import os

def get_task_concern_instruction(instance_id, concerns) -> str:
    # issues_dir/instance_id/issue_data.json
    issue_data_path = os.path.join(ISSUES_DIR, f"{instance_id}/issue_data.json")
    with open(issue_data_path, 'r', encoding='utf-8') as file:
        instance = json.load(file)
    instruction = f"""
Your objective is to localize the specific files and functions that need modification or contain key information to resolve the issue.
I will provide you with:

<issue_title>
{instance['title']}
</issue_title>

<issue_body>
{instance['issue_repo_steps']}
</issue_body>

Concerns: additional relevant functional scenarios related to the issue, each containing a short description along with the involved files and functions.
<concerns>
{concerns}
</concerns>

Follow these steps to localize the issue:
## Step 1: Categorize and Extract Key Problem Information
- Classify the problem statement into the following categories:
    Problem description, error trace, code to reproduce the bug, and additional context.
- Use extracted keywords, line numbers, and the provided concerns (including descriptions, files, and functions) to search for relevant code references for additional context.

## Step 2: Locate Referenced Modules
- Accurately determine specific modules
    - Explore the repo to familiarize yourself with its structure.
    - When exploring or referencing files during your analysis, you should use absolute file paths and the workspace direction is '{WORKSPACE_DIR}'. This is different from the final output format, which requires relative paths.
    - Analyze the described execution flow and the provided concerns (including descriptions, files, and functions) to identify specific modules or components being referenced.
- Pay special attention to distinguishing between modules with similar names using context, described execution flow, and the given concern information.
- Output Format for collected relevant modules:
    - Use the format: 'file_path:QualifiedName'
    - E.g., for a function `calculate_sum` in the `MathUtils` class located in `src/helpers/math_helpers.py`, represent it as: 'src/helpers/math_helpers.py:MathUtils.calculate_sum'.

## Step 3: Analyze and Reproducing the Problem
- Clarify the Purpose of the Issue
    - If expanding capabilities: Identify where and how to incorporate new behavior, fields, or modules.
    - If addressing unexpected behavior: Focus on localizing modules containing potential bugs.
- Reconstruct the execution flow
    - Identify main entry points triggering the issue.
    - Trace function calls, class interactions, and sequences of events, making use of the provided concern scenarios (including descriptions, files, and functions) to guide and verify the flow.
    - Identify potential breakpoints causing the issue.
    Important: Keep the reconstructed flow focused on the problem, avoiding irrelevant details, while cross-referencing concern information to ensure coverage of relevant functional scenarios.

## Step 4: Locate Areas for Modification
- Locate specific files and functions requiring changes or containing critical information for resolving the issue, using the provided concerns (descriptions, files, and functions) as guiding context.
- Consider upstream and downstream dependencies that may affect or be affected by the issue.
- If applicable, identify where to introduce new fields, functions
- Think Thoroughly: List multiple potential solutions and consider edge cases that could impact the resolution.

## Step 5: Final Output Generation
- Your final output MUST be a single JSON object, enclosed in a single pair of triple backticks (```json ... ```).
- The JSON object MUST contain the following three keys, each mapping to an ARRAY of strings. All file paths MUST be relative to the project root and NOT start with `./`.
    - "file_list": A list of relative file paths.
    - "function_list": Fully-qualified names of functions (e.g. `src/module/file.py:ClassName.method` or `src/module/file.py:function_name`).
    - "class_list": Fully-qualified names of classes (e.g. `src/module/file.py:ClassName`).
- Order the items in each list by importance, from most to least important.
- Provide 10 items in each list.
- Do NOT include any other text, explanation, or conversation in your final response. Only the JSON object in the backticks.

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
],
"class_list": [
    "src/helpers/math_helpers.py:MathUtils",
    "src/services/payment_service.py:PaymentService"
]
}}
```

Note: Your thinking should be thorough and so it's fine if it's very long.
"""
    instruction += (
        'IMPORTANT: You should ONLY interact with the environment provided to you AND NEVER ASK FOR HUMAN HELP.\n'
        "Don't include any lambda functions!\n"
        'You should NOT modify any files!\n'
    )
    instruction += """
<IMPORTANT!>
You SHOULD NEVER attempt to browse the web.
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

def extract_json_from_trajectory(trajectory_name):
    """
    extract the final JSON content from the trajectory file
    """
    trajectory_path = os.path.join(TRAJECTORY_DIR, trajectory_name)
    with open(trajectory_path, 'r', encoding='utf-8') as f:
        trajectory = json.load(f)

    json_content = None
    occure_id = None

    for event in reversed(trajectory):
        if "source" not in event or "action" not in event:
            continue
        if event['source'] != "agent":
            continue
        if event['action'] == "message":
            message = event['message']
            if "```json" in message:
                try:
                    json_content = message.split('```json', 1)[1].rsplit('```', 1)[0].strip()
                    occure_id = event['id']
                    break
                except Exception as e:
                    print(e)
        if event['action'] == "finish":
            # extract message, final_thought, thought
            message = None
            final_thought = None
            thought = None
            if "message" in event:
                message = event['message']
            args = event['args']
            if "final_thought" in args:
                final_thought = args['final_thought']
            if "thought" in args:
                thought = args['thought']

            # extract json from message, final_thought, thought respectively
            for information in [message, final_thought, thought]:
                if "```json" in information:
                    try:
                        json_content = information.split('```json', 1)[1].rsplit('```', 1)[0].strip()
                        occure_id = event['id']
                        break
                    except Exception as e:
                        print(e)

    if json_content:
        json_data = json.loads(json_content)
        return json_data, occure_id
    else:
        return None, None

def write_json(json_data, state, instance_id):
    """
    write json_data to JSON_OUTPUT_FILE
    if json_data is None, write failure json to JSON_OUTPUT_FILE
    """

    if json_data:
        json_data["session_id"] = state.session_id
        json_data["issue_id"] = instance_id
        json_data["status"] = 0
        json_data['used_turns'] = state.iteration_flag.current_value
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
            write_error_json(state.session_id, instance_id, state.iteration_flag.current_value)
        except Exception as e:
            print(e)

def main(instance_id):
    args = parse_arguments()
    args.config_file = CONFIG_FILE
    config: OpenHandsConfig = setup_config_from_args(args)
    config.workspace_base = WORKSPACE_DIR
    config.save_trajectory_path = TRAJECTORY_DIR

    concern_file_path = os.path.join(CONCERN_DIR, f"{instance_id}/{CONCERN_FILE_NAME}")
    with open(concern_file_path, 'r', encoding='utf-8') as file:
        concerns = json.load(file)
    try:
        assert(concerns)
    except Exception as e:
        print(e)
        return
    task_str = get_task_concern_instruction(instance_id, concerns)
    if not task_str:
        return

    initial_user_action = MessageAction(content=task_str)

    # set trajectory file name
    session_name = f"issue_{instance_id}.log"
    sid = generate_sid(config, session_name)

    # config
    config.max_iterations = MAX_ITERATION
    config.get_llm_config().model = MODEL_NAME
    config.workspace_base = WORKSPACE_DIR
    print(config)
    state = asyncio.run(
        run_controller(
            config=config,
            initial_user_action=initial_user_action,
            sid=sid,
            fake_user_response_fn=None
            if args.no_auto_continue
            else auto_continue_response,
        )
    )

    # 1. extract json data
    json_data, _ = extract_json_from_trajectory(str(state.session_id) + ".json")
    used_turns = state.iteration_flag.current_value

    if json_data and "file_list" in json_data and "function_list" in json_data and "class_list" in json_data:
        write_json(json_data, state, instance_id)
    else:
        write_error_json(state.session_id, instance_id, used_turns)
        
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