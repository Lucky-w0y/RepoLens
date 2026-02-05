"""
Tree-sitter Language Library Builder

This script builds language-specific parser libraries for tree-sitter,
enabling AST parsing for multiple programming languages.

Usage:
    python build_library.py
"""

from tree_sitter import Language
from definitions import ROOT_DIR
import os

def build_library():
    """
    Build all required tree-sitter language libraries
    
    Builds libraries for:
    - Python
    - JavaScript
    - TypeScript (including TSX)
    - Go
    - C
    """
    parsers_dir = ROOT_DIR + '/data/parsers'
    
    python_parser = parsers_dir + '/tree-sitter-python'
    if os.path.exists(python_parser):
        print("Building Python language library...")
        Language.build_library(
            'build/python-languages.so',
            [python_parser]
        )
        print("Python language library built successfully")
    else:
        print(f"Warning: Python parser not found at {python_parser}")
    
    js_parser = parsers_dir + '/tree-sitter-javascript'
    if os.path.exists(js_parser):
        print("Building JavaScript language library...")
        Language.build_library(
            'build/js-languages.so',
            [js_parser]
        )
        print("JavaScript language library built successfully")
    else:
        print(f"Warning: JavaScript parser not found at {js_parser}")
    
    ts_parser = parsers_dir + '/tree-sitter-typescript/typescript'
    tsx_parser = parsers_dir + '/tree-sitter-typescript/tsx'
    if os.path.exists(ts_parser) and os.path.exists(tsx_parser):
        print("Building TypeScript language library...")
        Language.build_library(
            'build/my-languages.so',
            [ts_parser, tsx_parser]
        )
        print("TypeScript language library built successfully")
    else:
        print("Warning: TypeScript parser not found")
    
    go_parser = parsers_dir + '/tree-sitter-go'
    if os.path.exists(go_parser):
        print("Building Go language library...")
        Language.build_library(
           'build/go-languages.so',
            [go_parser]
        )
        print("Go language library built successfully")
    else:
        print(f"Info: Go parser not found at {go_parser}, download tree-sitter-go if needed")
    
    c_parser = parsers_dir + '/tree-sitter-c'
    if os.path.exists(c_parser):
        print("Building C language library...")
        Language.build_library(
            'build/c-languages.so',
            [c_parser]
        )
        print("C language library built successfully")
    else:
        print(f"Info: C parser not found at {c_parser}, download tree-sitter-c if needed")


if __name__ == "__main__":
    build_library()
