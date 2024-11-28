import streamlit as st
st.set_page_config(page_title="Employee", layout="wide")
from streamlit import session_state as ss
from modules.nav import MenuButtons
from pages.account import get_roles
import pandas as pd
import datetime

# If the user reloads or refreshes the page while still logged in,
# go to the account page to restore the login status. Note reloading
# the page changes the session id and previous state values are lost.
# only to relogin the user.
if 'authentication_status' not in ss:
    st.switch_page('./pages/account.py')

MenuButtons(get_roles())

# Employee dashboard interface
st.title("Employee Dashboard")

# Function to load availability data
def load_availability_data():
    if 'available_days' not in ss:
        try:
            # Read CSV with flexible datetime parsing
            ss.available_days = pd.read_csv('data/availability_database.csv', parse_dates=['Day'], infer_datetime_format=True)
        except FileNotFoundError:
            # If the file is not found, initialize an empty DataFrame
            ss.available_days = pd.DataFrame(columns=["Day", "Shift", "Available", "Selected by"])

    # Ensure the "Day" column is in datetime format
    ss.available_days['Day'] = pd.to_datetime(ss.available_days['Day'], errors='coerce')
    # Remove rows with invalid dates
    ss.available_days = ss.available_days.dropna(subset=['Day'])

# Load availability data
load_availability_data()

# an option to upload a CSV file if the DataFrame is empty
if ss.available_days.empty:
    uploaded_file = st.file_uploader("Upload a CSV file to populate availability data", type=["csv"])
    if uploaded_file is not None:
        # Load the uploaded file into the session state
        ss.available_days = pd.read_csv(uploaded_file, parse_dates=['Day'], infer_datetime_format=True)
        # Ensure the "Day" column is in datetime format
        ss.available_days['Day'] = pd.to_datetime(ss.available_days['Day'], errors='coerce')
        # Remove rows with invalid dates
        ss.available_days = ss.available_days.dropna(subset=['Day'])
        # Save the uploaded file to the local directory for future use
        ss.available_days.to_csv('data/availability_database.csv', index=False)

# Function to display available days as checkboxes
def display_days_in_grid(days_df):
    selected_days = []
    days_df["Day"] = pd.to_datetime(days_df["Day"], errors='coerce').dt.strftime("%Y-%m-%d")
    start_date = pd.to_datetime(days_df["Day"].min(), errors='coerce')
    end_date = pd.to_datetime(days_df["Day"].max(), errors='coerce')

    if pd.isna(start_date) or pd.isna(end_date):
       # st.error("Invalid date data. Please check the 'Day' column in your CSV file.")
        return selected_days

    if "Shift" not in days_df.columns:
        st.error("The data does not contain 'Shift' column.")
        return selected_days

    current_date = start_date
    shift_types = days_df["Shift"].unique()

    while current_date <= end_date:
        week_dates = pd.date_range(start=current_date, periods=7).strftime("%Y-%m-%d")
        week_fully_booked = True  # Variable to track if all shifts in the week are taken

        for date in week_dates:
            if pd.to_datetime(date) > end_date:
                break
            if date in days_df["Day"].values:
                for shift in shift_types:
                    if shift in days_df.loc[days_df["Day"] == date, "Shift"].values:
                        available = days_df.loc[(days_df["Day"] == date) & (days_df["Shift"] == shift), "Available"].values[0]
                        if available > 0:
                            week_fully_booked = False
                            break

        if not week_fully_booked:
            with st.container():
                st.write(f"### Week of {current_date.strftime('%Y-%m-%d')}")
                col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
                columns = [col1, col2, col3, col4, col5, col6, col7]

                for idx, date in enumerate(week_dates):
                    if pd.to_datetime(date) > end_date:
                        break
                    with columns[idx]:
                        st.write(pd.to_datetime(date).strftime("%a %d-%b"))
                        for shift in shift_types:
                            if date in days_df["Day"].values and shift in days_df.loc[days_df["Day"] == date, "Shift"].values:
                                available = days_df.loc[(days_df["Day"] == date) & (days_df["Shift"] == shift), "Available"].values[0]
                                if available > 0:
                                    if st.checkbox(f"{shift} ({available})", key=f"checkbox_{date}_{shift}"):
                                        selected_days.append((date, shift))
        current_date += datetime.timedelta(days=7)

    return selected_days

# Display available days and allow selection
selected_days = display_days_in_grid(ss.available_days)

# Check if there are available days to display
if not ss.available_days.empty:
    if selected_days:
        st.write("### Selected Dates:")
        for day, shift in selected_days:
            st.write(f"- {day} ({shift})")

    # Allow employee to enter their name and submit selections
    name = st.text_input("Enter your name")
    if st.button("Submit Selection"):
        if name and selected_days:
            for day, shift in selected_days:
                existing_names = ss.available_days.loc[(ss.available_days["Day"].astype(str) == day) & (ss.available_days["Shift"] == shift), "Selected by"].values
                if len(existing_names) > 0 and pd.notna(existing_names[0]):
                    updated_names = f"{existing_names[0]}, {name}"
                else:
                    updated_names = name
                ss.available_days.loc[(ss.available_days["Day"].astype(str) == day) & (ss.available_days["Shift"] == shift), "Selected by"] = updated_names
                ss.available_days.loc[(ss.available_days["Day"].astype(str) == day) & (ss.available_days["Shift"] == shift), "Available"] -= 1

            # Save updated data back to CSV
            ss.available_days.to_csv('data/availability_database.csv', index=False)

            st.success("Your selections have been submitted!")
            st.write("### Updated Availability:")
            st.dataframe(ss.available_days)
else:
    st.write("No available days uploaded yet.")
