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

HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Referer": "https://www.amc.af.mil/",
}

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
  """Removes extra line breaks and duplicate whitespace."""
  if val is None:
    return ""
  return re.sub(r"\s+", " ", str(val)).strip()


def extract_page_date(page):
  """Extracts the departure date from the top text/header of a slide page."""
  text = page.extract_text() or ""
  header_text = text[:400].upper()

  date_patterns = [
      r"(?:MON|TUE|WED|THU|FRI|SAT|SUN)[A-Z]*,\s*(\d{1,2}\s+[A-Z]{3,9}\s+\d{2,4})",
      (
          r"\b(\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4})\b"
      ),
      (
          r"\b((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{1,2},?\s+\d{2,4})\b"
      ),
      r"\b(\d{1,2}-[A-Z]{3,9}-\d{2,4})\b",
  ]

  for pattern in date_patterns:
    match = re.search(pattern, header_text)
    if match:
      return match.group(1 if "(" in pattern else 0).strip()

  return "Unknown Date"


def parse_flight_table(table, base_name, source_url, page_date):
  """Parses table rows into essential flight destination records."""
  rows = []
  if not table:
    return rows

  for row in table:
    cleaned = [clean_text(cell) for cell in row]
    non_empty = [c for c in cleaned if c]

    if not non_empty:
      continue

    # Skip header, title, or empty schedule notice rows
    row_str = " ".join(non_empty).upper()
    if any(
        h in row_str
        for h in [
            "ROLL CALL",
            "DESTINATION",
            "SEATS",
            "REMARKS",
            "72 HOUR",
            "SCHEDULE",
            "PAGE",
            "NO FLIGHTS",
        ]
    ):
      continue

    # Filter out numeric codes, time strings, or seat indicators to isolate arrival location
    arrival_candidates = [
        c
        for c in non_empty
        if not re.match(r"^\d{4}$", c)
        and not re.search(r"\d+\s*[F|T|P]", c, re.I)
        and c.upper() not in ["TBD", "TBA"]
        and len(c) > 1
    ]

    arrival = (
        arrival_candidates[0]
        if arrival_candidates
        else (non_empty[0] if non_empty else "Unknown Destination")
    )

    rows.append({
        "Departure Date": page_date,
        "Departure Location": base_name,
        "Arrival Location": arrival,
        "Source URL": source_url,
    })

  return rows


def download_and_parse(url, base_name):
  """Downloads PDF via ScraperAPI (if secret set) or directly, then extracts flight board."""
  extracted_rows = []

  api_key = st.secrets.get("SCRAPER_API_KEY", None)
  target_url = (
      f"http://api.scraperapi.com?api_key={api_key}&url={url}"
      if api_key
      else url
  )

  try:
    response = requests.get(target_url, headers=HTTP_HEADERS, timeout=30)
    response.raise_for_status()

    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
      for page in pdf.pages:
        page_date = extract_page_date(page)
        tables = page.extract_tables()

        for table in tables:
          parsed_rows = parse_flight_table(table, base_name, url, page_date)
          extracted_rows.extend(parsed_rows)

    return extracted_rows, None
  except Exception as e:
    return [], str(e)


# Streamlit UI
st.title("✈️ Space-A Flight Board Aggregator")
st.write("Consolidated 72-hour flight routes from monitored terminals.")

st.sidebar.header("Monitored Terminals")
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

if st.button(
    "🚀 Fetch Consolidated Schedules", type="primary", use_container_width=True
):
  active_bases = edited_df.dropna(subset=["URL"]).to_dict("records")

  if not active_bases:
    st.warning("Please enter at least one Base Name and PDF URL.")
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
      with st.expander("⚠️ Fetch Warnings"):
        for e in errors:
          st.write(e)

    if all_rows:
      df = pd.DataFrame(all_rows)

      # Deduplicate exact identical flight rows
      df = df.drop_duplicates()

      # Schema
      final_cols = [
          "Departure Date",
          "Departure Location",
          "Arrival Location",
          "Source URL",
      ]
      df = df[final_cols]

      st.success(f"Extracted {len(df)} flight departures across all bases!")

      # Flight Board Display
      st.subheader("📋 Flight Board")

      unique_dates = df["Departure Date"].unique()
      selected_date = st.selectbox(
          "Filter by Departure Date:", ["All Dates"] + list(unique_dates)
      )

      if selected_date != "All Dates":
        display_df = df[df["Departure Date"] == selected_date]
      else:
        display_df = df

      st.dataframe(
          display_df,
          use_container_width=True,
          column_config={
              "Source URL": st.column_config.LinkColumn("Follow-Up Link")
          },
      )

      # CSV Export
      csv_bytes = df.to_csv(index=False).encode("utf-8")
      st.download_button(
          label="📥 Download Flight Board CSV",
          data=csv_bytes,
          file_name=(
              f"space_a_flight_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
          ),
          mime="text/csv",
          type="primary",
      )
    else:
      st.error(
          "No valid flight schedule rows could be parsed from the specified"
          " URLs."
      )