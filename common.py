from datetime import datetime
import os
import re
import pandas as pd


def get_files_from_directory_as_df(directory_path):
    file_data = [
        (os.path.join(directory_path, f), f)
        for f in os.listdir(directory_path)
        if os.path.isfile(os.path.join(directory_path, f))
    ]
    df = pd.DataFrame(file_data, columns=["full_path", "filename"])
    return df


def parse_date_from_filename(filename):
    # Regular expression pattern for YYYY-mm-DD
    pattern = r"\d{4}-\d{2}-\d{2}"

    # Search for the pattern in the filename
    match = re.search(pattern, filename)

    # If a match is found, parse it into a date
    if match:
        date_str = match.group()
        date_object = datetime.strptime(date_str, "%Y-%m-%d")
        return date_object.date()  # Use .date() to get just the date part

    # If no date found, return None or handle as needed
    return None


def parse_code_from_filename(filename):
    # Split the filename by " - "
    sections = filename.split(" - ")

    # If there are at least three sections, return the third one
    if len(sections) >= 3:
        return sections[2]

    # If there are not enough sections, return None or handle as needed
    return None
