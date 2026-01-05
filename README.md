# SFD-Marine-Forecast
# Seattle Fire Department Daily Marine Forecast App

A simple, mobile-friendly web app designed specifically for Seattle Fire Department Fireboat crews. It provides a clear, at-a-glance daily marine forecast for Puget Sound during your 24-hour shift (0800–0800), pulling real-time data from trusted sources with a focus on operational safety.

## Features

- **Custom Header** with official SFD Fireboat patch and title  
- **Shift Date Selector** – Choose any shift start date (defaults to today)  
- **High/Low Tides** for the selected 24-hour shift (Seattle station, NOAA)  
- **Interactive Tide Chart** covering 0800 to 0800  
- **Weather Alerts Box** – Prominently displays any active marine alerts (e.g., Small Craft Advisory)  
- **Four Shift Periods** in clean boxes:  
  - Morning (0800–1159)  
  - Afternoon (1200–1659)  
  - Evening (1700–2359)  
  - Overnight (0000–0800)  
- Key marine elements displayed:  
  - Conditions summary  
  - Wind speed/direction  
  - Wave height  
  - Visibility  
- Subdued blue/gray color scheme for easy reading in all lighting conditions  
- Data sourced primarily from NOAA (reliable, no API key required)  

## Live Demo

The app is deployed for free on Streamlit Community Cloud:  
[https://your-app-name.streamlit.app](https://your-app-name.streamlit.app)  
(Replace with your actual deployed URL)

Crew members can bookmark the link or scan the posted QR code for instant access from any phone or tablet – no login or app install required.

## Data Sources

- NOAA Tides & Currents (Station 9447130 – Seattle)  
- NOAA National Weather Service Marine Forecast (Zone PZZ135 – Puget Sound)  
- NOAA Weather Alerts API  

Additional models (Windy, AccuWeather, Wunderground, Nautide, etc.) are cross-referenced manually during development for consensus, but the app uses NOAA as the primary real-time source for reliability and availability.

## How to Use

1. Open the app via link or QR code.  
2. Select your shift start date if different from today.  
3. Review alerts first (red banner if active).  
4. Check tides and tide chart.  
5. Read the four period boxes for wind, waves, visibility, and conditions during your shift.  
6. Always verify critical conditions with real-time VHF weather broadcasts or buoys before operations.

## Deployment (for maintainers)

This app is built with Streamlit and hosted on Streamlit Community Cloud (free tier).

### Files in Repository
- `app.py` – Main application code  
- `fireboat.png` – Official SFD Fireboat patch (header logo)  
- `requirements.txt` – Dependencies  
- `README.md` – This file  

### Updating the App
1. Edit files directly on GitHub (or clone locally if preferred).  
2. Commit changes – Streamlit Cloud automatically redeploys within minutes.  

No local Python installation is required for updates or viewing.

## QR Code for Crew Access

A printed QR code is recommended for the fireboat ready room and apparatus. It links directly to the live app for one-scan access.

## Support & Feedback

This tool was created to support safe and efficient marine operations for the Seattle Fire Department Fireboat.  
Feedback or feature requests? Open an issue on this repository or contact the maintainer.

**Stay safe on the water.**

— Built for SFD Fireboat crews
