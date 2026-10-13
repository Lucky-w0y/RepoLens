from tqdm import tqdm
from common.utils import get_swe_pro_sampled_issues
from Issue_Specific_Term_Retrieval.extract_noun_from_issue import extract_nouns_from_issue, save_issue_nouns
from Issue_Specific_Term_Retrieval.match_noun_term import nouns_match
from Issue_Specific_Term_Retrieval.enrich_noun_term import noun_explanation_and_summary
from Concern_Clustering_and_Ranking.pre_cluster import noun_pre_cluster
from Concern_Clustering_and_Ranking.generate_concerns import concern_cluster
from Concern_Clustering_and_Ranking.sort_concerns import concern_rank_by_embedding_similarity
from definitions import DATA_DIR


def run_swe_bench_pro_issue():
    """
    Run complete SWE-bench Pro online processing pipeline
    """
    swe_pro_sampled_issues = get_swe_pro_sampled_issues()

    for issue in tqdm(swe_pro_sampled_issues):
        issue_id = issue['instance_id']
        
        issue_nouns_info = extract_nouns_from_issue(issue, benchmark="swe_pro")
        
        save_issue_nouns(issue_nouns_info, issue_id, benchmark="swe_pro")
        
        nouns_match(issue_id, issue_nouns_info, benchmark="swe_pro")
        
        noun_explanation_and_summary(issue_id, issue_nouns_info, benchmark="swe_pro")
        
        noun_pre_cluster(issue_id, issue_nouns_info, benchmark="swe_pro")
        
        concern_cluster(issue_id, issue_nouns_info, benchmark="swe_pro")
        
        concern_rank_by_embedding_similarity(issue_id, issue_nouns_info, benchmark="swe_pro")


if __name__ == "__main__":
    run_swe_bench_pro_issue()
