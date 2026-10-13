"""
Match Noun Terms from Issue to Repository Functions

This script matches noun terms extracted from issue titles with nouns found
in repository functions using n-gram matching.

Supports:
- SWE-Lancer
- SWE-bench Pro
"""

import json
import os
import itertools
from tqdm import tqdm
from common.utils import get_json_data, get_swe_lancer_issue_ids, get_swe_pro_sampled_issues
from definitions import DATA_DIR


def generate_all_ngrams(noun):
    """
    Generate all possible n-grams from a noun
    
    Args:
        noun: Input noun (can be multi-word)
        
    Returns:
        List of all n-grams
    """
    parts = noun.split()
    ngrams = []
    for r in range(1, len(parts)+1):
        for combo in itertools.combinations(parts, r):
            ngrams.append(' '.join(combo))
    return ngrams


def normalize_file_path(file_path, benchmark="swe_lancer"):
    """
    Normalize file path by removing workspace-specific prefixes
    
    Args:
        file_path: Original file path
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
        
    Returns:
        Normalized file path
    """
    if benchmark == "swe_lancer":
        if "/App/" in file_path:
            return file_path.split("/App/")[1]
    else:
        if "/workspace/" in file_path:
            return file_path.split("/workspace/")[1].split("/", 1)[1]
    return file_path


def nouns_match(issue_id, issue_nouns_info, benchmark="swe_lancer"):
    """
    Match nouns from issue with repository functions
    
    Args:
        issue_id: Issue ID
        issue_nouns_info: List of noun information dictionaries
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
    """
    if benchmark == "swe_lancer":
        benchmark_dir = "SWE-Lancer-Loc"
        suffix = ".json"
    else:
        benchmark_dir = "SWE-Pro-Loc"
        suffix = ".json"
    
    issue_repo_nouns_path = DATA_DIR + f"/{benchmark_dir}/extracted_terms/nouns/{issue_id}/total_nouns.json"
    issue_repo_nouns_functions = get_json_data(issue_repo_nouns_path)
    
    for noun_info in issue_nouns_info:
        noun = noun_info['noun']
        noun_ngrams = generate_all_ngrams(noun)
        sorted_noun_ngrams = sorted(noun_ngrams, key=lambda x: len(x.split()), reverse=True)
        joined_noun = "_".join(noun.split())
        
        result = []
        for n_gram in sorted_noun_ngrams:
            for function in issue_repo_nouns_functions:
                nouns = function['nouns']
                if n_gram in nouns:
                    temp = {}
                    temp['noun'] = n_gram
                    temp['file_path'] = normalize_file_path(function['file_path'], benchmark)
                    temp['function_name'] = function['function_name']
                    temp['function_body'] = function['function_body']
                    result.append(temp)
        
        if len(result) < 1000:
            issue_repo_nouns_dir = DATA_DIR + f"/{benchmark_dir}/issue_repo_nouns/{issue_id}"
            os.makedirs(issue_repo_nouns_dir, exist_ok=True)
            issue_repo_nouns_data_path = issue_repo_nouns_dir + f"/{joined_noun}_nouns_info{suffix}"
            with open(issue_repo_nouns_data_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    benchmark = "swe_lancer"
    
    if benchmark == "swe_lancer":
        issue_ids = get_swe_lancer_issue_ids()
        
        for issue_id in tqdm(issue_ids):
            issue_nouns_info_path = DATA_DIR + f"/SWE-Lancer-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
            if os.path.exists(issue_nouns_info_path):
                issue_nouns_info = get_json_data(issue_nouns_info_path)
                nouns_match(issue_id, issue_nouns_info, benchmark)
    else:
        swe_pro_sampled_issues = get_swe_pro_sampled_issues()
        
        for issue in tqdm(swe_pro_sampled_issues):
            issue_id = issue['instance_id']
            issue_nouns_info_path = DATA_DIR + f"/SWE-Pro-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
            
            if os.path.exists(issue_nouns_info_path):
                issue_nouns_info = get_json_data(issue_nouns_info_path)
                nouns_match(issue_id, issue_nouns_info, benchmark)
                