from datetime import datetime
import requests
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

 # Import OpenAI at the top of the file if not already imported
from openai import OpenAI

# Add OpenAI client setup after the existing API key setup
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise EnvironmentError("OPENAI_API_KEY not set")
client = OpenAI(api_key=openai_api_key)

session = requests.Session()
logger = logging.getLogger(__name__)

@dataclass
class ContractData:
    """Data structure for individual contract information."""
    award_id: str
    recipient_name: str
    awarding_agency: str
    awarding_sub_agency: str
    award_amount: float
    award_date: str
    description: str
    naics_code: str
    naics_description: str
    contract_type: str
    period_of_performance_start: str
    period_of_performance_end: str

@dataclass
class AgencySpendingData:
    """Data structure for agency spending analysis."""
    agency_name: str
    bureau_name: str
    total_spending: float
    contract_count: int
    top_contractors: List[Dict[str, any]]
    spending_categories: List[Dict[str, any]]
    recent_awards: List[ContractData]

def search_awards_by_agency(agency_name: str, bureau_name: str, page: int = 1,
                            limit: int = 10, fiscal_year: int = None) -> dict[str, any]:
    """Search for awards by agency and optional bureau name.

    Args:
        agency_name: Name of the agency
        bureau_name: Optional bureau/sub-agency name
        limit: Maximum number of results to return
        fiscal_year: Fiscal year to filter by (defaults to current)

    Returns:
        Dict containing API response with awards data
    """
    if fiscal_year is None:
        fiscal_year = datetime.now().year
    # print(fiscal_year)
    endpoint = f"https://api.usaspending.gov/api/v2/search/spending_by_award"


    if bureau_name:
        agencies = [{
            "type": "awarding",
            "tier": "subtier",
            "toptier_name": agency_name,
            "name": bureau_name
        }]
    else:
        agencies = [{
            "type": "awarding",
            "tier": "toptier",
            "name": agency_name
        }]

    # Build agencies filter
    payload = {
      "subawards": False,
      "limit": limit,
      "page": page,
      "filters": {
            "award_type_codes": ["A", "B", "C"],
            "time_period": [{"start_date": f"2024-01-01", "end_date": f"2025-12-30"}],
            "agencies": agencies,
            "sort": "date_signed",
            "order": "desc",
      },
      "fields": [
          "Award ID",
          "Recipient Name", 
          "Award Amount",
          "Award Date",
          "Start Date",
          "End Date",
          "Awarding Agency",
          "Awarding Sub Agency",
          "Award Description",
          "NAICS",
          "Contract Award Type",
          "Funding Agency",
          "Funding Sub Agency",
          "PSC",
          "piid",
      ],
    }

    try:
        response = session.post(endpoint, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"USASpending API request failed: {e}")
        return {}


# all_agency_data = []
# page = 1
# has_next = True

# while has_next:
#     agency_data = search_awards_by_agency(
#         agency_name="Department of Health and Human Services",
#         bureau_name="Office of the Inspector General",
#         page=page
#     )
    
#     if not agency_data:
#         break
        
#     all_agency_data.extend(agency_data.get('results', []))
#     page_metadata = agency_data.get('page_metadata', {})
#     has_next = page_metadata.get('hasNext', False)
#     has_next = False
#     page += 1

# print(agency_data)

def generate_usa_spending_analysis(agency_name: str, bureau_name: str) -> str:
    """
    Generate analysis of USA spending data for given agency and bureau using LLM.
    
    Args:
        agency_name: Name of the agency
        bureau_name: Name of the bureau/sub-agency
        
    Returns:
        String containing LLM analysis of the spending data
    """

    # Collect all agency data
    all_agency_data = ""
    page = 1
    has_next = True

    while has_next and len(all_agency_data) < 50:
        agency_data = search_awards_by_agency(
            agency_name=agency_name,
        bureau_name=bureau_name,
            page=page
        )

        if not agency_data:
            break
            
        # all_agency_data.extend(agency_data.get('results', []))
        all_agency_data += str(agency_data.get('results', [])) + "\n"
        page_metadata = agency_data.get('page_metadata', {})
        has_next = page_metadata.get('hasNext', False)
        page += 1

    
    # Create prompt for LLM analysis
    prompt = f"""
    Analyze the following USA spending data for {agency_name} - {bureau_name}:
    
    Please provide:
    1. Key spending patterns and trends
    2. Notable contractors and award sizes
    3. Main categories of spending

    DO NOT NOTE:
    1. If there is a 0 or empty column, or anything that is a data error, DO NOT comment on it.

    Agency Spending Data: {all_agency_data}
    """

    # Replace the commented section (lines 194-201) with:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3
        )
        analysis = response.choices[0].message.content
        return analysis
    except Exception as exc:
        logger.error("OpenAI request failed: %s", exc)
        return "Analysis could not be generated due to API error."

# print(search_awards_by_agency("Department of Homeland Security", "U.S. Citizenship and Immigration Services"))