import argparse
import logging
import os
from typing import List

from googlesearch import search

import requests
from bs4 import BeautifulSoup
import openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_google_results(query: str, max_results: int = 5) -> List[str]:
    """Fetch search result links from Google using Chrome."""
    try:
        return list(search(query, num_results=max_results))
    except Exception as exc:
        logger.error("Google search failed: %s", exc)
        return []

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
    openai.api_key = api_key
    prompt = (
        f"Using the following scraped information about {name} from {agency},\n"
        "craft a concise one-pager summarizing what a salesperson should know before a call.\n"
        "Information:\n" + context
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("OpenAI request failed: %s", exc)
        return ""

def main():
    parser = argparse.ArgumentParser(description="Generate one-pager for government contracting sales calls.")
    parser.add_argument("name", help="Individual's name")
    parser.add_argument("agency", help="Agency name")
    args = parser.parse_args()

    context = gather_information(args.name, args.agency)
    if not context:
        logger.warning("No context gathered; summary may be empty")
    summary = generate_summary(context, args.name, args.agency)
    print(summary)

if __name__ == "__main__":
    main()
