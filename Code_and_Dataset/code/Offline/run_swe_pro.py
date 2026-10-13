import argparse
import os
import json
import subprocess
import shutil
from tqdm import tqdm
from definitions import (
    ROOT_DIR,
    SWE_PRO_WORKSPACE,
    SWE_PRO_RAW_REPO_PATH
)

from term_extraction.extract_functions_and_identifiers import (
    extract_functions,
    filter_functions,
    extract_words
)
from term_extraction.extract_noun_terms import extract_nouns
from term_enrichment.enrich_noun_term import noun_explanation_and_summary
from common.utils import get_swe_pro_sampled_issues


def save_json(data, file_path):
    """Save data to JSON file"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if os.path.exists(file_path):
        os.remove(file_path)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def copy_and_checkout_repo(issue):
    """Copy issue's repo to workspace and checkout to specified commit id"""
    repo_name = issue['repo'].split("/")[-1]
    raw_repo = os.path.join(SWE_PRO_RAW_REPO_PATH, repo_name)
    repo_dir = os.path.join(SWE_PRO_WORKSPACE, repo_name)
    
    try:
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)
        shutil.copytree(raw_repo, repo_dir)
    except Exception as e:
        print(f"Error copying repo: {e}")

    commit_id = issue['base_commit']
    print(f"Switching to commit: {commit_id}")
    original_dir = os.getcwd()
    try:
        os.chdir(repo_dir)
        if "webclients" in repo_name.lower():
            print(f"Fetching commit {commit_id} for webclient repo...")
            subprocess.run(["git", "fetch", "origin", commit_id], check=True)
        subprocess.run(["git", "reset", "--hard", commit_id], check=True)
        subprocess.run(["git", "clean", "-fd"], check=True)
        subprocess.run(["git", "checkout", commit_id], check=True)
    finally:
        os.chdir(original_dir)


def run_term_extraction(swe_pro_issues):
    """Run term extraction for SWE-bench Pro benchmark"""
    for issue in tqdm(swe_pro_issues, desc="Processing SWE-bench Pro issues"):
        issue_id = issue['instance_id']
        repo_name = issue['repo'].split("/")[-1]
        repo_dir = os.path.join(SWE_PRO_WORKSPACE, repo_name)
        
        nouns_path = os.path.join(
            ROOT_DIR,
            f"Code_and_Dataset/dataset/SWE-Pro-Loc/extracted_terms/nouns/{issue_id}/total_nouns.json"
        )
        if os.path.exists(nouns_path):
            print(f"Skipping issue {issue_id}: target file already exists")
            continue
        
        try:
            print(f"\nProcessing issue: {issue_id}")
            
            print("  [0/4] Copying repo and checking out commit...")
            copy_and_checkout_repo(issue)
            
            print("  [1/4] Extracting all functions...")
            functions = extract_functions(repo_dir)
            
            functions_path = os.path.join(
                ROOT_DIR, 
                f"Code_and_Dataset/dataset/SWE-Pro-Loc/extracted_terms/functions/{issue_id}/total_functions.json"
            )
            save_json(functions, functions_path)
            
            print("  [2/4] Filtering functions...")
            filtered_functions = filter_functions(functions)
            
            filtered_functions_path = os.path.join(
                ROOT_DIR,
                f"Code_and_Dataset/dataset/SWE-Pro-Loc/extracted_terms/functions/{issue_id}/filtered_functions.json"
            )
            save_json(filtered_functions, filtered_functions_path)
            
            print("  [3/4] Extracting identifiers (words)...")
            words_data = extract_words(filtered_functions)
            
            words_path = os.path.join(
                ROOT_DIR,
                f"Code_and_Dataset/dataset/SWE-Pro-Loc/extracted_terms/words/{issue_id}/total_words.json"
            )
            save_json(words_data, words_path)
            
            print("  [4/4] Extracting nouns from identifiers...")
            nouns_data = extract_nouns(words_data)
            
            nouns_path = os.path.join(
                ROOT_DIR,
                f"Code_and_Dataset/dataset/SWE-Pro-Loc/extracted_terms/nouns/{issue_id}/total_nouns.json"
            )
            save_json(nouns_data, nouns_path)
            
            print(f"Completed processing issue: {issue_id}\n")
        except Exception as e:
            print(f"Error processing issue {issue_id}: {e}")
            import traceback
            traceback.print_exc()
            continue


def run_term_enrichment(swe_pro_issues):
    """Run term enrichment for SWE-bench Pro benchmark"""
    for issue in tqdm(swe_pro_issues, desc="Enriching SWE-bench Pro terms"):
        issue_id = issue['instance_id']
        try:
            print(f"\nEnriching issue: {issue_id}")
            noun_explanation_and_summary(issue_id, [], benchmark="swe_pro")
        except Exception as e:
            print(f"Error enriching issue {issue_id}: {e}")
            import traceback
            traceback.print_exc()
            continue


def main():
    parser = argparse.ArgumentParser(
        description="Run offline term extraction and enrichment for SWE-bench Pro benchmark"
    )
    parser.add_argument(
        '--stage',
        type=str,
        required=True,
        choices=['extraction', 'enrichment', 'all'],
        help='Stage to run (extraction, enrichment, or all)'
    )
    
    args = parser.parse_args()
    stage = args.stage
    
    swe_pro_issues = get_swe_pro_sampled_issues()
    print(f"Total {len(swe_pro_issues)} issues to process")
    
    print(f"Running {stage} for SWE-bench Pro benchmark")
    
    if stage in ['extraction', 'all']:
        print("\n=== Running Term Extraction ===")
        run_term_extraction(swe_pro_issues)
    
    if stage in ['enrichment', 'all']:
        print("\n=== Running Term Enrichment ===")
        run_term_enrichment(swe_pro_issues)


if __name__ == "__main__":
    main()
