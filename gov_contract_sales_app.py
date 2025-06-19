import logging
import os
import urllib.parse
from typing import List, Dict
import argparse
from dotenv import load_dotenv
import markdown
import html
import datetime

import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from playwright.sync_api import sync_playwright

# Import USASpending processor
from BetterUSASpending import generate_usa_spending_analysis
# =============================================================================
# CONFIGURATION AND SETUP
# =============================================================================

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
perplexity_api_key = os.getenv("PERPLEXITY_API_KEY")
samgov_api_key = os.getenv("SAMGOV_API_KEY")

if not openai_api_key:
    raise EnvironmentError("OPENAI_API_KEY not set")
if not perplexity_api_key:
    raise EnvironmentError("PERPLEXITY_API_KEY not set")
client = OpenAI(api_key=openai_api_key)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# WEB SCRAPING UTILITIES
# =============================================================================


def fetch_duckduckgo_results(query: str, max_results: int = 5) -> List[str]:
    """Fetch search result links from DuckDuckGo."""
    search_url = "https://duckduckgo.com/html/"
    params = {"q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.post(
            search_url, data=params, headers=headers, timeout=10)
        response.raise_for_status()
        logger.info("DuckDuckGo search response status: %d",
                    response.status_code)
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
                    parsed = urllib.parse.parse_qs(
                        urllib.parse.urlparse(href).query)
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

# =============================================================================
# API SEARCH FUNCTIONS
# =============================================================================

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
            "model": "sonar",
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
            "max_tokens": 2000,
            "temperature": 0.3,
            "return_citations": True,
            # "search_domain_filter": ["perplexity.ai"],
            "return_images": False,
            # "return_sources": True
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
        # print("result: ", result)
        if "search_results" in result:
            search_results = result["search_results"]
            search_results_text = "\n".join(
                f"[{result['title']}]({result['url']})" for result in search_results
            )

        return content + search_results_text

    except Exception as exc:
        logger.error("Web search request failed: %s", exc)
        return ""

def extract_adjacent_personnel(context: str, name: str, agency: str) -> str:
    """Identify managers or collaborators mentioned in the context using Perplexity API."""
    try:
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }

        query = (
            f"Based on the provided context, dive deeper into adjacent individuals and coworkers."
            f"Search for managers, supervisors, collaborators, or support staff "
            f"associated with {name} at {agency}. Focus on organizational structure, "
            f"team members, and professional relationships. Provide names and roles if available."
        )

        data = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a detective that finds related coworkers and connections."
                },
                {
                    "role": "user",
                    "content": f"Search for and provide relevant information about: {query}. Also analyze this context: {context}"
                }
            ],
            "max_tokens": 200,
            "temperature": 0.5,
            "return_citations": True,
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
            search_results_text = "\n".join(
                f"[{result['title']}]({result['url']})" for result in search_results
            )

        return content + search_results_text

    except Exception as exc:
        logger.error("Adjacent personnel extraction failed: %s", exc)
        return ""

def tag_expertise(context: str, name: str, agency: str) -> str:
    """Extract the person's key technical expertise using Perplexity API."""
    try:
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }

        query = (
            f"Based on the provided context, dive deeper into expertise."
            f"Search for technical expertise, skills, technologies, systems experience, "
            f"and procurement expertise of {name} at {agency}. Focus on specific technologies, "
            f"certifications, technical background, and specialized knowledge areas."
            f"If available, provide key names of technical products and services used."
        )

        data = {
            "model": "sonar",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a technical researcher that provides relevant technical and professional expertise information abotu a given individual."
                },
                {
                    "role": "user",
                    "content": f"Search for and provide relevant information about: {query}. Also analyze this context: {context}"
                }
            ],
            "max_tokens": 200,
            "temperature": 0.5,
            "return_citations": True,
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
            search_results_text = "\n".join(
                f"[{result['title']}]({result['url']})" for result in search_results
            )

        return content + search_results_text

    except Exception as exc:
        logger.error("Expertise tagging failed: %s", exc)
        return ""

def search_for_personal(query: str, name: str, agency: str) -> str:
    """Use Perplexity's search API to find personal/social information."""
    messages = [
        {
            "role": "system",
            "content": f"You are a friend of {name} from {agency}. You look through social media as well as key results to find insights that might help establish a connection to {name}"
        },
        {
            "role": "user",
            "content": f"Look through social media and online results to find information that is **non-professional** but might be useful in introductions as well as establishing a personal connection with {name} from {agency}."
        }
    ]
    return _make_perplexity_request(messages, max_tokens=1000, temperature=0.7)

# =============================================================================
# INFORMATION GATHERING AND PROCESSING
# =============================================================================

