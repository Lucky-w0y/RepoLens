# RepoLens

This is the replication package for ISSTA submission #856, titled *From Concepts to Clues: Abstracting Conceptual Knowledge for Issue Localization in Software Repositories*.

## Description of each folder

- **Code and Dataset**: the folder containing the source code and dataset of RepoLens.  
- **RQ1_Effectiveness**: the folder containing the experimental results and logs for RQ1, which evaluates the effectiveness of RepoLens compared to baseline approaches.  
- **RQ2_Generalizability**: the folder containing the experimental results and logs for RQ2, which assess the generalizability of RepoLens across different models.  
- **RQ3_Ablation_Study**: the folder containing the experimental results and logs for RQ3, which analyze the necessity of Concerns through ablation studies.  
- **RQ4_Reliability_of_Concerns**: the folder containing the evaluation materials and results for RQ4, which investigate the reliability and quality of the generated concerns using human assessment.

## Key Files

- **definitions.py**: the configuration file that defines key parameters and paths used across the RepoLens implementation.  
- **requirements.txt**: the dependency file that lists all the Python packages required to run RepoLens. You can install them with:  
  ```bash
  pip install -r requirements.txt

## Implementation Details

The implementation of RepoLens is organized into three stages: **Common utilities**, **Offline knowledge construction**, and **Online concern-enhanced localization**.  

1. **Common Utilities**  
   - `Common/prompts.py`: defines prompt templates for LLM-based tasks such as term enrichment, concern generation, and ranking.  
   - `Common/utils.py`: provides shared helper functions for file processing, data handling, and general utilities.  

2. **Offline Knowledge Construction**  
   - `Offline/run_swe_lancer.py`: runs the complete offline preprocessing pipeline for the SWE-Lancer benchmark.  
   - `Offline/run_swe_pro.py`: runs the complete offline preprocessing pipeline for the SWE-Pro benchmark.  
   - `Offline/Term_Extraction_and_Enrichment/term_extraction/extract_functions_and_identifiers.py`: extracts functions and identifiers from source code.  
   - `Offline/Term_Extraction_and_Enrichment/term_extraction/extract_noun_terms.py`: extracts noun terms from identifiers.  
   - `Offline/Term_Extraction_and_Enrichment/term_enrichment/enrich_noun_term.py`: enriches extracted noun terms with semantic information.  
   - `Offline/Term_Extraction_and_Enrichment/term_extraction/parser/build_library.py`: builds parsing support for structured code analysis.  

3. **Online Concern-Enhanced Localization**

   **Issue-Specific Term Retrieval**  
   - `Online/Issue-Specific_Term_Retrieval/extract_noun_from_issue.py`: extracts noun terms from issue titles and descriptions.  
   - `Online/Issue-Specific_Term_Retrieval/match_noun_term.py`: matches issue terms against repository terms.  
   - `Online/Issue-Specific_Term_Retrieval/enrich_noun_term.py`: refines and enriches matched terms with semantic information.  

   **Concern Clustering and Ranking**  
   - `Online/Concern_Clustering_and_Ranking/pre_cluster.py`: performs pre-clustering of related terms.  
   - `Online/Concern_Clustering_and_Ranking/generate_concerns.py`: generates concerns from clustered term groups.  
   - `Online/Concern_Clustering_and_Ranking/sort_concerns.py`: ranks concerns based on their relevance to the issue.  

   **Concern-Enhanced Issue Localization**  
   - `Online/Concern-Enhanced_Issue_Localization/AgentLess_with_Concern/`: scripts for running concern-enhanced localization with the AgentLess framework.  
     - `agentless_handle_file_level_with_concern.py`: handles file-level localization using concerns.  
     - `agentless_handle_method_level.py`: handles method-level localization using concerns.  
   - `Online/Concern-Enhanced_Issue_Localization/OpenHands_with_Concern/`: integration with the OpenHands framework.  
     - `run.py`: runs concern-enhanced localization with OpenHands.  
     - `config.toml`, `pyproject.toml`: configuration files.  
     - `trajectory/`, `workspace/`: logs and intermediate states during runs.  
   - `Online/Concern-Enhanced_Issue_Localization/mini-SWE-agent_with_Concern/`: integration with the mini-SWE-agent framework.  
     - `run.py`: runs concern-enhanced localization with mini-SWE-agent.  
     - `config.yaml`: configuration file.  
     - `trajectory/`, `workspace/`: logs and intermediate states during runs.  

## Dataset

The `dataset/` folder contains the data used in RepoLens experiments.  
The data are organized by benchmark, with each dataset containing the intermediate artifacts and ground-truth annotations required for concern construction and issue localization.

### SWE-Lancer-Loc/
Data for experiments on the SWE-Lancer-Loc benchmark.

- **concerns/**: the constructed top-10 concerns generated for each issue.  
- **extracted_terms/**: the extracted terms from source code, including functions, identifiers, and noun terms.  
- **issue_noun_terms/**: the noun terms extracted from issue titles and descriptions.  
- **issue_repo_nouns/**: the matched noun terms between issues and repository code.  
- **issues/**: the issue descriptions used in the experiments.  
- **pre_cluster_result/**: the intermediate clustering results for concern construction.  
- **gold.json**: the ground-truth annotations linking issues to relevant files/functions.  
- **valid_issue_ids.txt**: the list of issue IDs that are valid and included in the evaluation.  
- **workspace/**: intermediate runtime artifacts and cached results produced during localization.  

---

### SWE-Pro-Loc/
Data for experiments on the SWE-Pro-Loc benchmark.

- **concerns/**: the constructed top-10 concerns generated for each issue.  
- **extracted_terms/**: the extracted terms from source code, including functions, identifiers, and noun terms.  
- **issue_noun_terms/**: the noun terms extracted from issue descriptions.  
- **issue_repo_nouns/**: the matched noun terms between issues and repository code.  
- **issues.json**: the issue instances used in the experiments.  
- **pre_cluster_result/**: the intermediate clustering results for concern construction.  
- **gold.json**: the ground-truth annotations linking issues to relevant files/functions.  
- **sampled_issue_ids.json**: the sampled issue IDs selected for evaluation.  
- **workspace/**: intermediate runtime artifacts and cached results produced during localization.  
