import argparse
import logging
import os
from typing import List
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise EnvironmentError("OPENAI_API_KEY not set")
client = OpenAI(api_key=api_key)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_google_results(query: str, max_results: int = 5) -> List[str]:
    """Fetch search result links from Google."""
    search_url = "https://www.google.com/search"
    params = {"q": query, "hl": "en", "num": max_results}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        response = requests.get(search_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        logger.error("Search request failed: %s", exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    links = []
    # Try multiple selectors to improve reliability
    selectors = ["div.yuRUbf > a", "div.g div.yuRUbf > a", "div.g a[href^='http']", "a[href^='http']:not([href^='https://www.google'])"] 
    
    for selector in selectors:
        for a in soup.select(selector):
            href = a.get("href")
            if href and href.startswith("http") and "google.com" not in href:
                if href not in links:  # Avoid duplicates
                    links.append(href)
            if len(links) >= max_results:
                break
        if links:  # If we found links with this selector, no need to try others
            break
            
    logger.info("Found %d search result URLs", len(links))
    return links

def scrape_page_text(url: str) -> str:
    """Retrieve plain text from a webpage."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return ""

    soup = BeautifulSoup(response.text, "html.parser")
    # Remove scripts and styles
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = " ".join(chunk.strip() for chunk in soup.stripped_strings)
    return text

def gather_information(name: str, agency: str) -> str:
    query = f"{name} {agency}"
    logger.info("Searching for information on %s", query)
    urls = fetch_google_results(query)
    logger.info("Found %d urls", len(urls))
    texts = []
    for url in urls:
        logger.info("Scraping %s", url)
        texts.append(scrape_page_text(url))
    return "\n".join(texts)

def generate_summary(context: str, name: str, agency: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    prompt = (
        f"Using the following scraped information about {name} from {agency},\n"
        "craft a concise one-pager summarizing what a salesperson should know before a call.\n"
        "Format the response as a clean, non-repetitive list of 5-7 key points.\n"
        "Ensure there are no duplicate lines in your response.\n"
        "Information:\n" + context
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7
        )
        # Process the response to remove any potential duplicates
        content = response.choices[0].message.content
        lines = content.split('\n')
        unique_lines = []
        for line in lines:
            line = line.strip()
            if line and line not in unique_lines:
                unique_lines.append(line)
        return '\n'.join(unique_lines)
    except Exception as exc:
        logger.error("OpenAI request failed: %s", exc)
        return ""

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Generate one-pager for government contracting sales calls.")
    parser.add_argument("name", help="Individual's name")
    parser.add_argument("agency", help="Agency name", nargs='+')
    args = parser.parse_args()

    # Convert agency list to a single string
    agency = ' '.join(args.agency)
    
    context = gather_information(args.name, agency)
    if not context:
        logger.warning("No context gathered; summary may be empty")
    
    summary = generate_summary(context, args.name, agency)
    
    # Extract key points from the summary
    points = []
    for line in summary.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        # Check if line is a numbered point or bullet point
        if (line[0].isdigit() and '.' in line[:3]) or line[0] in ['•', '-', '*']:
            # Extract content without the numbering/bullet
            if line[0].isdigit() and '.' in line[:3]:
                content = line.split('.', 1)[1].strip()
            else:
                content = line[1:].strip()
                
            # Only add if not a duplicate
            if content and content.lower() not in [p.lower() for p in points]:
                points.append(content)
        elif line not in points:  # For non-bullet text
            points.append(line)
    
    # Print formatted output
    print(f"\n=== SALES CALL PREPARATION: {args.name} at {agency} ===\n")
    
    if points:
        for i, point in enumerate(points, 1):
            print(f"{i}. {point}")
    else:
        print("No specific information found. Consider researching more about this person.")

if __name__ == "__main__":
    main()
