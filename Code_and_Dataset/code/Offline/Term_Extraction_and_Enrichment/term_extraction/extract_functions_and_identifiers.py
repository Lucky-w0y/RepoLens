import os
import re
import warnings
from tree_sitter import Language, Parser
from definitions import BUILD_DIR

warnings.simplefilter('ignore', FutureWarning)

LANGUAGES = {}
LANGUAGE_MAP = {}

python_lib = os.path.join(BUILD_DIR, "python-languages.so")
if os.path.exists(python_lib):
    LANGUAGES['python'] = Language(python_lib, 'python')
    LANGUAGE_MAP['.py'] = 'python'

js_lib = os.path.join(BUILD_DIR, "js-languages.so")
if os.path.exists(js_lib):
    LANGUAGES['javascript'] = Language(js_lib, 'javascript')
    LANGUAGE_MAP['.js'] = 'javascript'

ts_lib = os.path.join(BUILD_DIR, "my-languages.so")
if os.path.exists(ts_lib):
    LANGUAGES['typescript'] = Language(ts_lib, 'typescript')
    LANGUAGES['tsx'] = Language(ts_lib, 'tsx')
    LANGUAGE_MAP['.ts'] = 'typescript'
    LANGUAGE_MAP['.tsx'] = 'tsx'

go_lib = os.path.join(BUILD_DIR, "go-languages.so")
if os.path.exists(go_lib):
    LANGUAGES['go'] = Language(go_lib, 'go')
    LANGUAGE_MAP['.go'] = 'go'

c_lib = os.path.join(BUILD_DIR, "c-languages.so")
if os.path.exists(c_lib):
    LANGUAGES['c'] = Language(c_lib, 'c')
    LANGUAGE_MAP['.c'] = 'c'

PYTHON_LANGUAGE = LANGUAGES.get('python', None)

PARSERS = {}


def get_parser(language):
    """Get or create parser for a language (reuse to avoid file descriptor exhaustion)"""
    if language not in PARSERS:
        parser = Parser()
        parser.set_language(language)
        PARSERS[language] = parser
    return PARSERS[language]


def read_file(file_path):
    """Read file content"""
    with open(file_path, "r", encoding="utf-8", errors='ignore') as file:
        return file.read()


def get_language_by_file(file_path):
    """Get language object by file extension"""
    file_ext = os.path.splitext(file_path)[1].lower()
    lang_name = LANGUAGE_MAP.get(file_ext)
    if lang_name and lang_name in LANGUAGES:
        return LANGUAGES[lang_name]
    return None


def get_all_code_files(directory):
    """
    Get all supported code files in the directory
    
    Args:
        directory: Code directory path
    
    Returns:
        list: List of code file paths
    """
    all_code_files = []
    supported_extensions = tuple(LANGUAGE_MAP.keys())
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(supported_extensions):
                file_path = os.path.join(root, file)
                all_code_files.append(file_path)
    
    return all_code_files


def parse_file(file_path):
    """
    Parse code file
    
    Args:
        file_path: File path
    
    Returns:
        tuple: (tree, code) Parse tree and code content
    """
    language = get_language_by_file(file_path)
    if language is None:
        file_ext = os.path.splitext(file_path)[1]
        raise ValueError(f"Unsupported file type: {file_ext}, file: {file_path}")
    
    parser = get_parser(language)
    code = read_file(file_path)
    tree = parser.parse(bytes(code, 'utf-8'))
    return tree, code


def parse_code(code, file_path=None, language_name=None):
    """
    Parse code string
    
    Args:
        code: Code string to parse
        file_path: File path (optional, for inferring language from extension)
        language_name: Language name (optional, e.g., 'python', 'javascript', 'go')
    
    Returns:
        tuple: (tree, code) Parse tree and code
    """
    language = None
    
    if language_name and language_name in LANGUAGES:
        language = LANGUAGES[language_name]
    elif file_path:
        language = get_language_by_file(file_path)
    
    if language is None:
        if PYTHON_LANGUAGE:
            language = PYTHON_LANGUAGE
        else:
            raise ValueError("Cannot determine code language, please provide file_path or language_name parameter")
    
    parser = get_parser(language)
    tree = parser.parse(bytes(code, 'utf-8'))
    return tree, code


