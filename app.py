import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import re

# Page config
st.set_page_config(page_title="SFD Marine Forecast", layout="wide")

# Custom CSS
st.markdown("""
<style>
.header {background-color: #001f3f; padding: 20px; text-align: center; color: white;}
.box {background-color: #f0f5fa; border-radius: 10px; padding: 20px; margin: 10px 0; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);}
.noaa-text {white-space: pre-wrap; line-height: 1.6; font-size: 0.95rem;}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("<div class='header'><h1>Seattle Fire Department:<br>Daily Marine Forecast</h1></div>", unsafe_allow_html=True)

# Auto-default to today
today = datetime.today().date()
shift_date = st.date_input("Select Shift Start Date (0800)", value=today)

# Shift times
shift_start = datetime(shift_date.year, shift_date.month, shift_date.day, 8, 0)
shift_end = shift_start + timedelta(days=1)

# Fetch tides
@st.cache_data(ttl=3600)
def fetch_tides(date):
    begin = date.strftime("%Y%m%d")
    end = (date + timedelta(days=1)).strftime("%Y%m%d")
    hilo_url = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=9447130&product=predictions&datum=MLLW&units=english&time_zone=lst_ldt&interval=hilo&format=json&begin_date={begin}&end_date={end}"
    response = requests.get(hilo_url)
    if response.status_code == 200:
        return response.json().get('predictions', [])
    return []

# Fetch NOAA text forecast
@st.cache_data(ttl=3600)
def fetch_noaa_forecast():
    url = "https://forecast.weather.gov/product.php?site=SEW&issuedby=SEW&product=CWF&format=txt&version=1&glossary=0"
    response = requests.get(url)
    if response.status_code == 200:
        text = response.text
        match = re.search(r'(PZZ135-.*?)(\n\nPZZ\d{3}-|\Z)', text, re.DOTALL)
        if match:
            zone_text = match.group(1).strip()
            periods = re.split(r'\n\.', zone_text)
            parsed = []
            for p in periods[1:]:
                lines = p.strip().split('\n', 1)
                if len(lines) == 2:
                    period_name = lines[0].strip().strip('.').upper()
                    detail = lines[1].strip()
                    parsed.append((period_name, detail))
            return parsed
    return []

# Fetch Open-Meteo Atmospheric (wind, temp, precip, visibility)
@st.cache_data(ttl=3600)
def fetch_openmeteo_atmospheric(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    hourly_vars = "temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,visibility,cloud_cover"
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly={hourly_vars}&start_date={start}&end_date={end}&timezone=America%2FLos_Angeles&wind_speed_unit=kn&temperature_unit=fahrenheit&precipitation_unit=inch&visibility_unit=mile"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get('hourly', {})
        df = pd.DataFrame({
            'time': pd.to_datetime(data.get('time', [])),
            'temp_f': [round(x) if x is not None else None for x in data.get('temperature_2m', [])],
            'wind_speed_kt': [round(x) if x is not None else None for x in data.get('wind_speed_10m', [])],
            'wind_dir': data.get('wind_direction_10m', []),
            'wind_gust_kt': [round(x) if x is not None else None for x in data.get('wind_gusts_10m', [])],
            'precip_in': data.get('precipitation', []),
            'visibility_mi': data.get('visibility', []),
            'cloud_cover': data.get('cloud_cover', [])
        })
        return df
    return pd.DataFrame()

# Fetch Open-Meteo Marine Waves
@st.cache_data(ttl=3600)
def fetch_openmeteo_waves(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    hourly_vars = "wave_height,wind_wave_height,swell_wave_height"
    url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly={hourly_vars}&start_date={start}&end_date={end}&timezone=America%2FLos_Angeles"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get('hourly', {})
        df = pd.DataFrame({
            'time': pd.to_datetime(data.get('time', [])),
            'wave_height_ft': [(round(x * 3.281, 1) if x is not None else None) for x in data.get('wave_height', [])]
        })
        return df
    return pd.DataFrame()

# Fetch alerts
@st.cache_data(ttl=1800)
def fetch_alerts():
    url = "https://api.weather.gov/alerts/active?zone=PZZ135"
    headers = {'User-Agent': 'SFD Marine App'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('features', [])
    return []

# Load data
hilo_tides = fetch_tides(shift_date)
noaa_periods = fetch_noaa_forecast()
atm_df = fetch_openmeteo_atmospheric(shift_date)
wave_df = fetch_openmeteo_waves(shift_date)
alerts = fetch_alerts()

# Merge atmospheric and waves on time (for aligned summaries)
if not atm_df.empty and not wave_df.empty:
    openmeteo_df = pd.merge(atm_df, wave_df[['time', 'wave_height_ft']], on='time', how='left')
else:
    openmeteo_df = atm_df if not atm_df.empty else wave_df

# Filter tides
filtered_tides = [tide for tide in hilo_tides if shift_start <= datetime.strptime(tide['t'], "%Y-%m-%d %H:%M") < shift_end]

# Period summary helper (now with waves from marine)
def period_summary(df, start_h, end_h):
    period_df = df[(df['time'].dt.hour >= start_h) & (df['time'].dt.hour < end_h)]
    if period_df.empty:
        return {k: "N/A" for k in ['wave', 'wind_speed', 'wind_dir', 'gust', 'precip', 'vis', 'temp']}
    summary = {
        'wave': f"{period_df['wave_height_ft'].min():.1f}–{period_df['wave_height_ft'].max():.1f} ft" if 'wave_height_ft' in period_df.columns and period_df['wave_height_ft'].notna().any() else "N/A",
        'wind_speed': f"{period_df['wind_speed_kt'].min():.0f}–{period_df['wind_speed_kt'].max():.0f} kt" if period_df['wind_speed_kt'].notna().any() else "N/A",
        'wind_dir': f"{int(period_df['wind_dir'].mode()[0])}°" if not period_df['wind_dir'].mode().empty else "Var",
        'gust': f"{period_df['wind_gust_kt'].max():.0f} kt" if period_df['wind_gust_kt'].notna().any() else "N/A",
        'precip': f"{period_df['precip_in'].sum():.2f} in" if period_df['precip_in'].sum() > 0 else "None",
        'vis': f"{period_df['visibility_mi'].min():.1f}–{period_df['visibility_mi'].max():.1f} mi" if period_df['visibility_mi'].notna().any() else "N/A",
        'temp': f"{period_df['temp_f'].min():.0f}–{period_df['temp_f'].max():.0f} °F" if period_df['temp_f'].notna().any() else "N/A"
    }
    return summary

# Alerts/Tides/Periods (same as before, with improved NOAA breaks)

# ... (rest of display code identical to previous version)

st.markdown("<div class='box'><h3>Weather Alerts</h3>", unsafe_allow_html=True)
# ... (alerts)

st.markdown("<div class='box'><h3>Tides</h3>", unsafe_allow_html=True)
# ... (tides list)

# Periods
# ... (use period_summary with the merged openmeteo_df)

# In NOAA display:
st.markdown("<div class='noaa-text'><strong>NOAA Details:</strong><br>" + noaa_text.replace('. ', '.<br>') + "</div>", unsafe_allow_html=True)

# Footer same
