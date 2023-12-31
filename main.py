import datetime
import string

import requests
import schedule
import json
import time
import toml
import sys
import os
from enum import Enum
from datetime import date
import openpyxl


class Salat(Enum):
    Fajr = 1
    Dhuhr = 2
    Maghrib = 3


'''
Read the configuration file
'''
if len(sys.argv) != 2:
    print("Usage: python3 main.py /path/to/config_file")
    sys.exit(1)

# Specify the path to your TOML file
toml_file = sys.argv[1]

# Check if the filename is an absolute path; if not, make it absolute
if not os.path.isabs(toml_file):
    # Get the current working directory
    current_directory = os.getcwd()
    # Convert the relative path to an absolute path
    toml_file = os.path.join(current_directory, toml_file)

# Read data from the TOML file
try:
    with open(toml_file, 'r') as file:
        data = toml.load(file)
except FileNotFoundError:
    print(f"Error: File '{toml_file}' not found.")
    sys.exit(1)
except Exception as e:
    print(f"An error occurred: {e}")
    sys.exit(1)

# Replace These variables with the proper one fits to your needs
TELEGRAM_BOT_TOKEN = data["telegram"]["bot_token"]
TELEGRAM_CHAT_ID = data["telegram"]["chat_id"]
SOURCE_MODE = data["source"]["mode"]
EXCEL_FILES_PATH = data["source"]["excel"]["root_path"]
CITY = data["source"]["aladhan"]["city"]
COUNTRY = data["source"]["aladhan"]["country"]
ADHAN_METHOD = data["source"]["aladhan"]["method"]
'''
Methods:
Muslim World League (MWL) - Method value: "1"
This is one of the most widely used methods. It calculates Fajr at 18 degrees
below the horizon and Isha at 17.5 degrees.
Islamic Society of North America (ISNA) - Method value: "2"
This method calculates Fajr at 15 degrees below the horizon and Isha at 15 degrees.
Egyptian General Authority of Survey (Egypt) - Method value: "3"
In this method, Fajr is calculated at 19.5 degrees below the horizon and Isha at
17.5 degrees.
Umm al-Qura University, Makkah (Saudi Arabia) - Method value: "4"
This method is commonly used in Saudi Arabia and calculates Fajr and Isha
differently for each month of the year.
University of Islamic Sciences, Karachi (Pakistan) - Method value: "5"
This method calculates Fajr at 18 degrees below the horizon and Isha at 18 degrees.
Institute of Geophysics, University of Tehran (Iran) - Method value: "7"
This method is used in Iran and calculates Fajr at 17.7 degrees below the
horizon and Isha at 14 degrees.
Shia Ithna Ashari (Jafari) - Method value: "8"
'''


