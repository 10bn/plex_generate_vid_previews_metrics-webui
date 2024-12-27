"""
merge.py

This script merges all files from the current repository into a single file named 'merged_repository.txt'.
At the beginning of the merged file, it includes the file and folder structure of the repository.
Each file's content is preceded by a header containing its relative path.

Folders specified in the EXCLUDED_DIRS list (e.g., '.git', '.build') will be excluded from the merge.

Usage:
    python merge.py
"""

import os

# List of directories to exclude from the merge
EXCLUDED_DIRS = {'.git', '.build', 'merge.py'}  # Use a set for faster lookups

def get_file_structure(root_dir=".", excluded_dirs=None):
    """
    Traverse the directory tree and collect the relative paths of all files,
    excluding specified directories.

    Args:
        root_dir (str): The root directory to start traversal.
        excluded_dirs (set): A set of directory names to exclude.

    Returns:
        list: A list of relative file paths.
    """
    if excluded_dirs is None:
        excluded_dirs = set()

    structure = []
    for root, dirs, files in os.walk(root_dir):
        # Modify 'dirs' in-place to exclude specified directories
        dirs[:] = [d for d in dirs if d not in excluded_dirs]

        for file in files:
            # Skip the output file to prevent recursion
            if file == "merged_repository.txt":
                continue
            filepath = os.path.join(root, file)
            # Normalize the path to use forward slashes
            normalized_path = os.path.normpath(filepath).replace(os.sep, "/")
            structure.append(normalized_path)
    return structure

def merge_files(file_structure, output_file="merged_repository.txt"):
    """
    Merge the contents of all files into a single output file with headers.

    Args:
        file_structure (list): A list of file paths to merge.
        output_file (str): The name of the output merged file.
    """
    with open(output_file, "w", encoding="utf-8") as outfile:
        # Write the file and folder structure
        outfile.write("File and Folder Structure:\n")
        outfile.write("===========================\n")
        for filepath in file_structure:
            outfile.write(f"{filepath}\n")
        outfile.write("\n\n")

        # Write each file's content with a header
        for filepath in file_structure:
            outfile.write(f"===== {filepath} =====\n")
            try:
                with open(filepath, "r", encoding="utf-8") as infile:
                    content = infile.read()
            except UnicodeDecodeError:
                # If the file is binary or has a different encoding, read in binary mode
                with open(filepath, "rb") as infile:
                    content = infile.read()
                    # Represent binary content in a readable format
                    content = content.decode("utf-8", errors="replace")
            outfile.write(content)
            outfile.write("\n\n")  # Add spacing between files

def main():
    # Define the output file name
    output_filename = "merged_repository.txt"

    # Get the file structure, excluding specified directories
    file_structure = get_file_structure(excluded_dirs=EXCLUDED_DIRS)

    # Merge the files into the output file
    merge_files(file_structure, output_file=output_filename)

    print(f"All files have been merged into '{output_filename}'.")
    if EXCLUDED_DIRS:
        excluded = ", ".join(EXCLUDED_DIRS)
        print(f"Excluded directories: {excluded}")

if __name__ == "__main__":
    main()
