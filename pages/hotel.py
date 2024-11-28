import streamlit as st
from io import BytesIO
import pandas as pd
import random
from datetime import timedelta, datetime
import altair as alt
from streamlit import session_state as ss
from modules.nav import MenuButtons
from pages.account import get_roles
import os
import numpy as np

CSV_FILE_PATH = "data/roster_data.csv"

def calculate_shift_hours(start_time, end_time):
    now = datetime.now()
    
    # Combine current date with time for start and end
    start = datetime.combine(now, start_time)
    end = datetime.combine(now, end_time)
    
    if end < start:
        end += timedelta(days=1)  # handles overnight shifts
    
    return (end - start).total_seconds() / 3600

def generate_roster(employees, employee_status, shifts, dates, shift_hours, min_employees_per_shift, max_employees_per_day, min_hours, max_hours, off_days, arrivals_departures):
    total_hours = {employee: 0 for employee in employees}
    roster = {date: {shift: [] for shift in shifts} for date in dates}
    
    # convert dates to the same format to keep format uniform
    date_keys = {pd.to_datetime(date).strftime('%Y-%m-%d'): date for date in dates}
    
    # calculate total arrivals and departures for each date
    arrivals_departures_totals = [arrivals_departures[date_keys[pd.to_datetime(date).strftime('%Y-%m-%d')]]['Arrivals'] + arrivals_departures[date_keys[pd.to_datetime(date).strftime('%Y-%m-%d')]]['Departures'] for date in dates]
    max_arr_dep = max(arrivals_departures_totals)
    
    q95, q90, q85 = np.percentile(arrivals_departures_totals, [95, 90, 85])

    for date in dates:
        available_employees = employees.copy()
        available_fulltime = [emp for emp, status in employee_status.items() if status == "Full-time"]
        available_parttime = [emp for emp, status in employee_status.items() if status == "Part-time"]
        available_managers = [emp for emp, status in employee_status.items() if status == "Manager"]

        # this tracks the number of shifts each employee is assigned to per day
        shifts_assigned_today = {emp: 0 for emp in employees}

        
        for shift in shifts:
            num_employees = min_employees_per_shift[shift]
            # scale the number of employees based on the proportion of the day's total arrivals and departures
            total_arr_dep = arrivals_departures[date_keys[pd.to_datetime(date).strftime('%Y-%m-%d')]]['Arrivals'] + arrivals_departures[date_keys[pd.to_datetime(date).strftime('%Y-%m-%d')]]['Departures']
            scale_factor = total_arr_dep / max_arr_dep
            
            if scale_factor > 0.85:
                num_employees += 3  # High traffic day
            elif scale_factor > 0.80:
                num_employees += 2  # Medium-high traffic day
            elif scale_factor > 0.75:
                num_employees += 1  # Medium-low traffic day
            # No adjustment for low traffic days

            if num_employees > max_employees_per_day:
                st.warning(f"Exceeding maximum number of employees for {date}. Adjusting...")
                num_employees = max_employees_per_day

            # Assign managers first to each shift evenly
            manager_hours = {emp: total_hours[emp] for emp in available_managers}
            sorted_managers = sorted(available_managers, key=lambda emp: manager_hours[emp])
            assignable_managers = [emp for emp in sorted_managers if total_hours[emp] + shift_hours[shift] <= max_hours]
            assignable_managers = [emp for emp in assignable_managers if emp not in off_days.get(date, [])]
            
            assigned_managers = assignable_managers[:1]  # ensure at least one manager per shift
            remaining_slots = num_employees - len(assigned_managers)

            # Assign full-time employees after managers
            assignable_fulltime = [emp for emp in available_fulltime if total_hours[emp] + shift_hours[shift] <= max_hours]
            assignable_fulltime = [emp for emp in assignable_fulltime if emp not in off_days.get(date, [])]
            
            random.shuffle(assignable_fulltime)

            assigned_employees = assignable_fulltime[:remaining_slots]
            remaining_slots -= len(assigned_employees)
            assigned_employees.extend(assigned_managers)  # Add managers

            # Assign part-time employees if there are still remaining slots
            if remaining_slots > 0:
                parttime_hours = {emp: total_hours[emp] for emp in available_parttime}
                sorted_parttime = sorted(available_parttime, key=lambda emp: parttime_hours[emp])               
                assignable_parttime = [emp for emp in sorted_parttime if total_hours[emp] + shift_hours[shift] <= max_hours]
                assignable_parttime = [emp for emp in assignable_parttime if emp not in off_days.get(date, [])]
                assigned_parttime = assignable_parttime[:remaining_slots]
                assigned_employees.extend(assigned_parttime)

            roster[date][shift] = assigned_employees
            for emp in assigned_employees:
                total_hours[emp] += shift_hours[shift]
                shifts_assigned_today[emp] += 1
                
                # Remove the employee from availability lists to prevent multiple assignments on the same day
                available_fulltime = [e for e in available_fulltime if e != emp]
                available_parttime = [e for e in available_parttime if e != emp]
                available_managers = [e for e in available_managers if e != emp]

        # Ensure total number of employees per day does not exceed max_employees_per_day
        total_employees_today = sum(len(shift_employees) for shift_employees in roster[date].values())
        if total_employees_today > max_employees_per_day:
            excess = total_employees_today - max_employees_per_day
            for shift in shifts:
                if excess <= 0:
                    break
                while len(roster[date][shift]) > min_employees_per_shift[shift] and excess > 0:
                    removed_employee = roster[date][shift].pop()
                    total_hours[removed_employee] -= shift_hours[shift]
                    excess -= 1

    # Post-processing: check for duplicate names in each shift and across shifts in a day
    for date in roster:
        assigned_employees_today = set()  # To track employees already assigned a shift for the day
        for shift in roster[date]:
            assigned_employees = roster[date][shift]
            shift_duplicates = {}  # Dictionary to count occurrences of employees in the same shift
            
            # Check for employees assigned more than one shift in a day
            for emp in assigned_employees:
                if emp in assigned_employees_today:
                    # Swap employee assigned to multiple shifts on the same day
                    for part_time in available_parttime:
                        if part_time not in assigned_employees and total_hours[part_time] + shift_hours[shift] <= max_hours:
                            assigned_employees.remove(emp)
                            assigned_employees.append(part_time)
                            total_hours[part_time] += shift_hours[shift]
                            total_hours[emp] -= shift_hours[shift]
                            break
                assigned_employees_today.add(emp)

            # Check for duplicate employees in the same shift
            for emp in assigned_employees:
                if emp in shift_duplicates:
                    shift_duplicates[emp] += 1
                else:
                    shift_duplicates[emp] = 1
            
            # If there are duplicate employees, try to swap them with part-timers
            for emp, count in shift_duplicates.items():
                if count > 1:
                    # Try to swap the duplicate with a part-timer
                    for part_time in available_parttime:
                        if part_time not in assigned_employees and total_hours[part_time] + shift_hours[shift] <= max_hours:
                            assigned_employees.remove(emp)
                            assigned_employees.append(part_time)
                            total_hours[part_time] += shift_hours[shift]
                            total_hours[emp] -= shift_hours[shift]
                            break
            
            roster[date][shift] = assigned_employees
    
    return roster, total_hours

