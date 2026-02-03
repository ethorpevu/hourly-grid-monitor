import pandas as pd
import re
import os

class EIATranslator:
    def __init__(self):
        base_path = os.path.dirname(__file__)
        # Use exact names from your repository
        ba_path = os.path.join(base_path, 'EIA930_Reference_Tables.xlsx - BAs.csv')
        fuel_path = os.path.join(base_path, 'Energy Sources.csv')
        
        self.bas_df = pd.read_csv(ba_path)
        self.fuels_df = pd.read_csv(fuel_path)
        self.base_url = "https://api.eia.gov/v2/electricity/rto/"

    def get_ba_code(self, text):
        text = text.upper()
        for code in self.bas_df['BA Code'].dropna().unique():
            if re.search(rf'\b{code}\b', text): return code
        for _, row in self.bas_df.iterrows():
            if str(row['BA Name']).upper() in text: return row['BA Code']
        return None

    def get_fuel_codes(self, text):
        text = text.upper()
        return [row['Energy Source Code'] for _, row in self.fuels_df.iterrows() 
                if str(row['Energy Source Name']).upper() in text]

    def generate_url(self, query, start_dt, end_dt, api_key):
        query_low = query.lower()
        time_params = f"frequency=hourly&data[0]=value&start={start_dt.strftime('%Y-%m-%dT%H')}&end={end_dt.strftime('%Y-%m-%dT%H')}"
        key_param = f"&api_key={api_key}" if api_key else ""
        suffix = "sort[0][column]=period&sort[0][direction]=desc&offset=0&length=5000"
        
        # Determine Route
        fuel_codes = self.get_fuel_codes(query_low)
        is_interchange = any(word in query_low for word in ["interchange", "sending", "between"])
        
        if is_interchange:
            found_bas = [c for c in self.bas_df['BA Code'].dropna().unique() if re.search(rf'\b{c}\b', query.upper())]
            if len(found_bas) >= 2:
                return f"{self.base_url}interchange-data/data/?{time_params}{key_param}&facets[fromba][]={found_bas[0]}&facets[toba][]={found_bas[1]}&{suffix}", "interchange"

        if fuel_codes or "fuel" in query_low or "source" in query_low:
            ba_code = self.get_ba_code(query_low)
            fuel_facets = "".join([f"&facets[fueltype][]={f}" for f in fuel_codes])
            ba_facet = f"&facets[respondent][]={ba_code}" if ba_code else ""
            return f"{self.base_url}fuel-type-data/data/?{time_params}{key_param}{fuel_facets}{ba_facet}&{suffix}", "fuel"

        # Default to Region Data
        metric_map = {'forecast': 'DF', 'demand': 'D', 'generation': 'NG', 'interchange': 'TI'}
        metric_code = next((v for k, v in metric_map.items() if k in query_low), 'D')
        ba_code = self.get_ba_code(query_low)
        ba_facet = f"&facets[respondent][]={ba_code}" if ba_code else ""
        return f"{self.base_url}region-data/data/?{time_params}{key_param}{ba_facet}&facets[type][]={metric_code}&{suffix}", "region"
