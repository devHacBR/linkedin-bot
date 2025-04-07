import time
import sqlite3
import json
import schedule
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Load messages
with open("messages.json", "r") as f:
    messages = json.load(f)

def init_db():
    conn = sqlite3.connect("data/db.sqlite3")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            linkedin_url TEXT PRIMARY KEY,
            name TEXT,
            status TEXT,
            last_contacted TIMESTAMP,
            followup_count INTEGER DEFAULT 0,
            date_connected DATE
        )
    """)
    conn.commit()
    conn.close()

def save_lead(url, name):
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO leads (linkedin_url, name, status, date_connected) VALUES (?, ?, ?, ?)",
        (url, name, "connected", today)
    )
    conn.commit()
    conn.close()

def update_followup(url):
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE leads
        SET followup_count = followup_count + 1,
            last_contacted = ?
        WHERE linkedin_url = ?
    """, (datetime.datetime.now(), url))
    conn.commit()
    conn.close()

def get_today_connection_count():
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM leads WHERE date_connected = ?", (today,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def start_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-data-dir=/root/.config/google-chrome")
    return webdriver.Chrome(options=options)

def search_and_connect(region, message):
    driver = start_driver()
    driver.get("https://www.linkedin.com/login")
    input("Login manually and press Enter here when done...")

    keywords = ["CEO", "Founder", "CTO", "Owner", "Project Manager", "Operations Manager"]
    total_sent = get_today_connection_count()
    print(f"Already sent today: {total_sent}")

    for title in keywords:
        if total_sent >= 100:
            print("Reached 100 connections today.")
            break

        driver.get("https://www.linkedin.com/search/results/people/?keywords=" + title + " " + region)
        time.sleep(5)

        profiles = driver.find_elements(By.CLASS_NAME, "entity-result__title-text")

        for profile in profiles:
            if total_sent >= 100:
                break
            try:
                name_elem = profile.find_element(By.TAG_NAME, "span")
                profile_link = profile.find_element(By.TAG_NAME, "a").get_attribute("href")

                profile.find_element(By.TAG_NAME, "a").send_keys(Keys.CONTROL + Keys.RETURN)
                driver.switch_to.window(driver.window_handles[-1])
                time.sleep(3)

                connect_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Connect')]")
                connect_btn.click()
                time.sleep(2)

                try:
                    add_note = driver.find_element(By.XPATH, "//button[contains(text(), 'Add a note')]")
                    add_note.click()
                    msg_box = driver.find_element(By.TAG_NAME, "textarea")
                    msg_box.send_keys(message)
                    driver.find_element(By.XPATH, "//button[contains(text(), 'Send')]").click()
                except:
                    pass

                save_lead(profile_link, name_elem.text)
                print(f"Connected to {name_elem.text}")
                total_sent += 1
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                time.sleep(10)
            except:
                continue

    driver.quit()

def send_followups():
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT linkedin_url, name, followup_count FROM leads
        WHERE status = 'connected' AND followup_count < 4
    """)
    leads = cursor.fetchall()
    conn.close()

    driver = start_driver()
    driver.get("https://www.linkedin.com/")
    time.sleep(3)

    for url, name, count in leads:
        try:
            driver.get(url)
            time.sleep(3)
            msg_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Message')]")
            msg_btn.click()
            time.sleep(2)
            msg_box = driver.find_element(By.TAG_NAME, "textarea")
            msg_box.send_keys(messages["followups"][count])
            msg_box.send_keys(Keys.RETURN)
            update_followup(url)
            print(f"Sent follow-up to {name}")
            time.sleep(5)
        except Exception as e:
            print(f"Skipped {name}: {e}")

    driver.quit()

if __name__ == "__main__":
    init_db()
    region = input("Enter region: ")
    connect_msg = input("Enter message to send after connection: ")
    schedule.every().day.at("10:00").do(lambda: search_and_connect(region, connect_msg))
    schedule.every().day.at("11:00").do(send_followups)

    print("🚀 Bot running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(10)
