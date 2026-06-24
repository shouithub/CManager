"""Merge RunPython functions into the squashed migration."""
import re, os, ast

BASE = r'D:\sync\Code\CManager\clubs\migrations'
SQUASHED = os.path.join(BASE, '0001_squashed_0013_formchannel_show_zip_download.py')

def extract_top_level_functions(source_code):
    """Extract all top-level function definitions from source code."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return {}
    
    funcs = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            lines = source_code.split('\n')
            # Get from start line to end line (1-indexed to 0-indexed)
            start = node.lineno - 1
            end = node.end_lineno  # end_lineno is 1-indexed, exclusive
            func_body = '\n'.join(lines[start:end])
            funcs[node.name] = func_body
    return funcs


def find_dependencies(func_body, all_funcs_in_file):
    """Find which other functions from the same file are called."""
    deps = set()
    for name in all_funcs_in_file:
        if name != func_body and re.search(rf'\b{re.escape(name)}\b', func_body):
            deps.add(name)
    return deps


def main():
    # Read squashed file
    with open(SQUASHED, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all unique (file, func) RunPython references
    pattern = r'code=clubs\.migrations\.(\d{4}_\w+)\.(\w+)'
    refs = set(re.findall(pattern, content))
    
    # Also check reverse_code
    pattern2 = r'reverse_code=clubs\.migrations\.(\d{4}_\w+)\.(\w+)'
    refs2 = set(re.findall(pattern2, content))
    refs = refs | refs2

    print(f"Found {len(refs)} unique function references:")
    for fname, func in sorted(refs):
        print(f"  {fname}.{func}")

    # Extract all functions from each referenced migration file
    all_funcs = {}  # (fname, func) -> source code
    
    for fname, func in refs:
        filepath = os.path.join(BASE, fname + '.py')
        if not os.path.exists(filepath):
            print(f"WARN: {filepath} not found, skipping")
            continue
        
        with open(filepath, 'r', encoding='utf-8') as f:
            src = f.read()
        
        extracted = extract_top_level_functions(src)
        
        # Get the target function
        if func in extracted:
            all_funcs[(fname, func)] = extracted[func]
            print(f"  OK: {fname}.{func}")
        else:
            print(f"  MISS: {fname}.{func} not found in file")

    # Build the list of all functions to inline (with dependencies)
    to_inline = {}  # unique_name -> source_code
    
    for (fname, func), source in all_funcs.items():
        unique_name = f'{func}__from_{fname}'
        to_inline[unique_name] = source

    # Now build new content:
    # 1. Imports + comment block (keep as-is until we hit the class Migration line)
    # 2. Insert all inlined functions
    # 3. Rest of the file with updated references
    
    # Find insertion point: right before "class Migration"
    class_match = re.search(r'\nclass Migration\(', content)
    if not class_match:
        print("ERROR: Could not find 'class Migration' in squashed file")
        return
    
    insert_pos = class_match.start()
    before = content[:insert_pos]
    after = content[insert_pos:]

    # Build functions block
    funcs_block = []
    funcs_block.append('\n# === Inlined RunPython functions from squashed migrations ===\n')
    for unique_name in sorted(to_inline.keys()):
        source = to_inline[unique_name]
        funcs_block.append(source)
        funcs_block.append('\n')
    
    funcs_text = '\n'.join(funcs_block)
    
    # Replace all clubs.migrations.XXXX.func references with local names
    updated_after = after
    for (fname, func) in sorted(refs, reverse=True):
        unique_name = f'{func}__from_{fname}'
        old_ref = f'clubs.migrations.{fname}.{func}'
        updated_after = updated_after.replace(old_ref, unique_name)
    
    # Also remove the "Functions from the following migrations need manual copying" comment block
    comment_pattern = r'# Functions from the following migrations need manual copying\.\n(?:# .*\n)*'
    before = re.sub(comment_pattern, '', before)

    new_content = before + funcs_text + updated_after

    # Write output
    output_path = os.path.join(BASE, '0001_squashed_merged.py')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f'\nWritten merged migration to: {output_path}')
    print(f'Total size: {len(new_content)} chars')

if __name__ == '__main__':
    main()
