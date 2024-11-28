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
import subprocess
import importlib


# Define the CSV file path
CSV_FILE_PATH = "data/roster_data.csv"

if 'authentication_status' not in ss:
    st.switch_page('./pages/account.py')

MenuButtons(get_roles())


# Dropdown menu for business type selection
business_type = st.selectbox('Select Business Type:', ['Hotel', 'FnB', 'Retail', 'Others'])

# Map selection to module names
module_map = {
    'Hotel': 'hotel',
    'FnB': 'fnb',
    'Retail': 'retail',
    'Others': 'other',

}

# Dynamically import the selected module
if business_type in module_map:
    module_name = module_map[business_type]
    module = importlib.import_module(f'pages.{module_name}')

    # Call the main function of the imported module
    if hasattr(module, 'main'):
        module.main()
    else:
        st.error(f"Module {module_name} does not have a main() function.")
