import json
import openai
import re
from definitions import (
    SWE_LANCER_ISSUE_IDS,
    SWE_LANCER_ISSUES_DIR,
    SWE_PRO_ISSUES,
    SWE_PRO_SAMPLED_ISSUE_IDS,
    OPENAI_API_KEY
)

openai.api_key = OPENAI_API_KEY


def get_json_data(file_path):
    """ Read JSON data from file """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def get_swe_lancer_issue_ids():
    """ Get issue IDs for SWE-Lancer-Loc benchmark """
    file_path = SWE_LANCER_ISSUE_IDS
    issue_ids = []
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        for line in lines:
            if line.strip():
                issue_id = int(line.strip())
                issue_ids.append(issue_id)
    return issue_ids


def get_swe_lancer_issue_data(issue_id):
    """ Get issue title and body for SWE-Lancer benchmark """
    issue_data_path = SWE_LANCER_ISSUES_DIR + f"/{issue_id}/issue_data.json"
    issue_data = get_json_data(issue_data_path)
    issue_title = issue_data['title']
    issue_body = issue_data['issue_repo_steps']
    return issue_title, issue_body


def get_swe_pro_issues():
    """ Get all issues from SWE-Pro-Loc benchmark """
    swe_pro_issues = []
    with open(SWE_PRO_ISSUES, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                swe_pro_issues.append(json.loads(line))
    return swe_pro_issues


def get_swe_pro_sampled_issues():
    """ Get sampled issues from SWE-Pro-Loc benchmark """
    swe_pro_sampled_issues = []
    swe_pro_issues = get_swe_pro_issues()
    with open(SWE_PRO_SAMPLED_ISSUE_IDS, 'r', encoding='utf-8') as f:
        swe_pro_sampled_issue_ids = json.load(f)
    for sampled_issue_id in swe_pro_sampled_issue_ids:
        for issue in swe_pro_issues:
            if issue['instance_id'] == sampled_issue_id:
                swe_pro_sampled_issues.append(issue)
                break
    return swe_pro_sampled_issues


def query_llm(prompt, model_name):
    """ Query LLM with the given prompt """
    completion = openai.ChatCompletion.create(
        model=model_name,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        n=1,
        temperature=0
    )
    
    return completion.choices[0].message['content']


def extract_json_data_in_llm_answer(answer):
    """ Extract JSON data from LLM answer """
    pattern = r"```json(.*?)```"
    matches = re.search(pattern, answer, re.DOTALL)
    if matches:
        extracted_code = matches.group(1).strip()
        return extracted_code
    else:
        return ""


def extract_python_code_in_llm_answer(answer):
    """ Extract Python code from LLM answer """
    pattern = r"```python(.*?)```"
    matches = re.search(pattern, answer, re.DOTALL)
    if matches:
        extracted_code = matches.group(1).strip()
        return extracted_code
    else:
        return ""
