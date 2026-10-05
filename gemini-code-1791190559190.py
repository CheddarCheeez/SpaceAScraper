import io
import re
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import pdfplumber
import requests
import streamlit as st

# Page setup
st.set_page_config(
    page_title="Space-A Flight Aggregator",
    page_icon="✈️",
    layout="wide"
)

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

DEFAULT_BASES = [
    {"Base Name": "Dover AFB", "URL": "https://www.amc.af.mil/Portals/12/Dover_72HR.pdf"},
    {"Base Name": "Travis AFB", "URL": "https://www.amc.af.mil/Portals/12/Travis_72HR.pdf"},
]

def clean_text(val):
    """Removes extra line breaks and whitespace."""
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()


Conversation with Gemini
I'd like you to help me develop either a script, app, or service that can visit my local military Space Available (Space A) websites, grab their 72-hour or 3-day schedule, and display the conjugate information in an easy to view table or file. Can we do this?

Yes, building an automated script or service to aggregate military Space Available (Space-A) flight schedules is entirely feasible. Air Mobility Command (AMC) passenger terminals publish unclassified 72-hour schedules on public .mil pages (AFPIMS) and official social media channels.   
Air Mobility Command - AF.mil

However, because bases do not publish these schedules via a single centralized REST API, your pipeline must handle varied document formats.

Data Sources & Technical Challenges
Source Type	Base Examples	Primary Format	Automation Strategy
AMC AFPIMS Sites	Dover AFB, Travis AFB, Ramstein AB	Direct PDF Downloads	Fetch URLs via HTTP requests or playwright, parse tables with pdfplumber.
Social Media / Facebook	NAS Jacksonville, Norfolk	Image files (.jpg/.png) or text posts	Scrape public graph pages or use Meta Graph API; run OCR (tesseract/easyocr).
Specialized Sites	BWI, Seattle-Tacoma (SEATAC)	Dynamic HTML Tables	Web scrapers like BeautifulSoup or playwright.
Note: Operational Support Airlift (JOSAC) schedules require a Common Access Card (CAC) on internal networks, but standard 72-hour AMC passenger terminal schedules are fully public.

Recommended System Architecture
[ AMC Terminal .mil Sites / Social Pages ]
                   │
                   ▼
       ┌──────────────────────┐
       │ Ingestion & Scraper  │ (Requests / Playwright)
       └───────────┬──────────┘
                   │
                   ▼
       ┌──────────────────────┐
       │ Extractor Engine     │ (pdfplumber for PDFs / Tesseract for Images)
       └───────────┬──────────┘
                   │
                   ▼
       ┌──────────────────────┐
       │ Data Normalizer      │ (Standardize UTC/Local Time, Seats, Destinations)
       └───────────┬──────────┘
                   │
                   ▼
  ┌─────────────────────────────────┐
  │ Consolidated Table / Streamlit  │ (CSV, JSON, Streamlit Dashboard, or CLI)
  └─────────────────────────────────┘
Starter Script Prototype (Python)
This Python prototype uses requests and pdfplumber to download an AMC terminal PDF schedule, extract the structured flight table, and clean it into a unified pandas DataFrame.

Python
import re
import pandas as pd
import pdfplumber
import requests

# Example header to prevent .mil WAF blocks
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

def download_pdf(url: str, save_path: str = "temp_schedule.pdf") -> str:
    """Downloads a public Space-A schedule PDF from an AMC base site."""
    response = requests.get(url, headers=HEADERS, timeout=15)
    response.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(response.content)
    return save_path

def parse_space_a_pdf(pdf_path: str) -> pd.DataFrame:
    """Extracts tables from an AMC PDF schedule and standardizes the columns."""
    raw_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Clean newlines and null entries
                    cleaned_row = [
                        cell.replace("\n", " ").strip() if cell else ""
                        for cell in row
                    ]
                    if any(cleaned_row):
                        raw_data.append(cleaned_row)

    if not raw_data:
        return pd.DataFrame()

    df = pd.DataFrame(raw_data)

    # Simple heuristic to identify header vs data rows
    # Expected standard fields: Date, Roll Call Time, Destination, Seats
    df.columns = [f"Col_{i}" for i in range(df.shape[1])]
    return df

