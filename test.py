import requests
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

session = requests.Session()
logger = logging.getLogger(__name__)
SAM_BASE = "https://api.sam.gov/prod/opportunities/v2/search"
load_dotenv()
samgov_api_key = os.getenv("SAMGOV_API_KEY")
print(samgov_api_key)
if not samgov_api_key:
    raise EnvironmentError("SAMGOV_API_KEY not set")


def fetch_hhs_oig_solicitations(status: str="active"):
    """
    status: "active" or "archived"
    Returns a list of solicitations for HHS → OIG.
    """
    page = 1
    perpage = 10

    payload = {
        "api_key": samgov_api_key,
        "ptype":   "o",                   # only solicitations (vs grants)
        # "status":  status,/# active | archived
        # "organizationCode": "075",
        "deptname": "Health and Human Services",
        # "postedFrom": (datetime.now() - timedelta(days=364)).strftime("%Y-%m-%d"),       # Filter for recent solicitations
        # "postedTo": (datetime.now() - timedelta(days=0)).strftime("%Y-%m-%d"),         # Current date
        "postedFrom": "01/01/2024",     # Filter for recent solicitations
        "postedTo": "12/31/2024",       # Current date
        "page":   page,
        "limit":  perpage
    }
    resp = requests.get(SAM_BASE, params=payload)
    print(f"GET Request URL: {resp.request.url}")
    resp.raise_for_status()
    return resp.json()

active_ops = fetch_hhs_oig_solicitations("active")
# archived_ops = fetch_hhs_oig_solicitations("archived")
# print(f"Got {len(active_ops)} active + {len(archived_ops)} archived solicitations") 
print(active_ops)