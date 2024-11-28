import streamlit as st
st.set_page_config(page_title="Analysis", layout="wide")
from streamlit import session_state as ss
from modules.nav import MenuButtons
from pages.account import get_roles
import pandas as pd
from datetime import datetime, timedelta
import altair as alt

if 'authentication_status' not in ss:
    st.switch_page('./pages/account.py')

MenuButtons(get_roles())

# Load availability data
try:
    availability_df = pd.read_csv('data/availability_database.csv', parse_dates=['Day'], infer_datetime_format=True)
except FileNotFoundError:
    st.error("No availability data found. Please upload the availability data in the Manager page.")
    st.stop()

# Ensure the "Day" column is in datetime format
availability_df['Day'] = pd.to_datetime(availability_df['Day'], errors='coerce')

# Calculate shift duration
def calculate_shift_duration(start, end):
    start_time = datetime.strptime(start, '%H:%M').time()
    end_time = datetime.strptime(end, '%H:%M').time()
    
    if end_time > start_time:
        duration = datetime.combine(datetime.min, end_time) - datetime.combine(datetime.min, start_time)
    else:
        duration = datetime.combine(datetime.min + timedelta(days=1), end_time) - datetime.combine(datetime.min, start_time)
        
    return duration.total_seconds() / 3600

# Add a column for shift duration
availability_df['Shift Duration'] = availability_df.apply(lambda row: calculate_shift_duration(row['Start'], row['End']), axis=1)

# Calculate total hours per employee
def calculate_total_hours(df):
    employees_hours = {}

    for _, row in df.iterrows():
        shift_duration = row['Shift Duration']
        if pd.notna(row['Selected by']):
            employees = row['Selected by'].split(', ')
            for employee in employees:
                if employee in employees_hours:
                    employees_hours[employee] += shift_duration
                else:
                    employees_hours[employee] = shift_duration

    return employees_hours

# add a column for week number
availability_df['Week'] = availability_df['Day'].dt.isocalendar().week

# Drop NA values from 'Week' column before getting the unique values
unique_weeks = sorted(availability_df['Week'].dropna().unique())

# Create a sidebar for week selection
selected_week = st.sidebar.selectbox("Select Week", ["Overall"] + [str(week) for week in unique_weeks])

# filter data based on the selected week
if selected_week != "Overall":
    selected_week = int(selected_week)
    filtered_df = availability_df[availability_df['Week'] == selected_week]
else:
    filtered_df = availability_df

employees_hours = calculate_total_hours(filtered_df)
employee_hours_df = pd.DataFrame(list(employees_hours.items()), columns=['Employee', 'Total Hours'])

# display total hours per employee in a chart
st.title("Employee Work Analysis")
st.write(f"### Total Hours per Employee - Week {selected_week if selected_week != 'Overall' else 'Overall'}")

# Create a bar chart using Altair
chart = alt.Chart(employee_hours_df).mark_bar().encode(
    x='Employee',
    y='Total Hours',
    color='Employee',
    tooltip=['Employee', 'Total Hours']
).properties(
    title=f'Total Hours per Employee - Week {selected_week if selected_week != "Overall" else "Overall"}'
).interactive()

st.altair_chart(chart, use_container_width=True)

# give an option to download the data as CSV
csv = employee_hours_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Download data as CSV",
    data=csv,
    file_name=f'employee_work_hours_week_{selected_week if selected_week != "Overall" else "overall"}.csv',
    mime='text/csv',
)

# Load performance data
try:
    performance_df = pd.read_csv('data/performance_data.csv', parse_dates=['Day'], infer_datetime_format=True)
except FileNotFoundError:
    st.error("No performance data found. Please upload performance data in the Manager page.")
    st.stop()

# Ensure the "Day" column is in datetime format
performance_df['Day'] = pd.to_datetime(performance_df['Day'], errors='coerce')

# Filter data based on the selected week
if selected_week != "Overall":
    filtered_performance_df = performance_df[performance_df['Day'].dt.isocalendar().week == selected_week]
else:
    filtered_performance_df = performance_df

# Display performance data in a chart
st.write("### Performance Analysis")
selected_employee = st.selectbox("Select Employee", ["All"] + list(performance_df['Staff'].unique()))

if selected_employee != "All":
    filtered_performance_df = filtered_performance_df[filtered_performance_df['Staff'] == selected_employee]

performance_chart = alt.Chart(filtered_performance_df).mark_line().encode(
    x='Day:T',
    y=alt.Y('Performance', scale=alt.Scale(domain=["Excellent", "Good", "Fair", "Poor"])),
    color='Staff',
    tooltip=['Day', 'Staff', 'Performance']
).properties(
    title=f'Performance Analysis - {selected_employee if selected_employee != "All" else "All"}'
).interactive()

st.altair_chart(performance_chart, use_container_width=True)