def find_identifier_in_node(n):
    """Recursively find identifier node"""
    if n.type == 'identifier':
        return n
    for child in n.children:
        result = find_identifier_in_node(child)
        if result:
            return result
    return None


def extract_name_from_parent(node, code_bytes):
    """Extract function name from parent node, for functions assigned to variables (JavaScript/TypeScript)"""
    try:
        parent = node.parent
    except:
        return None
    
    if not parent:
        return None
    
    if parent.type in ['variable_declarator', 'lexical_declaration', 'variable_declaration']:
        name_node = parent.child_by_field_name("name")
        if name_node:
            if name_node.type == 'identifier':
                return code_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
            elif name_node.type in ['object_pattern', 'array_pattern']:
                identifier = find_identifier_in_node(name_node)
                if identifier:
                    return code_bytes[identifier.start_byte:identifier.end_byte].decode('utf-8')
    
    elif parent.type == 'assignment_expression':
        left_node = parent.child_by_field_name("left")
        if left_node and left_node.type in ['identifier', 'member_expression']:
            return code_bytes[left_node.start_byte:left_node.end_byte].decode('utf-8')
        
    elif parent.type in ['property', 'pair']:
        key_node = parent.child_by_field_name("key")
        if key_node:
            if key_node.type in ['property_identifier', 'identifier']:
                return code_bytes[key_node.start_byte:key_node.end_byte].decode('utf-8')
            elif key_node.type == 'string':
                key_text = code_bytes[key_node.start_byte:key_node.end_byte].decode('utf-8')
                return key_text.strip('"\'')
    
    return None


def extract_functions_from_node(file, node, code):
    """
    Recursively traverse AST and extract functions
    
    Args:
        file: File path
        node: AST node
        code: Code content
    
    Returns:
        list: Function list, each element contains file_path, function_name, function_body
    """
    functions = []
    code_bytes = code.encode('utf-8')
    
    function_node_types = [
        'function_definition',
        'function_declaration',
        'function_expression',
        'method_definition',
        'arrow_function',
        'method_declaration',
    ]
    
    if node.type in function_node_types:
        start_byte = node.start_byte
        end_byte = node.end_byte
        function_body = code_bytes[start_byte:end_byte].decode('utf-8')
        function_name = None
        
        if node.type == 'function_definition':
            name_node = node.child_by_field_name("name")
            if name_node:
                function_name = code_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
            else:
                declarator_node = node.child_by_field_name("declarator")
                if declarator_node:
                    identifier_node = find_identifier_in_node(declarator_node)
                    if identifier_node:
                        function_name = code_bytes[identifier_node.start_byte:identifier_node.end_byte].decode('utf-8')
        
        elif node.type == 'function_declaration':
            name_node = node.child_by_field_name("name")
            if name_node:
                function_name = code_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
            else:
                identifier_node = find_identifier_in_node(node)
                if identifier_node:
                    function_name = code_bytes[identifier_node.start_byte:identifier_node.end_byte].decode('utf-8')
        
        elif node.type == 'method_definition':
            name_node = node.child_by_field_name("name")
            if name_node:
                if name_node.type in ['property_identifier', 'identifier']:
                    function_name = code_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
                elif name_node.type == 'string':
                    name_text = code_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    function_name = name_text.strip('"\'')
        
        elif node.type == 'method_declaration':
            name_node = node.child_by_field_name("name")
            if name_node:
                function_name = code_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
            else:
                identifier_node = find_identifier_in_node(node)
                if identifier_node:
                    function_name = code_bytes[identifier_node.start_byte:identifier_node.end_byte].decode('utf-8')
        
        elif node.type in ['function_expression', 'arrow_function']:
            name_node = node.child_by_field_name("name")
            if name_node:
                function_name = code_bytes[name_node.start_byte:name_node.end_byte].decode('utf-8')
            else:
                function_name = extract_name_from_parent(node, code_bytes)
        
        if function_name:
            functions.append({
                'file_path': file,
                'function_name': function_name,
                'function_body': function_body
            })
    
    for child in node.children:
        functions.extend(extract_functions_from_node(file, child, code))
    
    return functions


