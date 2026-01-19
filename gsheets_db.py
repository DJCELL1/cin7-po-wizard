"""
Google Sheets Database Module
Provides database operations using Google Sheets as the backend storage.
"""

import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Optional, List, Dict
from datetime import datetime
import json
import os


class GoogleSheetsDatabase:
    """A Google Sheets-based database with basic CRUD operations."""

    def __init__(self, spreadsheet_name: str = "SDATA Database", worksheet_name: str = "data"):
        """
        Initialize the Google Sheets database.

        Args:
            spreadsheet_name: Name of the Google Spreadsheet
            worksheet_name: Name of the worksheet/tab within the spreadsheet
        """
        self.spreadsheet_name = spreadsheet_name
        self.worksheet_name = worksheet_name
        self.client = None
        self.sheet = None
        self._connect()

    def _connect(self):
        """Connect to Google Sheets using credentials from Streamlit secrets or local file."""
        try:
            # Get credentials
            scope = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive"
            ]

            credentials = None

            # Try Streamlit secrets first (for cloud deployment)
            try:
                import streamlit as st
                if hasattr(st, 'secrets') and 'gcp_service_account' in st.secrets:
                    credentials_dict = dict(st.secrets["gcp_service_account"])
                    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
                        credentials_dict, scope
                    )
            except:
                pass

            # Fall back to local credentials.json file
            if credentials is None:
                if os.path.exists('credentials.json'):
                    credentials = ServiceAccountCredentials.from_json_keyfile_name(
                        'credentials.json', scope
                    )
                else:
                    raise FileNotFoundError("No credentials found. Please add credentials.json or configure Streamlit secrets.")

            self.client = gspread.authorize(credentials)

            # Try to open existing spreadsheet or create new one
            try:
                spreadsheet = self.client.open(self.spreadsheet_name)
            except gspread.SpreadsheetNotFound:
                spreadsheet = self.client.create(self.spreadsheet_name)
                # Share with your email (optional)
                # spreadsheet.share('your-email@gmail.com', perm_type='user', role='writer')

            # Try to get worksheet or create new one
            try:
                self.sheet = spreadsheet.worksheet(self.worksheet_name)
            except gspread.WorksheetNotFound:
                self.sheet = spreadsheet.add_worksheet(
                    title=self.worksheet_name,
                    rows="1000",
                    cols="26"
                )
                # Initialize with headers
                self.sheet.append_row(["id", "timestamp"])

        except Exception as e:
            print(f"Failed to connect to Google Sheets: {str(e)}")
            raise

    def read_all(self) -> pd.DataFrame:
        """Read all data from Google Sheets."""
        try:
            data = self.sheet.get_all_records()
            if len(data) == 0:
                # Return empty DataFrame with id and timestamp columns
                return pd.DataFrame(columns=["id", "timestamp"])
            return pd.DataFrame(data)
        except Exception as e:
            print(f"Error reading from Google Sheets: {str(e)}")
            return pd.DataFrame()

    def add_record(self, data: Dict) -> bool:
        """
        Add a new record to Google Sheets.

        Args:
            data: Dictionary containing the record data

        Returns:
            True if successful, False otherwise
        """
        try:
            df = self.read_all()

            # Auto-generate ID
            if len(df) == 0:
                new_id = 1
            else:
                new_id = int(df["id"].max()) + 1

            # Add timestamp
            data["id"] = new_id
            data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Get all columns (union of existing and new)
            all_columns = list(self.sheet.row_values(1))  # Header row
            for col in data.keys():
                if col not in all_columns:
                    all_columns.append(col)
                    # Update header row
                    self.sheet.update([all_columns], 'A1')

            # Create row with all columns
            row_data = [data.get(col, "") for col in all_columns]

            # Append the row
            self.sheet.append_row(row_data)
            return True
        except Exception as e:
            print(f"Error adding record: {str(e)}")
            return False

    def update_record(self, record_id: int, data: Dict) -> bool:
        """
        Update an existing record.

        Args:
            record_id: ID of the record to update
            data: Dictionary containing the updated data

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the row with the matching ID
            cell = self.sheet.find(str(record_id))
            if not cell:
                print(f"Record with ID {record_id} not found")
                return False

            row_num = cell.row
            headers = self.sheet.row_values(1)

            # Update timestamp
            data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Update cells
            for key, value in data.items():
                if key in headers and key != "id":
                    col_num = headers.index(key) + 1
                    self.sheet.update_cell(row_num, col_num, value)

            return True
        except Exception as e:
            print(f"Error updating record: {str(e)}")
            return False

    def delete_record(self, record_id: int) -> bool:
        """
        Delete a record from Google Sheets.

        Args:
            record_id: ID of the record to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the row with the matching ID
            cell = self.sheet.find(str(record_id))
            if not cell:
                print(f"Record with ID {record_id} not found")
                return False

            self.sheet.delete_rows(cell.row)
            return True
        except Exception as e:
            print(f"Error deleting record: {str(e)}")
            return False

    def search(self, column: str, value) -> pd.DataFrame:
        """
        Search for records matching a specific value in a column.

        Args:
            column: Column name to search in
            value: Value to search for

        Returns:
            DataFrame containing matching records
        """
        try:
            df = self.read_all()
            if column not in df.columns:
                print(f"Column {column} not found")
                return pd.DataFrame()

            return df[df[column] == value]
        except Exception as e:
            print(f"Error searching: {str(e)}")
            return pd.DataFrame()

    def get_columns(self) -> List[str]:
        """Get list of all columns in the database."""
        try:
            return self.sheet.row_values(1)
        except Exception as e:
            print(f"Error getting columns: {str(e)}")
            return ["id", "timestamp"]

    def bulk_import(self, df_import: pd.DataFrame, mode: str = "append") -> bool:
        """
        Import data from a DataFrame in bulk.

        Args:
            df_import: DataFrame to import
            mode: 'append' to add to existing data, 'replace' to overwrite

        Returns:
            True if successful, False otherwise
        """
        try:
            if mode == "replace":
                # Clear all data except header
                self.sheet.clear()

                # Add id and timestamp columns
                df_import = df_import.reset_index(drop=True)
                df_import.insert(0, "id", range(1, len(df_import) + 1))
                df_import["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Update sheet with new data
                self.sheet.update([df_import.columns.values.tolist()] + df_import.values.tolist())

            elif mode == "append":
                df_existing = self.read_all()

                # Get the next ID
                if len(df_existing) == 0:
                    next_id = 1
                else:
                    next_id = int(df_existing["id"].max()) + 1

                # Add id and timestamp to imported data
                df_import = df_import.reset_index(drop=True)
                df_import.insert(0, "id", range(next_id, next_id + len(df_import)))
                df_import["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Append rows to sheet
                values = df_import.values.tolist()
                self.sheet.append_rows(values)

            return True
        except Exception as e:
            print(f"Error importing data: {str(e)}")
            return False

    def get_spreadsheet_url(self) -> str:
        """Get the URL of the Google Spreadsheet."""
        try:
            spreadsheet = self.client.open(self.spreadsheet_name)
            return spreadsheet.url
        except:
            return ""
