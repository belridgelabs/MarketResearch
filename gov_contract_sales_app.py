import argparse
import logging
import os
import urllib.parse
from typing import List
from dotenv import load_dotenv

import requests
from bs4 import BeautifulSoup
from openai import OpenAI

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
if not openai_api_key:
    raise EnvironmentError("OPENAI_API_KEY not set")
if not perplexity_api_key:
    raise EnvironmentError("PERPLEXITY_API_KEY not set")
client = OpenAI(api_key=openai_api_key)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_duckduckgo_results(query: str, max_results: int = 5) -> List[str]:
    """Fetch search result links from DuckDuckGo."""
    search_url = "https://duckduckgo.com/html/"
    params = {"q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.post(search_url, data=params, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info("DuckDuckGo search response status: %d", response.status_code)
    except Exception as exc:
        logger.error("Search request failed: %s", exc)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    links = []
    
    # Try multiple selectors for DuckDuckGo results
    selectors = [
        "a.result__a",
        "a[href*='uddg']",
        ".result__body a",
        ".web-result a",
        "a[href^='http']"
    ]
    
    for selector in selectors:
        for a in soup.select(selector):
            href = a.get("href")
            if href:
                # Handle DuckDuckGo's redirect URLs
                 if "uddg=" in href:
                     # Extract the actual URL from DuckDuckGo's redirect
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    if "uddg" in parsed:
                         href = urllib.parse.unquote(parsed["uddg"][0])
                
                    if href and href.startswith("http") and "duckduckgo.com" not in href:
                        if href not in links:  # Avoid duplicates
                            links.append(href)
                            logger.info("Found URL: %s", href)
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

def search_with_openai(query: str) -> str:
    """Use OpenAI's search API to find relevant information."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": f"Search for and provide relevant information about: {query}. Focus on professional background, recent activities, government contracting experience, and any publicly available information that would be useful for a sales call preparation."
                }
            ],
            max_tokens=500,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("OpenAI search request failed: %s", exc)
        return ""

def search_with_perplexity(query: str) -> str:
    """Use Perplexity's search API to find relevant information."""
    try:
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that searches for and provides relevant professional information."
                },
                {
                    "role": "user",
                    "content": f"Search for and provide relevant information about: {query}. Focus on professional background, recent activities, government contracting experience, and any publicly available information that would be useful for a sales call preparation."
                }
            ],
            "max_tokens": 500,
            "temperature": 0.3,
            "return_citations": True,
            "search_domain_filter": ["perplexity.ai"],
            "return_images": False
        }
        
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # Extract search results if available
        search_results = ""
        if "search_results" in result:
            citations = result["search_results"]
            if citations:
                search_results = "\n\nSearch Results Sources:\n" + "\n".join([f"- {citation}" for citation in citations])
        
        return content + search_results
        
    except Exception as exc:
        logger.error("Perplexity search request failed: %s", exc)
        return ""

def gather_information(name: str, agency: str) -> str:
    query = f"{name} {agency}"
    logger.info("Searching for information on %s", query)
    
    # Stage 1: DuckDuckGo web scraping
    urls = fetch_duckduckgo_results(query)
    logger.info("Found %d urls", len(urls))
    texts = []
    for url in urls:
        logger.info("Scraping %s", url)
        texts.append(scrape_page_text(url))
    web_context = "\n".join(texts)
    
    # # Stage 2: OpenAI search for additional information
    # logger.info("Using OpenAI search for additional context")
    # openai_context = search_with_openai(query)
    openai_context = ""
    
    # Stage 3: Perplexity search with search results
    logger.info("Using Perplexity search for additional context with search results")
    perplexity_context = search_with_perplexity(query)
    
    # Combine all sources of information
    combined_context = f"Web Search Results:\n{web_context}\n\nOpenAI Research:\n{openai_context}\n\nPerplexity Search Results:\n{perplexity_context}"
    return combined_context

def generate_summary(context: str, name: str, agency: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    prompt = (
        f"Using the following scraped information about {name} from {agency},\n"
        "craft a concise one-pager summarizing what a salesperson should know before a call.\n"
        "Format the response as a clean, non-repetitive list of 5-7 key points.\n"
        "For each bullet point, provide a quote from the source that proves that point.\n"
        "Do not use language that is unclear or ambigious (ex. 'likely').\n"
        "Shy away from overly complicated language. Be direct and concise, with information that would actually be valuable for sales (not fluff).\n"
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
    
    # # Extract key points from the summary
    # points = []
    # for line in summary.split('\n'):
    #     line = line.strip()
    #     if not line:
    #         continue
            
    #     # Check if line is a numbered point or bullet point
    #     if (line[0].isdigit() and '.' in line[:3]) or line[0] in ['•', '-', '*']:
    #         # Extract content without the numbering/bullet
    #         if line[0].isdigit() and '.' in line[:3]:
    #             content = line.split('.', 1)[1].strip()
    #         else:
    #             content = line[1:].strip()
                
    #         # Only add if not a duplicate
    #         if content and content.lower() not in [p.lower() for p in points]:
    #             points.append(content)
    #     elif line not in points:  # For non-bullet text
    #         points.append(line)
    
    # Print formatted output
    print(f"\n=== SALES CALL PREPARATION: {args.name} at {agency} ===\n")
    
    if points:
        for i, point in enumerate(points, 1):
            print(f"{i}. {point}")
    else:
        print("No specific information found. Consider researching more about this person.")

if __name__ == "__main__":
    main()
