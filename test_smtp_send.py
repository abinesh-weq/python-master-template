import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
USERNAME = "abineshatweq@gmail.com"
PASSWORD = "zhqeyvoyjbkxmdlm"  # Replace with real app password

TO_ADDRESS = "abinesh.r@weqtechnologies.com"  # test recipient


def send_test_email():
    msg = EmailMessage()
    msg["From"] = "noreply@audi.com"
    msg["To"] = TO_ADDRESS
    msg["Subject"] = "SMTP Capability Check"
    msg.set_content("Hi Karan,\n\nThis is a test email to verify SMTP sending capability from the backend application.\n\nBest,\nWeQ Team")

    print(f"Connecting to SMTP {SMTP_HOST}:{SMTP_PORT}...")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.set_debuglevel(1)  # prints SMTP conversation
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            print("Logging in...")
            smtp.login(USERNAME, PASSWORD)
            print("Sending test email...")
            smtp.send_message(msg)
            print("Email sent successfully!")
            return True
    except Exception as exc:
        print("Failed to send email.")
        print(type(exc).__name__, exc)
        return False


if __name__ == "__main__":
    ok = send_test_email()
    if not ok:
        print("Check host/port/username/password or network/Google SMTP settings.")
