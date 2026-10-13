"""
Extract Noun Terms from Issue Titles

This script extracts relevant noun terms from issue titles using LLM-based analysis.

Supports:
- SWE-Lancer
- SWE-bench Pro
"""

import re
import json
import os
from tqdm import tqdm
from common.utils import get_swe_lancer_issue_ids, get_swe_lancer_issue_data, get_swe_pro_sampled_issues, query_llm, extract_json_data_in_llm_answer
from common.prompts import prompt_extract_nouns_from_issue_title
from definitions import DATA_DIR, ROOT_DIR


def remove_bracketed_content(text):
    """ Remove bracketed content from issue title (e.g., [xxx]) """
    cleaned = re.sub(r'\[[^\]]*\]', '', text)
    return cleaned.strip()


def extract_issue_title(issue_content):
    """
    Extract issue title from problem statement (for SWE-bench Pro)
    
    Args:
        issue_content: Problem statement content
        
    Returns:
        Extracted issue title
    """
    issue_content = issue_content.lower()
    is_translated = False
    if issue_content.startswith('"'):
        is_translated = True
        
    while True:
        original_length = len(issue_content)
        if issue_content and issue_content[0] in {'"', '#','*',' ', '\n', '\t', ':'}:
            issue_content = issue_content[1:]
            continue
            
        if issue_content.startswith('title'):
            issue_content = issue_content[5:]
            continue
            
        if issue_content.startswith('\\n'):
            issue_content = issue_content[2:]

        if len(issue_content) == original_length:
            break
    
    if is_translated:
        issue_title = issue_content.split('\\n')[0]
    else:
        issue_title = issue_content.split('\n')[0]
    
    return issue_title


def remove_duplicates(original_noun_list):
    """
    Remove duplicate nouns from the list
    
    Args:
        original_noun_list: List of nouns to deduplicate
        
    Returns:
        Deduplicated list of nouns
    """
    noun_list = []
    for o_n in original_noun_list:
        o_n_splits = o_n.split()
        key = 0
        for n in noun_list:
            n_splits = n.split()
            if all(elem in o_n_splits for elem in n_splits) or all(elem in n_splits for elem in o_n_splits):
                key = 1
                break
        if key == 0:
            noun_list.append(o_n)
    return noun_list


def extract_nouns_from_issue(issue_input, benchmark="swe_lancer"):
    """
    Extract noun terms from issue title using LLM
    
    Args:
        issue_input: For SWE-Lancer: issue_id (integer)
                     For SWE-bench Pro: issue dictionary with 'problem_statement' key
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
        
    Returns:
        List of noun information dictionaries with 'noun' and 'noun_definition' keys
    """
    if benchmark == "swe_lancer":
        issue_id = issue_input
        issue_title, issue_body = get_swe_lancer_issue_data(issue_id)
        cleaned_issue_title = remove_bracketed_content(issue_title)
    else:
        issue = issue_input
        issue_title = extract_issue_title(issue['problem_statement'])
        cleaned_issue_title = issue_title
    
    prompt = prompt_extract_nouns_from_issue_title(cleaned_issue_title)
    model_response = query_llm(prompt, 'gpt-4o-mini')
    extracted_nouns = extract_json_data_in_llm_answer(model_response)
    extracted_noun_list = json.loads(extracted_nouns)
    original_noun_list = [noun.lower().replace("_", " ").replace(".", " ") for noun in extracted_noun_list]
    noun_list = remove_duplicates(original_noun_list)

    issue_nouns_info = []
    for noun in noun_list:
        temp = {}
        temp['noun'] = noun
        temp['noun_definition'] = ""
        issue_nouns_info.append(temp)
    
    return issue_nouns_info


def save_issue_nouns(issue_nouns_info, issue_id, benchmark="swe_lancer"):
    """
    Save extracted noun information to file
    
    Args:
        issue_nouns_info: List of noun information dictionaries
        issue_id: Issue ID
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
    """
    if benchmark == "swe_lancer":
        store_path = DATA_DIR + f"/SWE-Lancer-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
    else:
        store_path = ROOT_DIR + f"/data/SWE-Pro-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
    
    os.makedirs(os.path.dirname(store_path), exist_ok=True)
    with open(store_path, 'w', encoding='utf-8') as f:
        json.dump(issue_nouns_info, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    benchmark = "swe_lancer"
    
    if benchmark == "swe_lancer":
        issue_ids = get_swe_lancer_issue_ids()
        
        for issue_id in issue_ids:
            issue_nouns_info = extract_nouns_from_issue(issue_id, benchmark)
            save_issue_nouns(issue_nouns_info, issue_id, benchmark)
    else:
        swe_pro_sampled_issues = get_swe_pro_sampled_issues()
        
        for issue in tqdm(swe_pro_sampled_issues):
            issue_id = issue['instance_id']
            issue_nouns_info = extract_nouns_from_issue(issue, benchmark)
            save_issue_nouns(issue_nouns_info, issue_id, benchmark)
