import streamlit as st
st.set_page_config(page_title="Manager",layout="wide")
from streamlit import session_state as ss
from modules.nav import MenuButtons
from pages.account import get_roles
import pandas as pd
from io import StringIO  #for the download csv function
from io import BytesIO
import io
import os



# If the user reloads or refreshes the page while still logged in,
# go to the account page to restore the login status. Note reloading
# the page changes the session id and previous state values are lost.
# What we are doing is only to relogin the user.
if 'authentication_status' not in ss:
    st.switch_page('./pages/account.py')

MenuButtons(get_roles())
st.title("Upload File")




# Load availability data
if 'available_days' not in st.session_state:
    try:
        st.session_state.available_days = pd.read_csv('data/availability_database.csv', parse_dates=['Day'], infer_datetime_format=True)
    except FileNotFoundError:
        st.session_state.available_days = pd.DataFrame(columns=["Day", "Shift", "Available", "Selected by", "Start", "End", "Performance"])

# Function to parse CSV and return a dataframe
def parse_csv(uploaded_file):
    return pd.read_csv(uploaded_file, parse_dates=['Day'], infer_datetime_format=True)

# Upload new CSV
uploaded_file = st.file_uploader("Choose a CSV file to upload", type="csv")
if uploaded_file:
    new_data = parse_csv(uploaded_file)
    if not st.session_state.available_days.empty:
        st.session_state.available_days = pd.concat([st.session_state.available_days, new_data]).drop_duplicates().reset_index(drop=True)
    else:
        st.session_state.available_days = new_data
    st.session_state.available_days.to_csv('data/availability_database.csv', index=False)
    st.success("File uploaded successfully!")

# Check if the file is uploaded and available
if st.session_state.available_days.empty:
    st.warning("No data available. Please upload a file.")
