import json
import os
import re
import time

from openai import OpenAI
def get_repository_structure(root_dir):
    def traverse(dir_path, indent=0):
        files_and_dirs = os.listdir(dir_path)
        structure = ""
        for item in files_and_dirs:
            full_path = os.path.join(dir_path, item)
            if os.path.isdir(full_path):  
                structure += " " * indent + item + "/\n"
                structure += traverse(full_path, indent+2)
            else:
                if item.endswith(('.py', '.js', '.ts','.tsx','.c','.go')):
                    structure += " " * indent + item + "\n"
        return structure
    
    return root_dir+"\n"+traverse(root_dir,2)
    
def unique_predicts(predicts):
    uuu=set()
    ans=[]
    for item in predicts:
        if item not in uuu:
            ans.append(item)
            uuu.add(item)
    return ans
def use_get_structure(path):
    root_directory = path
    structure = []
    files_and_dirs = os.listdir(root_directory)
    for item in files_and_dirs:
        full_path = os.path.join(root_directory, item)
        if os.path.isdir(full_path):  
            structure.append(get_repository_structure(full_path))
        else:  
            if item.endswith(('.py', '.js', '.ts','.tsx','.c','.go')):
                structure.append(full_path)
    return structure

def format_predicts(predicts):
    def format_predict(predict):
        predict = re.split(r'\s+|\'|\n|\[|\]|\"|\,|`', predict)

        res = [a for a in predict if '/' in a]
        
        res = [a[1:] if a.startswith("/") else a for a in res]

        return res

    predict_paths = []
    for predict in predicts:
        predict_paths.extend(format_predict(predict))
        
    return unique_predicts(predict_paths)


def structure_files(file_list):
    structure = {}
    
    for item in file_list:
        parts = item.rstrip('/').split('/')
        
        current_level = structure
        
        for part in parts:
            if part not in current_level:
                current_level[part] = {}
            current_level = current_level[part]
        
        if parts[-1] not in current_level:
            current_level[parts[-1]] = None
    
    return structure
def build_structure_string(structure, indent=0):
    """
    Build a string representation of the file structure.
    
    :param structure: A nested dictionary representing the file structure.
    :param indent: The current indentation level.
    :return: A string representing the file structure.
    """
    structure_string = ""
    for key, value in sorted(structure.items()):
        if value is None:
            structure_string += ' ' * indent + key + '\n'
        else:
            structure_string += ' ' * indent + key + '/\n'
            structure_string += build_structure_string(value,indent+2)
    return structure_string

        
def create_openai_client():
    from openai import OpenAI
    
    client = OpenAI(
        api_key=YOUR_API_KEY
        
    )

    return client

obtain_relevant_files_prompt = """   
Please look through the following GitHub problem description and Repository structure and provide a list of files that one would need to edit to fix the problem.

### GitHub Problem Description ###
{problem_statement}

###

### Repository Structure ###
{structure}

###

You can only search for files within the current given file repository structure.
Please only provide the path without "{entry_path}" prefix and return at most 10 files.
The returned files are sorted by importance in descending order
Do not return null values.
Please format your answer in a list.
such as ["src/components/ThreeDotsMenu/index.tsx"] or ["src/components/ThreeDotsMenu/index.tsx", "src/components/VideoPlayer/shouldReplayVideo.ts"] without commentary. 
""" 


def handle_predict(predicts, entry_path):
    predicts = format_predicts(predicts)
    final_predicts = []
    predicts=unique_predicts(predicts)
    predicts_without_prefix=[]
    for predict in predicts:
        if predict.startswith(entry_path):
            predict=predict[len(entry_path):]
        predicts_without_prefix.append(predict)
    predicts = predicts_without_prefix
    for predict in predicts:
        while True:
            if os.path.exists(os.path.join(entry_path, predict)):
                final_predicts.append(predict)
                break
            if '/' not in predict:
                predict="" 
                final_predicts.append(predict)
                break
            else: 
                parts = predict.rsplit('/', 1)
                predict = parts[0]
    predicts=final_predicts
    predicts=unique_predicts(predicts)
    return predicts

