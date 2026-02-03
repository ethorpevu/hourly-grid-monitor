import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from eia_translator import EIATranslator  # Import your separate logic script

# Page Config
st.set_page_config(page_title="EIA Grid Bot", layout="wide")
st.title("⚡ EIA Grid Monitor Query Bot")

# Initialize the translator
translator = EIATranslator()

# Sidebar for Individual API Key
st.sidebar.header("Settings")
api_key = st.sidebar.text_input("Enter your EIA API Key", type="password")
st.sidebar.info("Don't have a key? [Register here](https://www.eia.gov/opendata/register.php)")

# Query Inputs
query = st.text_input("Ask about energy supply/demand (e.g., 'What is the nuclear generation for PJM?')")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", datetime.now() - timedelta(days=2))
with col2:
    end_date = st.date_input("End Date", datetime.now())

if query:
    url = translator.generate_url(query, start_date, end_date, api_key)
    
    if url:
        st.success(f"Targeting API Endpoint")
        
        if st.button("Execute API Call"):
            if not api_key:
                st.error("⚠️ Please enter your API key in the sidebar to execute calls.")
            else:
                with st.spinner("Fetching data..."):
                    try:
                        response = requests.get(url)
                        if response.status_code == 200:
                            data = response.json()
                            df = pd.DataFrame(data['response']['data'])
                            
                            # Clean Data
                            df['period'] = pd.to_datetime(df['period'])
                            df['value'] = pd.to_numeric(df['value'])
                            df = df.sort_values('period')

                            # Visualization & Download
                            st.line_chart(df.set_index('period')['value'])
                            
                            csv_data = df.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="📥 Download for Excel",
                                data=csv_data,
                                file_name=f"eia_export_{datetime.now().strftime('%Y%m%d')}.csv",
                                mime='text/csv'
                            )
                            st.dataframe(df)
                        else:
                            st.error(f"EIA API Error: {response.status_code} - {response.text}")
                    except Exception as e:
                        st.error(f"Failed to fetch data: {e}")
    else:
        st.warning("Could not identify the dataset. Try specifying a BA code (PJM, DUK) or Fuel type.")