def extract_variables_from_node(file, node, code):
    """
    Recursively traverse AST and extract all variable identifiers
    
    Args:
        file: File path
        node: AST node
        code: Code content
    
    Returns:
        list: List of variable names
    """
    variables = []
    if node.type == "identifier":
        variable = code.encode('utf-8')[node.start_byte:node.end_byte].decode('utf-8')
        variables.append(variable)

    for child in node.children:
        variables.extend(extract_variables_from_node(file, child, code))
    
    return variables


def extract_functions(repo_dir):
    """
    Extract all functions from code repository
    
    Args:
        repo_dir: Code repository directory path
    
    Returns:
        list: Function list, each element contains:
            - file_path: File path
            - function_name: Function name
            - function_body: Function body code
    """
    all_code_files = get_all_code_files(repo_dir)
    print(f'Found {len(all_code_files)} code files')
    
    total_functions = []
    failed_files = []
    
    for file in all_code_files:
        tree = None
        try:
            tree, code = parse_file(file)
            root_node = tree.root_node
            functions = extract_functions_from_node(file, root_node, code)
            total_functions.extend(functions)
        except Exception as e:
            failed_files.append((file, str(e)))
            print(f"Failed to parse file: {file}, error: {e}")
        finally:
            if tree is not None:
                del tree
    
    if failed_files:
        print(f"Total {len(failed_files)} files failed to parse")
    
    print(f"Extracted {len(total_functions)} functions from the project.")
    return total_functions


def filter_functions(functions):
    """
    Filter out unwanted functions including test functions and functions from specific file types
    
    This function filters:
    - Test functions (containing 'test', 'Test', or 'TEST' in file path or function name)
    - Functions from .jsx files
    - Functions from .xx.js files (e.g., .test.js, .spec.js)
    - Functions from _generated.go and _mock.go files
    - Functions from .xx.go files (e.g., .test.go, .gen.go)
    
    Args:
        functions: Function list, each element contains file_path, function_name, function_body
    
    Returns:
        list: Filtered function list
    """
    filtered_functions = []
    test_keywords = ['test', 'Test', 'TEST']
    
    def should_filter_file(file_path):
        """Check if file should be filtered"""
        file_name = os.path.basename(file_path)
        
        if file_path.endswith('.jsx'):
            return True
        
        if file_path.endswith('.js'):
            if re.search(r'\.[^.]+\.js$', file_name):
                return True
        
        if file_name.endswith('_generated.go') or file_name.endswith('_mock.go'):
            return True
        
        if file_path.endswith('.go'):
            if re.search(r'\.[^.]+\.go$', file_name):
                return True
        
        return False
    
    for func in functions:
        file_path = func['file_path']
        function_name = func['function_name']
        
        if should_filter_file(file_path):
            continue
        
        should_filter = any(
            keyword in file_path or keyword in function_name 
            for keyword in test_keywords
        )
        
        if not should_filter:
            filtered_functions.append(func)
    
    return filtered_functions


def extract_words(functions):
    """
    Extract identifiers (words) from function list
    
    Args:
        functions: Function list, each element contains file_path, function_name, function_body
    
    Returns:
        list: Function list with words, each element contains:
            - file_path: File path
            - function_name: Function name
            - function_body: Function body code
            - words: Identifier list (function names and variable names)
    """
    result = []
    
    for func in functions:
        temp = {
            'file_path': func['file_path'],
            'function_name': func['function_name'],
            'function_body': func['function_body'],
            'words': []
        }
        
        file_path = func['file_path']
        function_name = func['function_name']
        function_body = func['function_body']
        
        try:
            tree, code = parse_code(function_body, file_path=file_path)
            root_node = tree.root_node
            variables = extract_variables_from_node(file_path, root_node, code)
            
            temp['words'].append(function_name)
            for var in variables:
                if var not in temp['words']:
                    temp['words'].append(var)
        except Exception as e:
            print(f"Failed to extract identifiers: {file_path}, function: {function_name}, error: {e}")
            temp['words'].append(function_name)
        
        result.append(temp)
    
    return result
