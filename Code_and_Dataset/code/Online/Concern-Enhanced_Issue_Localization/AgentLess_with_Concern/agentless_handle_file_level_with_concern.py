import json
import os
import re
import time

from agentless_handle_file_level import unique_predicts, use_get_structure, handle_predict, structure_files, build_structure_string, create_openai_client


obtain_relevant_files_prompt = """   
Please look through the following GitHub problem description and Repository structure and provide a list of files that one would need to edit to fix the problem.

### GitHub Problem Description ###
{problem_statement}

###

### Repository Structure ###
{structure}

###


### Concern Analysis Guidance
You will be provided with a functional concern that includes files and functions relevant to the Issue. Use the following rules to guide your analysis:
1. Start from the concern files/functions: 
You must begin your investigation from the files and functions listed in the concern. These are your primary entry points. Carefully analyze their content and logic, as they are most likely to contain or invoke the root cause of the Issue.
Do not list all the files in the project!
2. Limited file access:
During analysis, if necessary, you may access other files that are explicitly imported within the concern-listed files. Do not access unrelated files.
3. Track and report your confidence level (0.0-1.0):
After each round of analysis, you must explicitly report your current confidence level regarding the identification of the root cause of the Issue.
This value must be a float between 0.0 and 1.0, reflecting how confident you are that you have found the actual cause of the Issue based on your reasoning so far.
A confidence of 0.5 indicates that you have found logic or code that is potentially the root cause of the Issue and requires further analysis.
A confidence of 0.7 or higher indicates that, after deeper analysis, you are reasonably certain about the root cause and can output the localization result.
** You must include the following line at the end of each response: Current confidence level: [your numeric value, e.g., 0.3]
4. Output result if your confidence ≥ 0.7:
Once your confidence level reaches 0.7 or above, and you have found the specific code or logic responsible for triggering the Issue, you should output the localization result.
You do not need to fix the issue or propose a solution — just identify and explain the root cause.
5. Continue analyzing if confidence < 0.7
If you are not yet sufficiently confident (i.e., confidence < 0.7), do not return the result.
Instead, continue analyzing relevant files and functions, refining your understanding and increasing your confidence through reasoning.
6. Focus solely on root cause identification:
Your task is to deeply analyze the code to identify and explain the root cause of the Issue.
You are not required to modify the code or propose a fix. Do not attempt to generate patches or edits.

### Concern Information
To help you analyze the root cause of the Issue, I will provide you with a functional concern related to the issue for reference.
The following is the concern information you can reference (including scenario_id, scenario_summary, related functions and file location):

{concern_list}

You can only search for files within the current given file repository structure.
Please only provide the path without "{entry_path}" prefix and return at most 10 files.
The returned files are sorted by importance in descending order
Do not return null values.
Please format your answer in a list.
such as ["src/components/ThreeDotsMenu/index.tsx"] or ["src/components/ThreeDotsMenu/index.tsx", "src/components/VideoPlayer/shouldReplayVideo.ts"] without commentary.



""" 


def agentless_generate_dirs(id, bug, model_version, entry_path, concern_path):

    concern = json.loads(open(concern_path).read())
    print("success load concern from "+concern_path)
    client = create_openai_client()

    bug_information = ("Title: " + bug['title'] + "\n" +
                    "Issue Repo Steps: " + (bug.get('issue_repo_steps') or bug.get('issue_repro_steps', ''))  + "\n")
    
    input_tokens=0
    output_tokens=0
    predicts_all=[]
    structure_no=1
    bug_structure=use_get_structure(entry_path)
    
    concern_string = ""
    for item in concern:
        concern_string += str(item) + "\n"

    for structure_data in bug_structure:
        try:
            
            structure_no=structure_no+1
            path_now=structure_data.split('\n', 1)[0]
            prompt=obtain_relevant_files_prompt.format(
                problem_statement=bug_information,
                structure=structure_data,
                concern_list=concern_string,
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
                        concern_list=concern_string,
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
            handle_predicts.append(predict)
    structured_files = structure_files(handle_predicts)
    structure_string = build_structure_string(structured_files)
    
    prompt=obtain_relevant_files_prompt.format(
        problem_statement=bug_information,
        structure=structure_string, 
        concern_list=concern_string,
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
