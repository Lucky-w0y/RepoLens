"""
Term Extraction Module

This module provides functionality for extracting and analyzing code terms,
including functions, identifiers, and nouns from code repositories.

Main components:
- extract_functions_and_identifiers: Extract and filter functions and identifiers from code
- extract_noun_terms: Extract noun terms from identifiers using NLP techniques
"""

from .extract_functions_and_identifiers import (
    extract_functions,
    filter_functions,
    extract_words,
    get_all_code_files,
    parse_file,
    parse_code,
    extract_functions_from_node,
    extract_variables_from_node
)
from .extract_noun_terms import extract_nouns

__all__ = [
    'extract_functions',
    'filter_functions',
    'extract_words',
    'extract_nouns',
    'get_all_code_files',
    'parse_file',
    'parse_code',
    'extract_functions_from_node',
    'extract_variables_from_node'
]
