# Philippine Heat Index Monitoring System

## Overview

This project is an automated heat index monitoring system for the Philippines. It collects real-time heat index data from PAGASA weather stations, processes and maps stations to Philippine regions using geospatial analysis, stores cleaned records in Google Sheets, and prepares the dataset for future dashboard visualization and analytics.

The system is designed to automate the extraction, transformation, and storage of environmental data for monitoring regional heat conditions across the country.

---

## Features

- Automated PAGASA heat index data scraping
- Geospatial mapping of weather stations to Philippine regions
- Rolling 5-day data retention system
- Automated duplicate filtering and data cleaning
- Google Sheets cloud integration
- Scheduled automation using GitHub Actions
- Future-ready integration for Tableau dashboards and visualization

---

## Project Workflow

```text
PAGASA Website
      ↓
Python Scraper
      ↓
Data Cleaning & Transformation
      ↓
Geospatial Region Mapping
      ↓
Google Sheets Database
      ↓
Future Tableau Dashboard Integration
```

---

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Core programming language |
| Pandas | Data processing and cleaning |
| GeoPandas | Geospatial analysis |
| Requests | Web scraping |
| GSpread | Google Sheets integration |
| JSON / GeoJSON | Regional boundary mapping |
| GitHub Actions | Workflow automation |
| Google Sheets API | Cloud data storage |

---

## Repository Structure

```text
├── .github/workflows/
│   └── scrape_update.yml
├── Regions.50m.json
├── UPDATED_EXTRACT_AND_UPLOAD.py
├── gsheets_transfer.ipynb
├── requirements.txt
└── README.md
```

### File Descriptions

- `scrape_update.yml`
  - Automates execution of the pipeline every 6 hours using GitHub Actions.

- `Regions.50m.json`
  - GeoJSON file containing Philippine regional boundaries used for spatial mapping.

- `UPDATED_EXTRACT_AND_UPLOAD.py`
  - Main ETL pipeline script responsible for scraping, processing, spatial mapping, and uploading data.

- `gsheets_transfer.ipynb`
  - Notebook used for Google Sheets integration and testing.

---

## Automation

The project uses GitHub Actions to automatically execute the pipeline every 6 hours.

### Scheduled Workflow

```yaml
cron: '0 */6 * * *'
```

This ensures that the dataset remains continuously updated with recent PAGASA heat index records.

---

## Data Processing Pipeline

### 1. Data Extraction
Heat index data is scraped from PAGASA weather station records.

### 2. Data Transformation
Extracted records are cleaned and converted into structured tabular data.

### 3. Geospatial Mapping
Weather station coordinates are spatially joined with Philippine regional boundaries using GeoPandas.

### 4. Data Storage
Processed records are uploaded to Google Sheets for cloud-based storage and access.

### 5. Rolling Data Retention
Only records from the most recent 5 days are retained to maintain a lightweight and updated dataset.

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-link>
cd <repository-folder>
```

### 2. Create Virtual Environment

#### Windows

```bash
python -m venv sheets
```

Activate environment:

```bash
sheets\Scripts\activate
```

#### Linux / macOS

```bash
python3 -m venv sheets
source sheets/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Required Files

The project requires a Google Service Account credentials file:

```text
credentials.json
```

This file should NOT be uploaded publicly and should instead be configured using GitHub Secrets for deployment workflows.

---

## Future Improvements

- Tableau dashboard integration
- Interactive heat maps
- Regional trend analytics
- Historical heat index archiving
- Predictive heat trend analysis
- Real-time dashboard refresh system

---

## Contributors

- Add contributor names here

---

## Data Source

Heat index data is sourced from PAGASA:

https://www.panahon.gov.ph/heat_index.html
