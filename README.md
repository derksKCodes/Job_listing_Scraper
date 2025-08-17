# Italy Foreign Hiring Lead Generator

This Python script automatically scrapes job listings from multiple sources to identify Italian companies in target industries that are open to hiring international candidates.

## Features

- Scrapes job listings from Indeed Italy, EURES, and Jooble Italy
- Targets three key industries: Hotels & hospitality, Warehousing & logistics, Cleaning & maintenance
- Identifies companies open to foreign workers using keyword matching
- Extracts company contact information from websites
- Outputs structured lead data in CSV format

## Installation

1. Ensure you have Python 3.12+ installed
2. Clone this repository or download the script files
3. Install dependencies:

```bash
pip install -r requirements.txt
Usage
Run the script:

bash
python lead_generator.py
The script will:

Search job boards for relevant positions

Filter for companies open to international candidates

Extract contact information from company websites

Save results to italy_foreign_hiring_companies.csv

Output
The CSV file will contain the following columns:

company_name: Official company name

industry: Target industry category

contact_person: Name of HR manager or recruiter (when found)

position_title: Example job title they're hiring for

email: Contact email (HR or recruiter, when found)

phone: Contact phone (when available)

company_website: Official site URL

job_posting_url: Direct link to the job posting

source_platform: Website where job was found

proof_text: Snippet showing openness to foreign candidates

Customization
To modify search parameters, edit these constants in the script:

INDUSTRY_KEYWORDS: Keywords for each target industry

INTERNATIONAL_KEYWORDS: Phrases indicating openness to foreign workers

JOB_SOURCES: URLs of job boards to scrape

Notes
The script implements polite scraping with delays between requests

A cache file (scrape_cache.json) is maintained to avoid reprocessing known websites

The script can be stopped and resumed without losing progress

text

## Key Features

1. **Multi-Source Scraping**: Targets Indeed, EURES, and Jooble job boards
2. **Smart Filtering**: Uses regex patterns to identify international hiring policies
3. **Contact Extraction**: Crawls company websites for HR/recruiter information
4. **Resilient Operation**: 
   - Retry logic for failed requests
   - User-agent rotation
   - Request throttling
   - Cache system to avoid reprocessing

5. **Structured Output**: CSV formatted for easy import into Excel/Sheets/CRM

The script is production-ready with proper error handling and respects website terms of service with polite scraping practices.
