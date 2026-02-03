import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
from eia_translator import EIATranslator

st.set_page_config(page_title="EIA Grid Bot", layout="wide")
st.title("⚡ EIA Grid Monitor Query Bot")

translator = EIATranslator()

# Sidebar
st.sidebar.header("Settings")
api_key = st.sidebar.text_input("Enter your EIA API Key", type="password")

# Inputs
query = st.text_input("Query (e.g., 'Natural gas, nuclear and solar for PJM')")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start", datetime.now() - timedelta(days=2))
with col2:
    end_date = st.date_input("End", datetime.now())

if query:
    url_data = translator.generate_url(query, start_date, end_date, api_key)
    
    if url_data:
        url, route_type = url_data
        if st.button("🚀 Execute API Call"):
            if not api_key:
                st.error("Please enter an API key.")
            else:
                try:
                    res = requests.get(url).json()
                    df = pd.DataFrame(res['response']['data'])
                    df['period'] = pd.to_datetime(df['period'])
                    df['value'] = pd.to_numeric(df['value'])

                    # --- 1. GENERATION CHARTING ---
                    st.subheader("Electricity Generation / Demand (MWh)")
                    
                    # Pivot based on route
                    pivot_col = 'fueltype' if route_type == 'fuel' else ('type' if route_type == 'region' else 'toba')
                    chart_df = df.pivot(index='period', columns=pivot_col, values='value').fillna(0)
                    
                    show_total = st.checkbox("Show Total Line", value=False)
                    if show_total:
                        chart_df['TOTAL'] = chart_df.sum(axis=1)
                    
                    st.line_chart(chart_df)

                    # --- 2. EMISSIONS LOGIC ---
                    if route_type == 'fuel':
                        st.divider()
                        # Map emissions factors
                        factors = translator.fuels_df.set_index('Energy Source Code')['Emissions Factor (tons CO2e/MWh)'].to_dict()
                        
                        # Calculate hourly emissions
                        # Create a copy of the values and multiply by factors
                        emissions_df = chart_df.drop(columns=['TOTAL'], errors='ignore').copy()
                        for col in emissions_df.columns:
                            factor = factors.get(col, 0)
                            emissions_df[col] = emissions_df[col] * factor
                        
                        hourly_total_emissions = emissions_df.sum(axis=1) # Tons
                        hourly_total_gen = chart_df.drop(columns=['TOTAL'], errors='ignore').sum(axis=1)
                        intensity = (hourly_total_emissions / hourly_total_gen).fillna(0)
                        
                        total_period_emissions = hourly_total_emissions.sum() / 1000 # 1000s of tons
                        
                        e_col1, e_col2 = st.columns([3, 1])
                        with e_col1:
                            st.subheader("Emissions Intensity (tons CO2e/MWh)")
                            st.area_chart(intensity)
                        with e_col2:
                            st.metric("Total Emissions", f"{total_period_emissions:,.2f}k Tons CO2e")
                            st.caption("Calculated based on generation mix and EIA emissions factors.")

                    # --- 3. EXPORT ---
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download Raw Data", data=csv, file_name="eia_data.csv", mime='text/csv')
                    
                except Exception as e:
                    st.error(f"Error: {e}")
