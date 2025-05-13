import gspread
from google.oauth2.service_account import Credentials
import os

def write_to_sheet(data: list):
    creds_path = os.getenv("GSHEET_CREDENTIALS")  # ✅ 從環境變數取得 JSON 金鑰檔名
    creds = Credentials.from_service_account_file(creds_path, scopes=[
        "https://www.googleapis.com/auth/spreadsheets"
    ])
    client = gspread.authorize(creds)

    sheet_url = os.getenv("SHEET_URL")  # ✅ 從環境變數取得 Google Sheet URL
    sheet = client.open_by_url(sheet_url).sheet1
    sheet.append_row(data, value_input_option="USER_ENTERED")
