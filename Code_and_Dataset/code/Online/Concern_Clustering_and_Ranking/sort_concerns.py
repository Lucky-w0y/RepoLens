"""
Sort and Rank Concerns Using LLM and Embedding Similarity

This script sorts and ranks concerns using LLM-based analysis and embedding similarity.

Supports:
- SWE-Lancer
- SWE-bench Pro
"""

import json
import os
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
from collections import defaultdict
from sentence_transformers import SentenceTransformer
from common.utils import get_json_data, get_swe_lancer_issue_ids, get_swe_lancer_issue_data, get_swe_pro_sampled_issues, query_llm, extract_json_data_in_llm_answer
from common.prompts import prompt_concern_sorting
from definitions import DATA_DIR

model = SentenceTransformer('all-MiniLM-L6-v2')


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


def group_concerns_by_noun(concern_list):
    """
    Group concerns by related noun
    
    Args:
        concern_list: List of concerns
        
    Returns:
        List of grouped concerns
    """
    grouped_concerns = defaultdict(list)

    for concern in concern_list:
        related_noun = concern["related_noun"]
        concern_summary = concern["concern_summary"]

        related_code = []
        for func in concern["related_functions"]:
            code_location = f'{func["file_path"]}:{func["function_name"]}'
            reference_code = func.get("noun_reference_code", "")
            related_code.append({
                "code_location": code_location,
                "reference_code": reference_code
            })

        grouped_concerns[related_noun].append({
            "concern_summary": concern_summary,
            "related_code": related_code
        })

    result = []
    for noun, concerns in grouped_concerns.items():
        result.append({
            "related_noun": noun,
            "concerns": concerns
        })
    return result


def compute_similarity_df(query, candidates, k):
    """
    Compute similarity between query and candidates
    
    Args:
        query: Query text
        candidates: List of candidate texts
        k: Number of top results to return
        
    Returns:
        List of top k candidates
    """
    q_embedding = model.encode(query).tolist()
    query_embedding = np.array(q_embedding)
    query_norm = np.linalg.norm(query_embedding)

    embeddings = model.encode(candidates).tolist()
    embeddings_matrix = np.vstack(embeddings)
    
    dot_products = np.dot(embeddings_matrix, query_embedding)
    candidate_norms = np.linalg.norm(embeddings_matrix, axis=1)
    denom = candidate_norms * query_norm
    denom[denom == 0] = 1e-10

    similarities = dot_products / denom

    df = pd.DataFrame({
        'content': candidates,
        'embedding': embeddings,
        'similarity': similarities
    })

    temp_res = df.sort_values(by='similarity', ascending=False).reset_index(drop=True).head(k)
    res = [temp_res.iloc[i]['content'] for i in range(len(temp_res))]
    return res


def concern_rank_by_embedding_similarity(issue_id, issue_nouns_info, benchmark="swe_lancer"):
    """
    Sort concerns using embedding similarity
    
    Args:
        issue_id: Issue ID
        issue_nouns_info: List of noun information dictionaries
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
    """
    if benchmark == "swe_lancer":
        issue_title, issue_body = get_swe_lancer_issue_data(issue_id)
        concern_suffix = ".json"
        output_path = DATA_DIR + f"/SWE-Lancer-Loc/concerns/{issue_id}/__sorted_concern_list_4o_emb50.json"
    else:
        issue = get_swe_pro_sampled_issues()
        issue_title = extract_issue_title(issue['problem_statement'])
        issue_body = ""
        concern_suffix = ".json"
        output_path = DATA_DIR + f"/SWE-Pro-Loc/concerns/{issue_id}/sorted_concern_list_emb50.json"
    
    all_concern_list = []
    concern_summaries = []
    
    for issue_noun in issue_nouns_info:
        noun = issue_noun['noun']
        joined_noun = "_".join(noun.split())
        
        if benchmark == "swe_lancer":
            concern_path = DATA_DIR + f"/SWE-Lancer-Loc/concerns/{issue_id}/{joined_noun}_concern_list{concern_suffix}"
        else:
            concern_path = DATA_DIR + f"/SWE-Pro-Loc/concerns/{issue_id}/{joined_noun}_concern_list{concern_suffix}"
        
        if not os.path.exists(concern_path):
            continue
        
        concerns = get_json_data(concern_path)
        
        for concern in concerns:
            temp = concern.copy()
            temp['related_noun'] = issue_noun['noun']
            all_concern_list.append(temp)
            concern_summaries.append(concern['concern_summary'])
    
    sorted_concern_list = []
    if len(concern_summaries) != 0:
        sorted_concern_summaries = compute_similarity_df(issue_title, concern_summaries, k=50)
        for concern_summary in sorted_concern_summaries:
            for concern in all_concern_list:
                if concern['concern_summary'] == concern_summary:
                    sorted_concern_list.append(concern)
                    break
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_concern_list, f, indent=2, ensure_ascii=False)


