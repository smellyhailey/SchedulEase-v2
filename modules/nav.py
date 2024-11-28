import streamlit as st
from streamlit import session_state as ss

def HomeNav():
    st.sidebar.page_link("streamlit_app.py", label="Home", icon='🏠')
    
def LoginNav():
    st.sidebar.page_link("./pages/account.py", label="Account", icon='🔐')

def Page1Nav():
    st.sidebar.page_link("./pages/employee.py", label="Employee", icon='✈️')
    
def Page2Nav():
    st.sidebar.page_link("./pages/manager.py", label="Manager", icon='✈️')

def Page3Nav():
    st.sidebar.page_link("./pages/user_management.py", label="User Management", icon='✈️')

def Page4Nav():
    st.sidebar.page_link("./pages/roster_generator.py", label="Roster Generator", icon='✈️')
    
def Page5Nav():
    st.sidebar.page_link("./pages/analysis.py", label="Analysis", icon='✈️')
    
# def Page6Nav():
#     st.sidebar.page_link("./pages/test.py", label="Test", icon='✈️')

def MenuButtons(user_roles=None):
    if user_roles is None:
        user_roles = {}

    if 'authentication_status' not in ss:
        ss.authentication_status = False

    # Always show the home and login navigators.
    LoginNav()

    # Show the other page navigators depending on the users' role.
    if ss["authentication_status"]:

        # (1) Only the admin role can access page 1 and other pages.
        # In a user roles get all the usernames with admin role.
        admins = [k for k, v in user_roles.items() if v == 'admin']
        manager = [k for k, v in user_roles.items() if v == 'manager']
        employee = [k for k, v in user_roles.items() if v == 'employee']

        # Show page 1 if the username that logged in is an admin.
        if ss.username in admins:
            Page1Nav() #employee
            Page2Nav() #manager
            Page5Nav() #analysis
            Page4Nav() #roster generator
            Page3Nav() #user management
            # Page6Nav() #test

        # (2) users with user and admin roles have access to page 2.
        if ss.username in manager:
            Page2Nav() #manager
            Page5Nav() #analysis
            Page4Nav() #roster generator

            
        if ss.username in employee:
            Page1Nav() #employee
            

            






