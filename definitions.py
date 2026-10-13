import os
from pathlib import Path

# Replace with your actual API key
OPENAI_API_KEY = "YOUR_OPENAI_KEY"  

# This is your Project Root
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))  

DATA_DIR = ROOT_DIR + "/Code_and_Dataset/dataset"

# SWE-Lancer-Loc related path
SWE_LANCER_ISSUES_DIR = DATA_DIR + "/SWE-Lancer-Loc/issues"
SWE_LANCER_ISSUE_IDS = DATA_DIR + "/SWE-Lancer-Loc/valid_issue_ids.txt"
SWE_LANCER_RRAW_REPO_PATH = "YOUR_CLONED_REPO_PATH"  # Replace with your actual cloned repo path


# SWE-Pro-Loc related paths
SWE_PRO_ISSUES = DATA_DIR + "/SWE-Pro-Loc/issues.json"
SWE_PRO_SAMPLED_ISSUE_IDS = DATA_DIR + "/SWE-Pro-Loc/sampled_issue_ids.json"
SWE_PRO_RAW_REPO_PATH = "YOUR_SWE_PRO_CLONED_REPO_PATH"  # Replace with your actual path
SWE_PRO_WORKSPACE = DATA_DIR + "SWE-Pro-Loc/workspace"

# Tree-sitter language library build directory
BUILD_DIR = ROOT_DIR + "/Code_and_Dataset/code/Offline/Term_Extraction_and_Enrichment/term_extraction/parser/build"
