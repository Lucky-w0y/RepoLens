"""
Pre-cluster Noun Terms Using Hierarchical Clustering

This script performs pre-clustering of noun terms using hierarchical clustering
with semantic embeddings and function call relationships.

Supports:
- SWE-Lancer
- SWE-bench Pro
"""

import os
import json
import numpy as np
import pandas as pd
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from common.utils import get_json_data, get_swe_lancer_issue_ids, get_swe_pro_sampled_issues
from definitions import DATA_DIR

model = SentenceTransformer('all-MiniLM-L6-v2')


def cosine_similarity(a, b):
    """
    Calculate cosine similarity between two vectors
    
    Args:
        a: First vector
        b: Second vector
        
    Returns:
        Cosine similarity value
    """
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


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


def has_call_relation(idx1, idx2, issue_repo_noun_data):
    """
    Check if two functions have call relationship
    
    Args:
        idx1: Index of first function
        idx2: Index of second function
        issue_repo_noun_data: List of noun data dictionaries
        
    Returns:
        1 if functions have call relationship, 0 otherwise
    """
    data1 = issue_repo_noun_data[idx1]
    data2 = issue_repo_noun_data[idx2]

    call_data1 = data1['function_name'] + "("
    call_data2 = data2['function_name'] + "("
    if call_data1 in data2['function_body'] or call_data2 in data1['function_body']:
        return 1
    else:
        return 0


def hierarchical_clustering(exp_embeddings, def_embeddings, func_embeddings, issue_repo_noun_data):
    """
    Perform hierarchical clustering
    
    Args:
        exp_embeddings: List of expanded name embeddings
        def_embeddings: List of definition embeddings
        func_embeddings: List of functionality embeddings
        issue_repo_noun_data: List of noun data dictionaries
        
    Returns:
        Root cluster node (tree structure)
    """
    n = len(exp_embeddings)
    similarity_matrix = np.zeros((n, n))

    for i in range(n):
        for j in range(i+1, n):
            exp_emb_sim = cosine_similarity(exp_embeddings[i], exp_embeddings[j])
            def_emb_sim = cosine_similarity(def_embeddings[i], def_embeddings[j])
            func_emb_sim = cosine_similarity(func_embeddings[i], func_embeddings[j])
            call_bonus = 1.0 if has_call_relation(i, j, issue_repo_noun_data) else 0.0
            sim = 0.25 * exp_emb_sim + 0.25 * def_emb_sim + 0.25 * func_emb_sim + 0.25 * call_bonus
            similarity_matrix[i, j] = sim
            similarity_matrix[j, i] = sim

    clusters = [
        {"indices": [i], "children": [], "sim": 0.0}
        for i in range(n)
    ]

    while len(clusters) > 1:
        max_sim = -1
        merge_pair = None
        for i in range(len(clusters)):
            for j in range(i+1, len(clusters)):
                sims = [similarity_matrix[a, b] for a in clusters[i]["indices"] for b in clusters[j]["indices"]]
                avg_sim = np.mean(sims)
                if avg_sim > max_sim:
                    max_sim = avg_sim
                    merge_pair = (i, j)

        if merge_pair is None:
            break

        i, j = merge_pair
        new_indices = clusters[i]["indices"] + clusters[j]["indices"]
        new_node = {
            "indices": new_indices,
            "children": [clusters[i], clusters[j]],
            "sim": max_sim,
        }
        clusters[i] = new_node
        del clusters[j]
    
    return clusters[0]


def split_tree(node, max_cluster_size=100):
    """
    Recursively split tree to ensure leaf clusters <= max_cluster_size
    
    Args:
        node: Cluster node (tree structure)
        max_cluster_size: Maximum size of leaf clusters
        
    Returns:
        List of leaf cluster indices
    """
    if len(node["indices"]) <= max_cluster_size:
        return [node["indices"]]

    results = []
    for child in node["children"]:
        if len(child["indices"]) <= max_cluster_size:
            results.append(child["indices"])
        else:
            results.extend(split_tree(child, max_cluster_size))
    return results


def noun_pre_cluster(issue_id, issue_nouns_info, benchmark="swe_lancer"):
    """
    Perform pre-clustering for noun terms
    
    Args:
        issue_id: Issue ID
        issue_nouns_info: List of noun information dictionaries
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
    """
    if benchmark == "swe_lancer":
        benchmark_dir = "SWE-Lancer-Loc"
        repo_suffix = ".json"
        pre_suffix = "_pre_clusters_hc.json"
    else:
        benchmark_dir = "SWE-Pro-Loc"
        repo_suffix = ".json"
        pre_suffix = "_pre_clusters.json"
    
    for issue_noun in issue_nouns_info:
        noun = issue_noun['noun']
        joined_noun = "_".join(noun.split())
        issue_repo_noun_path = DATA_DIR + f"/{benchmark_dir}/issue_repo_nouns/{issue_id}/{joined_noun}_nouns_info{repo_suffix}"
        
        if not os.path.exists(issue_repo_noun_path):
            continue
        
        issue_repo_noun_data = get_json_data(issue_repo_noun_path)
        
        if len(issue_repo_noun_data) == 0:
            final_clusters = []
        else:
            noun_expanded_names = []
            noun_definitions = []
            noun_functionalities = []
            for issue_repo_noun in issue_repo_noun_data:
                noun_expanded_names.append(issue_repo_noun['noun_expanded_name'])
                noun_definitions.append(issue_repo_noun['noun_definition'])
                noun_functionalities.append(issue_repo_noun['noun_functionality'])

            exp_embeddings = model.encode(noun_expanded_names).tolist()
            def_embeddings = model.encode(noun_definitions).tolist()
            func_embeddings = model.encode(noun_functionalities).tolist()
            
            root_cluster = hierarchical_clustering(exp_embeddings, def_embeddings, func_embeddings, issue_repo_noun_data)
            final_clusters = split_tree(root_cluster, max_cluster_size=100)

        issue_pre_cluster_dir = DATA_DIR + f"/{benchmark_dir}/pre_cluster_result/{issue_id}"
        os.makedirs(issue_pre_cluster_dir, exist_ok=True)
        issue_pre_cluster_path = issue_pre_cluster_dir + f"/{joined_noun}_pre_clusters{pre_suffix}"
        with open(issue_pre_cluster_path, 'w', encoding='utf-8') as f:
            json.dump(final_clusters, f, indent=2, ensure_ascii=False)


if __name__ == '__main__':
    benchmark = "swe_lancer"
    
    if benchmark == "swe_lancer":
        issue_ids = get_swe_lancer_issue_ids()
        
        for issue_id in tqdm(issue_ids):
            issue_nouns_info_path = DATA_DIR + f"/SWE-Lancer-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
            if os.path.exists(issue_nouns_info_path):
                issue_nouns_info = get_json_data(issue_nouns_info_path)
                noun_pre_cluster(issue_id, issue_nouns_info, benchmark)
    else:
        swe_pro_sampled_issues = get_swe_pro_sampled_issues()
        
        for issue in tqdm(swe_pro_sampled_issues):
            issue_id = issue['instance_id']
            issue_nouns_info_path = DATA_DIR + f"/SWE-Pro-Loc/issue_noun_terms/{issue_id}/issue_nouns_info.json"
            if os.path.exists(issue_nouns_info_path):
                issue_nouns_info = get_json_data(issue_nouns_info_path)
                noun_pre_cluster(issue_id, issue_nouns_info, benchmark)
