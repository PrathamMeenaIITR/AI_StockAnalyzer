import requests
import pandas as pd
from openai import OpenAI
import time, datetime

pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
# from transformers import Any

# Base URL for MF API
BASE_URL = "https://api.mfapi.in/mf/"
AI_API_TOKEN = "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"
AI_ANALYSIS_URL = "https://integrate.api.nvidia.com/v1"

def fetch_mutual_fund_data(scheme_code: str,start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Fetch mutual fund data for a given scheme code.
    Example scheme codes: 118834, 100027, etc.
    """
    url = f"{BASE_URL}{scheme_code}"
    if start_date and end_date:
        url = f"{BASE_URL}{scheme_code}?startDate={start_date}&endDate={end_date}"

    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        # Extract NAV data
        nav_data = data.get("data", [])
        # Convert to DataFrame
        df = pd.DataFrame(nav_data)
        # Convert NAV column to numeric
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
        # Convert date column to datetime
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        return df
    else:
        raise Exception(f"Failed to fetch data: {response.status_code}")
    
def prepare_ai_payload(
    # ticker: str,
    mf_df: pd.DataFrame
    # fundamentals: Dict[str, Any],
    # technical: pd.DataFrame
) -> str:
    """Serialise data into JSON‑compatible structures for the AI endpoint."""
    # Convert OHLCV to list of dicts (ISO timestamp string)
    mf_records = [
        {
            "date": row['date'],
            "nav": row["nav"],
        }
        for ts, row in mf_df.iterrows()
    ]

    # Technical – only latest values for brevity
    # latest_tech = technical.iloc[-1].to_dict() if not technical.empty else {}

    payload = {
        "ohlcv": mf_records
        }
    # J_format = """{"stock_id":"","analysis_period":{"start_date":"","end_date":""},"current_price":"","performance_metrics":{"absolute_return":{"1_day":"","1_week":"","1_month":"","3_months":"","6_months":"","1_year":"","2_years":"","3_years":""},"annualized_return":{"1_year":"","2_years":"","3_years":""},"volatility":{"1_month":"","3_months":"","1_year":"","3_years":""},"sharpe_ratio":{"1_year":"","3_years":""},"max_drawdown":{"1_year":"","3_years":""}},"trend_analysis":{"short_term":"","medium_term":"","long_term":""},"support_resistance":{"immediate_support":"","immediate_resistance":"","strong_support":"","strong_resistance":""},"moving_averages":{"50_day":"","100_day":"","200_day":""},"relative_strength":{"vs_nifty50":{"1_year":"","3_years":""},"vs_sector":{"1_year":"","3_years":""}},"risk_assessment":"","recommendation":"","key_observations":["","","","",""]}""" 
    # prompt = f"""You are a financial analyst. Provide a concise analysis in json format for the 
    # Indian stock **{scheme_code}**, PFB a python dictionary containing histocial data {payload}.
    # Do not include any explanatory text or comments, only return the JSON in following format: 
    # {J_format}
    prompt = f"""You are a financial analyst. Provide a concise analysis in json format for the 
    Indian stock **{scheme_code}**, PFB a python dictionary containing histocial data {payload}."""

    return prompt

def call_ai_analysis(session: requests.Session, prompt: str) -> str:
    
    try:
        client = OpenAI(
        base_url = AI_ANALYSIS_URL,
        api_key = AI_API_TOKEN
        )

        completion = client.chat.completions.create(
        model="mistralai/devstral-2-123b-instruct-2512",
        messages=[{"role":"user","content":prompt}],
        temperature=0.15,
        top_p=0.95,
        max_tokens=8192,
        seed=42,
        stream=True
        )

        response_text = ""
        print(datetime.datetime.now())
        for chunk in completion:
            if chunk.choices and chunk.choices[0].delta.content is not None:
                # print(chunk.choices[0].delta.content, end="")
                response_text += chunk.choices[0].delta.content
            # print('Model is Thinking...' + time.sleep(5))
        
        print(datetime.datetime.now())
        return response_text.strip()
    except Exception as exc:
        print(f"AI analysis failed for {scheme_code}: {exc}")
        raise

def parse_json_to_dataframe(data: dict) -> pd.DataFrame:
    """
    Parse a nested JSON-like dict into a flat Pandas DataFrame.
    Handles nested dictionaries and lists.
    """
    # Flatten JSON using pandas.json_normalize
    df = pd.json_normalize(data, sep="_")

    # If there are list fields (like key_observations), expand them
    # if "key_observations" in df.columns:
    #     # Convert list into multiple rows
    #     observations = pd.DataFrame(df["key_observations"].iloc[0], columns=["key_observations"])
    #     # Drop original list column and merge
    #     df = df.drop(columns=["key_observations"])
    #     df = pd.concat([df, observations], axis=1)

    return df

import json

def convert_to_json(json_string):
  # Remove the triple quotes and extra whitespace
  cleaned = json_string.replace('json','').strip().strip('"""').strip("```")
  # Parse the JSON string
  return json.loads(cleaned)

# Example usage
if __name__ == "__main__":
    scheme_code = "118663"  # SBI Bluechip Fund - Direct Plan
    df = fetch_mutual_fund_data(scheme_code,start_date="2023-01-01", end_date="2026-03-31")
    print(df.head())  # Show first 5 rows
    p_load = prepare_ai_payload(df)
    # print(p_load)
    responseText = call_ai_analysis(requests.Session(), p_load)
    # responseText = call_ai_analysis(requests.Session(), 'Summarize the last msgs i sent')
    # responseDf = parse_json_to_dataframe(convert_to_json(responseText))
    # print(responseDf.head())
    # print(responseText.replace("```", ""))
    print(responseText)
