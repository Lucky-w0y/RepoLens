import os
import json
import time
from tqdm import tqdm
from common.utils import get_json_data, query_llm, extract_json_data_in_llm_answer
from common.prompts import prompt_function_noun_analysis
from definitions import DATA_DIR

processed_data = []


def noun_explanation_and_summary(issue_id, issue_nouns_info, benchmark="swe_lancer"):
    """
    Enrich noun terms with expanded names, definitions, and functionality descriptions
    
    Args:
        issue_id: Issue ID (integer for SWE-Lancer, string for SWE-bench Pro)
        issue_nouns_info: List of noun information dictionaries
        benchmark: Benchmark type ("swe_lancer" or "swe_pro")
    """
    for issue_noun in issue_nouns_info:
        noun = issue_noun['noun']
        joined_noun = "_".join(noun.split())
        
        if benchmark == "swe_lancer":
            benchmark_dir = "SWE-Lancer-Loc"
        else:
            benchmark_dir = "SWE-Pro-Loc"
        
        issue_repo_noun_path = DATA_DIR + f"/{benchmark_dir}/issue_repo_nouns/{issue_id}/{joined_noun}_nouns_info.json"
        output_path = DATA_DIR + f"/{benchmark_dir}/issue_repo_nouns/{issue_id}/{joined_noun}_nouns_info.json"
        
        result = []
        
        if os.path.exists(issue_repo_noun_path):
            issue_repo_noun_data = get_json_data(issue_repo_noun_path)
            
            for noun_data in tqdm(issue_repo_noun_data, desc=f"Processing {joined_noun}"):
                noun = noun_data['noun']
                function_body = noun_data['function_body']
                temp = noun_data
                
                is_processed = 0
                for p_d in processed_data:
                    if p_d['noun'] == noun and p_d['function_body'] == function_body:
                        temp['noun_expanded_name'] = p_d['output']['noun_expanded_name']
                        temp['noun_definition'] = p_d['output']['noun_definition']
                        temp['noun_functionality'] = p_d['output']['noun_functionality']
                        result.append(temp)
                        is_processed = 1
                        break
                
                if not is_processed:
                    prompt = prompt_function_noun_analysis(noun, noun_data['function_body'])
                    
                    max_retries = 100
                    retries = 0
                    while retries < max_retries:
                        try:
                            model_response = query_llm(prompt, "gpt-4o-mini")
                            noun_info = extract_json_data_in_llm_answer(model_response)
                            noun_info_dict = json.loads(noun_info)

                            new_p_d = {}
                            new_p_d['noun'] = noun
                            new_p_d['function_body'] = function_body
                            new_p_d['output'] = noun_info_dict
                            processed_data.append(new_p_d)

                            temp['noun_expanded_name'] = noun_info_dict['noun_expanded_name']
                            temp['noun_definition'] = noun_info_dict['noun_definition']
                            temp['noun_functionality'] = noun_info_dict['noun_functionality']
                            result.append(temp)
                            break
                        except Exception as e:
                            retries += 1
                            time.sleep(1)
                    else:
                        print(f"Failed on issue {issue_id} {joined_noun} after {max_retries} retries.")
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

    