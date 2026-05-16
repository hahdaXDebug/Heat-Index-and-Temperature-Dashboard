import os
import json
import pandas as pd
import geopandas as gpd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import re
from datetime import datetime, timedelta

# =========================================================
# CONFIGURATION
# =========================================================

SHEET_NAME = "Philippine Heat Index Google Sheet"
MAP_FILE = "Regions.50m.json"
CREDS_FILE = "credentials.json"
PAGASA_URL = "https://www.panahon.gov.ph/heat_index.html"

# =========================================================
# NORMALIZE STATION NAMES
# =========================================================

def normalize_name(name):

    if pd.isna(name):
        return ""

    return (
        str(name)
        .strip()
        .lower()
        .replace("  ", " ")
    )

# =========================================================
# MAIN PIPELINE
# =========================================================

def run_pipeline():

    print(f"--- Process Started: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")

    # =========================================================
    # 1. SCRAPE LATEST DATA
    # =========================================================

    print("Step 1: Scraping latest data from PAGASA...")

    try:

        html = requests.get(PAGASA_URL, timeout=15).text

        stations_raw = re.findall(
            r'\{"sitename".*?"data_as_of".*?\}',
            html
        )

        new_data = []

        for s in stations_raw:

            try:

                j = json.loads(s)

                if j.get("data"):

                    latest = j["data"][-1]

                    new_data.append({
                        "sitename": j["sitename"],
                        "site_key": normalize_name(j["sitename"]),
                        "lat": float(j["lat"]),
                        "lng": float(j["lng"]),
                        "heat_index": float(latest["heat_index"]),
                        "observed_at": latest["observed_at"]
                    })

            except:
                continue

        new_df = pd.DataFrame(new_data)

        if new_df.empty:
            print("No new data found on PAGASA site. Aborting.")
            return

    except Exception as e:

        print(f"Scrape failed: {e}")
        return

    # =========================================================
    # 2. MAP STATIONS TO REGIONS
    # =========================================================

    print(f"Step 2: Mapping stations using {MAP_FILE}...")

    try:

        ph_regions = gpd.read_file(MAP_FILE)

        gdf_stations = gpd.GeoDataFrame(
            new_df,
            geometry=gpd.points_from_xy(
                new_df.lng,
                new_df.lat
            ),
            crs="EPSG:4326"
        )

        gdf_enriched = gpd.sjoin(
            gdf_stations,
            ph_regions,
            how="left",
            predicate="within"
        )

        final_batch = gdf_enriched[
            [
                'REGION',
                'sitename',
                'site_key',
                'lat',
                'lng',
                'heat_index',
                'observed_at'
            ]
        ].fillna("Unknown")

    except Exception as e:

        print(f"Spatial Mapping failed: {e}")
        return

    # =========================================================
    # 3. CONNECT TO GOOGLE SHEETS
    # =========================================================

    print("Step 3: Connecting to Google Sheets...")

    try:

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        # GitHub Actions
        if "GOOGLE_CREDENTIALS_JSON" in os.environ:

            creds_dict = json.loads(
                os.environ["GOOGLE_CREDENTIALS_JSON"]
            )

            creds = ServiceAccountCredentials.from_json_keyfile_dict(
                creds_dict,
                scope
            )

        # Local machine
        else:

            creds = ServiceAccountCredentials.from_json_keyfile_name(
                CREDS_FILE,
                scope
            )

        client = gspread.authorize(creds)

        spreadsheet = client.open(SHEET_NAME)

        sheet = spreadsheet.get_worksheet(0)

        # =========================================================
        # 4. LOAD EXISTING DATA
        # =========================================================

        print("Step 4: Managing 5-day rolling window...")

        existing_data = sheet.get_all_records()

        old_df = pd.DataFrame(existing_data)

        # =========================================================
        # ENSURE REQUIRED COLUMNS EXIST
        # =========================================================

        required_cols = [
            'REGION',
            'sitename',
            'site_key',
            'lat',
            'lng',
            'heat_index',
            'observed_at'
        ]

        for col in required_cols:

            if col not in old_df.columns:
                old_df[col] = ""

        # =========================================================
        # NORMALIZE EXISTING STATION NAMES
        # =========================================================

        old_df["site_key"] = old_df["sitename"].apply(
            normalize_name
        )

        # =========================================================
        # RECOVER MISSING COORDINATES
        # =========================================================

        station_lookup = final_batch[
            ['site_key', 'lat', 'lng']
        ].drop_duplicates()

        old_df = old_df.merge(
            station_lookup,
            on='site_key',
            how='left',
            suffixes=('', '_new')
        )

        # Fill empty coordinates only
        old_df['lat'] = old_df['lat'].replace("", pd.NA)
        old_df['lng'] = old_df['lng'].replace("", pd.NA)

        old_df['lat'] = old_df['lat'].fillna(
            old_df['lat_new']
        )

        old_df['lng'] = old_df['lng'].fillna(
            old_df['lng_new']
        )

        # Cleanup
        old_df = old_df.drop(
            columns=['lat_new', 'lng_new'],
            errors='ignore'
        )

        # Keep structure
        old_df = old_df[required_cols]

        # =========================================================
        # COMBINE OLD + NEW
        # =========================================================

        combined_df = pd.concat(
            [final_batch, old_df],
            ignore_index=True
        )

        # Remove duplicates
        combined_df = combined_df.drop_duplicates(
            subset=['sitename', 'observed_at']
        )

        # =========================================================
        # FILTER LAST 5 DAYS
        # =========================================================

        combined_df['date_dt'] = pd.to_datetime(
            combined_df['observed_at'],
            dayfirst=True,
            errors='coerce'
        )

        cutoff = datetime.now() - timedelta(days=5)

        filtered_df = combined_df[
            combined_df['date_dt'] >= cutoff
        ].copy()

        # Sort newest first
        filtered_df = filtered_df.sort_values(
            by='date_dt',
            ascending=False
        )

        # Remove helper column
        filtered_df = filtered_df.drop(
            columns=['date_dt']
        )

        # Remove helper matching key before upload
        filtered_df = filtered_df.drop(
            columns=['site_key'],
            errors='ignore'
        )

        # =========================================================
        # 5. UPLOAD TO GOOGLE SHEETS
        # =========================================================

        print("Step 5: Uploading updated dataset...")

        upload_data = [
            filtered_df.columns.values.tolist()
        ] + filtered_df.astype(str).values.tolist()

        sheet.clear()

        sheet.update(
            range_name='A1',
            values=upload_data
        )

        print("\n--- SUCCESS! ---")
        print("Sheet updated successfully.")
        print(f"Total records in 5-day window: {len(filtered_df)}")

    except Exception as e:

        print(f"Google Sheets update failed: {e}")

# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    run_pipeline()
