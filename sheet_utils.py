import gspread
from google.oauth2.service_account import Credentials
import os

def write_to_sheet(data: list):
    creds_path = os.getenv("GOOGLE_SHEET_CREDENTIALS_PATH")  # ✅ 正確名稱
    creds = Credentials.from_service_account_file(creds_path, scopes=[
        "https://www.googleapis.com/auth/spreadsheets"
    ])
    client = gspread.authorize(creds)

    sheet_url = os.getenv("SHEET_URL")
    sheet = client.open_by_url(sheet_url).sheet1
    sheet.append_row(data, value_input_option="USER_ENTERED")