else:
    st.session_state.available_days['Day'] = pd.to_datetime(st.session_state.available_days['Day'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y')

    # Display current availability
    st.write("### Current Availability")
    st.dataframe(st.session_state.available_days)

    # Allow manager to remove entries
    st.write("### Remove Entries")
    remove_type = st.selectbox("Select what to remove", ["Date", "Shift", "Name"])

    if remove_type == "Name":
        all_names = st.session_state.available_days["Selected by"].dropna().str.split(", ").explode().unique()
        name_to_remove = st.selectbox("Select name to remove", all_names)
        if st.button("Remove Name"):
            st.session_state.available_days["Selected by"] = st.session_state.available_days["Selected by"].apply(lambda x: ', '.join([n for n in x.split(', ') if n != name_to_remove]) if pd.notna(x) else x)
            st.session_state.available_days["Available"] += st.session_state.available_days["Selected by"].apply(lambda x: 1 if not x else 0)
            st.session_state.available_days["Selected by"] = st.session_state.available_days["Selected by"].replace("", None)
            st.session_state.available_days.to_csv('data/availability_database.csv', index=False)
            st.success(f"Removed all instances of {name_to_remove}.")

    elif remove_type == "Date":
        st.session_state.available_days['Day'] = pd.to_datetime(st.session_state.available_days['Day'], errors='coerce')

        all_dates = st.session_state.available_days["Day"].dropna().unique()
        date_to_remove = st.date_input("Select date to remove", min_value=min(all_dates), max_value=max(all_dates))

        if st.button("Remove Date"):
            st.session_state.available_days = st.session_state.available_days[st.session_state.available_days["Day"] != pd.to_datetime(date_to_remove)]
            st.session_state.available_days.to_csv('data/availability_database.csv', index=False)
            st.success(f"Removed all entries for {date_to_remove.strftime('%d/%m/%Y')}.")

    elif remove_type == "Shift":
        all_shifts = st.session_state.available_days["Shift"].unique()
        shift_to_remove = st.selectbox("Select shift to remove", all_shifts)
        if st.button("Remove Shift"):
            st.session_state.available_days = st.session_state.available_days[st.session_state.available_days["Shift"] != shift_to_remove]
            st.session_state.available_days.to_csv('data/availability_database.csv', index=False)
            st.success(f"Removed all entries for {shift_to_remove}.")

    # Allows the manager to input performance
    st.write("### Input Performance")
    performance_grades = ["Excellent", "Good", "Fair", "Poor"]

    # Display just the date in the selectbox
    st.session_state.available_days["Day"] = pd.to_datetime(st.session_state.available_days['Day'], errors='coerce')
    all_dates = st.session_state.available_days["Day"].dropna().unique()
    selected_date = st.date_input("Select date", min_value=min(all_dates), max_value=max(all_dates))

    # Format the selected_date for further use
    selected_date_str = selected_date.strftime('%d/%m/%Y')
    selected_shift = st.selectbox("Select shift", st.session_state.available_days["Shift"].unique())

    # Filter employees based on selected date and shift
    filtered_employees = st.session_state.available_days[
        (st.session_state.available_days["Day"].dt.strftime('%d/%m/%Y') == selected_date_str) & 
        (st.session_state.available_days["Shift"] == selected_shift)
    ]["Selected by"]

    # Drop rows where 'Selected by' is NaN or empty, then split the names
    filtered_employees = filtered_employees.dropna()  # Remove NaN values
    filtered_employees = filtered_employees[filtered_employees != ""]  # Remove empty strings
    
    # If there are any valid employees, split and process them
    if not filtered_employees.empty:
        filtered_employees = filtered_employees.str.split(", ").explode().unique()
    else:
        filtered_employees = []  # Set to empty if no valid names are found
    
    # create a dictionary for performance input for managers
    performance_dict = {employee: "" for employee in filtered_employees}

    # create dropdowns for each employee name based on the whats in the availability_
    for employee in filtered_employees:
        performance_dict[employee] = st.selectbox(f"Select performance for {employee}", performance_grades, key=f"performance_{employee}")

    # Save performance data to a CSV file for future analysis
    if st.button("Submit Performance"):
        performance_data = pd.read_csv('data/performance_data.csv') if os.path.exists('data/performance_data.csv') else pd.DataFrame(columns=["Day", "Staff", "Performance"])

        # Ensure the selected_date is in the desired format
        formatted_date = pd.to_datetime(selected_date_str, dayfirst=True).strftime('%d/%m/%Y')

        for employee, performance in performance_dict.items():
            # Remove existing entry for the same day and staff if it exists
            performance_data = performance_data[~((performance_data["Day"] == formatted_date) & (performance_data["Staff"] == employee))]
            # Add the new entry
            new_data = {"Day": formatted_date, "Staff": employee, "Performance": performance}
            performance_data = pd.concat([performance_data, pd.DataFrame([new_data])], ignore_index=True)

        performance_data.to_csv('data/performance_data.csv', index=False)
        st.success("Performance data updated successfully!")

def download_template():
    # Data for the template
    template_data = pd.DataFrame([
        {"Day": "22/08/2024", "Shift": "Morning", "Available": 2, "Selected by": "Emp", "Start": "8:00", "End": "16:00"},
        {"Day": "22/08/2024", "Shift": "Mid", "Available": 0, "Selected by": "Emp, Emp, Emp", "Start": "16:00", "End": "0:00"},
        {"Day": "22/08/2024", "Shift": "Night", "Available": 0, "Selected by": "Emp, Emp, Emp", "Start": "0:00", "End": "8:00"},
        {"Day": "23/08/2024", "Shift": "Morning", "Available": 1, "Selected by": "Emp, Emp", "Start": "8:00", "End": "16:00"},
    ])
    
    # Convert the DataFrame to CSV in-memory and store in a BytesIO object
    csv_stream = BytesIO()
    template_data.to_csv(csv_stream, index=False)
    
    # Move to the beginning of the stream
    csv_stream.seek(0)
    
    # Set the filename for the CSV file
    csv_filename = "availability_database.csv"
    
    # Provide a download button in Streamlit
    st.write("")
    st.write("")
    st.write("")
    st.write("")
    st.write("Please follow the template design and maintain the date and time format as shown. Modify the template to reflect the correct days and the number of shifts per day based on your requirements.")
    
    st.download_button(
        label="Download Template CSV File", 
        data=csv_stream,
        file_name=csv_filename,
        mime="text/csv"
    )

# Add the download button in the Streamlit app
download_template()