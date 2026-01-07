import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import re
import math

# Page config
st.set_page_config(page_title="SFD Marine Forecast", layout="wide")

# Custom CSS - compact, no header images
st.markdown("""
<style>
.header {background-color: #001f3f; padding: 20px; text-align: center; color: white; margin-bottom: 20px;}
.box {background-color: #f0f5fa; border-radius: 8px; padding: 10px; margin: 6px 0; box-shadow: 2px 2px 5px rgba(0,0,0,0.1);}
.noaa-text {white-space: pre-wrap; line-height: 1.3; font-size: 0.88rem; margin-top: 6px;}
h3, h4 {margin: 0 0 6px 0;}
p {margin: 4px 0 !important;}
</style>
""", unsafe_allow_html=True)

# Simple header (no images)
st.markdown("<div class='header'><h2>SFD Daily Marine Forecast</h2></div>", unsafe_allow_html=True)

# Auto-default to today
today = datetime.today().date()
shift_date = st.date_input("Shift Start (0800)", value=today)

# Shift times
shift_start = datetime(shift_date.year, shift_date.month, shift_date.day, 8, 0)
shift_end = shift_start + timedelta(days=1)

# WMO Weather Code mapping (short)
WMO_CODES = {
    0: "Clear", 1: "Mst clear", 2: "P cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog", 51: "Lt drizzle", 53: "Drizzle", 55: "Hvy drizzle",
    61: "Lt rain", 63: "Rain", 65: "Hvy rain", 80: "Showers", 95: "TS"
}

def get_condition_description(code):
    return WMO_CODES.get(code, "N/A")

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
                if detail:
                    parsed.append((period_name, detail))
            return parsed
    return []

