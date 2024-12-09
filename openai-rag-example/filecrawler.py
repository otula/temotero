#
# Requires:
#  - pip install pymupdf
#

import os
import fitz  # PyMuPD

def collect_files_with_suffixes(directory, *suffixes):
    """
    Recursively collects all files with any of the specified suffixes (case-insensitive) from the given directory.
    
    Parameters:
    directory (str): The root directory to search.
    *suffixes (str): Variable number of file suffixes to filter files by (e.g., '.txt', '.py', '.jpg').
    
    Returns:
    list: A list of absolute paths to the files that match any of the suffixes.
    """
    file_list = []
    suffixes = tuple(suffix.lower() for suffix in suffixes)  # Convert all suffixes to lowercase
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(suffixes):  # Check if the file ends with any of the suffixes
                file_list.append(os.path.join(os.path.abspath(root), file))
    
    return file_list

def filter_pdfs_without_text(file_paths):
    processed_list = []

    for file_path in file_paths:
        # Check if the file is a PDF
        if not file_path.lower().endswith('.pdf'):
            continue  # Skip non-PDF files

        try:
            # Open the PDF
            doc = fitz.open(file_path)
            contains_text = False

            # Check each page for text
            for page_num in range(doc.page_count):
                page = doc.load_page(page_num)
                text = page.get_text("text")
                if text.strip():  # If any text is found, mark as containing text
                    contains_text = True
                    break

            # If the PDF contains text, keep it; otherwise, remove it and print the name
            if contains_text:
                processed_list.append(file_path)
            else:
                print(f"Removing: {os.path.basename(file_path)} (contains only images)")

        except Exception as e:
            print(f"Error processing file {file_path}: {e}")

    return processed_list

# Example usage:
if __name__ == "__main__":
    directory_to_search = "/path/to/your/directory"
    file_suffixes = (".txt", ".py", ".jpg")  # Case-insensitive list of suffixes
    files = collect_files_with_suffixes(directory_to_search, *file_suffixes)
    
    # Print collected files
    for file in files:
        print(file)
