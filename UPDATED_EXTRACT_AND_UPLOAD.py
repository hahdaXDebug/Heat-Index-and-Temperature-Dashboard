import os
import json
import pandas as pd
import geopandas as gpd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---
SHEET_NAME = "Philippine Heat Index Google Sheet"
MAP_FILE = "Regions.50m.json"
CREDS_FILE = "credentials.json"
PAGASA_URL = "https://www.panahon.gov.ph/heat_index.html"

def run_pipeline():
    print(f"--- Process Started: {datetime.now().strftime('%Y-%m-%d %H:%M')} ---")

    # 1. SCRAPE LATEST DATA
    print("Step 1: Scraping latest data from PAGASA...")
    try:
        html = requests.get(PAGASA_URL, timeout=15).text
        stations_raw = re.findall(r'\{"sitename".*?"data_as_of".*?\}', html)
        new_data = []
        for s in stations_raw:
            try:
                j = json.loads(s)
                if j.get("data"):
                    latest = j["data"][-1]
                    new_data.append({
                        "sitename": j["sitename"],
                        "lat": float(j["lat"]),
                        "lng": float(j["lng"]),
                        "heat_index": latest["heat_index"],
                        "observed_at": latest["observed_at"]
                    })
            except: continue
        new_df = pd.DataFrame(new_data)
        if new_df.empty:
            print("No new data found on PAGASA site. Aborting.")
            return
    except Exception as e:
        print(f"Scrape failed: {e}")
        return

    # 2. SPATIAL JOIN (Mapping to Regions)
    print(f"Step 2: Mapping stations using {MAP_FILE}...")
    try:
        ph_regions = gpd.read_file(MAP_FILE)
        gdf_stations = gpd.GeoDataFrame(
            new_df, geometry=gpd.points_from_xy(new_df.lng, new_df.lat), crs="EPSG:4326"
        )
        # Spatial join with your specific 'REGION' column from the JSON
        gdf_enriched = gpd.sjoin(gdf_stations, ph_regions, how="left", predicate="within")
        
        # Prepare the final scraped batch
        final_batch = gdf_enriched[['REGION', 'sitename', 'heat_index', 'observed_at']].fillna("Unknown")
    except Exception as e:
        print(f"Spatial Mapping failed: {e}")
        return

    # 3. CONNECT TO GOOGLE SHEETS
    print(f"Step 3: Connecting to Google Sheets...")
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

        # AUTHENTICATION SWITCH
        if "GOOGLE_CREDENTIALS_JSON" in os.environ:
            # Runs on GitHub Actions
            creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            # Runs on your Laptop
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
            
        client = gspread.authorize(creds)
        spreadsheet = client.open(SHEET_NAME)
        sheet = spreadsheet.get_worksheet(0) 

        # 4. ROLLING 5-DAY LOGIC
        print("Step 4: Managing 5-day rolling window...")
        existing_data = sheet.get_all_records()
        old_df = pd.DataFrame(existing_data)

        # Merge Old + New and remove duplicates (checks site + time)
        combined_df = pd.concat([old_df, final_batch], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=['sitename', 'observed_at'])

        # Convert to datetime for the 5-day "cutoff"
        combined_df['date_dt'] = pd.to_datetime(combined_df['observed_at'], errors='coerce')
        
        # Calculate cutoff (Current time - 5 days)
        cutoff = datetime.now() - timedelta(days=5)
        filtered_df = combined_df[combined_df['date_dt'] >= cutoff].copy()
        
        # Sort so newest data is always at the top of the sheet
        filtered_df = filtered_df.sort_values(by='date_dt', ascending=False)
        filtered_df = filtered_df.drop(columns=['date_dt']) 

        # 5. UPLOAD
        sheet.clear()
        upload_data = [filtered_df.columns.values.tolist()] + filtered_df.astype(str).values.tolist()
        sheet.update('A1', upload_data)
        
        print(f"--- SUCCESS! ---")
        print(f"Sheet updated. Total records in 5-day window: {len(filtered_df)}")

    except Exception as e:
        print(f"Google Sheets update failed: {e}")

if __name__ == "__main__":
    run_pipeline()
