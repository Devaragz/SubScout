import sqlite3
import smtplib
from email.message import EmailMessage
import datetime
from collections import defaultdict
import os
from dotenv import load_dotenv

# Load the hidden .env file
load_dotenv()


def send_consolidated_alert(target_email, sub_names):
    msg = EmailMessage()
    msg['Subject'] = "🚨 SubScout Alert: Subscriptions Expiring Soon!"

    # Fetch secrets securely
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASS")

    msg['From'] = sender_email
    msg['To'] = target_email

    subs_list = "\n".join([f"- {name}" for name in sub_names])
    msg.set_content(f"Heads up! The following subscriptions are expiring within 7 days:\n\n{subs_list}")

    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"✅ Consolidated email sent to {target_email}!")
    except Exception as e:
        print(f"❌ Error sending email: {e}")


def check_expirations():
    conn = sqlite3.connect("subscriptions.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute('''
        SELECT users.email, subscriptions.name, subscriptions.due_date 
        FROM subscriptions
        JOIN users ON subscriptions.user_id = users.id
    ''')

    subs = cur.fetchall()
    today = datetime.date.today()

    # Group subscriptions by email address
    expiring_subs = defaultdict(list)

    for sub in subs:
        due = datetime.datetime.strptime(sub["due_date"], "%Y-%m-%d").date()
        days_left = (due - today).days

        if 0 <= days_left <= 7:
            expiring_subs[sub["email"]].append(sub["name"])

    # Send exactly one email per user
    for email, names in expiring_subs.items():
        send_consolidated_alert(email, names)

    conn.close()


if __name__ == "__main__":
    check_expirations()