def display_roster(roster, total_hours):
    st.write("### Employee Roster")
    dates = list(roster.keys())
    shifts = list(roster[dates[0]].keys())

    # change the dates to "dd/mm/yyyy" format
    formatted_dates = [pd.to_datetime(date).strftime('%Y-%m-%d') for date in dates]

    roster_table = []
    for date in formatted_dates:
        # Map the formatted date back to the original date for roster lookup
        original_date = pd.to_datetime(date, format='%Y-%m-%d').strftime('%Y-%m-%d')
        row = [date]
        for shift in shifts:
            row.append(', '.join(roster[original_date][shift]))
        roster_table.append(row)
    
    header = ["Date"] + shifts
    df_roster = pd.DataFrame(roster_table, columns=header)
    st.table(df_roster)
    
    st.write("### Total Hours Worked by Each Employee")
    hours_data = [{'Employee': employee, 'Hours': round(hours, 2)} for employee, hours in total_hours.items()]
    df_hours = pd.DataFrame(hours_data)
    st.table(df_hours)
    
    return roster_table, hours_data

def create_barchart(hours_data):
    df = pd.DataFrame(hours_data)
    chart = alt.Chart(df).mark_bar().encode(
        x='Employee',
        y='Hours',
        color='Employee'
    ).properties(
        title='Total Hours Worked by Each Employee'
    )
    st.altair_chart(chart, use_container_width=True)