# Fetch Open-Meteo Atmospheric (removed timezone to avoid 400 error)
@st.cache_data(ttl=3600)
def fetch_openmeteo_atmospheric(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    hourly_vars = "temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,visibility,cloud_cover,weather_code"
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly={hourly_vars}&start_date={start}&end_date={end}&wind_speed_unit=kn&temperature_unit=fahrenheit&precipitation_unit=inch"
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

# Fetch Open-Meteo Waves + Water Temp
@st.cache_data(ttl=3600)
def fetch_openmeteo_marine(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    hourly_vars = "wave_height,sea_surface_temperature"
    url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly={hourly_vars}&start_date={start}&end_date={end}&temperature_unit=fahrenheit"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get('hourly', {})
        df = pd.DataFrame({
            'time': pd.to_datetime(data.get('time', [])),
            'wave_height_ft': [(round(x * 3.281, 1) if x is not None else None) for x in data.get('wave_height', [])],
            'water_temp_f': [round(x) if x is not None else None for x in data.get('sea_surface_temperature', [])]
        })
        return df
    return pd.DataFrame()

# Fetch Sunrise/Sunset + Moon Phase + UV Index
@st.cache_data(ttl=3600)
def fetch_astronomy(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    daily_vars = "sunrise,sunset,moon_phase,uv_index_max"
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily={daily_vars}&start_date={start}&end_date={end}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json().get('daily', {})
        if data:
            sunrise = data['sunrise'][0][11:] if data['sunrise'] else "N/A"
            sunset = data['sunset'][0][11:] if data['sunset'] else "N/A"
            moon_phase = data.get('moon_phase', [None])[0]
            uv_max = data.get('uv_index_max', [None])[0]
            return sunrise, sunset, moon_phase, uv_max
    return "N/A", "N/A", None, None

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
marine_df = fetch_openmeteo_marine(shift_date)
sunrise, sunset, moon_phase_code, uv_max = fetch_astronomy(shift_date)
alerts = fetch_alerts()

# Merge data
if not atm_df.empty and not marine_df.empty:
    openmeteo_df = pd.merge(atm_df, marine_df[['time', 'wave_height_ft', 'water_temp_f']], on='time', how='left')
else:
    openmeteo_df = atm_df if not atm_df.empty else pd.DataFrame()

# Filter tides
filtered_tides = [tide for tide in hilo_tides if shift_start <= datetime.strptime(tide['t'], "%Y-%m-%d %H:%M") < shift_end]

# Period summary
def period_summary(df, start_h, end_h):
    period_df = df[(df['time'].dt.hour >= start_h) & (df['time'].dt.hour < end_h)]
    if period_df.empty:
        return {k: "N/A" for k in ['condition', 'wave', 'wind', 'gust', 'precip', 'vis', 'temp', 'water_temp']}
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
        'temp': f"{period_df['temp_f'].min():.0f}–{period_df['temp_f'].max():.0f} °F" if period_df['temp_f'].notna().any() else "N/A",
        'water_temp': f"{period_df['water_temp_f'].mean():.0f} °F" if 'water_temp_f' in period_df.columns and period_df['water_temp_f'].notna().any() else "N/A"
    }
    return summary

# Moon phase description
def get_moon_phase_desc(code):
    if code is None:
        return "N/A", "N/A"
    phase = code
    illumination = round((1 - math.cos(2 * math.pi * phase)) / 2 * 100)
    names = ["New Moon", "Waxing Crescent", "First Quarter", "Waxing Gibbous", "Full Moon", "Waning Gibbous", "Last Quarter", "Waning Crescent"]
    index = min(int(phase * 8), 7)
    name = names[index]
    return name, f"{illumination}% Illuminated"

# UV Index description
def get_uv_desc(index):
    if index is None:
        return "N/A", "N/A"
    index = round(index)
    levels = ["Low", "Low", "Moderate", "Moderate", "Moderate", "High", "High", "Very High", "Very High", "Very High", "Extreme"]
    level = levels[min(index, 10)]
    return index, level

# Alerts
if alerts:
    st.error("Active Alerts")
    for alert in alerts:
        props = alert['properties']
        st.error(f"{props['event']}: {props.get('headline', '')}")
else:
    st.success("No active alerts")

# Tides + Sunrise/Sunset + Moon + UV + Water Temp
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown("<div class='box'><h3>Tides</h3>", unsafe_allow_html=True)
    if filtered_tides:
        for tide in filtered_tides:
            time_only = tide['t'][11:16]
            arrow = "↑" if tide['type'].upper() == "H" else "↓"
            st.write(f"{arrow} {time_only} — {tide['v']} ft")
    else:
        st.write("No tides in shift")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='box'><h3>Sunrise / Sunset</h3>", unsafe_allow_html=True)
    st.write(f"Sunrise: {sunrise}")
    st.write(f"Sunset: {sunset}")
    st.markdown("</div>", unsafe_allow_html=True)

with col3:
    moon_name, moon_illum = get_moon_phase_desc(moon_phase_code)
    st.markdown("<div class='box'><h3>Moon</h3>", unsafe_allow_html=True)
    st.write(f"**{moon_name}**")
    st.write(moon_illum)
    st.markdown("</div>", unsafe_allow_html=True)

with col4:
    uv_index, uv_level = get_uv_desc(uv_max)
    st.markdown("<div class='box'><h3>UV Index</h3>", unsafe_allow_html=True)
    st.write(f"**{uv_index}**")
    st.write(uv_level)
    st.markdown("</div>", unsafe_allow_html=True)

with col5:
    avg_water_temp = openmeteo_df['water_temp_f'].mean() if 'water_temp_f' in openmeteo_df.columns and openmeteo_df['water_temp_f'].notna().any() else None
    st.markdown("<div class='box'><h3>Water Temp</h3>", unsafe_allow_html=True)
    if avg_water_temp is not None:
        st.write(f"**{round(avg_water_temp)} °F**")
    else:
        st.write("N/A")
    st.markdown("</div>", unsafe_allow_html=True)

# Forecast Periods
if shift_date > today + timedelta(days=7):
    st.warning("Limited detail beyond 7 days")
st.markdown("<h3>Forecast Periods</h3>", unsafe_allow_html=True)

time_periods = [
    ("Morning (0800–1159)", 8, 12),
    ("Afternoon (1200–1659)", 12, 17),
    ("Evening (1700–2359)", 17, 24),
    ("Overnight (0000–0800)", 0, 8)
]

for period_name, start_h, end_h in time_periods:
    st.markdown(f"<div class='box'><h4>{period_name}</h4>", unsafe_allow_html=True)
    summary = period_summary(openmeteo_df, start_h, end_h)
    st.write(f"**Cond**: {summary['condition']}")
    st.write(f"**Waves**: {summary['wave']}")
    st.write(f"**Wind**: {summary['wind']} ({summary['dir']}), gusts {summary['gust']}")
    st.write(f"**Precip**: {summary['precip']}")
    st.write(f"**Vis**: {summary['vis']}")
    st.write(f"**Temp**: {summary['temp']}")
    st.write(f"**Water Temp**: {summary['water_temp']}")
    
    matched = False
    for noaa_name, noaa_text in noaa_periods:
        if any(word in noaa_name.upper() for word in period_name.upper().split()):
            formatted = noaa_text.replace('. ', '.<br>')
            st.markdown(f"<div class='noaa-text'><strong>NOAA:</strong><br>{formatted}</div>", unsafe_allow_html=True)
            matched = True
            break
    if not matched:
        st.write("_NOAA unavailable_")
    
    st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.caption("Open-Meteo aggregate + NOAA | Stay safe")
