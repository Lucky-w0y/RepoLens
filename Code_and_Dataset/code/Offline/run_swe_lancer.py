import argparse
import os
import json
import subprocess
from tqdm import tqdm
from definitions import (
    ROOT_DIR,
    SWE_LANCER_ISSUES_DIR,
    SWE_LANCER_RRAW_REPO_PATH
)

from term_extraction.extract_functions_and_identifiers import (
    extract_functions,
    filter_functions,
    extract_words
)
from term_extraction.extract_noun_terms import extract_nouns
from term_enrichment.enrich_noun_term import noun_explanation_and_summary
from common.utils import get_swe_lancer_issue_ids


def save_json(data, file_path):
    """Save data to JSON file"""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    if os.path.exists(file_path):
        os.remove(file_path)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_issue_commit_id(issue_id):
    """Get commit ID for a specific issue"""
    issue_data_path = os.path.join(SWE_LANCER_ISSUES_DIR, str(issue_id), "commit_id.txt")
    with open(issue_data_path, "r", encoding="utf-8") as f:
        commit_id = f.read().strip()
    return commit_id


def checkout_repo(commit_id):
    """Checkout repository to specified commit id"""
    print(f"Switching to commit: {commit_id}")
    original_dir = os.getcwd()
    try:
        os.chdir(SWE_LANCER_RRAW_REPO_PATH)
        subprocess.run(["git", "reset", "--hard", commit_id], check=True)
        subprocess.run(["git", "clean", "-fd"], check=True)
        subprocess.run(["git", "checkout", commit_id], check=True)
    finally:
        os.chdir(original_dir)


def run_term_extraction(issue_ids):
    """Run term extraction for SWE-Lancer benchmark"""
    for issue_id in tqdm(issue_ids, desc="Processing SWE-Lancer issues"):
        nouns_path = os.path.join(
            ROOT_DIR,
            f"Code_and_Dataset/dataset/SWE-Lancer-Loc/extracted_terms/nouns/{issue_id}/total_nouns.json"
        )
        if os.path.exists(nouns_path):
            print(f"Skipping issue {issue_id}: target file already exists")
            continue
        
        try:
            print(f"\nProcessing issue: {issue_id}")
            
            print("  [0/4] Checking out commit...")
            commit_id = get_issue_commit_id(issue_id)
            checkout_repo(commit_id)
            
            print("  [1/4] Extracting all functions...")
            functions = extract_functions(SWE_LANCER_RRAW_REPO_PATH)
            
            functions_path = os.path.join(
                ROOT_DIR, 
                f"Code_and_Dataset/dataset/SWE-Lancer-Loc/extracted_terms/functions/{issue_id}/total_functions.json"
            )
            save_json(functions, functions_path)
            
            print("  [2/4] Filtering functions...")
            filtered_functions = filter_functions(functions)
            
            filtered_functions_path = os.path.join(
                ROOT_DIR,
                f"Code_and_Dataset/dataset/SWE-Lancer-Loc/extracted_terms/functions/{issue_id}/filtered_functions.json"
            )
            save_json(filtered_functions, filtered_functions_path)
            
            print("  [3/4] Extracting identifiers (words)...")
            words_data = extract_words(filtered_functions)
            
            words_path = os.path.join(
                ROOT_DIR,
                f"Code_and_Dataset/dataset/SWE-Lancer-Loc/extracted_terms/words/{issue_id}/total_words.json"
            )
            save_json(words_data, words_path)
            
            print("  [4/4] Extracting nouns from identifiers...")
            nouns_data = extract_nouns(words_data)
            
            nouns_path = os.path.join(
                ROOT_DIR,
                f"Code_and_Dataset/dataset/SWE-Lancer-Loc/extracted_terms/nouns/{issue_id}/total_nouns.json"
            )
            save_json(nouns_data, nouns_path)
            
            print(f"Completed processing issue: {issue_id}\n")
        except Exception as e:
            print(f"Error processing issue {issue_id}: {e}")
            import traceback
            traceback.print_exc()
            continue


def run_term_enrichment(issue_ids):
    """Run term enrichment for SWE-Lancer benchmark"""
    for issue_id in tqdm(issue_ids, desc="Enriching SWE-Lancer terms"):
        try:
            print(f"\nEnriching issue: {issue_id}")
            noun_explanation_and_summary(issue_id, [], benchmark="swe_lancer")
        except Exception as e:
            print(f"Error enriching issue {issue_id}: {e}")
            import traceback
            traceback.print_exc()
            continue


def main():
    parser = argparse.ArgumentParser(
        description="Run offline term extraction and enrichment for SWE-Lancer benchmark"
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
    
    issue_ids = get_swe_lancer_issue_ids()
    print(f"Total {len(issue_ids)} issues to process")
    
    print(f"Running {stage} for SWE-Lancer benchmark")
    
    if stage in ['extraction', 'all']:
        print("\n=== Running Term Extraction ===")
        run_term_extraction(issue_ids)
    
    if stage in ['enrichment', 'all']:
        print("\n=== Running Term Enrichment ===")
        run_term_enrichment(issue_ids)


if __name__ == "__main__":
    main()