def save_uploaded_file(uploaded_file):
    data_folder = "data"
    os.makedirs(data_folder, exist_ok=True)
    file_path = os.path.join(data_folder, "hotel_uploaded_file.xlsx")
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path

def append_to_csv(roster, shifts, shift_df):
    # Define the file path for your CSV
    csv_path = os.path.join("data", "availability_database.csv")
    
    # Prepare the data to append
    data_to_append = []

    for date, shifts_dict in roster.items():
        for shift, employees in shifts_dict.items():
            # for employee in employees:
            data_to_append.append({
                'Day': pd.to_datetime(date).strftime('%Y-%m-%d'),  # Convert date to dd/mm/yyyy format
                'Shift': shift,
                'Available': 0,  # Assuming all slots are filled
                'Selected by': ', '.join(employees), # employee,  # ', '.join(employees),  # Join employee names,
                'Start': shift_df.loc[shift_df['Shift'] == shift, 'Start'].apply(lambda t: t.strftime('%H:%M')).values[0],
                'End': shift_df.loc[shift_df['Shift'] == shift, 'End'].apply(lambda t: t.strftime('%H:%M')).values[0]
            })
    
    # Convert the data to DataFrame
    df_to_append = pd.DataFrame(data_to_append)
    
    # Check if the CSV file exists
    if os.path.exists(csv_path):
        # Read existing data
        existing_df = pd.read_csv(csv_path)

        # Convert 'Day' column to datetime for comparison
        existing_df['Day'] = pd.to_datetime(existing_df['Day'], format='%Y-%m-%d')
        df_to_append['Day'] = pd.to_datetime(df_to_append['Day'], format='%Y-%m-%d')

        # Find overlapping dates
        overlapping_dates = df_to_append['Day'].unique()
        
        # Remove overlapping dates from the existing data
        existing_df = existing_df[~existing_df['Day'].isin(overlapping_dates)]
        
        # Append new data
        updated_df = pd.concat([existing_df, df_to_append], ignore_index=True)
    else:
        # If file does not exist, just use the new data
        updated_df = df_to_append

    # Convert 'Day' column back to string format 'yyyy-mm-dd'
    updated_df['Day'] = updated_df['Day'].dt.strftime('%Y-%m-%d')

    # Save the updated data to the CSV file
    updated_df.to_csv(csv_path, index=False)


