import streamlit as st
import pandas as pd
import re
import requests
from datetime import datetime, timedelta
from io import BytesIO

# Load reference data
@st.cache_data
def load_data():
    bas = pd.read_csv('EIA930_Reference_Tables.xlsx - BAs.csv')
    fuels = pd.read_csv('EIA930_Reference_Tables.xlsx - Energy Sources.csv')
    return bas, fuels

bas_df, fuels_df = load_data()

def get_ba_code(text):
    text = text.upper()
    for code in bas_df['BA Code'].dropna().unique():
        if re.search(rf'\b{code}\b', text):
            return code
    for _, row in bas_df.iterrows():
        if str(row['BA Name']).upper() in text:
            return row['BA Code']
    return None

def get_fuel_codes(text):
    text = text.upper()
    return [row['Energy Source Code'] for _, row in fuels_df.iterrows() if str(row['Energy Source Name']).upper() in text]

def generate_eia_url(query, start_dt, end_dt, api_key):
    query_low = query.lower()
    base_params = f"frequency=hourly&data[0]=value&start={start_dt.strftime('%Y-%m-%dT%H')}&end={end_dt.strftime('%Y-%m-%dT%H')}"
    if api_key:
        base_params += f"&api_key={api_key}"
    
    suffix = "sort[0][column]=period&sort[0][direction]=desc&offset=0&length=5000"
    
    # Routing Logic
    # 1. Interchange
    if any(word in query_low for word in ["interchange", "sending", "receiving", "between"]):
        found_bas = [c for c in bas_df['BA Code'].dropna().unique() if re.search(rf'\b{c}\b', query.upper())]
        if len(found_bas) >= 2:
            return f"https://api.eia.gov/v2/electricity/rto/interchange-data/data/?{base_params}&facets[fromba][]={found_bas[0]}&facets[toba][]={found_bas[1]}&{suffix}"

    # 2. Fuel Type
    fuel_codes = get_fuel_codes(query_low)
    if fuel_codes or "fuel" in query_low or "source" in query_low:
        ba_code = get_ba_code(query_low)
        fuel_facets = "".join([f"&facets[fueltype][]={f}" for f in fuel_codes])
        ba_facet = f"&facets[respondent][]={ba_code}" if ba_code else ""
        return f"https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/?{base_params}{fuel_facets}{ba_facet}&{suffix}"

    # 3. Region Data
    metric_map = {'forecast': 'DF', 'demand': 'D', 'generation': 'NG', 'interchange': 'TI'}
    metric_code = next((v for k, v in metric_map.items() if k in query_low), None)
    ba_code = get_ba_code(query_low)
    if ba_code or metric_code:
        ba_facet = f"&facets[respondent][]={ba_code}" if ba_code else ""
        type_facet = f"&facets[type][]={metric_code}" if metric_code else ""
        return f"https://api.eia.gov/v2/electricity/rto/region-data/data/?{base_params}{ba_facet}{type_facet}&{suffix}"

    return None

# --- UI Setup ---
st.set_page_config(page_title="EIA Grid Bot", layout="wide")
st.title("⚡ EIA Grid Monitor Query Bot")

# Sidebar for Config
st.sidebar.header("Configuration")
api_key = st.sidebar.text_input("Enter EIA API Key", type="password", help="Get one at eia.gov/opendata/register.php")

# Main Interface
query = st.text_input("Query (e.g., 'What is the nuclear generation for PJM?')")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start", datetime.now() - timedelta(days=7))
with col2:
    end_date = st.date_input("End", datetime.now())

if query:
    url = generate_eia_url(query, start_date, end_date, api_key)
    
    if url:
        st.info(f"Generated API URL: {url}")
        
        if st.button("🚀 Fetch Data"):
            if not api_key:
                st.error("Please enter an API Key in the sidebar first.")
            else:
                with st.spinner("Fetching from EIA..."):
                    try:
                        response = requests.get(url)
                        data = response.json()
                        df = pd.DataFrame(data['response']['data'])
                        
                        # Data Cleaning for Excel & Charting
                        df['period'] = pd.to_datetime(df['period'])
                        df['value'] = pd.to_numeric(df['value'])
                        df = df.sort_values('period')

                        # Display Visuals
                        st.subheader("Data Preview")
                        st.line_chart(df.set_index('period')['value'])
                        
                        # Download Section
                        csv = df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download CSV for Excel",
                            data=csv,
                            file_name=f"eia_data_{datetime.now().strftime('%Y%m%d')}.csv",
                            mime='text/csv',
                        )
                        st.dataframe(df)
                        
                    except Exception as e:
                        st.error(f"Error fetching data: {e}")
    else:
        st.warning("Could not identify the dataset. Try specifying a Balancing Authority (e.g. 'PJM') or Energy Source (e.g. 'Solar').")