def gather_information(name: str, agency: str) -> str:
    """Orchestrate the information gathering process from multiple sources."""
    query = f"{name} {agency}"
    logger.info("Searching for information on %s", query)

    # OpenAI search for additional information (currently disabled)
    logger.info("Using OpenAI search for additional context")
    openai_context = search_with_openai(query)
    openai_context = ""

    # Perplexity search with search results
    logger.info("Using Broad web search for key context with search results")
    perplexity_context = search_with_perplexity(query)

    # Extract additional structured information using dedicated roles
    logger.info("Extracting adjacent personnel and expertise")
    adjacent_info = extract_adjacent_personnel(
        perplexity_context, name, agency)
    expertise_info = tag_expertise(perplexity_context, name, agency)
    # personal_info = search_for_personal(
    #     perplexity_context, name, agency
    # )

    # Combine all sources of information
    combined_context = (
        f"\nWeb Search Results:\n{perplexity_context}\n"
        f"OpenAI Research:\n{openai_context}\n\n"
        f"Adjacent Personnel:\n{adjacent_info}\n"
        f"Technical Expertise:\n{expertise_info}\n"
        # f"Personal Information:\n{personal_info}\n"
    )

    return combined_context

def generate_summary(context: str, name: str, agency: str) -> str:
    """Generate initial summary from gathered context."""
    prompt = (
        f"Using the following scraped information about {name} from {agency},\n"
        "craft a document summarizing what a salesperson should know before a call.\n"
        "Ensure each point is on a new line and separated by a blank line for clear readability.\n"
        "Include details on their technical background, past contracts, and specific projects if available.\n"
        "Place the source link with the Title immediately below the related detail using markdown formatting for hyperlinks. Italicize links.\n"
        "Do not use language that is unclear or ambiguous (ex. 'likely').\n"
        "Ensure Diversified Sources – don't just use one."
        "Shy away from overly complicated language. Be direct and concise, with information that would actually be valuable for sales (not fluff).\n"
        "Prioritize actionable insights and distinguishing traits about the individual.\n"
        "Mention managers, collaborators, or support staff when referenced in the sources.\n"
        "Avoid broad statements or givens that are too general.\n"
        "Information:\n" + context
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.6
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error("OpenAI request failed: %s", exc)
        return ""

# =============================================================================
# REVIEW AND IMPROVEMENT
# =============================================================================

def review_agent(summary: str, name: str, agency: str) -> Dict[str, any]:
    """Review Agent using Perplexity's Sonar Pro to evaluate summary accuracy and completeness."""
    review_prompt = (
        f"You are a fact-checking expert reviewing a sales preparation document about {name} from {agency}. "
        f"Evaluate the following summary for factual accuracy and completeness:\n\n{summary}\n\n"
        "Please assess:\n"
        "1. Are all statements factually correct?\n"
        "2. Is the information hyper-specific?\n"
        "3. Is this document sufficient for someone who doesn't know the person to go toe-to-toe in a call?\n\n"
        f"4. Are there any specific products or technologies that {name} prefers?\n"
        f"5. DO NOT USE the source HHS names OIG Chief Data Officer and Assistant IG for the OMP \n"
        "6. Emphasize recent activities, projects, and accomplishments \n"
        "Do NOT use markdown formatting:\n"
        "Respond **only** with this exact format. No extra characters:\n"
        "NEEDS_IMPROVEMENT: true/false\n"
        "FEEDBACK: Specific areas that need improvement or missing information\n"
        "MISSING_INFO: What specific information should be researched and added"
    )

    try:
        headers = {
            "Authorization": f"Bearer {perplexity_api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "sonar-pro",
            "messages": [{"role": "user", "content": review_prompt}],
            "max_tokens": 2000,
            "temperature": 0.6
        }

        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        review_content = result["choices"][0]["message"]["content"]

        # Parse the response
        needs_improvement = (
            "needs_improvement: true" in review_content.lower() or
            "**needs_improvement:** false" in review_content.lower()
        )
        feedback_lines = review_content.split("\n")
        feedback = "\n".join([line for line in feedback_lines[1:]])
        if "search_results" in result:
            search_results = result["search_results"]
            search_results_text = "\n".join(
                f"[{result['title']}]({result['url']})" for result in search_results
            )
            feedback += f"\n\nSearch Results:\n{search_results_text}"

        return {
            "needs_improvement": needs_improvement,
            "feedback": feedback,
            "full_review": review_content
        }

    except Exception as exc:
        logger.error(f"Perplexity API request failed: {exc}")
        return {"needs_improvement": False, "feedback": "Review failed"}

def writer_agent(original_summary: str, feedback: str, name: str, agency: str, context: str) -> str:
    """Writer Agent that improves the summary based on review feedback."""

    improvement_prompt = (
        f"You are an expert sales preparation writer. You need to improve the following summary about {name} from {agency} "
        f"based on the review feedback provided.\n\n"
        f"ORIGINAL SUMMARY:\n{original_summary}\n\n"
        f"REVIEW FEEDBACK:\n{feedback}\n\n"
        f"ORIGINAL CONTEXT (for reference):\n{context}\n\n"
        "Please rewrite and expand the summary to address the feedback. "
        "Ensure each point is on a new line and separated by a blank line for clear readability. "
        "Include details on their technical background, past contracts, and specific projects if available. "
        "Place the source link with the Title immediately below the related detail using markdown formatting for hyperlinks. Italicize links. "
        "Focus on information about specific products or technologies that the individual prefers."
        "Ensure Diversified Sources – 5 or more."
        "Do not use language that is unclear or ambiguous (ex. 'likely'). "
        "Shy away from overly complicated language. Be direct and concise, with information that would actually be valuable for sales (not fluff). "
        "Prioritize actionable insights and distinguishing traits about the individual. "
        "Don't repeat information. If necessary, expand the existing point."
        "Do not say something could not be found. Simply don't include it."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": improvement_prompt}],
            max_tokens=4000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as exc:
        logger.error(f"Writer agent failed: {exc}")
        return original_summary

def review_and_improve_summary(initial_summary: str, name: str, agency: str, context: str, max_iterations: int = 3) -> str:
    """Orchestrate the review and improvement process between Review Agent and Writer Agent."""
    current_summary = initial_summary
    iteration = 0

    logger.info("Starting review and improvement process...")

    while iteration < max_iterations:
        iteration += 1
        logger.info(f"Review iteration {iteration}/{max_iterations}")

        # Review Agent evaluates the current summary
        review_result = review_agent(current_summary, name, agency)

        if not review_result["needs_improvement"]:
            logger.info("Review Agent satisfied with summary quality")
            break

        # Writer Agent improves the summary
        improved_summary = writer_agent(
            current_summary, review_result["feedback"], name, agency, context)

        if improved_summary == current_summary:
            logger.warning(
                "Writer Agent did not make changes, stopping iteration")
            break

        current_summary = improved_summary
        logger.info(f"Summary improved in iteration {iteration}")

    if iteration >= max_iterations:
        logger.warning(
            f"Reached maximum iterations ({max_iterations}) without full satisfaction")

    return current_summary

# =============================================================================
# PDF REPORT GENERATION
# ==============================================================================

def generate_pdf_report(summary: str, name: str, agency: str, output_path: str = "sales_report.pdf", 
                        usaspending_analysis: str = None) -> str:
    """Generate a formatted PDF report using Playwright and Tailwind CSS.
    
    Args:
        summary: Main summary content
        name: Person's name
        agency: Agency name
        output_path: Path for output PDF
        usaspending_analysis: Optional USASpending LLM analysis in markdown format
    """

    import markdown
    # Convert markdown summary to HTML
    summary_html = markdown.markdown(summary, extensions=['extra'])
    
    # Convert USASpending analysis to HTML if provided
    usaspending_html = ""
    if usaspending_analysis:
        usaspending_html = markdown.markdown(usaspending_analysis, extensions=['extra'])

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
            
            {f'''
            <div class="bg-blue-50 rounded-lg p-6 mb-8">
            <h3 class="text-xl font-semibold text-blue-800 mb-4">Agency Spending & Market Analysis</h3>
            <div class="space-y-2 text-sm">
                {usaspending_html}
            </div>
            </div>
            ''' if usaspending_analysis else ''}

            
            <div class="border-t pt-6">
            <p class="text-sm text-gray-500 text-center">Generated by Belridge Labs</p>
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


def generate_report_file(final_summary: str, name: str, agency: str, tag: str = "", 
                        usaspending_analysis: str = None) -> str:
    """Generate PDF report file from the final summary.

    Args:
        final_summary: The formatted summary text
        name: Name of the person
        agency: Agency name
        tag: Optional tag for filename
        usaspending_analysis: Optional USASpending LLM analysis in markdown format

    Returns:
        str: Path to generated PDF file, or empty string if generation failed
    """
    if not final_summary:
        print("\n⚠️  No summary available to generate PDF")
        return ""

    pdf_filename = f"{name.replace(' ', '_')}_{tag.replace(' ', '_')}_sales_report.pdf"
    pdf_path = generate_pdf_report(final_summary, name, agency, pdf_filename, usaspending_analysis)

    if pdf_path:
        print(f"\n📄 PDF report generated: {pdf_path}")
        return pdf_path
    else:
        print("\n❌ Failed to generate PDF report")
        return ""

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Generate one-pager for government contracting sales calls.")
    parser.add_argument("name", help="Individual's name")
    parser.add_argument("agency", help="Agency name")
    parser.add_argument("bureau", help="Bureau/sub-agency name (optional)")

    args = parser.parse_args()

    # Convert agency list to a single string
    agency = args.agency

    # Gather personal information
    # context = ""
    context = gather_information(args.name, agency)
    if not context:
        logger.warning("No context gathered; summary may be empty")

    # summary = ""
    summary = generate_summary(context, args.name, agency)

    usaspending = ""
    usaspending = generate_usa_spending_analysis(agency, args.bureau)

    original_pdf = generate_report_file(summary, args.name, agency, "original", usaspending)

    final_summary = review_and_improve_summary(
        summary, args.name, agency, context)
    # final_summary = summary

    points = []
    for line in final_summary.split('\n'):
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

    print(f"\n=== SALES CALL PREPARATION: {args.name} at {agency} ===\n")
    if points:
        for i, point in enumerate(points, 1):
            print(f"{i}. {point}")
    else:
        print("No specific information found.")
    
    # Generate final PDF with USASpending analysis
    pdf_path = generate_report_file(final_summary, args.name, agency, "final", usaspending)

if __name__ == "__main__":
    main()