def main():
    st.title("Hotel Employee Roster Generator")

    file_path = None  # Initialize file_path to None

    if 'file_path' not in st.session_state:
        uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx"])

        if uploaded_file:
            file_path = save_uploaded_file(uploaded_file)
            st.session_state.file_path = file_path
    else:
        file_path = st.session_state.file_path
        uploaded_file = None

    if file_path:
        # Reading data from each sheet
        employee_df = pd.read_excel(file_path, sheet_name="Employee Information")
        shift_df = pd.read_excel(file_path, sheet_name="Shift Information")
        day_df = pd.read_excel(file_path, sheet_name="Day Information")
        off_days_df = pd.read_excel(file_path, sheet_name="Off Days")
        general_df = pd.read_excel(file_path, sheet_name="General Information")

        st.dataframe(employee_df)
        st.dataframe(shift_df)
        st.dataframe(day_df)
        st.dataframe(off_days_df)
        st.dataframe(general_df)

        employees = employee_df['Employee'].tolist()
        employee_status = dict(zip(employee_df['Employee'], employee_df['Status']))
        shifts = shift_df['Shift'].tolist()
        
        # Ensure shift start and end times are in the correct format
        shift_hours = {}
        for shift, start, end in zip(shift_df['Shift'], shift_df['Start'], shift_df['End']):
            if isinstance(start, str):
                start_time = pd.to_datetime(start).time()
                end_time = pd.to_datetime(end).time()
            else:
                start_time = start
                end_time = end

            shift_hours[shift] = calculate_shift_hours(start_time, end_time)
        
        min_employees_per_shift = dict(zip(shift_df['Shift'], shift_df['Min Employees']))
        max_employees_per_day = general_df['Max Employees per Day'].iloc[0]
        min_hours = general_df['Min Hours per Employee'].iloc[0]
        max_hours = general_df['Max Hours per Employee'].iloc[0]

        # Convert "Date" column to datetime in "Day Information" and "Off Days"
        day_df['Date'] = pd.to_datetime(day_df['Date'], format='%Y-%m-%d').dt.strftime('%Y-%m-%d')
        off_days_df['Date'] = pd.to_datetime(off_days_df['Date'], format='%Y-%m-%d').dt.strftime('%Y-%m-%d')

        dates = day_df['Date'].tolist()

        off_days = {}
        for date, employee in zip(off_days_df['Date'], off_days_df['Employee']):
            if date not in off_days:
                off_days[date] = []
            off_days[date].append(employee)

        arrivals_departures = {}
        for date, arrivals, departures in zip(day_df['Date'], day_df['Arrivals'], day_df['Departures']):
            arrivals_departures[date] = {'Arrivals': arrivals, 'Departures': departures}

        if st.button("Generate Roster"):
            try:
                roster, total_hours = generate_roster(employees, employee_status, shifts, dates, shift_hours, min_employees_per_shift, max_employees_per_day, min_hours, max_hours, off_days, arrivals_departures)
                roster_table, hours_data = display_roster(roster, total_hours)
                create_barchart(hours_data)
                
                # Append data to CSV
                append_to_csv(roster, shifts, shift_df)
                
                # Convert the roster_table and hours_data to Excel
                roster_df = pd.DataFrame(roster_table, columns=["Date"] + shifts)
                hours_df = pd.DataFrame(hours_data)
                
                with BytesIO() as buffer:
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        roster_df.to_excel(writer, sheet_name='Roster', index=False)
                        hours_df.to_excel(writer, sheet_name='Total Hours', index=False)
                    st.download_button(
                        label="Download Roster and Total Hours",
                        data=buffer.getvalue(),
                        file_name="roster_and_total_hours.xlsx",
                        mime="application/vnd.ms-excel"
                    )
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.error(f"I'm having some trouble generating your roster :(")
                st.error(f"Please rerun again!")

        else:
            st.info("Generating the roster will automatically add the staff to the database. To change it, Regenerate the roster again.")
    # Providing a template download link if no file is uploaded
    employee_data = {
        "Employee": ["Name", "Name"],
        "Status": ["Manager", "Employee"]
    }

    shift_data = {
        "Shift": ["Morning", "Mid", "Night"],
        "Start": ["08:00", "16:00", "00:00"],
        "End": ["16:00", "00:00", "08:00"],
        "Min Employees": [1, 1, 1]
    }

    day_data = {
        "Day": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "Busyness Level": [1, 1, 1, 1, 2, 3, 2]
    }

    off_days_data = {
        "Employee": ["Name", "Name"],
        "Day": ["Monday", "Tuesday"]
    }

    general_data = {
        "Min Employees per Day": [6],
        "Max Employees per Day": [15],
        "Min Hours per Employee": [10],
        "Max Hours per Employee": [90]
    }

    # Create an in-memory stream for the Excel file
    excel_stream = BytesIO()

    # Excel writer using XlsxWriter
    with pd.ExcelWriter(excel_stream, engine="xlsxwriter") as excel_writer:
        # Write each DataFrame to a different sheet
        pd.DataFrame(employee_data).to_excel(excel_writer, sheet_name="Employee Information", index=False)
        pd.DataFrame(shift_data).to_excel(excel_writer, sheet_name="Shift Information", index=False)
        pd.DataFrame(day_data).to_excel(excel_writer, sheet_name="Day Information", index=False)
        pd.DataFrame(off_days_data).to_excel(excel_writer, sheet_name="Off Days", index=False)
        pd.DataFrame(general_data).to_excel(excel_writer, sheet_name="General Information", index=False)

    # Set Excel file name
    excel_filename = "hotel_template.xlsx"

    # Set content type and provide download link
    excel_stream.seek(0)
    if 'file_path' not in ss:
        st.download_button(label="Download Template Excel File", data=excel_stream, file_name=excel_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


