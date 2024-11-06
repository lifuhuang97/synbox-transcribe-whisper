import os
import ast
import sys
from pathlib import Path


def is_local_module(module_name, directory):
    """Check if the module is a local directory or .py file."""
    module_path = Path(directory) / module_name
    return (
        module_path.is_dir()
        or module_path.with_suffix(".py").is_file()
        or module_name.startswith(".")
    )


def find_imports(file_path):
    """Parse Python file and extract all imports."""
    with open(file_path, "r", encoding="utf-8") as file:
        try:
            tree = ast.parse(file.read())
        except SyntaxError:
            print(f"Could not parse {file_path} - syntax error in Python code")
            return set()
        except (UnicodeDecodeError, IOError) as e:
            print(f"Could not read {file_path}: {e}")
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


def filter_modules(imports, directory):
    """Remove standard library modules and local modules from the import list."""
    stdlib_modules = sys.stdlib_module_names
    external_imports = set()
    local_modules = set()

    for imp in imports:
        if imp not in stdlib_modules:
            if is_local_module(imp, directory):
                local_modules.add(imp)
            else:
                external_imports.add(imp)

    return external_imports, local_modules


if __name__ == "__main__":
    directory = "."  # Current directory
    all_imports = scan_directory(directory)
    external_imports, local_modules = filter_modules(all_imports, directory)

    print("\nFound external dependencies:")
    for imp in sorted(external_imports):
        print(imp)

    print("\nLocal modules:")
    for imp in sorted(local_modules):
        print(imp)

    print("\nInstall command:")
    # Map some common package name differences
    package_map = {
        "dotenv": "python-dotenv",
    }

    packages = [package_map.get(imp, imp) for imp in external_imports]
    print(f"pip install {' '.join(packages)}")
