import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import re
import math

# Page config
st.set_page_config(page_title="SFD Marine Forecast", layout="wide")

# Custom CSS - compact + fixed header
st.markdown("""
<style>
.header {background-color: #001f3f; padding: 15px 10px; text-align: center; color: white; margin-bottom: 15px; display: flex; align-items: center; justify-content: center; flex-wrap: wrap; gap: 20px;}
.header img {max-height: 80px; width: auto;}
.box {background-color: #f0f5fa; border-radius: 8px; padding: 12px; margin: 8px 0;}
.noaa-text {white-space: pre-wrap; line-height: 1.4; font-size: 0.9rem; margin-top: 8px;}
h3, h4 {margin: 0 0 8px 0;}
p {margin: 4px 0 !important;}
@media (max-width: 768px) {
    .header {flex-direction: column; gap: 10px;}
    .header img {max-height: 60px;}
}
</style>
""", unsafe_allow_html=True)

# Header with four images + title
st.markdown("<div class='header'>", unsafe_allow_html=True)
st.image("https://i.imgur.com/7zL5v3k.png", width=80)  # SFD maltese cross
st.image("https://i.imgur.com/0kE8Z0j.png", width=80)  # Fireboat
st.markdown("<h2 style='color: white; margin: 0;'>SFD Daily Marine Forecast</h2>", unsafe_allow_html=True)
st.image("https://i.imgur.com/2mK0Z4k.png", width=80)  # Engine 5
st.image("https://i.imgur.com/3nL5p7q.png", width=80)  # Dive Rescue
st.markdown("</div>", unsafe_allow_html=True)

# Rest of the code remains the same as the last working version (tides, sun/moon/UV/water temp, forecast periods, etc.)
# (Paste the rest from your previous good version here - the body below the header)

# Auto-default to today
today = datetime.today().date()
shift_date = st.date_input("Shift Start (0800)", value=today)

# ... (all the fetch functions, data loading, period_summary, display sections from the previous code)

# Footer
st.caption("Open-Meteo aggregate + NOAA | Stay safe")
