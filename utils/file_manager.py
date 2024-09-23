import os
from datetime import datetime
import re

def save_excel(workbook, base_dir, regnum='', report_type='report'):
    
    # Format the current date and time for uniqueness
    date = datetime.now()
    date_str = date.strftime('%Y-%m-%d')
    
    # turn on this option if you need timestamp
    # time_str = date.strftime('%H-%M-%S')

    # Sanitize the registry number to avoid special characters in filenames
    def sanitize_filename(value):
        """
        Removes any unsafe characters from the given string to make it safe for filenames.
        """
        return re.sub(r'[^\w\s-]', '', value).strip().replace(' ', '_')
    
    regnum_safe = sanitize_filename(regnum)

    # Construct the filename with date and timestamp to ensure uniqueness
    filename = f"{report_type}_{regnum_safe}_ot_{date_str}.xlsx"

    # Ensure there's a directory to save the file in
    save_dir = os.path.join(base_dir, 'saves')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # Construct the full path for the file
    file_path = os.path.join(save_dir, filename)

    # Save the workbook
    workbook.save(file_path)

    # Return the relative path or any identifier you prefer
    return filename