import datetime

import requests
import schedule
import json
import time
import toml
from enum import Enum


class Salat(Enum):
    Fajr = 1
    Dhuhr = 2
    Maghrib = 3

'''
Read the configuration file
'''
# Specify the path to your TOML file
toml_file = 'config.toml'
# Read data from the TOML file
with open(toml_file, 'r') as file:
    data = toml.load(file)

# Replace These variables with the proper one fits to your needs
TELEGRAM_BOT_TOKEN = data["telegram"]["bot_token"]
TELEGRAM_CHAT_ID = data["telegram"]["chat_id"]
CITY = data["aladhan"]["city"]
COUNTRY = data["aladhan"]["country"]
ADHAN_METHOD = data["aladhan"]["method"]
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
    praying_time = get_prayer_times()
    if praying_time is None:
        print("Oops! Praying time is not available!")
        return

    now = time.localtime()

    if now < praying_time["Fajr"]:
        salat = Salat.Fajr
        start = praying_time["Fajr"]
        end = praying_time["Sunrise"]
    elif now < praying_time["Dhuhr"]:
        salat = Salat.Dhuhr
        start = praying_time["Dhuhr"]
        end = praying_time["Sunset"]
    elif now < praying_time["Maghrib"]:
        salat = Salat.Maghrib
        start = praying_time["Maghrib"]
        end = praying_time["Midnight"]
    else:
        print(f'Fetched time is not for today')
        return

    print(f"Next alarm is set for {time.strftime('%H:%M', start)}")

    # Schedule the next message based on the next sunrise or sunset time
    schedule.every().day.at(time.strftime('%H:%M', start)).do(
        send_praying_time, salat, start, end)


def get_prayer_times():
    # Make a request to the Aladhan API
    url = f"http://api.aladhan.com/v1/timingsByCity//{int(time.time())}?"\
          f"city={CITY}&country={COUNTRY}&method={ADHAN_METHOD}"
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
        current_date = time.strftime("%Y-%m-%d")
        for prayer_name, prayer_time in prayer_times_str.items():
            # Combine the date and time string
            date_time_string = f"{current_date} {prayer_time}"
            prayer_times[prayer_name] = datetime.datetime.strptime(
                date_time_string,
                date_time_format).timetuple()

        # Print prayer times
        return prayer_times
    else:
        print(f'Error fetching prayer times {response.status_code}.')
        return None


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