# Function to send a message via the Telegram Bot API
def send_telegram_message(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    telegram_data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    response = requests.post(url, data=telegram_data)
    print(response.json())


def send_praying_time(salat, start, end):
    next_event_time = None

    start_time_str = time.strftime('%H:%M', start)
    end_time_str = time.strftime('%H:%M', end)

    if salat is Salat.Fajr:
        message = f"🌄 Fajr praying time\n\n"
        message += f"Fajr: {start_time_str}\n"
        message += f"Sunrise: {end_time_str}"
    elif salat is Salat.Dhuhr:
        message = f"🌞 Dhuhr praying time\n\n"
        message += f"Dhuhr: {start_time_str}\n"
        message += f"Sunset: {end_time_str}"
    elif salat is Salat.Maghrib:
        message = f"🌇 Maghrib praying time\n\n"
        message += f"Maghrib: {start_time_str}\n"
        message += f"Midnight: {end_time_str}"
    else:
        print(f"Salat time is invalid, don't send any message")
        return

    # Send the message
    send_telegram_message(message)

    # Cancel the schedule to execute it only once
    return schedule.CancelJob


def schedule_next_praying_time():
    today = date.today()
    praying_time_today = get_prayer_times(today)
    if praying_time_today is None:
        print("Oops! Praying time is not available!")
        return

    now = time.localtime()

    if now < praying_time_today["Fajr"]:
        salat = Salat.Fajr
        start = praying_time_today["Fajr"]
        end = praying_time_today["Sunrise"]
    elif now < praying_time_today["Dhuhr"]:
        salat = Salat.Dhuhr
        start = praying_time_today["Dhuhr"]
        end = praying_time_today["Sunset"]
    elif now < praying_time_today["Maghrib"]:
        salat = Salat.Maghrib
        start = praying_time_today["Maghrib"]
        end = praying_time_today["Midnight"]
    elif now > praying_time_today["Maghrib"]:
        tomorrow = today + datetime.timedelta(days=1)
        praying_time_tomorrow = get_prayer_times(tomorrow)
        if praying_time_tomorrow is None:
            print("Oops! Praying time of tomorrow is not available!")
            return
        salat = Salat.Fajr
        start = praying_time_tomorrow["Fajr"]
        end = praying_time_tomorrow["Sunrise"]
    else:
        print(f'Oops, Compare error! now:\n{now}\ntime:\n{praying_time_today}')
        return

    print(f"Next alarm is set for {time.strftime('%H:%M', start)}")

    # Schedule the next message based on the next sunrise or sunset time
    schedule.every().day.at(time.strftime('%H:%M', start)).do(
        send_praying_time, salat, start, end)


def get_prayer_times(date_time: datetime):
    if SOURCE_MODE == "excel":
        return get_prayer_times_excel(date_time)
    elif SOURCE_MODE == "aladhan":
        return get_prayer_times_aladhan(date_time)
    else:
        print(f"The source mode ({SOURCE_MODE}) is invalid")
        return None


def get_prayer_times_aladhan(date_time: datetime):
    # Make a request to the Aladhan API
    data_str = date_time.strftime('%d-%m-%Y')
    url = f"http://api.aladhan.com/v1/timingsByCity/{data_str}?" \
          f"city={CITY}&country={COUNTRY}&method={ADHAN_METHOD}"
    print(url)
    response = requests.get(url)

    if response.status_code == 200:
        data = json.loads(response.text)

        # Extract prayer times from the API response
        prayer_times_str = data["data"]["timings"]

        # convert from string to time_struct format
        prayer_times = {}
        # Define the format of the date and time string
        date_time_format = "%Y-%m-%d %H:%M"
        # Get the current date as a string (you can adjust the date as needed)
        current_date = date_time.strftime("%Y-%m-%d")
        for prayer_name, prayer_time in prayer_times_str.items():
            # Combine the date and time string
            date_time_string = f"{current_date} {prayer_time}"
            prayer_times[prayer_name] = datetime.datetime.strptime(
                date_time_string,
                date_time_format).timetuple()

        # Print prayer times
        return prayer_times
    else:
        print(f'Error fetching prayer times: ({response.status_code}).')
        return None


def get_prayer_times_excel(date_time: datetime):
    DATE_OFFSET = 1
    LAST_FROZEN_MONTH = 4
    LAST_FROZEN_DAY = 26
    month = date_time.month
    day = date_time.day

    # get the file name based on the parameters
    file_name = f"{EXCEL_FILES_PATH}/{month}.xlsx"

    print("file name: ", file_name)

    # load the excel sheet
    dataframe = openpyxl.load_workbook(file_name)
    sheet_obj = dataframe.active

    # set row number based on the file format and the parmeters
    row = day + DATE_OFFSET

    salat_names = ["Fajr", "Sunrise", "Dhuhr", "Sunset", "Maghrib", "Midnight"]

    # convert from string to time_struct format
    prayer_times = {}
    # Define the format of the date and time string
    date_time_format = "%Y-%m-%d %H:%M:%S"
    # Get the current date as a string (you can adjust the date as needed)
    current_date = date_time.strftime("%Y-%m-%d")
    for item in range(len(salat_names)):
        col = item + 2
        prayer_time_cell = sheet_obj.cell(row=row, column=col)
        prayer_time = prayer_time_cell.value
        if prayer_time == '*':
            last_valid = \
                get_prayer_times_excel(datetime.datetime(date_time.year,
                                                         LAST_FROZEN_MONTH,
                                                         LAST_FROZEN_DAY,
                                                         00, 00))
            prayer_time = \
                f"{last_valid[salat_names[item]].tm_hour}:" \
                f"{last_valid[salat_names[item]].tm_min}:00"
        # Combine the date and time string
        date_time_string = f"{current_date} {prayer_time}"
        prayer_times[salat_names[item]] = datetime.datetime.strptime(
            date_time_string,
            date_time_format).timetuple()

    # Print prayer times
    return prayer_times


# Keep the script running to continue scheduling messages
while True:
    # If no schedule is available, set the next salat time
    jobs = schedule.get_jobs()
    if len(jobs) == 0:
        schedule_next_praying_time()
    # Process the pending schedules
    schedule.run_pending()
    # Check again after one minute
    time.sleep(60)
