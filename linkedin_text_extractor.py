from bs4 import BeautifulSoup
import os
import glob
import re

def clean_extracted_text(raw_text):
    """
    Clean extracted text by removing unwanted content and normalizing whitespace.
    
    Args:
        raw_text (str): Raw text extracted from HTML
    
    Returns:
        str: Cleaned text
    """
    cleaned_text = raw_text
    
    # Remove JSON blocks
    cleaned_text = re.sub(r"{.*?}", "", cleaned_text, flags=re.DOTALL)
    
    # Remove repeated pipes
    cleaned_text = re.sub(r"\|+", "", cleaned_text)
    
    # Remove JavaScript functions
    cleaned_text = re.sub(r"\bfunction\b.*?{.*?}", "", cleaned_text, flags=re.DOTALL)
    
    # Remove inline JS like document.write;
    cleaned_text = re.sub(r"document\..*?;", "", cleaned_text)
    
    # Remove other common web artifacts
    cleaned_text = re.sub(r"window\.[^\s]*", "", cleaned_text)  # window.* calls
    cleaned_text = re.sub(r"var\s+[^=]*=.*?;", "", cleaned_text)  # variable declarations
    cleaned_text = re.sub(r"\bif\s*\([^)]*\)\s*{[^}]*}", "", cleaned_text)  # simple if statements
    
    # Reduce long whitespace to single newline
    cleaned_text = re.sub(r"\s{2,}", "\n", cleaned_text)
    
    # Normalize newlines (max 2 consecutive)
    cleaned_text = re.sub(r"\n{2,}", "\n\n", cleaned_text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in cleaned_text.splitlines()]
    
    # Remove empty lines at the beginning and end
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    
    return "\n".join(lines)

def extract_linkedin_text(html_file_path, output_dir="extracted_text"):
    """
    Extract plain text from LinkedIn HTML file and save only the status slice content.
    
    Args:
        html_file_path (str): Path to the LinkedIn HTML file
        output_dir (str): Directory to save extracted text files
    
    Returns:
        str: Path to the saved status slice file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the HTML content from the file
    with open(html_file_path, "r", encoding="utf-8") as file:
        html_content = file.read()
    
    # Use BeautifulSoup to strip all HTML tags and get only text
    soup = BeautifulSoup(html_content, "html.parser")
    raw_text = soup.get_text(separator="\n")
    
    # Clean the extracted text
    cleaned_text = clean_extracted_text(raw_text)
    
    # Generate output filename based on input filename and content type
    base_name = os.path.splitext(os.path.basename(html_file_path))[0]
    
    # Determine if this is a Skills page or Profile page
    if "Skills" in base_name:
        # Extract number from Skills page filename
        import re
        match = re.search(r'Skills.*?-?(\d+)', base_name)
        if match:
            number = match.group(1)
            output_filename = f"skills-{number}.txt"
        else:
            output_filename = "skills.txt"
    else:
        output_filename = "Profile.txt"
    
    # Extract only the content between the two lines containing "Status is"
    lines = cleaned_text.splitlines()
    start_index = None
    end_index = None
    
    for i, line in enumerate(lines):
        if "Status is" in line:
            if start_index is None:
                start_index = i
            elif end_index is None:
                end_index = i
                break
        if end_index is None:
            if "More profiles for you" in line:
                end_index = i
                break
    
    # Extract and save the relevant portion if both markers are found
    output_path = os.path.join(output_dir, output_filename)
    
    if start_index is not None and end_index is not None and start_index < end_index:
        sliced_text = "\n".join(lines[start_index:end_index + 1])
        status_message = f"Found content between 'Status is' markers (lines {start_index+1} to {end_index+1})"
    else:
        sliced_text = "Could not find two 'Status is' markers in the text."
        status_message = "No valid 'Status is' markers found"
    
    # Save the sliced content
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(sliced_text)
    
    print(f"✅ Status slice saved to: {output_path} - {status_message}")
    
    return output_path

def process_all_linkedin_files(input_dir="linkedin_html_dumps", output_dir="extracted_text"):
    """
    Process all LinkedIn HTML files in the specified directory.
    
    Args:
        input_dir (str): Directory containing LinkedIn HTML files
        output_dir (str): Directory to save extracted text files
    """
    html_files = glob.glob(os.path.join(input_dir, "*.html"))
    
    if not html_files:
        print(f"❌ No HTML files found in {input_dir}")
        return
    
    print(f"📁 Found {len(html_files)} HTML files to process:")
    
    results = []
    for html_file in html_files:
        print(f"\n🔄 Processing: {os.path.basename(html_file)}")
        try:
            slice_path = extract_linkedin_text(html_file, output_dir)
            results.append({
                'source': html_file,
                'status_slice': slice_path
            })
        except Exception as e:
            print(f"❌ Error processing {html_file}: {str(e)}")
    
    print(f"\n✅ Processing complete! Processed {len(results)} files successfully.")
    return results

if __name__ == "__main__":
    # Process all LinkedIn HTML files in the linkedin_html_dumps directory
    results = process_all_linkedin_files()
    
    # Or process a specific file:
    # extract_linkedin_text("linkedin_html_dumps/(2) Steven Grunch _ LinkedIn.html")