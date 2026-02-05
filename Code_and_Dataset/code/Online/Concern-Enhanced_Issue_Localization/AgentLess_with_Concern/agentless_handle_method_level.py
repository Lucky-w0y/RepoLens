#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os, shutil, subprocess
import argparse

from tqdm import tqdm

from openai import OpenAI
import ast

from agentless_handle_file_level_with_concern import agentless_generate_dirs as agentless_generate_dirs_with_concern
from agentless_handle_file_level import agentless_generate_dirs as agentless_generate_dirs_no_concern

def create_openai_client():
    from openai import OpenAI
    
    client = OpenAI(
        
        api_key= YOUR_API_KEY

    )
    return client


def get_end_line(lines, start_line):
    content_start_line=start_line
    content_end_line=start_line
    find_function_body=False
    left_bracket=0
    for line in range(start_line-1,len(lines)):
        if not find_function_body:
            if '{' in lines[line]:
                l=lines[line].strip()
                if l[0]=='{' or l[-1]=='{':
                    find_function_body=True
                    if len(l)>1:
                        content_start_line=line+2
                    else:
                        content_start_line=line+1
                left_bracket+=1
            else:
                continue
        elif '{' in lines[line] or '}' in lines[line]:
            left_bracket+=lines[line].count('{')
            left_bracket-=lines[line].count('}')
            if left_bracket==0:
                content_end_line=line+1
                return [content_start_line,content_end_line]
            if lines[line]=='}\n':
                content_end_line=line+1
                return [content_start_line,content_end_line]
    return [content_start_line,content_end_line]

def parse_c_file_by_line(file_path):
    delete_lines=[]
    try:
        with open(file_path,'r',errors='ignore') as f:
            lines=f.readlines()
            for i,line in enumerate(lines):
                line_number=i+1
                if line.strip().endswith('{'):
                    line_info=get_end_line(lines,line_number)
                    start_line=line_info[0]
                    end_line=line_info[1]
                    delete_lines.append((start_line,end_line))
    except Exception as e:
        return []    
    finally:
        return delete_lines

def summary_file_by_Fline(file_path):
    useless_line=parse_c_file_by_line(file_path)
    refined_file=''
    with open(file_path,'r',errors='replace') as f:
        all_lines=f.readlines()
        for i in range(len(all_lines)):
            line=all_lines[i]
            line_number=i+1
            is_useless=False
            for t in useless_line:
                if line_number>=t[0] and line_number<=t[1]:
                    is_useless=True
                    break
            
            if line.strip().startswith('import') or \
            line.strip().startswith('//') or \
            line.strip().startswith('/*') or \
            line.strip().startswith(' *'):
                is_useless=True
            if is_useless:
                continue
            else:
                if line.strip().endswith('=> {'):
                    line=line.replace('=> {','')
                if line.strip().endswith('= {'):
                    line=line.replace('= {','')
                if line.strip().endswith('{'):
                    line=line.replace('{','')
                refined_file+=line
    return refined_file 

def parse_completion_content(content):
    function_list = []
    type_list = []
    const_list = []
    
    lines = content.strip().split('\n')
    
    current_file = None
    
    for line in lines:
        line = line.strip()
        
        if not line or line.startswith('```'):
            continue
        
        if not line.startswith('function:') and not line.startswith('type:') and not line.startswith('const:'):
            current_file = line
            continue
        
        if line.startswith('function:'):
            func_name = line.replace('function:', '').strip()
            if current_file and func_name:
                function_list.append({
                    'file': current_file,
                    'name': func_name
                })
        
        elif line.startswith('type:'):
            type_name = line.replace('type:', '').strip()
            if current_file and type_name:
                type_list.append({
                    'file': current_file,
                    'name': type_name
                })

        elif line.startswith('const:'):
            const_name = line.replace('const:', '').strip()
            if current_file and const_name:
                const_list.append({
                    'file': current_file,
                    'name': const_name
                })
    
    return function_list, type_list, const_list


obtain_relevant_functions_and_vars_from_compressed_files_prompt_more = """
Please look through the following Linux Problem Description and the Skeleton of Relevant Files.
Identify all locations that need inspection or editing to fix the problem, including directly related areas as well as any potentially related global variables, constants, functions, and structures.
For each location you provide, either give the name of a function, the name of a type, or the name of a constant.

### GitHub Problem Description ###
{problem_statement}

### Skeleton of Relevant Files ###
{file_contents}

The returned locations should be separated by new lines ordered by most to least important.
Please return at most 10 locations.
For files, please only provide the path without "{entry_path}" prefix.

### Examples:
```
file1.py
function: my_function_1
function: my_function_2
type: my_type_1

file2.py
function: my_function_3
type: my_type_2
const: my_const_1

```

Return just the locations wrapped with ```.
"""
def method_location(id, bug, predicts):
    input_tokens=0
    output_tokens=0
    predict_file_paths=[]
    for predict in predicts:
        path=os.path.join(YOUR_WORKSPACE, predict)
        if os.path.exists(path):
            predict_file_paths.append(path)
    files_skeleton=[]
    
    for path in predict_file_paths:
        skeleton=summary_file_by_Fline(path)
        files_skeleton.append(skeleton)
    combine=""
    for i in range(len(predict_file_paths)):
        combine+=predict_file_paths[i]+':'+'\n'+files_skeleton[i]+"\n"    
        
    client = create_openai_client()
    bug_information = ("Title: " + bug['title'] + "\n" +
                    "Issue Repo Steps: " + (bug.get('issue_repo_steps') or bug.get('issue_repro_steps', ''))  + "\n")
    prompt=obtain_relevant_functions_and_vars_from_compressed_files_prompt_more.format(
        problem_statement=bug_information,
        file_contents=combine,
        entry_path=YOUR_WORKSPACE
    ).strip()
    message=[
        {"role":"system","content":"You are a helpful assistant. Must Do NOT think. Return the answer quickly."},
        {"role":"user","content":prompt}
    ]
    if len(message) > 4096:
        message=message[:4096]
    max_retries = 100
    retries = 0
    while retries < max_retries:
        try:
            completion = client.chat.completions.create(
                model=MODEL_VERSION,
                messages=message,
                n=1,
                temperature=0,
                timeout=1000,
                top_p=0.1
            )
            break
        except Exception as e:
            retries += 1
            time.sleep(1)
    input_tokens+=completion.usage.prompt_tokens
    output_tokens+=completion.usage.completion_tokens
    function_list, type_list, const_list = parse_completion_content(completion.choices[0].message.content)
    result = {
        "bug_id": id,
        "predicts_location": completion.choices[0].message.content,
        "function_list": function_list,
        "input_tokens_sum": input_tokens,
        "output_tokens_sum": output_tokens
    }
    return result

