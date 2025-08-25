import os
import re
import csv
import time
import random
import json
import pandas as pd
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, quote
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from tqdm import tqdm

# Enhanced Constants
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15"
]

COMMON_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.google.com/',
    'DNT': '1',
}

INTERNATIONAL_KEYWORDS = [
    "open to foreign candidates",
    "visa sponsorship",
    "hiring from abroad",
    "relocation support",
    "sponsor visa",
    "international candidates",
    "foreign workers",
    "candidates worldwide"
]

INDUSTRY_KEYWORDS = {
    "Hotels & hospitality": ["hotel receptionist", "hospitality staff", "chef", "waiter", "hotel staff", "front desk"],
    "Warehousing & logistics": ["warehouse worker", "logistics staff", "forklift operator", "inventory clerk", "shipping clerk"],
    "Cleaning & maintenance": ["cleaning staff", "janitor", "maintenance worker", "custodian", "sanitation worker"]
}

# JOB_SOURCES = {
#     "EURES": {
#         "base_url": "https://ec.europa.eu/eures/portal/jv-se/search",
#         "params": {
#             "page": 1,
#             "resultsPerPage": 100,
#             "keywords": "{query}",
#             "locationCodes": "it"
#         }
#     }
# }

# JOB_SOURCES = {
#     "EURES": {
#         "base_url": "https://ec.europa.eu/eures/eures-apps/rest/hle/v1/jobs",
#         "params": {
#             "offset": 0,
#             "limit": 50,
#             "sortBy": "BEST_MATCH",
#             "lang": "en",
#             "keywords": "{query}",
#             "locationCodes": "it"
#         }
#     }
# }

JOB_SOURCES = {
    "EURES": {
        "base_url": "https://ec.europa.eu/eures/eures-apps/rest/hle/v1/jobs",
        "params": {
            "offset": 0,
            "limit": 50,
            "lang": "en",
            "keywords": "{query}",
            "locationCodes": "IT"   # must be uppercase
        }
    },
    "Adzuna": {
        "base_url": "https://api.adzuna.com/v1/api/jobs/it/search/1",
        "params": {
            "app_id": "YOUR_APP_ID",
            "app_key": "YOUR_APP_KEY",
            "what": "{query}"
        }
    },
    "Jooble": {
        "base_url": "https://jooble.org/api/YOUR_API_KEY",
        "method": "POST"   # must use POST, not GET
    }
}



OUTPUT_FILE = "italy_foreign_hiring_companies.csv"
CACHE_FILE = "scrape_cache.json"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
DELAY_RANGE = (2, 5)  # Increased delay to be more polite

@dataclass
class CompanyLead:
    company_name: str
    industry: str
    contact_person: str
    position_title: str
    email: str
    phone: str
    company_website: str
    job_posting_url: str
    source_platform: str
    proof_text: str

