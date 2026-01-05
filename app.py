import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import re

# Page config
st.set_page_config(page_title="SFD Marine Forecast", layout="wide")

# Custom CSS - subdued blues and greys
st.markdown("""
<style>
.header {background-color: #001f3f; padding: 20px; text-align: center; color: white;}
.box {background-color: #f0f5fa; border-radius: 10px; padding: 15px; margin: 10px 0; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);}
</style>
""", unsafe_allow_html=True)

# Simple centered header
st.markdown("<div class='header'><h1>Seattle Fire Department:<br>Daily Marine Forecast</h1></div>", unsafe_allow_html=True)

# Shift date selector
today = datetime.today().date()
shift_date = st.date_input("Select Shift Start Date (0800)", today)

# Shift start and end times
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

# Fetch NOAA marine forecast
@st.cache_data(ttl=3600)
def fetch_noaa_forecast():
    url = "https://api.weather.gov/zones/marine/PZZ135/forecast"
    headers = {'User-Agent': 'SFD Marine App'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['properties']['periods']
    return []

# Fetch Open-Meteo aggregate wave model
@st.cache_data(ttl=3600)
def fetch_openmeteo_waves(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    variables = "wave_height,wind_wave_height,swell_wave_height"
    url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly={variables}&start_date={start}&end_date={end}&timezone=America%2FLos_Angeles"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        hourly = data.get('hourly', {})
        df = pd.DataFrame({
            'time': pd.to_datetime(hourly.get('time', [])),
            'wave_height_m': hourly.get('wave_height', []),
            'wind_wave_m': hourly.get('wind_wave_height', []),
            'swell_wave_m': hourly.get('swell_wave_height', [])
        })
        df['wave_height_ft'] = (df['wave_height_m'] * 3.281).round(1)
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

# Extraction helper
def extract_from_text(text, keyword):
    match = re.search(rf"{keyword}.*?(\d+[\d-]*\s*(kt|ft|miles|to|around|with|becoming|variable)?)", text, re.IGNORECASE)
    return match.group(1) if match else "N/A"

# Load data
hilo_tides = fetch_tides(shift_date)
noaa_periods = fetch_noaa_forecast()
openmeteo_df = fetch_openmeteo_waves(shift_date)
alerts = fetch_alerts()

# Filter tides within shift
filtered_tides = []
for tide in hilo_tides:
    tide_time = datetime.strptime(tide['t'], "%Y-%m-%d %H:%M")
    if shift_start <= tide_time < shift_end:
        filtered_tides.append(tide)

# Prepare wave ranges per period
def get_wave_range(df, start_hour, end_hour):
    period_df = df[(df['time'].dt.hour >= start_hour) & (df['time'].dt.hour < end_hour)]
    if period_df.empty:
        return "N/A"
    min_h = period_df['wave_height_ft'].min()
    max_h = period_df['wave_height_ft'].max()
    if pd.isna(min_h) or pd.isna(max_h):
        return "N/A"
    return f"{min_h:.1f}–{max_h:.1f} ft" if min_h != max_h else f"{min_h:.1f} ft"

# Weather Alerts
st.markdown("<div class='box'><h3>Weather Alerts</h3>", unsafe_allow_html=True)
if alerts:
    for alert in alerts:
        props = alert['properties']
        st.error(f"**{props['event']}**: {props.get('headline', 'Active Alert')} — {props.get('description', '')}")
else:
    st.success("No active weather alerts for Puget Sound.")
st.markdown("</div>", unsafe_allow_html=True)

# Tides
st.markdown("<div class='box'><h3>Tides</h3>", unsafe_allow_html=True)
if filtered_tides:
    for tide in filtered_tides:
        time_only = tide['t'][11:]
        st.write(f"**{tide['type'].title()} Tide**: {time_only} — {tide['v']} ft")
else:
    st.write("No tides within the 0800–0800 shift period.")
st.markdown("</div>", unsafe_allow_html=True)

# Forecast Periods with integrated wave data
st.markdown("<h3>Forecast Periods (Puget Sound)</h3>", unsafe_allow_html=True)
cols = st.columns(2)
time_periods = [
    ("Morning (0800–1159)", 8, 12),
    ("Afternoon (1200–1659)", 12, 17),
    ("Evening (1700–2359)", 17, 24),
    ("Overnight (0000–0800)", 0, 8)
]

for i, (period_name, start_h, end_h) in enumerate(time_periods):
    with cols[i % 2]:
        st.markdown(f"<div class='box'><h4>{period_name}</h4>", unsafe_allow_html=True)
        
        # Wave information from Open-Meteo
        wave_range = get_wave_range(openmeteo_df, start_h, end_h)
        st.write(f"**Waves (Open-Meteo)**: {wave_range}")
        
        # NOAA text forecast
        if i < len(noaa_periods):
            p = noaa_periods[i]
            text = p['detailedForecast']
            wind = extract_from_text(text, "wind")
            waves_noaa = extract_from_text(text, "wave|seas")
            vis = extract_from_text(text, "visibility")
            st.write(f"**Conditions**: {p.get('shortForecast', text.split('.')[0])}")
            st.write(f"**Wind**: {wind}")
            st.write(f"**Wave Height (NOAA)**: {waves_noaa}")
            st.write(f"**Visibility**: {vis}")
        else:
            st.write("Detailed NOAA forecast unavailable.")
        
        st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.caption("Primary: NOAA | Waves: Open-Meteo aggregate model (global + local wave models) | Cross-check Windy, AccuWeather, etc. | Stay safe!")