def get_YOUR_sampled_issues():
    YOUR_sampled_issue_ids = []
    with open(YOUR_SAMPLED_ISSUE_IDS, 'r') as f:
        YOUR_sampled_issue_ids = json.load(f)

    return YOUR_sampled_issue_ids


def checkout_by_test_id(id):
    try:
        
        raw_repo_path = YOUR_RAW_REPO_PATH
        repo_dir = YOUR_WORKSPACE
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir) 
        shutil.copytree(raw_repo_path, repo_dir)

        commit_id_file = os.path.join(YOUR_ISSUES, f"{id}/commit_id.txt")
        
        with open(commit_id_file, 'r', encoding='utf-8') as f:
            commit_id = f.read().strip()
            
        result = subprocess.run(
            ['git', 'checkout', commit_id],
            cwd=repo_dir,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"git checkout failed: {result.stderr}")
            return False
        else:
            print(f"git checkout success")
            patch_file = f"{YOUR_ISSUES}/{id}/bug_reintroduce.patch"

            patch_result = subprocess.run(
                ['git', 'apply', patch_file],
                cwd=repo_dir,
                capture_output=True,
                text=True
            )
            
            if patch_result.returncode == 0:
                return True
            else:
                if patch_result.stderr and 'error' in patch_result.stderr.lower():
                    print(f"git apply failed: {patch_result.stderr}")
                    return False
                else:
                    if patch_result.stderr:
                        print(f"git apply warning: {patch_result.stderr}")
                    return True

    except Exception as e:
        print(f"Error occured during execution: {str(e)}")
        return False
    
if __name__ == '__main__':
    
    import json
    import time

    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--number', type=int, help='Worker number')
    parser.add_argument('-c', '--concern', action='store_true', help='Use concern')
    parser.add_argument('-m', '--model', type=str, help='Model version', default='gemini-2.5-pro')
    args = parser.parse_args()

    if args.concern:
        agentless_generate_dirs = agentless_generate_dirs_with_concern
        YOUR_OUTPUT_PATH = f"{YOUR_OUTPUT_PATH}_concern"
    else:
        agentless_generate_dirs = agentless_generate_dirs_no_concern

    if args.number:
        n = args.number
        if args.concern:
            YOUR_WORKSPACE = f"{YOUR_WORKSPACE}-c{n}"
        else:
            YOUR_WORKSPACE = f"{YOUR_WORKSPACE}-{n}"
        YOUR_OUTPUT_FILE = f"{YOUR_OUTPUT_PATH}/agentless_results-{n}.jsonl"
        issue_start = 20 * (n - 1)
    else:
        issue_start = 0
        
    if args.model:
        MODEL_VERSION = args.model
    else:
        MODEL_VERSION = "gemini-2.5-pro"

    with open(YOUR_OUTPUT_FILE, 'w') as output_file:
        sampled_issues = get_YOUR_sampled_issues()
        print(f"Current model: {MODEL_VERSION}")
        print(f"Current workspace: {YOUR_WORKSPACE}")
        issue_end = len(sampled_issues) if issue_start + 20 > len(sampled_issues) else issue_start + 20
        for id in sampled_issues[issue_start:issue_end]:
            start_time = time.time()
            print('issue_id:', id)
            bug = json.loads(open(f"{YOUR_ISSUES}/{id}/issue_data.json").read())

            if checkout_by_test_id(id):
                file_level_result = agentless_generate_dirs(
                    id,
                    bug,
                    MODEL_VERSION,
                    YOUR_WORKSPACE,
                    f"{YOUR_CONCERN_PATH}/{id}/__sorted_concern_list_4o-mini_emb_llm.json"
                )
                file_level_list = file_level_result["predicts"]
                function_level_result = method_location(id, bug, file_level_list)
                input_tokens_used = (
                    file_level_result["input_tokens_sum"] + function_level_result["input_tokens_sum"] 
                )
                output_tokens_used = (
                    file_level_result["output_tokens_sum"] + function_level_result["output_tokens_sum"] 
                )
                elapsed_time = time.time() - start_time

                result_item = {
                    "issue_id": id,
                    "files": file_level_list,
                    "functions": function_level_result["function_list"],
                    "input_token": input_tokens_used,
                    "output_token": output_tokens_used,
                    "time": elapsed_time,
                    "cost": calculate_cost(input_tokens_used, output_tokens_used)
                }

                output_file.write(json.dumps(result_item, ensure_ascii=False) + "\n")
                print(f"Written result for {id}")
                print(result_item)
            else:
                result_item = {
                    "issue_id": id,
                    "error": "checkout_failed"
                }
                output_file.write(json.dumps(result_item, ensure_ascii=False) + "\n")