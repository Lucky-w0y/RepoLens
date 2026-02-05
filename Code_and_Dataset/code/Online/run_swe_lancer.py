from tqdm import tqdm
from common.utils import get_issue_ids
from Issue_Specific_Term_Retrieval.extract_noun_from_issue import extract_nouns_from_issue, save_issue_nouns
from Issue_Specific_Term_Retrieval.match_noun_term import nouns_match
from Issue_Specific_Term_Retrieval.enrich_noun_term import noun_explanation_and_summary
from Concern_Clustering_and_Ranking.pre_cluster import noun_pre_cluster
from Concern_Clustering_and_Ranking.generate_concerns import concern_cluster
from Concern_Clustering_and_Ranking.sort_concerns import concern_rank_by_embedding_similarity

def run_swe_lancer_issue():
    """
    Run complete SWE-Lancer online processing pipeline
    """
    issue_ids = get_issue_ids()

    for issue_id in tqdm(issue_ids):
        issue_nouns_info = extract_nouns_from_issue(issue_id, benchmark="swe_lancer")
        
        save_issue_nouns(issue_nouns_info, issue_id, benchmark="swe_lancer")
        
        nouns_match(issue_id, issue_nouns_info, benchmark="swe_lancer")
        
        noun_explanation_and_summary(issue_id, issue_nouns_info, benchmark="swe_lancer")
        
        noun_pre_cluster(issue_id, issue_nouns_info, benchmark="swe_lancer")
        
        concern_cluster(issue_id, issue_nouns_info, benchmark="swe_lancer")
        
        concern_rank_by_embedding_similarity(issue_id, issue_nouns_info, benchmark="swe_lancer")


if __name__ == "__main__":
    run_swe_lancer_issue()