# Example Usage:
# pdf_file = download_pdf("https://www.amc.af.mil/Portals/.../72HR_Schedule.pdf")
# df = parse_space_a_pdf("temp_schedule.pdf")
# print(df.to_string())
Key Data Pipeline Steps
URL Indexing: Build a configuration mapping base terminal names to their public 72-hour schedule PDF/page links.

Date & Time Normalization: Schedules use local terminal times or Julian dates; convert all Roll Call times into UTC and standard ISO timestamps.

Destination Mapping: Convert inconsistent destination names (e.g., "KCHS", "Charleston AFB", "CHS") into standardized ICAO base codes.

Change Detection: Compare PDF hash signatures to ensure you only parse new updates, as bases refresh schedules irregularly.

Want me to write a full script that targets specific bases and exports to Streamlit or CSV?

Yes
Yeah write a full script that exports to csv but I want it to first ask the user running it for a list of the base's amc URLs that it wants daily updates from

Your Python script is ready

PY icon
space_a_scraper
 PY 
Overview of space_a_scraper.py
This standalone Python script interactively collects, downloads, parses, and consolidates 72-hour Space Available schedules from military terminal websites into a single CSV spreadsheet.

Key Features
Interactive AMC URL Prompts:

Asks you to enter the AMC Terminal schedule URLs (e.g., PDF links from Dover AFB, Travis AFB, Ramstein AB, etc.).

Asks for an optional base name for each URL (or auto-derives one from the link).

Persistent Configuration (space_a_urls.json):

Saves your list of URLs to a local JSON file so you don't have to re-type them on daily runs.

Automatically detects saved URLs on startup and prompts: "Use these saved URLs for today's run? (y/n)".

Automated PDF Scraping & Parsing:

Includes custom browser headers to prevent HTTP 403 blocks from military Web Application Firewalls (WAF).

Uses pdfplumber to extract multi-page schedule tables.

CSV Export (consolidated_space_a_schedule.csv):

Normalizes text, adds metadata (Base_Name, Page, Scraped_At, Source_URL), and exports the merged dataset to CSV.

How to Install & Run
Install Prerequisites:
Run the following in your terminal or command prompt:

Bash
pip install pdfplumber pandas requests
Run the Script:

Bash
python space_a_scraper.py
Example Interactive Workflow
==================================================
      Space-A AMC Schedule Aggregator Script      
==================================================

--- Interactive AMC URL Setup ---
Enter the AMC Terminal 72-hour schedule PDF URLs you wish to monitor.
Enter 'done' when finished.