class LeadGenerator:
    def __init__(self):
        self.client = None
        self.initialize_client()
        self.leads: List[CompanyLead] = []
        self.seen_leads = set()
        self.cache = self.load_cache()
    
    def initialize_client(self):
        """Initialize HTTP client with proper configuration"""
        try:
            self.client = httpx.Client(
                timeout=REQUEST_TIMEOUT,
                headers=COMMON_HEADERS,
                follow_redirects=True,
                http2=True
            )
        except Exception as e:
            print(f"Failed to initialize HTTP client: {str(e)}")
            raise

    def load_cache(self) -> List[Dict]:
        """Load cache from file"""
        if not os.path.exists(CACHE_FILE):
            return []
        
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading cache: {str(e)}")
            return []
    
    def save_cache(self):
        """Save cache to file"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving cache: {str(e)}")

    def __del__(self):
        """Cleanup resources"""
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
            self.save_cache()
        except Exception as e:
            print(f"Error during cleanup: {str(e)}")
    
    def get_random_user_agent(self) -> str:
        return random.choice(USER_AGENTS)
    
    def make_request(self, url: str, params: dict = None, method: str = "GET") -> Optional[httpx.Response]:
        if not self.client:
            self.initialize_client()
        
        headers = {'User-Agent': self.get_random_user_agent()}
        
        for attempt in range(MAX_RETRIES):
            try:
                response = self.client.request(
                    method,
                    url,
                    params=params,
                    headers=headers
                )
                response.raise_for_status()
                
                # Check for blocking
                if response.status_code == 403 or "access denied" in response.text.lower():
                    raise httpx.HTTPStatusError("Blocking detected", request=response.request, response=response)
                
                time.sleep(random.uniform(*DELAY_RANGE))
                return response
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                if attempt == MAX_RETRIES - 1:
                    print(f"Failed to fetch {url} after {MAX_RETRIES} attempts: {str(e)}")
                    return None
                
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Retry {attempt + 1} for {url}, waiting {wait_time:.1f} seconds...")
                time.sleep(wait_time)
    
    def search_job_boards(self) -> None:
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            print(f"\nSearching for {industry} jobs...")
            for keyword in tqdm(keywords, desc="Keywords"):
                for platform, source_info in JOB_SOURCES.items():
                    params = source_info['params'].copy()
                    params['keywords'] = params['keywords'].format(query=keyword)
                    
                    # URL encode the parameters properly
                    # encoded_params = {k: quote(str(v)) for k, v in params.items()}
                    encoded_params = {k: str(v) for k, v in params.items()}

                    
                    response = self.make_request(
                        source_info['base_url'],
                        params=encoded_params
                    )
                    
                    if not response:
                        continue
                    
                    self.scrape_job_board(response.text, platform, industry)
    
    def scrape_job_board(self, response: httpx.Response, platform: str, industry: str) -> None:
        if platform == "EURES":
            self.scrape_eures(response.json(), platform, industry)

    def scrape_eures(self, data: dict, platform: str, industry: str) -> None:
        try:
            jobs = data.get("jobs", [])
            if not jobs:
                print("No jobs found in EURES response")
                return

            for job in jobs:
                try:
                    job_title = job.get("title", "").strip()
                    company_name = job.get("employer", {}).get("name", "").strip()
                    job_id = job.get("id")
                    job_url = f"https://ec.europa.eu/eures/portal/jv-search/details/{job_id}"

                    if not job_title or not company_name:
                        continue

                    lead_key = f"{company_name}_{job_title}"
                    if lead_key in self.seen_leads:
                        continue

                    print(f"\nFound job: {job_title} at {company_name}")

                    # Job description text
                    job_text = " ".join([
                        job.get("description", ""),
                        job.get("profileDescription", ""),
                        job.get("requirements", ""),
                    ]).lower()

                    proof_text = self.find_international_hiring_proof(job_text)
                    if not proof_text:
                        print("No international hiring proof found")
                        continue

                    # Company website if available
                    company_website = job.get("employer", {}).get("url", "")

                    lead = CompanyLead(
                        company_name=company_name,
                        industry=industry,
                        contact_person="",
                        position_title=job_title,
                        email="",
                        phone="",
                        company_website=company_website,
                        job_posting_url=job_url,
                        source_platform=platform,
                        proof_text=proof_text
                    )

                    if company_website:
                        self.enrich_lead_with_contact_info(lead)

                    self.leads.append(lead)
                    self.seen_leads.add(lead_key)
                    print(f"Added lead: {company_name} - {job_title}")

                except Exception as e:
                    print(f"Error processing EURES job item: {str(e)}")
                    continue

        except Exception as e:
            print(f"Error scraping EURES JSON: {str(e)}")

    
    def find_international_hiring_proof(self, text: str) -> str:
        """Find proof of international hiring in the text and return the relevant snippet."""
        text_lower = text.lower()
        
        for keyword in INTERNATIONAL_KEYWORDS:
            if keyword in text_lower:
                start = max(0, text_lower.find(keyword) - 50)
                end = min(len(text), start + len(keyword) + 100)
                snippet = text[start:end].strip()
                snippet = re.sub(r'\s+', ' ', snippet)
                return snippet
                
        return ""
    
    def enrich_lead_with_contact_info(self, lead: CompanyLead) -> None:
        """Attempt to find contact information from company website."""
        try:
            # Normalize website URL
            if not lead.company_website.startswith(('http://', 'https://')):
                lead.company_website = f"https://{lead.company_website}"
            
            # Check cache first
            cached_info = next((item for item in self.cache if item.get('url') == lead.company_website), None)
            if cached_info:
                lead.contact_person = cached_info.get('contact_person', "")
                lead.email = cached_info.get('email', "")
                lead.phone = cached_info.get('phone', "")
                return
            
            print(f"Fetching contact info from: {lead.company_website}")
            
            response = self.make_request(lead.company_website)
            if not response:
                return
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Try to find contact page link
            contact_links = []
            for link in soup.find_all('a', href=True):
                href = link['href'].lower()
                if any(word in href for word in ['contact', 'contatti', 'contatto', 'kontakt', 'contacto']):
                    contact_links.append(link['href'])
            
            # Resolve relative URLs and deduplicate
            contact_links = list(set(urljoin(lead.company_website, link) for link in contact_links))
            
            # Try each contact page
            for contact_url in contact_links[:3]:  # Limit to first 3 contact pages
                try:
                    contact_response = self.make_request(contact_url)
                    if not contact_response:
                        continue
                    
                    contact_text = contact_response.text
                    
                    # Extract email
                    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
                    emails = re.findall(email_pattern, contact_text)
                    if emails:
                        valid_emails = [e for e in emails if not any(d in e for d in ['info@', 'contact@', 'support@', 'hello@'])]
                        if valid_emails:
                            lead.email = valid_emails[0]
                    
                    # Extract phone
                    phone_pattern = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}\b'
                    phones = re.findall(phone_pattern, contact_text)
                    if phones:
                        lead.phone = phones[0]
                    
                    # Try to find HR contact person
                    hr_keywords = ['hr', 'human resources', 'recruiter', 'assunzioni', 'risorse umane', 'personale', 'hiring']
                    contact_soup = BeautifulSoup(contact_text, 'lxml')
                    for elem in contact_soup.find_all(['h2', 'h3', 'div', 'p', 'span']):
                        text = elem.get_text().lower()
                        if any(keyword in text for keyword in hr_keywords):
                            parent_text = elem.parent.get_text()
                            name_match = re.search(r'(?:Sig\.|Signor|Signora|Mr\.|Ms\.|Mrs\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', parent_text, re.IGNORECASE)
                            if name_match:
                                lead.contact_person = name_match.group(1)
                            break
                    
                    # If we found any info, cache it
                    if lead.email or lead.phone or lead.contact_person:
                        self.cache.append({
                            'url': lead.company_website,
                            'contact_person': lead.contact_person,
                            'email': lead.email,
                            'phone': lead.phone,
                            'timestamp': datetime.now().isoformat()
                        })
                        break
                    
                except Exception as e:
                    print(f"Error processing contact page {contact_url}: {str(e)}")
                    continue
                    
        except Exception as e:
            print(f"Error enriching lead for {lead.company_website}: {str(e)}")
    
    def save_to_csv(self, filename: str = OUTPUT_FILE) -> None:
        """Save collected leads to CSV file."""
        if not self.leads:
            print("No leads to save.")
            return
        
        # Convert leads to dicts
        lead_dicts = []
        for lead in self.leads:
            lead_dicts.append({
                'company_name': lead.company_name,
                'industry': lead.industry,
                'contact_person': lead.contact_person,
                'position_title': lead.position_title,
                'email': lead.email,
                'phone': lead.phone,
                'company_website': lead.company_website,
                'job_posting_url': lead.job_posting_url,
                'source_platform': lead.source_platform,
                'proof_text': lead.proof_text
            })
        
        # Create DataFrame and save to CSV
        df = pd.DataFrame(lead_dicts)
        
        # Ensure proper CSV formatting for Excel
        df.to_csv(filename, index=False, encoding='utf-8-sig', quoting=csv.QUOTE_ALL)
        
        print(f"\nSuccessfully saved {len(self.leads)} leads to {filename}")

def main():
    print("Starting Italy Foreign Hiring Lead Generator...")
    
    try:
        generator = LeadGenerator()
        generator.search_job_boards()
        generator.save_to_csv()
        print("\nLead generation completed!")
    except Exception as e:
        print(f"\nError during lead generation: {str(e)}")
    finally:
        if 'generator' in locals():
            del generator  # Ensure proper cleanup

if __name__ == "__main__":
    main()