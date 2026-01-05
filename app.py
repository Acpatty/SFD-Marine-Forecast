import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import re

# Page config
st.set_page_config(page_title="SFD Marine Forecast", layout="wide")

# Custom CSS - more compact and readable
st.markdown("""
<style>
.header {background-color: #001f3f; padding: 15px; text-align: center; color: white; margin-bottom: 20px;}
.box {background-color: #f0f5fa; border-radius: 10px; padding: 12px; margin: 8px 0; box-shadow: 2px 2px 6px rgba(0,0,0,0.1);}
.noaa-text {white-space: pre-wrap; line-height: 1.4; font-size: 0.9rem; margin-top: 8px;}
h3, h4 {margin: 0 0 8px 0;}
</style>
""", unsafe_allow_html=True)

# Compact header
st.markdown("<div class='header'><h2>Seattle Fire Department<br>Daily Marine Forecast</h2></div>", unsafe_allow_html=True)

# Auto-default to today
today = datetime.today().date()
shift_date = st.date_input("Shift Start Date (0800)", value=today)

# Shift times
shift_start = datetime(shift_date.year, shift_date.month, shift_date.day, 8, 0)
shift_end = shift_start + timedelta(days=1)

# WMO Weather Code mapping (shortened descriptions)
WMO_CODES = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Heavy freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Heavy showers",
    82: "Violent showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "TS with hail",
    99: "TS with heavy hail"
}

def get_condition_description(code):
    return WMO_CODES.get(code, "Unknown")

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
            period_matches = re.finditer(r'^\.([A-Z ]+?)\.\.\.(.*?)(?=^\.|$)', zone_text, re.MULTILINE | re.DOTALL)
            parsed = []
            for m in period_matches:
                period_name = m.group(1).strip().upper()
                detail = m.group(2).strip()
                parsed.append((period_name, detail))
            return parsed
    return []

# Fetch Open-Meteo Atmospheric + weather_code
@st.cache_data(ttl=3600)
def fetch_openmeteo_atmospheric(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    hourly_vars = "temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,visibility,cloud_cover,weather_code"
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly={hourly_vars}&start_date={start}&end_date={end}&timezone=America%2FLos_Angeles&wind_speed_unit=kn&temperature_unit=fahrenheit&precipitation_unit=inch"
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
            'visibility_m': data.get('visibility', []),
            'cloud_cover': data.get('cloud_cover', []),
            'weather_code': data.get('weather_code', [])
        })
        df['visibility_mi'] = (df['visibility_m'] / 1609.34).round(1).clip(upper=20.0)
        df = df.drop(columns=['visibility_m'])
        return df
    return pd.DataFrame()

# Fetch Open-Meteo Waves
@st.cache_data(ttl=3600)
def fetch_openmeteo_waves(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    hourly_vars = "wave_height"
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

# Merge data
if not atm_df.empty and not wave_df.empty:
    openmeteo_df = pd.merge(atm_df, wave_df[['time', 'wave_height_ft']], on='time', how='left')
else:
    openmeteo_df = atm_df if not atm_df.empty else pd.DataFrame()

# Filter tides
filtered_tides = []
for tide in hilo_tides:
    tide_time = datetime.strptime(tide['t'], "%Y-%m-%d %H:%M")
    if shift_start <= tide_time < shift_end:
        filtered_tides.append(tide)

# Period summary (compact)
def period_summary(df, start_h, end_h):
    period_df = df[(df['time'].dt.hour >= start_h) & (df['time'].dt.hour < end_h)]
    if period_df.empty:
        return {k: "N/A" for k in ['condition', 'wave', 'wind', 'gust', 'precip', 'vis', 'temp']}
    mode_code = period_df['weather_code'].mode()
    condition = get_condition_description(int(mode_code[0])) if not mode_code.empty else "N/A"
    summary = {
        'condition': condition,
        'wave': f"{period_df['wave_height_ft'].min():.1f}–{period_df['wave_height_ft'].max():.1f} ft" if 'wave_height_ft' in period_df.columns and period_df['wave_height_ft'].notna().any() else "N/A",
        'wind': f"{period_df['wind_speed_kt'].min():.0f}–{period_df['wind_speed_kt'].max():.0f} kt" if period_df['wind_speed_kt'].notna().any() else "N/A",
        'dir': f"{int(period_df['wind_dir'].mode()[0])}°" if not period_df['wind_dir'].mode().empty else "Var",
        'gust': f"{period_df['wind_gust_kt'].max():.0f} kt" if period_df['wind_gust_kt'].notna().any() else "N/A",
        'precip': f"{period_df['precip_in'].sum():.2f} in" if period_df['precip_in'].sum() > 0 else "None",
        'vis': f"{period_df['visibility_mi'].min():.1f}–{period_df['visibility_mi'].max():.1f} mi" if period_df['visibility_mi'].notna().any() else "N/A",
        'temp': f"{period_df['temp_f'].min():.0f}–{period_df['temp_f'].max():.0f} °F" if period_df['temp_f'].notna().any() else "N/A"
    }
    return summary

# Alerts (compact)
if alerts:
    st.error("Active Alerts")
    for alert in alerts:
        props = alert['properties']
        st.error(f"**{props['event']}**: {props.get('headline', '')}")
else:
    st.success("No active alerts")

# Tides (compact)
st.markdown("<div class='box'><h3>Tides</h3>", unsafe_allow_html=True)
if filtered_tides:
    for tide in filtered_tides:
        time_only = tide['t'][11:16]  # Just HH:MM
        st.write(f"**{tide['type'].title()}**: {time_only} — {tide['v']} ft")
else:
    st.write("No tides in shift")
st.markdown("</div>", unsafe_allow_html=True)

# Forecast Periods (condensed layout)
if shift_date > today + timedelta(days=7):
    st.warning("Limited detail beyond 7 days")
st.markdown("<h3>Forecast Periods</h3>", unsafe_allow_html=True)
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
        summary = period_summary(openmeteo_df, start_h, end_h)
        st.write(f"**Cond**: {summary['condition']}")
        st.write(f"**Waves**: {summary['wave']}")
        st.write(f"**Wind**: {summary['wind']} ({summary['dir']}), gusts {summary['gust']}")
        st.write(f"**Precip**: {summary['precip']}")
        st.write(f"**Vis**: {summary['vis']}")
        st.write(f"**Temp**: {summary['temp']}")
        
        if i < len(noaa_periods):
            _, noaa_text = noaa_periods[i]
            formatted = noaa_text.replace('. ', '.<br>')
            st.markdown(f"<div class='noaa-text'><strong>NOAA:</strong><br>{formatted}</div>", unsafe_allow_html=True)
        else:
            st.write("_NOAA detail unavailable_")
        st.markdown("</div>", unsafe_allow_html=True)

# Compact footer
st.caption("Open-Meteo aggregate + NOAA | Use near dates for full detail | Stay safe")
