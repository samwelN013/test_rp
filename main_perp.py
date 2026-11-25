from datetime import date
import time

def get_todays_date():
    return date.today()

if __name__ == "__main__":
    while True:
        today = get_todays_date()
        print(today)  
        time.sleep(3) # prints date every after those seconds