"""
Debug script — prints the raw extracted text from an episode page so we can
see exactly what the tracklist parser is (or isn't) matching.

Usage:
    python debug_tracklist.py [URL]

Defaults to a known 2025 episode if no URL is given.
"""

import sys
import re
import requests
from bs4 import BeautifulSoup
from config import USER_AGENT

DEFAULT_URL = "https://communionafterdark.squarespace.com/listennow/3ezn5p2b6wcsc2bejcttr3npktp6xd"

url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
print(f"Fetching: {url}\n")

resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
soup = BeautifulSoup(resp.text, "lxml")

content_root = (
    soup.find("article")
    or soup.find("main")
    or soup.find(class_=re.compile(r"entry-content|post-content|sqs-block"))
    or soup.body
)

print("=== RAW TEXT (first 4000 chars) ===\n")
print(content_root.get_text(separator="\n")[:4000])

print("\n\n=== LINES CONTAINING A TIMESTAMP-LIKE PATTERN ===\n")
for line in content_root.get_text(separator="\n").splitlines():
    if re.search(r"\d{1,2}:\d{2}", line):
        print(repr(line))
