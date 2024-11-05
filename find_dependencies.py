import os
import ast
import sys
from pathlib import Path


def find_imports(file_path):
    """Parse Python file and extract all imports."""
    with open(file_path, "r", encoding="utf-8") as file:
        try:
            tree = ast.parse(file.read())
        except:
            print(f"Could not parse {file_path}")
            return set()

    imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                imports.add(name.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                imports.add(node.module.split(".")[0])

    return imports


def scan_directory(directory):
    """Scan directory recursively for Python files and collect all imports."""
    all_imports = set()

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                if "venv" not in file_path and "env" not in file_path:
                    imports = find_imports(file_path)
                    all_imports.update(imports)

    return all_imports


def filter_stdlib_modules(imports):
    """Remove standard library modules from the import list."""
    stdlib_modules = sys.stdlib_module_names
    return {imp for imp in imports if imp not in stdlib_modules}


if __name__ == "__main__":
    directory = "."  # Current directory
    all_imports = scan_directory(directory)
    external_imports = filter_stdlib_modules(all_imports)

    print("\nFound external dependencies:")
    for imp in sorted(external_imports):
        print(imp)
