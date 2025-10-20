import os
from dotenv import load_dotenv
import resend

# Load environment variables from .env
load_dotenv('.env')

# Set your Resend API key
resend.api_key = os.environ.get("RESEND_API_KEY")


def send_test_email():
    """
    Send a simple test email using Resend.
    Make sure to set your RESEND_API_KEY environment variable.
    """
    # Hardcoded values - update these with your actual email addresses
    from_email = "kush@developiq.ai"

    to_email = "bidbuddy@agentmail.to"

    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": "Test Email from Bid Buddy",
        "html": "<h1>Hello!</h1><p>This is a test email sent from Bid Buddy using Resend.</p>",
    }

    try:
        email = resend.Emails.send(params)
        print(f" Email sent successfully!")
        print(f"Email ID: {email}")
        return email
    except Exception as e:
        print(f"L Error sending email: {e}")
        return None


if __name__ == "__main__":
    send_test_email()
