"""
Generate Concern Clusters from Pre-clustered Data

This script generates concern lists from pre-clustered noun data using LLM-based analysis.

Supports:
- SWE-Lancer
- SWE-bench Pro
"""

import json
import os
import time
from tqdm import tqdm
from common.utils import get_json_data, get_swe_lancer_issue_ids, get_swe_pro_sampled_issues, query_llm, extract_json_data_in_llm_answer
from common.prompts import prompt_concern_clustering
from definitions import DATA_DIR



def generate_concern_list_by_clusters(issue_id, issue_nouns_info, benchmark="swe_lancer"):
    """
    Generate concern list from pre-clustered data using LLM
    
    Args:
        issue_id: Issue ID
        issue_nouns_info: List of noun information dictionaries
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
    """
    if benchmark == "swe_lancer":
        benchmark_dir = "SWE-Lancer-Loc"
        repo_suffix = ".json"
        pre_suffix = "_pre_clusters_hc.json"
        concern_suffix = ".json"
    else:
        benchmark_dir = "SWE-Pro-Loc"
        repo_suffix = ".json"
        pre_suffix = "_pre_clusters.json"
        concern_suffix = ".json"
    
    total_concern_num = 0
    
    for issue_noun in issue_nouns_info:
        noun = issue_noun['noun']
        joined_noun = "_".join(noun.split())
        
        issue_repo_nouns_path = DATA_DIR + f"/{benchmark_dir}/issue_repo_nouns/{issue_id}/{joined_noun}_nouns_info{repo_suffix}"
        
        if not os.path.exists(issue_repo_nouns_path):
            continue
        
        issue_repo_noun_data = get_json_data(issue_repo_nouns_path)
        
        issue_pre_cluster_path = DATA_DIR + f"/{benchmark_dir}/pre_cluster_result/{issue_id}/{joined_noun}_pre_clusters{pre_suffix}"
        
        if not os.path.exists(issue_pre_cluster_path):
            continue
        
        pre_clusters = get_json_data(issue_pre_cluster_path)
        concern_list = []
        
        for pre_cluster in pre_clusters:
            pre_cluster_data = []
            for idx in pre_cluster:
                noun_data = issue_repo_noun_data[idx]
                pre_cluster_data.append(noun_data)
            
            if len(pre_cluster_data) == 0:
                continue
            
            noun_functionalities = []
            id = 1
            for n_d in pre_cluster_data:
                temp = {}
                temp['id'] = id
                temp['noun_expanded_name'] = n_d['noun_expanded_name']
                temp['noun_functionality'] = n_d['noun_functionality']
                noun_functionalities.append(temp)
                id += 1
            
            prompt = prompt_concern_clustering(noun, noun_functionalities)
            
            max_retries = 100
            for attempt in range(max_retries):
                try:
                    output = query_llm(prompt, "gpt-4o")
                    concerns = json.loads(extract_json_data_in_llm_answer(output))
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        raise
            
            total_concern_num += len(concerns)
            
            for concern in concerns:
                temp = {}
                temp['concern_summary'] = concern['concern_summary']
                ids = concern['ids']
                related_functions = []
                for id in ids:
                    t = {}
                    t['function_name'] = pre_cluster_data[id-1]['function_name']
                    t['file_path'] = pre_cluster_data[id-1]['file_path']
                    related_functions.append(t)
                temp['related_functions'] = related_functions
                concern_list.append(temp)
        
        issue_concern_dir = DATA_DIR + f"/{benchmark_dir}/concerns/{issue_id}"
        os.makedirs(issue_concern_dir, exist_ok=True)
        issue_concern_path = issue_concern_dir + f"/{joined_noun}_concern_list{concern_suffix}"
        with open(issue_concern_path, 'w', encoding='utf-8') as f:
            json.dump(concern_list, f, indent=2, ensure_ascii=False)


def concern_cluster(issue_id, issue_nouns_info, benchmark="swe_lancer"):
    """
    Generate concern list with retry mechanism
    
    Args:
        issue_id: Issue ID
        issue_nouns_info: List of noun information dictionaries
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
    """
    max_retries = 10
    retries = 0
    while retries < max_retries:
        try:
            generate_concern_list_by_clusters(issue_id, issue_nouns_info, benchmark)
            break
        except Exception as e:
            retries += 1
            print(f"Error on {issue_id}, retry {retries}/{max_retries}: {e}")
            time.sleep(1)
    else:
        print(f"Failed on issue {issue_id} after {max_retries} retries.")


if __name__ == "__main__":
    benchmark = "swe_lancer"
    
    if benchmark == "swe_lancer":
        issue_ids = get_swe_lancer_issue_ids()
        
        for issue_id in tqdm(issue_ids):
            issue_nouns_info_path = DATA_DIR + f"/SWE-Lancer-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
            if os.path.exists(issue_nouns_info_path):
                issue_nouns_info = get_json_data(issue_nouns_info_path)
                concern_cluster(issue_id, issue_nouns_info, benchmark)
    else:
        swe_pro_sampled_issues = get_swe_pro_sampled_issues()
        
        for issue in tqdm(swe_pro_sampled_issues):
            issue_id = issue['instance_id']
            issue_nouns_info_path = DATA_DIR + f"/SWE-Pro-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
            if os.path.exists(issue_nouns_info_path):
                issue_nouns_info = get_json_data(issue_nouns_info_path)
                concern_cluster(issue_id, issue_nouns_info, benchmark)
