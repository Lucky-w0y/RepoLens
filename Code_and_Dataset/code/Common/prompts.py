"""
Prompts Module for LLM-based Analysis

This module contains prompt templates for various LLM-based analysis tasks including:
- Function-noun analysis with code snippet extraction
- Noun extraction from issue titles
- Concern clustering for noun terms
- Concern sorting based on issue relevance
"""

def prompt_function_noun_analysis(noun, function, extract_code_snippets=True):
    """Perform Noun Enrich"""
    prompt = f'''You are a senior software engineer. Analyze the give noun term (a noun word or phrase) and its related TypeScript or TSX function code.

## Instructions
Carefully analyze the code and perform the following tasks:
1. **Name Expansion**  
   - Determine whether the given noun term is an abbreviation.  
   - If it is, expand it into its full form based on the code context.  
   - After obtaining the full form, add necessary modifiers or qualifiers based on the context to make the noun term more specific and precise.  
   - The final result must remain a concrete noun term (not a descriptive sentence), and use spaces between words within the term.  

2. **Definition Generation**  
   - Provide a concise natural language sentence that defines what the given term **is**.  
   - The definition should capture the intrinsic meaning of the noun term, independent of how it is used in the code.  

3. **Term-Centric Functionality Summarization**  
   - Analyze the functional semantics/responsiblities or business logic in the given function that specifically relates to the noun term.  
   - Focus only on the part of the logic that is relevant to the noun term, **not the overall functionality of the entire function**.  

4. **Reference Code Extraction**  
   - Identify and extract 2-5 lines of code from the function that are **directly** related to the term-centric functionality.  

## Noun Term
{noun}

## Function Code
{function}

## Output Format
- Return the result as a JSON dictionary with the following keys:
    - noun_expanded_name: The expanded and contextually refined version of the original noun term (still a noun word or phrase).  
    - noun_definition: A natural language sentence defining what this noun term is.  
    - noun_functionality: A brief description of the functional semantics or business logic related to the noun term.  
    - noun_reference_code: 2-5 lines of code related to the term-centric functionality.  
- Do not include any explanations or extra text, return only the JSON dictionary.
'''
    return prompt


def prompt_extract_nouns_from_issue_title(issue_title):
    """Extract noun terms from an issue title"""
    prompt = f'''You are a professional language analyst. Given an Issue title, your task is to extract **all nouns or noun phrases**(both singular and plural) from it.
Requirements:
1. Only extract the nouns or noun phrases explicitly appear in the issue title.
2. A noun phrase should include its attached modifiers such as compound nouns, but **must not include**:
   - Adverbs (e.g., "recently", "more", "automatically")
   - Adjectives (e.g., "new", "primary", "random")
   - Numerals (e.g., "a", "first", "two")
3. Even if a noun appears inside a prepositional phrase, it must still be extracted if it satisfies all other rules.
4. Do not include any punctuation in the noun phrases or in the JSON output.
5. **Must** convert plural nouns to their singular form, but do not remove modifiers, determiners, or adjectives from noun phrases.
6. Return the result as a JSON-formatted list of strings.
Issue Title:
{issue_title}
'''
    return prompt


def prompt_concern_clustering(noun, noun_functionalities):
    """ Cluster atomic functionalities into concerns for a noun term """
    prompt = f'''You are a senior software engineer. You are given a list of atomic functionalities related to the noun term "{noun}", each with a unique ID. These functionalities are extracted from scattered places within the code repository, but they may be semantically related or associated at a higher concern level.

## Definition of Concern
A **Concern** is a cohesive set of functionalities in code that are conceptually related to a specific term (entity, object, or domain concept).
- These functionalities may be scattered across different parts of the codebase, but together they are concerned with a single responsibility or area of interest.
- A Concern can be composed of atomic operations and low-level details, which, when aggregated, form a higher-level functional semantics or business logic tied to that term.

## Instructions
Carefully analyze the conceptual and semantic relationships and semantic connections among the given atomic functionalities, and cluster them to identify which functionalities can be aggregated to form a cohesive Concern related to the given noun term.

**Notes:**
- Each functionality can appear in multiple concerns (i.e., it can be reused).
- The clustering should be based on genuine conceptual connections, not subjective speculation.

## Noun Term
{noun}

## Atomic Functionalities
{noun_functionalities}

## Output Format
- Return a JSON list, where each item represents one identified concern, containing the following fields:
    - ids: a list of functionality IDs that constitute the concern.
    - concern_summary: a description of the concern, focusing solely on the functional semantics achieved by combining these functionalities (no code-level details are required).
- Do not include any explanations or extra text, return only the JSON list.
'''
    return prompt


def prompt_concern_sorting(issue_title, issue_body, concern_list):
    """ Sort concerns based on issue relevance """
    prompt = f"""You are a senior software engineer. Analyze the given GitHub Issue (including title and body) along with the list of concerns related to the noun terms mentioned in the issue.

## Definition of Concern
A **Concern** is a cohesive set of functionalities in code that are conceptually related to a specific term (entity, object, or domain concept).
- These functionalities may be scattered across different parts of the codebase, but together they are concerned with a single responsibility or area of interest.
- A Concern can be composed of atomic operations and low-level details, which, when aggregated, form a higher-level functional semantics or business logic tied to that term.

## Format of Concern
Each concern in the list is an object with the following structure:
- concern_summary: a description of the concern, summarizing the functional semantics or business logic it represents.
- related_code: a list of code snippets related to this concern, where each item contains:
    - code_location: the file path and function name where the code is located (format: file_path:function_name).
    - reference_code: the actual code snippets relevant to this concern.

## Instructions
Identify the top 10 concerns that are most likely to match the root cause of this issue.
- Thoroughly analyze the issue title and body to infer potential root causes as comprehensively as posible.
- Compare these potential root causes with the semantics and responsibility of each concern.
- Rank the selected concerns from most to least relevant, with the first item being the most relevant.
    
## Issue Title
{issue_title}

## Issue Body
{issue_body}

## Concern List
{concern_list}

## Output Format
- Return a JSON list of 10 strings, where each string is the `concern_summary` of a selected concern.
- Do not include any explanations or extra text, return only the JSON list.
"""
    return prompt