Enter URL #1 (or 'done' to finish): https://www.amc.af.mil/Portals/12/Dover_72HR.pdf
Enter Base Name for this URL (press Enter to auto-derive): Dover AFB
  [+] Added: Dover AFB (https://www.amc.af.mil/Portals/12/Dover_72HR.pdf)

Enter URL #2 (or 'done' to finish): https://www.amc.af.mil/Portals/12/Travis_72HR.pdf
Enter Base Name for this URL (press Enter to auto-derive): Travis AFB
  [+] Added: Travis AFB (https://www.amc.af.mil/Portals/12/Travis_72HR.pdf)

Enter URL #3 (or 'done' to finish): done

Would you like to save this list for future daily updates? (y/n, default: y): y
[+] Saved URL configuration to 'space_a_urls.json'

[+] Starting daily fetch for 2 bases...

[1/2] Processing: Dover AFB ...
  [✓] Successfully extracted 14 table entries.
[2/2] Processing: Travis AFB ...
  [✓] Successfully extracted 19 table entries.

==================================================
[✓] SUCCESS: Aggregated 33 total schedule rows.
[✓] Consolidated output saved to: consolidated_space_a_schedule.csv
==================================================
Code Architecture (space_a_scraper.py)
Python
"""
Space-A Schedule Aggregator & CSV Exporter

This script interactively asks the user for AMC Terminal PDF/Web URLs,
downloads the schedules, parses flight tables using pdfplumber,
and exports a consolidated CSV report.
"""

import json
import os
import re

from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import pdfplumber
import requests

CONFIG_FILE = "space_a_urls.json"
OUTPUT_CSV = "consolidated_space_a_schedule.csv"

# Custom headers to mimic a web browser and bypass WAF blocks
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def load_saved_urls():
  """Loads saved base configuration from JSON if present."""
  if os.path.exists(CONFIG_FILE):
    try:
      with open(CONFIG_FILE, "r") as f:
        return json.load(f)
    except Exception as e:
      print(f"[-] Warning: Could not read {CONFIG_FILE}: {e}")
  return []


def save_urls(base_configs):
  """Saves base configuration list to JSON for future daily runs."""
  try:
    with open(CONFIG_FILE, "w") as f:
      json.dump(base_configs, f, indent=4)
    print(f"[+] Saved URL configuration to '{CONFIG_FILE}'")
  except Exception as e:
    print(f"[-] Failed to save URL configuration: {e}")


def derive_base_name(url):
  """Generates a friendly base name from the URL path if not specified."""
  parsed = urlparse(url)
  path_parts = [p for p in parsed.path.split("/") if p]
  for part in path_parts:
    if "af" in part.lower() or "ab" in part.lower() or "base" in part.lower():
      return part.replace(".pdf", "").replace("-", " ").title()
  if len(path_parts) > 0:
    return path_parts[-1].replace(".pdf", "").replace("-", " ").title()
  return parsed.netloc


def prompt_user_for_urls():
  """Interactively asks the user for AMC URLs and optional base names."""
  base_configs = []

  # Check if saved config exists
  saved = load_saved_urls()
  if saved:
    print("\n--- Saved Base URLs Found ---")
    for idx, cfg in enumerate(saved, 1):
      print(f"  {idx}. {cfg['name']} -> {cfg['url']}")

    use_saved = (
        input("\nUse these saved URLs for today's run? (y/n, default: y): ")
        .strip()
        .lower()
    )
    if use_saved in ("", "y", "yes"):
      return saved

  print("\n--- Interactive AMC URL Setup ---")
  print("Enter the AMC Terminal 72-hour schedule PDF URLs you wish to monitor.")
  print("Enter 'done' when finished.\n")

  count = 1
  while True:
    url = input(f"Enter URL #{count} (or 'done' to finish): ").strip()
    if url.lower() == "done":
      break
    if not url.startswith("http://") and not url.startswith("https://"):
      print("  [!] Please enter a valid HTTP/HTTPS URL.")
      continue

    custom_name = input(
        f"Enter Base Name for this URL (press Enter to auto-derive): "
    ).strip()
    base_name = custom_name if custom_name else derive_base_name(url)

    base_configs.append({"name": base_name, "url": url})
    print(f"  [+] Added: {base_name} ({url})\n")
    count += 1

  if base_configs:
    save_choice = (
        input(
            "Would you like to save this list for future daily updates? (y/n,"
            " default: y): "
        )
        .strip()
        .lower()
    )
    if save_choice in ("", "y", "yes"):
      save_urls(base_configs)

  return base_configs


def download_file(url, target_path="temp_schedule.pdf"):
  """Downloads a public schedule PDF file."""
  try:
    response = requests.get(url, headers=HTTP_HEADERS, timeout=20)
    response.raise_for_status()
    with open(target_path, "wb") as f:
      f.write(response.content)
    return True
  except Exception as e:
    print(f"  [-] Failed to download from {url}: {e}")
    return False


def clean_text(val):
  """Cleans table cell text by removing duplicate whitespace and line breaks."""
  if val is None:
    return ""
  return re.sub(r"\s+", " ", str(val)).strip()


def parse_schedule_pdf(pdf_path, base_name, source_url):
  """Extracts tables from an AMC PDF schedule and returns formatted row dicts."""
  extracted_rows = []
  timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  try:
    with pdfplumber.open(pdf_path) as pdf:
      for page_num, page in enumerate(pdf.pages, 1):
        tables = page.extract_tables()
        for table in tables:
          if not table:
            continue

          for row in table:
            cleaned_row = [clean_text(cell) for cell in row]
            if not any(cleaned_row):
              continue

            row_dict = {
                "Base_Name": base_name,
                "Page": page_num,
                "Source_URL": source_url,
                "Scraped_At": timestamp,
            }

            for idx, val in enumerate(cleaned_row, 1):
              row_dict[f"Col_{idx}"] = val

            extracted_rows.append(row_dict)

  except Exception as e:
    print(f"  [-] Error parsing PDF {pdf_path}: {e}")

  return extracted_rows


def main():
  print("==================================================")
  print("      Space-A AMC Schedule Aggregator Script      ")
  print("==================================================")

  base_configs = prompt_user_for_urls()

  if not base_configs:
    print("\n[-] No URLs provided. Exiting script.")
    return

  print(f"\n[+] Starting daily fetch for {len(base_configs)} bases...\n")
  all_schedules = []

  for idx, base in enumerate(base_configs, 1):
    print(f"[{idx}/{len(base_configs)}] Processing: {base['name']} ...")
    temp_file = f"temp_base_{idx}.pdf"

    success = download_file(base["url"], temp_file)
    if success:
      rows = parse_schedule_pdf(temp_file, base["name"], base["url"])
      if rows:
        all_schedules.extend(rows)
        print(f"  [✓] Successfully extracted {len(rows)} table entries.")
      else:
        print(
            "  [!] Warning: Downloaded file, but found no standard table"
            " entries."
        )

      if os.path.exists(temp_file):
        os.remove(temp_file)
    else:
      print(f"  [x] Skipped {base['name']} due to download failure.")

  if all_schedules:
    df = pd.DataFrame(all_schedules)

    meta_cols = ["Base_Name", "Page", "Scraped_At", "Source_URL"]
    data_cols = [c for c in df.columns if c not in meta_cols]
    df = df[meta_cols + data_cols]

    df.to_csv(OUTPUT_CSV, index=False)
    print("\n==================================================")
    print(f"[✓] SUCCESS: Aggregated {len(df)} total schedule rows.")
    print(f"[✓] Consolidated output saved to: {OUTPUT_CSV}")
    print("==================================================")

    print("\nData Preview (First 5 Rows):")
    print(df.head().to_string())
  else:
    print("\n[-] No schedule data could be extracted from the specified URLs.")


if __name__ == "__main__":
  main()
How can I run this in Android on my phone? Where should I save the .py file and how can I execute it?

To run Python scripts on Android, you have two primary options: Pydroid 3 (easiest, built-in visual editor) or Termux (full Linux command line).

Option 1: Pydroid 3 (Recommended & Easiest)
Pydroid 3 is a graphical Python IDE for Android that includes a built-in terminal and package installer.

1. Where to Save the .py File
Download or save space_a_scraper.py into your Android phone's Download folder (or any internal storage folder you can easily access with a file manager).

2. Install Required Packages
Install Pydroid 3 from the Google Play Store.

Open Pydroid 3.

Tap the Menu icon (☰) in the top-left corner → tap Pip.

Tap Quick Install or switch to the Install tab.

Type each library name and tap Install:

requests

pdfplumber

pandas

3. How to Execute the Script
In Pydroid 3, tap the Folder icon in the top right → Open → navigate to your Download folder and select space_a_scraper.py. (Alternatively, copy and paste the script code directly into the main editor window).

Tap the big yellow Play Button at the bottom right.

The interactive terminal screen will launch directly on your phone:

Type in your Space-A PDF URLs when prompted.

Type done when finished.

Where outputs are saved: The resulting space_a_urls.json and consolidated_space_a_schedule.csv files will automatically be saved in the exact same directory where space_a_scraper.py is located.

Option 2: Termux (For Advanced / Terminal Users)
If you prefer a lightweight Linux command-line environment on Android:

1. Setup Environment
Download and install Termux (available via F-Droid).

Open Termux and run:

Bash
pkg update && pkg upgrade -y
pkg install python tur-repo -y
pkg install python-pandas -y
pip install requests pdfplumber
2. Give Termux File Storage Access
Run this command to allow Termux to access your phone’s internal storage:

Bash
termux-setup-storage
(Tap Allow on the Android permission popup).

3. Where to Save & How to Execute
Move space_a_scraper.py into your phone's Download folder.

In Termux, navigate to the Downloads directory:

Bash
cd ~/storage/downloads
Run the script:

Bash
python space_a_scraper.py
Can I run it natively as an application? Can an iPhone user use this script?

Running as a Native Mobile App
Out of the box, Python scripts cannot run as standalone .apk (Android) or .ipa (iOS) installer files because Python requires an interpreter environment to run pdfplumber and pandas.

However, you can turn this into a native-feeling application using two different approaches:

1. The Cloud Web App / PWA Approach (Recommended)
This is the cleanest, cross-platform solution for both Android and iPhone:

Convert the script to Streamlit or Flask: Build a lightweight web interface for the script using Streamlit.

Host it on a free cloud server: Deploy it to Streamlit Community Cloud, Render, or Replit.

Add to Home Screen: Open the web app URL in Chrome (Android) or Safari (iPhone), tap Share / Menu → Add to Home Screen.

The Result: It opens in full-screen mode like a native app, requires zero local setup on your phone, and can automatically run scheduled daily updates in the cloud.

2. Package as a Native APK/IPA
If you strictly want a standalone mobile installer file:

Frameworks: Tools like Kivy/Buildozer or BeeWare (Briefcase) can wrap Python code and package it into native Android (.apk) or iOS (.app) binaries.

Trade-off: You will need a desktop PC/Mac to run the compilation and build environment (Android SDK or Xcode) to produce the final installer file.

Running the Script on an iPhone (iOS)
Yes, an iPhone user can run this script locally. Because iOS is more locked down than Android, you cannot use Termux, but you have several iOS-native alternatives:

Option 1: Pyto IDE (Best GUI Experience)
Pyto is a Python 3 IDE built specifically for iOS available on the App Store.

Download Pyto from the iOS App Store.

Open Pyto, go to Settings → PyPi (or open the built-in terminal), and run:

Bash
pip install requests pdfplumber pandas
Create a new file, paste space_a_scraper.py, and tap Run.

The output CSV file will be saved directly into the Files app (On My iPhone/Pyto).

Option 2: a-Shell (Best Terminal Experience)
a-Shell is a local Unix terminal emulator for iOS.

Install a-Shell from the App Store.

Open a-Shell and install the packages:

Bash
pip install requests pdfplumber pandas
Place space_a_scraper.py into the a-Shell directory inside your iPhone Files app.

Run the script:

Bash
python space_a_scraper.py
Option 3: iOS Shortcuts Automation
Once installed in a-Shell or Pyto, an iPhone user can use the native Apple Shortcuts app to set up an automated trigger (e.g., "Run python space_a_scraper.py every morning at 7:00 AM"), making the process hands-free.

Help me convert this to the streamlit or flask web app option. Which do you recommend?

Streamlit is strongly recommended for this project.

Why Streamlit over Flask?
Zero Web Development Required: Streamlit is 100% Python. Flask requires writing HTML, CSS templates, JavaScript, and manual route management.

Built-in Data & Export UI: Streamlit natively renders interactive Pandas DataFrames, progress spinners, and direct CSV download buttons with single-line commands.

Instant Free Mobile Deployment: You can host a Streamlit app for free on Streamlit Community Cloud directly from a GitHub repository, then tap "Add to Home Screen" on Android or iPhone to use it like a native mobile app.

Complete Streamlit Application (app.py)
This web app lets you edit target URLs directly in an interactive browser table, runs the extraction in memory (without creating temporary local disk files), renders the schedule table, and provides a CSV download button.

Python
import io
import re
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd
import pdfplumber
import requests
import streamlit as st

import os



# Page setup
st.set_page_config(
    page_title="Space-A Flight Aggregator",
    page_icon="✈️",
    layout="wide"
)

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

DEFAULT_BASES = [
    {"Base Name": "Dover AFB", "URL": "https://www.amc.af.mil/Portals/12/Dover_72HR.pdf"},
    {"Base Name": "Travis AFB", "URL": "https://www.amc.af.mil/Portals/12/Travis_72HR.pdf"},
]

def clean_text(val):
    """Removes extra line breaks and whitespace."""
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val)).strip()

