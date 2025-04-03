# Streamlit-based Global Tariff Tracker (with USITC Live Scraper + Watchlist + WTO & USTR + Email Alerts)

import streamlit as st
import pandas as pd
import requests
import time
from bs4 import BeautifulSoup
from google.cloud import firestore
from google.oauth2 import service_account
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- Google Firestore Setup (requires credentials file) ---
credentials = service_account.Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]))
db = firestore.Client(credentials=credentials, project=credentials.project_id)

# --- UI Layout ---
st.set_page_config(page_title="Global Tariff Tracker", layout="wide")
st.title("🌎 Global Tariff Tracker Dashboard")

# --- Search Input ---
col1, col2 = st.columns([2, 1])
with col1:
    query = st.text_input("Search by Product Name or HS Code")
with col2:
    country = st.selectbox("Country", ["United States", "China", "EU", "Canada", "Mexico"])
    tariff_type = st.selectbox("Tariff Type", ["Applied", "Bound", "Section 301", "TRQ"])

# --- USITC Scraper Function ---
def scrape_usitc_tariffs(hs_code):
    url = f"https://hts.usitc.gov/?query={hs_code}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for row in soup.select("#search-results tbody tr"):
            cells = row.find_all("td")
            if len(cells) >= 5:
                results.append({
                    "HS Code": cells[0].get_text(strip=True),
                    "Product": cells[1].get_text(strip=True),
                    "Tariff Rate": cells[2].get_text(strip=True),
                    "Unit": cells[3].get_text(strip=True),
                    "Effective Date": cells[4].get_text(strip=True),
                })

        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Error fetching data from USITC: {e}")
        return pd.DataFrame()

# --- WTO Scraper (Sample via public dataset URL) ---
def scrape_wto_tariffs():
    url = "https://www.wto.org/english/res_e/booksp_e/tariff_profiles21_e.xlsx"
    try:
        df = pd.read_excel(url, sheet_name=1, skiprows=6)
        return df.head(10)  # Display limited rows for demo
    except Exception as e:
        st.error(f"Failed to load WTO data: {e}")
        return pd.DataFrame()

# --- USTR Parser (Basic URL listing Section 301 PDFs) ---
def get_ustr_updates():
    try:
        response = requests.get("https://ustr.gov/issue-areas/enforcement/section-301-investigations/tariff-actions")
        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.select(".view-content a")
        updates = [link.get("href") for link in links if link.get("href") and link.get("href").endswith(".pdf")]
        return updates[:5]  # Show top 5 most recent PDFs
    except Exception as e:
        st.error(f"Failed to load USTR updates: {e}")
        return []

# --- Send Email Notification via SendGrid SMTP ---
def send_email_alert(subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = st.secrets["sendgrid_user"]
        msg['To'] = st.secrets["alert_recipient"]
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP("smtp.sendgrid.net", 587) as server:
            server.starttls()
            server.login("apikey", st.secrets["sendgrid_api_key"])
            server.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

# --- Fetch USITC Data ---
if query and country == "United States":
    st.subheader("Live USITC Results")
    usitc_data = scrape_usitc_tariffs(query)
    if not usitc_data.empty:
        st.dataframe(usitc_data, use_container_width=True)

        # --- Watchlist Add Button ---
        if st.button("➕ Add to Watchlist"):
            try:
                watchlist_ref = db.collection("watchlist")
                watchlist_ref.add({
                    "query": query,
                    "country": country,
                    "tariff_type": tariff_type,
                    "timestamp": firestore.SERVER_TIMESTAMP
                })
                st.success("Added to watchlist.")

                # Optional email alert when adding to watchlist
                send_email_alert(
                    "New Tariff Watchlist Item Added",
                    f"You added the following to your watchlist:\n\nProduct/HS Code: {query}\nCountry: {country}\nTariff Type: {tariff_type}"
                )
            except Exception as e:
                st.error(f"Failed to add to watchlist: {e}")
    else:
        st.info("No results found or invalid HS code.")

# --- WTO Data Preview ---
st.subheader("🌐 WTO Tariff Profiles (Preview)")
wto_data = scrape_wto_tariffs()
if not wto_data.empty:
    st.dataframe(wto_data, use_container_width=True)

# --- USTR PDF Links ---
st.subheader("📄 Recent USTR Section 301 Updates")
ustr_links = get_ustr_updates()
for link in ustr_links:
    st.markdown(f"- [View Update]({link})")

# --- Mock Data Placeholder for Other Countries ---
data = pd.DataFrame({
    "Product": ["Green Tea", "Black Tea", "Tapioca Pearls"],
    "HS Code": ["0902.10", "0902.30", "1903.00"],
    "Country": ["United States"] * 3,
    "Tariff Type": ["Applied"] * 3,
    "Rate (%)": [6.4, 8.0, 5.0],
    "Last Updated": ["2025-04-01"] * 3
})

# --- Filter Data ---
filtered = data[(data['Country'] == country) & (data['Tariff Type'] == tariff_type)]
if query:
    filtered = filtered[filtered['Product'].str.contains(query, case=False) | filtered['HS Code'].str.contains(query)]

# --- Display Table ---
st.subheader("Tariff Results (Mock Data)")
st.dataframe(filtered, use_container_width=True)

# --- Graph Trends Over Time (Mock) ---
st.subheader("Tariff Trends Over Time")
graph_data = pd.DataFrame({
    "Date": pd.date_range(start="2024-01-01", periods=5, freq="M"),
    "Green Tea": [5.0, 5.5, 6.0, 6.4, 6.4],
    "Black Tea": [7.5, 7.5, 7.8, 8.0, 8.0]
})
fig = px.line(graph_data, x="Date", y=["Green Tea", "Black Tea"], markers=True)
st.plotly_chart(fig, use_container_width=True)

# --- Watchlist Display ---
st.subheader("🔔 My Watchlist")
try:
    watchlist_ref = db.collection("watchlist")
    docs = watchlist_ref.order_by("timestamp", direction=firestore.Query.DESCENDING).stream()
    watchlist_items = [{"Query": doc.to_dict().get("query"), "Country": doc.to_dict().get("country"), "Tariff Type": doc.to_dict().get("tariff_type")} for doc in docs]
    if watchlist_items:
        st.table(pd.DataFrame(watchlist_items))
    else:
        st.info("No items in your watchlist yet.")
except Exception as e:
    st.error(f"Error fetching watchlist: {e}")
