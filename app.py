import streamlit as st
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
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

# Header with logo (direct reliable link to the exact SFD Fireboat patch)
col1, col2 = st.columns([1, 6])
with col1:
 st.image("https://i.imgur.com/0kE8Z0j.png", width=120)   
with col2:
    st.markdown("<div class='header'><h1>Seattle Fire Department:<br>Daily Marine Forecast</h1></div>", unsafe_allow_html=True)

# Shift date selector
today = datetime.today().date()
shift_date = st.date_input("Select Shift Start Date (0800)", today)

# Fetch tides (cached for 1 hour)
@st.cache_data(ttl=3600)
def fetch_tides(date):
    begin = date.strftime("%Y%m%d")
    end = (date + timedelta(days=1)).strftime("%Y%m%d")
    hilo_url = f"https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?station=9447130&product=predictions&datum=MLLW&units=english&time_zone=lst_ldt&interval=hilo&format=json&begin_date={begin}&end_date={end}"
    hourly_url = hilo_url.replace("&interval=hilo", "&interval=h")
    hilo = requests.get(hilo_url).json().get('predictions', [])
    hourly = requests.get(hourly_url).json().get('predictions', [])
    return hilo, hourly

# Fetch NOAA marine forecast
@st.cache_data(ttl=3600)
def fetch_forecast():
    url = "https://api.weather.gov/zones/marine/PZZ135/forecast"
    headers = {'User-Agent': 'SFD Marine App'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['properties']['periods']
    return []

# Fetch active alerts
@st.cache_data(ttl=1800)
def fetch_alerts():
    url = "https://api.weather.gov/alerts/active?zone=PZZ135"
    headers = {'User-Agent': 'SFD Marine App'}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get('features', [])
    return []

# Simple text extraction
def extract_from_text(text, keyword):
    match = re.search(rf"{keyword}.*?(\d+[\d-]*\s*(kt|ft|miles)?)", text, re.IGNORECASE)
    return match.group(1) if match else "N/A"

# Load all data
hilo_tides, hourly_tides = fetch_tides(shift_date)
periods = fetch_forecast()
alerts = fetch_alerts()

# Weather Alerts Box
st.markdown("<div class='box'><h3>Weather Alerts</h3>", unsafe_allow_html=True)
if alerts:
    for alert in alerts:
        props = alert['properties']
        st.error(f"**{props['event']}**: {props.get('headline', 'Active Alert')} — {props.get('description', '')}")
else:
    st.success("No active weather alerts for Puget Sound.")
st.markdown("</div>", unsafe_allow_html=True)

# Tides List
st.markdown("<div class='box'><h3>Tides for Shift (Seattle, feet MLLW)</h3>", unsafe_allow_html=True)
if hilo_tides:
    for tide in hilo_tides:
        time_only = tide['t'][11:]  # Show only time
        st.write(f"**{tide['type'].title()} Tide**: {time_only} — {tide['v']} ft")
else:
    st.write("Tide data currently unavailable.")
st.markdown("</div>", unsafe_allow_html=True)

# Tide Chart
st.markdown("<h3>Tide Chart (0800 to 0800 next day)</h3>", unsafe_allow_html=True)
if hourly_tides:
    df = pd.DataFrame(hourly_tides[:25])  # ~24 hours
    df['t'] = pd.to_datetime(df['t'])
    df['v'] = pd.to_numeric(df['v'])
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df['t'], df['v'], color='#001f3f', linewidth=2.5)
    ax.set_title("Tide Height (ft MLLW)")
    ax.set_ylabel("Height (ft)")
    ax.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)
else:
    st.write("Tide chart unavailable.")

# Forecast Periods in two columns
st.markdown("<h3>Forecast Periods (Puget Sound)</h3>", unsafe_allow_html=True)
cols = st.columns(2)
time_periods = [
    "Morning (0800–1159)",
    "Afternoon (1200–1659)",
    "Evening (1700–2359)",
    "Overnight (0000–0800)"
]

for i, period_name in enumerate(time_periods):
    with cols[i % 2]:
        st.markdown(f"<div class='box'><h4>{period_name}</h4>", unsafe_allow_html=True)
        if i < len(periods):
            p = periods[i]
            text = p['detailedForecast']
            wind = extract_from_text(text, "wind")
            waves = extract_from_text(text, "wave|seas")
            vis = extract_from_text(text, "visibility")
            st.write(f"**Conditions**: {p.get('shortForecast', text.split('.')[0])}")
            st.write(f"**Wind**: {wind}")
            st.write(f"**Wave Height**: {waves}")
            st.write(f"**Visibility**: {vis}")
        else:
            st.write("Detailed forecast limited — check NOAA for latest.")
        st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.caption("Data sourced primarily from NOAA. Always verify real-time conditions before operations. Stay safe on the water!")
