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

# Fetch NOAA marine text forecast and parse PZZ135
@st.cache_data(ttl=3600)
def fetch_noaa_forecast():
    url = "https://forecast.weather.gov/product.php?site=SEW&issuedby=SEW&product=CWF&format=txt&version=1&glossary=0"
    response = requests.get(url)
    if response.status_code == 200:
        text = response.text
        # Find PZZ135 section
        match = re.search(r'(PZZ135-.*?)(\n\nPZZ\d{3}-|\Z)', text, re.DOTALL)
        if match:
            zone_text = match.group(1).strip()
            # Split into periods (lines starting with .period...)
            periods = re.split(r'\n\.', zone_text)
            parsed = []
            for p in periods[1:]:  # Skip header
                lines = p.strip().split('\n', 1)
                if len(lines) == 2:
                    period_name = lines[0].strip().strip('.').upper()
                    detail = lines[1].strip()
                    parsed.append((period_name, detail))
            return parsed
    return []

# Fetch Open-Meteo Forecast (atmospheric + marine in one call)
@st.cache_data(ttl=3600)
def fetch_openmeteo_forecast(date):
    lat = 47.6062
    lon = -122.3321
    start = date.strftime("%Y-%m-%d")
    end = (date + timedelta(days=1)).strftime("%Y-%m-%d")
    hourly_vars = "temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,visibility,cloud_cover,wave_height,wind_wave_height,swell_wave_height,wave_direction,wave_period"
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly={hourly_vars}&start_date={start}&end_date={end}&timezone=America%2FLos_Angeles&wind_speed_unit=kn&temperature_unit=fahrenheit&precipitation_unit=inch&visibility_unit=mile&cell_selection=sea"
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
            'cloud_cover': data.get('cloud_cover', []),
            'wave_height_ft': [(round(x * 3.281, 1) if x is not None else None) for x in data.get('wave_height', [])],
            'wind_wave_ft': [(round(x * 3.281, 1) if x is not None else None) for x in data.get('wind_wave_height', [])],
            'swell_wave_ft': [(round(x * 3.281, 1) if x is not None else None) for x in data.get('swell_wave_height', [])],
            'wave_dir': data.get('wave_direction', []),
            'wave_period': data.get('wave_period', [])
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
openmeteo_df = fetch_openmeteo_forecast(shift_date)
alerts = fetch_alerts()

# Filter tides within shift
filtered_tides = []
for tide in hilo_tides:
    tide_time = datetime.strptime(tide['t'], "%Y-%m-%d %H:%M")
    if shift_start <= tide_time < shift_end:
        filtered_tides.append(tide)

# Helper to get summary stats for a period
def period_summary(df, start_h, end_h):
    period_df = df[(df['time'].dt.hour >= start_h) & (df['time'].dt.hour < end_h)]
    if period_df.empty or period_df['wave_height_ft'].isna().all():
        return {
            'wave': "N/A",
            'wind_speed': "N/A",
            'wind_dir': "N/A",
            'gust': "N/A",
            'precip': "N/A",
            'vis': "N/A",
            'temp': "N/A"
        }
    summary = {
        'wave': f"{period_df['wave_height_ft'].min():.1f}–{period_df['wave_height_ft'].max():.1f} ft" if period_df['wave_height_ft'].notna().any() else "N/A",
        'wind_speed': f"{period_df['wind_speed_kt'].min():.0f}–{period_df['wind_speed_kt'].max():.0f} kt" if period_df['wind_speed_kt'].notna().any() else "N/A",
        'wind_dir': f"{int(period_df['wind_dir'].mode()[0])}°" if not period_df['wind_dir'].mode().empty else "Var",
        'gust': f"{period_df['wind_gust_kt'].max():.0f} kt" if period_df['wind_gust_kt'].notna().any() else "N/A",
        'precip': f"{period_df['precip_in'].sum():.2f} in" if period_df['precip_in'].sum() > 0 else "None",
        'vis': f"{period_df['visibility_mi'].min():.1f}–{period_df['visibility_mi'].max():.1f} mi" if period_df['visibility_mi'].notna().any() else "N/A",
        'temp': f"{period_df['temp_f'].min():.0f}–{period_df['temp_f'].max():.0f} °F" if period_df['temp_f'].notna().any() else "N/A"
    }
    return summary

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

# Forecast Periods
if shift_date > today + timedelta(days=7):
    st.warning("Detailed NOAA text forecasts unavailable beyond ~7 days. Showing Open-Meteo multi-model aggregate.")
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
        
        # Open-Meteo aggregate data
        summary = period_summary(openmeteo_df, start_h, end_h)
        st.write(f"**Waves (Aggregate)**: {summary['wave']}")
        st.write(f"**Wind**: {summary['wind_speed']} ({summary['wind_dir']}), gusts {summary['gust']}")
        st.write(f"**Precip**: {summary['precip']}")
        st.write(f"**Visibility**: {summary['vis']}")
        st.write(f"**Temperature**: {summary['temp']}")
        
        # NOAA textual if available
        if i < len(noaa_periods):
            noaa_name, noaa_text = noaa_periods[i]
            st.markdown("**NOAA Details**:")
            st.write(noaa_text)
        else:
            st.write("_Detailed NOAA text unavailable for this period._")
        
        st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.caption("Primary textual: NOAA | Numerical aggregate (wind, waves, precip, vis, temp): Open-Meteo (ECMWF, GFS, ICON blend) | Cross-check Windy, AccuWeather, etc. | Stay safe!")
