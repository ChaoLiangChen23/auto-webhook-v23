import gspread
from google.oauth2.service_account import Credentials
import os

def write_to_sheet(data: list):
    creds = Credentials.from_service_account_file("webhook-gsheet-0cddc63f4d59.json", scopes=[
        "https://www.googleapis.com/auth/spreadsheets"
    ])
    client = gspread.authorize(creds)
    
    sheet_url = os.getenv("SHEET_URL")
    sheet = client.open_by_url(sheet_url).sheet1
    sheet.append_row(data, value_input_option="USER_ENTERED")
