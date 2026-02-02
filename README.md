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

The implementation of RepoLens follows the main steps of the proposed approach. Each step corresponds to specific modules and scripts:

1. **Term Extraction and Enrichment**  
   - `Term_Extraction_and_Enrichment/term_extraction/extract_functions_and_identifiers.py`: extracts functions, identifiers from source code.  
   - `Term_Extraction_and_Enrichment/term_extraction/extract_noun_terms.py`: extracts noun terms from identifiers.  
   - `Term_Extraction_and_Enrichment/term_enrichment/enrich_noun_term.py`: enriches extracted noun terms with semantic information.  

2. **Issue-Specific Term Retrieval**  
   - `Issue-Specific_Term_Retrieval/extract_noun_from_issue.py`: extracts noun terms from issue titles.  
   - `Issue-Specific_Term_Retrieval/match_noun_term.py`: matches issue terms against code terms.  

3. **Concern Clustering and Ranking**  
   - `Concern_Clustering_and_Ranking/pre_cluster.py`: performs pre-clustering of terms.
   - `Concern_Clustering_and_Ranking/generate_concerns.py`: generates concerns from pre clustered term  groups.  
   - `Concern_Clustering_and_Ranking/sort_concerns.py`: ranks concerns based on relevance to the issue.   

4. **Concern-Enhanced Issue Localization**  
   - `Concern-Enhanced_Issue_Localization/AgentLess_with_Concern/`: scripts for running concern-enhanced localization with the AgentLess framework.  
     - `agentless_handle_file_level_with_concern_v2.py`: handles file-level localization using concerns.  
     - `agentless_handle_method_level-conc.py`: handles method-level localization using concerns.   
   - `Concern-Enhanced_Issue_Localization/OpenHands_with_Concern/`: integration with the OpenHands framework.  
     - `run.py`: runs concern-enhanced localization with OpenHands.  
     - `config.toml`, `pyproject.toml`: configuration files.  
     - `trajectory/`, `workspace/`: logs and intermediate states during runs.  
   - `Concern-Enhanced_Issue_Localization/mini-SWE-agent_with_Concern/`: integration with the mini-SWE-agent framework.  
     - `run.py`: runs concern-enhanced localization with mini-SWE-agent.  
     - `config.yaml`: configuration file.  
     - `trajectory/`, `workspace/`: logs and intermediate states during runs.  

5. **Ground Truth Generation**  
   - `Groung_Truth_Generation/generate_gold_files.py`: generates file-level gold annotations for evaluation.  
   - `Groung_Truth_Generation/generate_gold_functions.py`: generates function-level gold annotations for evaluation. 


## Dataset

The `dataset/` folder contains the data used in RepoLens experiments:

- **concerns/**: the constructed top-10 concerns generated for each issue.  
- **extracted_terms/**: the extracted terms from source code, including functions, identifiers and noun terms.  
- **issue_repo_nouns/**: the matched noun terms between issues and repository code.  
- **issue_noun_terms/**: the noun terms extracted from issue titles.  
- **issues/**: the issue used in the experiments.  
- **pre_cluster_result/**: the intermediate clustering results for concern construction.  
- **gold.json**: the ground-truth annotations linking issues to relevant files/functions.  
- **valid_issue_ids.txt**: the list of issue IDs that are valid and included in the evaluation.  