def download_and_parse(url, base_name):
    """Downloads PDF into memory and parses schedule tables using pdfplumber."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    extracted_rows = []

    try:
        response = requests.get(url, headers=HTTP_HEADERS, timeout=20)
        response.raise_for_status()

        # Parse in-memory bytes without writing temporary files
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        cleaned_row = [clean_text(cell) for cell in row]
                        if not any(cleaned_row):
                            continue
                        
                        row_dict = {
                            "Base_Name": base_name,
                            "Page": page_num,
                            "Scraped_At": timestamp,
                            "Source_URL": url,
                        }
                        for idx, val in enumerate(cleaned_row, 1):
                            row_dict[f"Col_{idx}"] = val
                        extracted_rows.append(row_dict)

        return extracted_rows, None
    except Exception as e:
        return [], str(e)

# UI Layout
st.title("✈️ Space-A 72-Hour Flight Aggregator")
st.write("Manage your monitored military passenger terminals and consolidate 72-hour flight schedules.")

st.sidebar.header("Base Configuration")
st.sidebar.write("Add, edit, or delete AMC Terminal URLs below:")

# Interactive table for managing URLs in the sidebar
if "base_df" not in st.session_state:
    st.session_state.base_df = pd.DataFrame(DEFAULT_BASES)

edited_df = st.sidebar.data_editor(
    st.session_state.base_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Base Name": st.column_config.TextColumn(required=True),
        "URL": st.column_config.LinkColumn(required=True)
    }
)

st.session_state.base_df = edited_df

# Main Action Button
if st.button("🚀 Fetch Consolidated Schedules", type="primary", use_container_width=True):
    active_bases = edited_df.dropna(subset=["URL"]).to_dict("records")
    
    if not active_bases:
        st.warning("Please add at least one valid base URL in the sidebar.")
    else:
        all_rows = []
        errors = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, base in enumerate(active_bases):
            base_name = base["Base Name"] or "Unknown Base"
            url = base["URL"]

            status_text.text(f"Fetching schedule for {base_name}...")
            rows, err = download_and_parse(url, base_name)
            
            if err:
                errors.append(f"**{base_name}**: {err}")
            else:
                all_rows.extend(rows)

            progress_bar.progress((idx + 1) / len(active_bases))

        status_text.empty()
        progress_bar.empty()

        if errors:
            with st.expander("⚠️ Download/Parsing Warnings"):
                for e in errors:
                    st.write(e)

        if all_rows:
            df = pd.DataFrame(all_rows)
            
            # Reorder meta columns first
            meta_cols = ["Base_Name", "Page", "Scraped_At", "Source_URL"]
            data_cols = [c for c in df.columns if c not in meta_cols]
            df = df[meta_cols + data_cols]

            st.success(f"Successfully extracted {len(df)} flight table entries!")

            # Display Data Table
            st.subheader("Aggregated Flight Schedule")
            st.dataframe(df, use_container_width=True)

            # Export to CSV Button
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Consolidated CSV File",
                data=csv_bytes,
                file_name=f"space_a_schedules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                type="primary"
            )
        else:
            st.error("No valid table data could be extracted from the specified URLs.")

def download_and_parse(url, base_name):
    """Downloads PDF using a proxy to bypass .mil AWS IP blocks."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    extracted_rows = []

    # Check if ScraperAPI key is available in Streamlit Secrets
    api_key = st.secrets.get("SCRAPER_API_KEY", None)

    if api_key:
        # Route through ScraperAPI to bypass cloud IP blocks
        target_url = f"http://api.scraperapi.com?api_key={api_key}&url={url}"
    else:
        # Direct fetch (fallback for local execution)
        target_url = url

    try:
        response = requests.get(target_url, headers=HTTP_HEADERS, timeout=30)
        response.raise_for_status()

        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables()
                for table in tables:
                    if not table:
                        continue
                    for row in table:
                        cleaned_row = [clean_text(cell) for cell in row]
                        if not any(cleaned_row):
                            continue
                        
                        row_dict = {
                            "Base_Name": base_name,
                            "Page": page_num,
                            "Scraped_At": timestamp,
                            "Source_URL": url,
                        }
                        for idx, val in enumerate(cleaned_row, 1):
                            row_dict[f"Col_{idx}"] = val
                        extracted_rows.append(row_dict)

        return extracted_rows, None
    except Exception as e:
        return [], str(e)

