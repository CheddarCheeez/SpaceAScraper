import io
import re
from datetime import datetime

import pandas as pd
import pdfplumber
import requests
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Space-A Flight Aggregator", page_icon="✈️", layout="wide"
)

# Comprehensive Browser Request Headers
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.amc.af.mil/",
    "Connection": "keep-alive",
}

# Default Sample Base URLs
DEFAULT_BASES = [
    {
        "Base Name": "Dover AFB",
        "URL": (
            "https://www.amc.af.mil/Portals/12/AMC%20Tvl%20Pg/Passenger%20Terminals/AMC%20CONUS%20Terminals/Dover%20AFB%20Pax%20Terminal/72%20Hour%20Flight%20Schedule.pdf"
        ),
    },
    {
        "Base Name": "Travis AFB",
        "URL": (
            "https://www.amc.af.mil/Portals/12/AMC%20Tvl%20Pg/Passenger%20Terminals/AMC%20CONUS%20Terminals/Travis%20AFB%20Pax%20Terminal/72%20HOUR%20SCHEDULE.pdf"
        ),
    },
]


def clean_text(val):
  """Removes extra line breaks and duplicate whitespace from table cell text."""
  if val is None:
    return ""
  return re.sub(r"\s+", " ", str(val)).strip()


def download_and_parse(url, base_name):
  """Downloads PDF into memory (via ScraperAPI proxy if configured) and parses tables."""
  timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
  extracted_rows = []

  # Retrieve API key from Streamlit Cloud Secrets (if set)
  api_key = st.secrets.get("SCRAPER_API_KEY", None)

  if api_key:
    # Route through ScraperAPI to bypass cloud IP blocks
    target_url = f"http://api.scraperapi.com?api_key={api_key}&url={url}"
  else:
    # Direct fetch
    target_url = url

  try:
    response = requests.get(target_url, headers=HTTP_HEADERS, timeout=30)
    response.raise_for_status()

    # Parse in-memory PDF bytes
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


# UI Title Block
st.title("✈️ Space-A 72-Hour Flight Aggregator")
st.write(
    "Manage your monitored military passenger terminals and consolidate"
    " 72-hour flight schedules."
)

# Sidebar Base URL Management
st.sidebar.header("Monitored Terminals")
st.sidebar.write("Add, edit, or delete AMC Terminal PDF URLs below:")

if "base_df" not in st.session_state:
  st.session_state.base_df = pd.DataFrame(DEFAULT_BASES)

edited_df = st.sidebar.data_editor(
    st.session_state.base_df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Base Name": st.column_config.TextColumn("Base Name", required=True),
        "URL": st.column_config.LinkColumn("PDF Schedule URL", required=True),
    },
)

st.session_state.base_df = edited_df

# Execution Trigger
if st.button(
    "🚀 Fetch Consolidated Schedules", type="primary", use_container_width=True
):
  active_bases = edited_df.dropna(subset=["URL"]).to_dict("records")

  if not active_bases:
    st.warning(
        "Please enter at least one valid Base Name and PDF URL in the sidebar."
    )
  else:
    all_rows = []
    errors = []

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, base in enumerate(active_bases):
      base_name = base.get("Base Name") or f"Base_{idx+1}"
      url = base.get("URL")

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
      with st.expander("⚠️ Fetching Warnings & Errors"):
        for e in errors:
          st.write(e)

    if all_rows:
      df = pd.DataFrame(all_rows)

      # Reorder metadata columns first
      meta_cols = ["Base_Name", "Page", "Scraped_At", "Source_URL"]
      data_cols = [c for c in df.columns if c not in meta_cols]
      df = df[meta_cols + data_cols]

      st.success(f"Successfully extracted {len(df)} schedule rows!")

      st.subheader("Aggregated Flight Schedules")
      st.dataframe(df, use_container_width=True)

      csv_bytes = df.to_csv(index=False).encode("utf-8")
      st.download_button(
          label="📥 Download Consolidated CSV File",
          data=csv_bytes,
          file_name=(
              f"space_a_schedules_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
          ),
          mime="text/csv",
          type="primary",
      )
    else:
      st.error(
          "No schedule table data could be extracted from the specified URLs."
      )
