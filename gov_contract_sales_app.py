import argparse
import logging
import os
import urllib.parse
from typing import List
from dotenv import load_dotenv
import markdown
import html

import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from playwright.sync_api import sync_playwright

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
                    "content": f"Search for and provide relevant information about: {query}. Focus on professional background, recent activities, government contracting experience, and any publicly available information that would be useful for a sales call preparation. Provide specifics about technical information, past contracts, and any relevant technologies or projects they have been involved with."
                }
            ],
            max_tokens=700,
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
                    "content": f"Search for and provide relevant information about: {query}. Focus on professional background, recent activities, government contracting experience, and any publicly available information that would be useful for a sales call preparation. Provide specifics about technical information as well as past contracts."
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
        search_results_text = ""
        if "search_results" in result:
            search_results = result["search_results"]
            if isinstance(search_results, list) and search_results:
                lines = []
                for entry in search_results:
                    title = entry.get("title", "")
                    url = entry.get("url", "")
                    date = entry.get("date", "")
                    line = f"- {title} ({date}): {url}" if title or date else f"- {url}"
                    lines.append(line)
                search_results_text = "\n\nSearch Results Sources:\n" + "\n".join(lines)

        return content + search_results_text

    except Exception as exc:
        logger.error("Perplexity search request failed: %s", exc)
        return ""

def extract_adjacent_personnel(context: str, name: str, agency: str) -> str:
    """Identify managers or collaborators mentioned in the context."""
    try:
        prompt = (
            f"From the following text about {name} at {agency}, list any managers," 
            " supervisors, collaborators, or support staff mentioned. "
            "Provide their names and roles if available."
            "\nText:\n" + context
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Adjacent personnel extraction failed: %s", exc)
        return ""

def tag_expertise(context: str, name: str) -> str:
    """Extract the person's key technical expertise from the context."""
    try:
        prompt = (
            f"Based on the following information about {name}, identify any specific"
            " technologies, systems experience, or procurement expertise they possess."
            "\nText:\n" + context
        )
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.3,
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("Expertise tagging failed: %s", exc)
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
        page_text = scrape_page_text(url)
        if page_text:
            texts.append(f"SOURCE: {url}\n{page_text}")
    web_context = "\n".join(texts)
    
    # # Stage 2: OpenAI search for additional information
    # logger.info("Using OpenAI search for additional context")
    # openai_context = search_with_openai(query)
    openai_context = ""
    
    # Stage 3: Perplexity search with search results
    logger.info("Using Perplexity search for additional context with search results")
    perplexity_context = search_with_perplexity(query)

    # Extract additional structured information using dedicated roles
    adjacent_info = extract_adjacent_personnel(perplexity_context, name, agency)
    expertise_info = tag_expertise(perplexity_context, name)

    # Combine all sources of information
    combined_context = (
        f"Web Search Results:\n{web_context}\n\nOpenAI Research:\n{openai_context}"
        f"\n\nPerplexity Search Results:\n{perplexity_context}\n\nAdjacent Personnel:\n{adjacent_info}\n\nTechnical Expertise:\n{expertise_info}"
    )
    return combined_context

def generate_summary(context: str, name: str, agency: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not set")
    prompt = (
        f"Using the following scraped information about {name} from {agency},\n"
        "craft a concise one-pager summarizing what a salesperson should know before a call.\n"
        "Format the response as a numbered list (e.g., 1., 2., etc.) of 7-10 key points.\n"
        "Ensure each point is on a new line and separated by a blank line for clear readability.\n"
        "Include details on their technical background, past contracts, and specific projects if available.\n"
        "For each numbered point, provide a short quote from the source that proves that point.\n"
        "Place the source link immediately below the quote using the format 'Source: <URL>'.\n"
        "Do not use language that is unclear or ambigious (ex. 'likely').\n"
        "Shy away from overly complicated language. Be direct and concise, with information that would actually be valuable for sales (not fluff).\n"
        "Prioritize actionable insights and distinguishing traits about the individual, including any relevant systems experience, AI tools, or procurement expertise.\n"
        "Mention managers, collaborators, or support staff when referenced in the sources.\n"
        "Avoid broad statements or givens that are too general.\n"
        "Information:\n" + context
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.7
        )
        # Process the response to remove any potential duplicates
        content = response.choices[0].message.content
        # Process the response to remove any potential duplicates and ensure proper line breaks
        # The LLM is now instructed to provide numbered points with blank lines in between.
        # We will preserve these as much as possible for markdown rendering.
        return content
    except Exception as exc:
        logger.error("OpenAI request failed: %s", exc)
        return ""

def generate_pdf_report(summary: str, name: str, agency: str, output_path: str = "sales_report.pdf") -> str:
    """Generate a formatted PDF report using Playwright and Tailwind CSS."""
    
    import markdown
    # Convert markdown summary to HTML
    summary_html = markdown.markdown(summary, extensions=['extra'])
    
    tailwind_html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://cdn.tailwindcss.com"></script>
  <title>Sales Call Preparation Report</title>
</head>
<body class="bg-white p-8">
  <div class="max-w-4xl mx-auto">
    <div class="border-b-4 border-blue-600 pb-4 mb-8">
      <h1 class="text-4xl font-bold text-blue-600 mb-2">Sales Call Preparation</h1>
      <h2 class="text-2xl font-semibold text-gray-800">{html.escape(name)} at {html.escape(agency)}</h2>
      <p class="text-sm text-gray-500 mt-2">Generated on {__import__('datetime').datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    
    <div class="bg-gray-50 rounded-lg p-6 mb-8">
      <h3 class="text-xl font-semibold text-gray-800 mb-4">Key Information</h3>
      <div class="space-y-2">
        {summary_html}
      </div>
    </div>
    
    <div class="border-t pt-6">
      <p class="text-sm text-gray-500 text-center">Generated via Government Contract Sales Research Tool</p>
      <p class="text-xs text-gray-400 text-center mt-1">Powered by Playwright + Tailwind CSS</p>
    </div>
  </div>
</body>
</html>
"""
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(tailwind_html)
            
            # Wait for Tailwind to load
            page.wait_for_timeout(2000)
            
            page.pdf(
                path=output_path, 
                format="A4", 
                print_background=True,
                margin={
                    "top": "1in",
                    "bottom": "1in", 
                    "left": "0.5in",
                    "right": "0.5in"
                }
            )
            browser.close()
            
        logger.info(f"PDF report generated successfully: {output_path}")
        return output_path
        
    except Exception as exc:
        logger.error(f"Failed to generate PDF: {exc}")
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
    
    # Generate PDF report
    if summary:
        pdf_filename = f"sales_report_{args.name.replace(' ', '_')}_{agency.replace(' ', '_')}.pdf"
        pdf_path = generate_pdf_report(summary, args.name, agency, pdf_filename)
        if pdf_path:
            print(f"\n📄 PDF report generated: {pdf_path}")
        else:
            print("\n❌ Failed to generate PDF report")
    else:
        print("\n⚠️  No summary available to generate PDF")

if __name__ == "__main__":
    main()
