import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from io import BytesIO
from streamlit import session_state as ss
from modules.nav import MenuButtons
from pages.account import get_roles
from datetime import datetime, timedelta
import altair as alt

# Ensure the user is authenticated
if 'authentication_status' not in ss:
    st.switch_page('./pages/account.py')

MenuButtons(get_roles())

# Sidebar for manager input to specify shifts
st.sidebar.title("Shift Configuration")
shift_count = st.sidebar.number_input("Number of Shifts", min_value=1, max_value=5, value=3)

# Get shift times from manager
shifts = []
for i in range(shift_count):
    start_time = st.sidebar.time_input(f"Shift {i+1} Start Time", value=(datetime.strptime("08:00", "%H:%M").time() if i == 0 else datetime.strptime("14:00", "%H:%M").time()))
    end_time = st.sidebar.time_input(f"Shift {i+1} End Time", value=(datetime.strptime("14:00", "%H:%M").time() if i == 0 else datetime.strptime("22:00", "%H:%M").time()))
    shifts.append((start_time.strftime('%H:%M'), end_time.strftime('%H:%M')))

# Sidebar for employee names input
employees = st.sidebar.text_area("Enter employee names (one per line)", key="employee_names").split('\n')

# Convert shifts into a list of strings, e.g., ["Shift 1", "Shift 2", "Shift 3"]
shift_labels = [f"Shift {i+1}" for i in range(shift_count)]

# FullCalendar CSS and JS with custom styles for white text and event drag-and-drop
fullcalendar_css = """
<link href="https://cdn.jsdelivr.net/npm/fullcalendar@5.10.2/main.min.css" rel="stylesheet" />
<style>
    #calendar {
        width: 80%;
        margin: 40px auto;
        color: white;
    }
    .fc-toolbar-title, .fc-col-header-cell-cushion, .fc-event-title {
        color: white !important;
    }
    .employee-list {
        margin: 20px;
        padding: 10px;
        background-color: #333;
        color: white;
        font-family: Arial, sans-serif;
        font-size: 16px;
    }
    .employee {
        padding: 5px;
        margin: 5px 0;
        cursor: grab;
        background-color: #555;
        color: white;
        border: 1px solid white;
    }
    .employee:hover {
        background-color: #777;
        color: gray;
    }
    .fc-timegrid-slot-label { /* Hide default time labels */
        display: none;
    }
</style>
"""

# FullCalendar JavaScript to handle shifts as time slots and drag-and-drop of employees
fullcalendar_js = f"""
<script src="https://cdn.jsdelivr.net/npm/fullcalendar@5.10.2/main.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@fullcalendar/interaction@5.10.2/main.min.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function() {{
        var calendarEl = document.getElementById('calendar');

        // Define shifts as custom events with 'resourceId' mapped to each shift label
        var shifts = {shift_labels};
        var events = [];

        // Loop over each shift and create a background event for it
        {''.join(f'''
            events.push({{
                title: 'Shift {i+1}',
                start: '2024-09-22T{shifts[i][0]}',  // Start time of shift {i+1}
                end: '2024-09-22T{shifts[i][1]}',    // End time of shift {i+1}
                allDay: false,
                display: 'background',
                resourceId: 'Shift {i+1}'
            }});
        ''' for i in range(shift_count))}

        var calendar = new FullCalendar.Calendar(calendarEl, {{
            initialView: 'timeGridWeek',
            editable: true,
            droppable: true,
            allDaySlot: false,
            slotMinTime: '00:00',
            slotMaxTime: '24:00',
            events: events,
            eventContent: function(arg) {{
                if (arg.event.display === 'background') {{
                    return {{ html: arg.event.title }};
                }}
            }},
            drop: function(info) {{
                if (info.draggedEl.classList.contains('employee')) {{
                    var employeeName = info.draggedEl.innerText;
                    calendar.addEvent({{
                        title: employeeName,
                        start: info.date,
                        allDay: info.allDay
                    }});
                }}
            }},
            eventOverlap: false,
        }});
        
        calendar.render();
        
        var draggableElems = document.querySelectorAll('.employee');
        draggableElems.forEach(function(elem) {{
            new FullCalendar.Draggable(elem, {{
                itemSelector: '.employee',
                eventData: function(eventEl) {{
                    return {{
                        title: eventEl.innerText
                    }};
                }}
            }});
        }});
    }});
</script>
"""

# App Title and Instructions
st.title("Employee Rostering with Drag and Drop")
st.write("Drag employees onto the calendar to assign them to shifts.")

# HTML structure for employee list and FullCalendar container
employee_list_html = '<div class="employee-list">' + ''.join(
    f'<div class="employee">{name.strip()}</div>' for name in employees if name.strip()
) + '</div>'

# Combine HTML and JavaScript code
html_code = f"""
{fullcalendar_css}
{employee_list_html}
<div id="calendar"></div>
{fullcalendar_js}
"""

# Embed the FullCalendar and draggable employee list into the Streamlit app
components.html(html_code, height=700)

# Optional: Add functionality to download the schedule as a CSV
st.subheader("Download Schedule as CSV")
employee_schedule = pd.DataFrame({"Employee Name": employees, "Shift": [""]*len(employees)})  # Add empty shift data for now

# Function to download the schedule
def download_csv(dataframe):
    csv = dataframe.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Schedule",
        data=csv,
        file_name="employee_schedule.csv",
        mime="text/csv",
    )

# Call the function to download the CSV
download_csv(employee_schedule)