def get_sorted_concerns_by_llm(issue_id, benchmark="swe_lancer"):
    """
    Sort concerns using LLM
    
    Args:
        issue_id: Issue ID
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
    """
    if benchmark == "swe_lancer":
        issue_title, issue_body = get_swe_lancer_issue_data(issue_id)
        issue_nouns_info_path = DATA_DIR + f"/SWE-Lancer-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
        emb_sorted_path = DATA_DIR + f"/SWE-Lancer-Loc/concerns/{issue_id}/__sorted_concern_list_emb50.json"
        output_path = DATA_DIR + f"/SWE-Lancer-Loc/concerns/{issue_id}/__sorted_concern_list_4o_emb_llm.json"
    else:
        issue = get_swe_pro_sampled_issues()
        issue_title = extract_issue_title(issue['problem_statement'])
        issue_body = ""
        issue_nouns_info_path = DATA_DIR + f"/SWE-Pro-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
        emb_sorted_path = DATA_DIR + f"/SWE-Pro-Loc/concerns/{issue_id}/sorted_concern_list_emb50.json"
        output_path = DATA_DIR + f"/SWE-Pro-Loc/concerns/{issue_id}/sorted_concern_list_llm.json"
    
    issue_nouns_info = get_json_data(issue_nouns_info_path)
    concerns = get_json_data(emb_sorted_path)
    grouped_concerns = group_concerns_by_noun(concerns)
    
    all_concern_list = []
    for concern in concerns:
        all_concern_list.append(concern)
    
    prompt = prompt_concern_sorting(issue_title, issue_body, grouped_concerns)

    max_retries = 20
    for attempt in range(max_retries):
        try:
            output = query_llm(prompt, "gpt-4o-mini")
            sorted_concern_summaries = json.loads(extract_json_data_in_llm_answer(output))
            break
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise

    sorted_concern_list = []
    for concern_summary in sorted_concern_summaries:
        for concern in all_concern_list:
            if concern['concern_summary'] == concern_summary:
                sorted_concern_list.append(concern)
                break

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_concern_list, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    benchmark = "swe_lancer"
    
    if benchmark == "swe_lancer":
        issue_ids = get_swe_lancer_issue_ids()
        
        for issue_id in tqdm(issue_ids):
            issue_nouns_info_path = DATA_DIR + f"/SWE-Lancer-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
            if os.path.exists(issue_nouns_info_path):
                issue_nouns_info = get_json_data(issue_nouns_info_path)
                concern_rank_by_embedding_similarity(issue_id, issue_nouns_info, benchmark)
                get_sorted_concerns_by_llm(issue_id, benchmark)
    else:
        issues = get_swe_pro_sampled_issues()
        
        for issue in tqdm(issues):
            issue_id = issue['instance_id']
            issue_nouns_info_path = DATA_DIR + f"/SWE-Pro-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
            if os.path.exists(issue_nouns_info_path):
                issue_nouns_info = get_json_data(issue_nouns_info_path)
                concern_rank_by_embedding_similarity(issue_id, issue_nouns_info, benchmark)
                get_sorted_concerns_by_llm(issue_id, benchmark)
        
       
