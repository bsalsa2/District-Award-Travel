import psutil
import smtplib
from email.mime.text import MIMEText

# Define the threshold for CPU usage
CPU_THRESHOLD = 80

# Define the email configuration
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
FROM_EMAIL = 'district.award.travel@example.com'
TO_EMAIL = 'mitchell@example.com'
PASSWORD = 'password123'

def get_cpu_usage():
    """Get the current CPU usage"""
    return psutil.cpu_percent(interval=1)

def send_email(subject, body):
    """Send an email notification"""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = FROM_EMAIL
    msg['To'] = TO_EMAIL

    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(FROM_EMAIL, PASSWORD)
    server.sendmail(FROM_EMAIL, TO_EMAIL, msg.as_string())
    server.quit()

def check_cpu_usage():
    """Check the CPU usage and send an alert if it exceeds the threshold"""
    cpu_usage = get_cpu_usage()
    if cpu_usage > CPU_THRESHOLD:
        subject = 'High CPU Usage Alert'
        body = f'CPU usage is currently at {cpu_usage}%'
        send_email(subject, body)

if __name__ == '__main__':
    check_cpu_usage()
