from datetime import date

def get_todays_date():
    return date.today()

if __name__ == "__main__":
    today = get_todays_date()
    print(today)  # Outputs in YYYY-MM-DD format (e.g., 2026-11-14)