def agentless_generate_dirs(id, bug, model_version, entry_path, concern_path):
    print("run without concern")
    client = create_openai_client()

    bug_information = ("Title: " + bug['title'] + "\n" +
                    "Issue Repo Steps: " + (bug.get('issue_repo_steps') or bug.get('issue_repro_steps', ''))  + "\n")
    input_tokens=0
    output_tokens=0
    predicts_all=[]
    structure_no=1
    bug_structure=use_get_structure(entry_path)

    for structure_data in bug_structure:
        try:
            structure_no=structure_no+1
            path_now=structure_data.split('\n', 1)[0]
            prompt=obtain_relevant_files_prompt.format(
                problem_statement=bug_information,
                structure=structure_data,
                entry_path=entry_path
            ).strip()
            message=[
                {"role":"system","content":"You are a helpful assistant. Must Do NOT think. Return the answer quickly."},
                {"role":"user","content":prompt}
            ]
            max_retries = 100
            retries = 0
            while retries < max_retries:
                try:
                    completion = client.chat.completions.create(
                        model=model_version,
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
            predicts = []
            predicts.append(completion.choices[0].message.content)
            input_tokens+=completion.usage.prompt_tokens
            output_tokens+=completion.usage.completion_tokens

            predicts = handle_predict(predicts, entry_path)
            predicts = [s for s in predicts if s]

            ri_predicts=[]
            for predict in predicts:
                if predict=="":
                    continue
                split_result=predict.split('/', 1)
                if len(split_result)>1:
                    predict=split_result[1]
                else:
                    continue
                if os.path.exists(os.path.join(path_now,predict)): 
                    ri_predicts.append(os.path.join(path_now,predict))
            
            ri_predicts=unique_predicts(ri_predicts)

            if len(ri_predicts)>0:  
                predicts_all.append(ri_predicts)

        except Exception as e:
            try:
                print(e)
                handled_structure = use_get_structure(structure_data.split('\n', 1)[0])
                for new_st in handled_structure:
                    structure_no=structure_no+1
                    path_now=new_st.split('\n', 1)[0]
                    prompt=obtain_relevant_files_prompt.format(
                        problem_statement=bug_information,
                        structure=new_st,
                        entry_path=entry_path
                    ).strip()
                    message=[
                        {"role":"system","content":"You are a helpful assistant. Must Do NOT think. Return the answer quickly."},
                        {"role":"user","content":prompt}
                    ]
                    max_retries = 100
                    retries = 0
                    while retries < max_retries:
                        try:
                            completion = client.chat.completions.create(
                                model=model_version,
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
                    predicts = []
                    predicts.append(completion.choices[0].message.content)
                    predicts = handle_predict(predicts, entry_path)
                    predicts = [s for s in predicts if s]
                    ri_predicts=[]
                    for predict in predicts:
                        if predict=="":
                            continue
                        split_result=predict.split('/', 1)
                        if len(split_result)>1:
                            predict=split_result[1]
                        else:
                            continue
                        if os.path.exists(os.path.join(path_now,predict)):  
                            ri_predicts.append(os.path.join(path_now,predict))
                            
                    ri_predicts=unique_predicts(ri_predicts)
                    if len(ri_predicts)>0:
                        predicts_all.append(ri_predicts)
            except Exception as ee:
                pass
            
    handle_predicts=[]
    for predict_list in predicts_all:
        for predict in predict_list:
            if predict.startswith("working/") or predict.startswith("working/"):
                predict='/'.join(predict.split('/')[1:])
            handle_predicts.append(predict)
    structured_files = structure_files(handle_predicts)
    structure_string = build_structure_string(structured_files)
    
    prompt=obtain_relevant_files_prompt.format(
        problem_statement=bug_information,
        structure=structure_string,
        entry_path=entry_path
    ).strip()

    message=[
        {"role":"system","content":"You are a helpful assistant. Must Do NOT think. Return the answer quickly."},
        {"role":"user","content":prompt}
    ]
    max_retries = 100
    retries = 0
    while retries < max_retries:
        try:
            completion = client.chat.completions.create(
                model=model_version,
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
    predicts = []
    predicts.append(completion.choices[0].message.content)
    predicts=handle_predict(predicts, entry_path)
    predicts = [s for s in predicts if s and re.search(r'\.[a-zA-Z]{2,5}$', s)]
    
    result = {
        "bug_id": id,
        "predicts": predicts,
        "input_tokens_sum": input_tokens,
        "output_tokens_sum": output_tokens
    }

    return result