# UI Layout
st.title("✈️ Space-A 72-Hour Flight Aggregator")
st.write("Manage your monitored military passenger terminals and consolidate 72-hour flight schedules.")

st.sidebar.header("Base Configuration")
st.sidebar.write("Add, edit, or delete AMC Terminal URLs below:")

# Interactive table for managing URLs in the sidebar
if "base_df" not in st.session_state:
    st.session_state.base_df = pd.DataFrame(DEFAULT_BASES)

edited_df = st.sidebar.data_editor(
    st.session_state.base_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Base Name": st.column_config.TextColumn(required=True),
        "URL": st.column_config.LinkColumn(required=True)
    }
)

st.session_state.base_df = edited_df

# Main Action Button
if st.button("🚀 Fetch Consolidated Schedules", type="primary", use_container_width=True):
    active_bases = edited_df.dropna(subset=["URL"]).to_dict("records")
    
    if not active_bases:
        st.warning("Please add at least one valid base URL in the sidebar.")
    else:
        all_rows = []
        errors = []
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx, base in enumerate(active_bases):
            base_name = base["Base Name"] or "Unknown Base"
            url = base["URL"]

            status_text.text(f"Fetching schedule for {base_name}...")
            rows, err = download_and_parse(url, base_name)
            
            if err:
                errors.append(f"**{base_name}**: {err}")
            else:
                all_rows.extend(rows)

            progress_bar.progress((idx + 1) / len(active_bases))

        status_text.empty()
        progress_bar.empty()

        if errors:
            with st.expander("⚠️ Download/Parsing Warnings"):
                for e in errors:
                    st.write(e)

        if all_rows:
            df = pd.DataFrame(all_rows)
            
            # Reorder meta columns first
            meta_cols = ["Base_Name", "Page", "Scraped_At", "Source_URL"]
            data_cols = [c for c in df.columns if c not in meta_cols]
            df = df[meta_cols + data_cols]

            st.success(f"Successfully extracted {len(df)} flight table entries!")

            # Display Data Table
            st.subheader("Aggregated Flight Schedule")
            st.dataframe(df, use_container_width=True)

            # Export to CSV Button
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Consolidated CSV File",
                data=csv_bytes,
                file_name=f"space_a_schedules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                type="primary"
            )
        else:
            st.error("No valid table data could be extracted from the specified URLs.")
