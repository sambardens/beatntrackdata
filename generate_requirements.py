import os
import importlib.metadata
import importlib.util
import subprocess
from typing import Set, List

def find_python_files(directory: str) -> Set[str]:
    """Find all Python files in the project"""
    python_files = set()
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.add(os.path.join(root, file))
    return python_files

def get_imports_from_file(file_path: str) -> Set[str]:
    """Extract import statements from a Python file"""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('import ') or line.startswith('from '):
                    # Extract package name (first part of import)
                    if line.startswith('from '):
                        package = line.split()[1].split('.')[0]
                    else:
                        package = line.split()[1].split('.')[0]
                    if package not in ('os', 'sys', 'typing', 'datetime', 'json', 're'):
                        imports.add(package)
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return imports

def get_installed_versions(packages: Set[str]) -> List[str]:
    """Get installed versions of packages"""
    requirements = []
    for package in packages:
        try:
            version = importlib.metadata.version(package)
            requirements.append(f"{package}=={version}")
        except importlib.metadata.PackageNotFoundError:
            print(f"Warning: Package '{package}' not found in installed packages")
            continue
    return requirements

def main():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    all_imports = set()
    
    # Find all imports in your Python files
    print("Scanning Python files...")
    python_files = find_python_files(project_dir)
    for py_file in python_files:
        imports = get_imports_from_file(py_file)
        all_imports.update(imports)
    
    print(f"Found {len(all_imports)} unique imports")
    
    # Get versions of installed packages
    requirements = get_installed_versions(all_imports)
    
    # Write to requirements.txt
    output_file = os.path.join(project_dir, 'requirements.txt')
    with open(output_file, 'w') as f:
        f.write("# Generated from actual project usage\n")
        f.write("# Date: " + importlib.metadata.datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n\n")
        f.write("\n".join(sorted(requirements)))
    
    print(f"\nGenerated requirements.txt with {len(requirements)} packages")
    print(f"Output file: {output_file}")

if __name__ == "__main__":
    main()