import os
import base64
from dotenv import load_dotenv
import resend
from pathlib import Path

# Load environment variables from .env
load_dotenv('.env')

# Set your Resend API key
resend.api_key = os.environ.get("RESEND_API_KEY")


def send_bid_email_with_attachment():
    """
    Send a test bid email with bid.pdf attached using Resend.
    """
    # Email configuration
    from_email = "ryane@developiq.ai"
    to_email = "bids@vanbrunt.developiq.co"
    
    # Read the PDF file
    pdf_path = Path("bid.pdf")
    if not pdf_path.exists():
        print(f"❌ Error: bid.pdf not found at {pdf_path.absolute()}")
        return None
    
    # Read and encode the PDF
    with open(pdf_path, 'rb') as f:
        pdf_content = f.read()
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
    
    # Prepare email parameters
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": "Test Bid Proposal - Plumbing Subcontractor XYZ-789",
        "html": """
            <h2>New Bid Proposal Submission</h2>
            <p>Dear Bid Management Team,</p>
            <p>Please find attached our bid proposal for the Construction Project ABC-123.</p>
            <ul>
                <li><strong>Project:</strong> Office Building Renovation</li>
                <li><strong>Location:</strong> 123 Main Street</li>
                <li><strong>Submission Date:</strong> November 2, 2025</li>
                <li><strong>Bid Amount:</strong> $450,000</li>
            </ul>
            <p>The attached PDF contains our detailed proposal including:</p>
            <ul>
                <li>Scope of work</li>
                <li>Timeline and milestones</li>
                <li>Cost breakdown</li>
                <li>Team qualifications</li>
            </ul>
            <p>Please confirm receipt of this bid proposal.</p>
            <p>Best regards,<br>
            Ryan E.<br>
            DevelopIQ Construction Division</p>
        """,
        "attachments": [
            {
                "filename": "bid_proposal_ABC123.pdf",
                "content": pdf_base64
            }
        ]
    }

    try:
        print("📧 Sending bid email to AgentMail...")
        print(f"   From: {from_email}")
        print(f"   To: {to_email}")
        print(f"   Subject: {params['subject']}")
        print(f"   Attachment: bid_proposal_ABC123.pdf ({len(pdf_content):,} bytes)")
        
        email = resend.Emails.send(params)
        
        print(f"\n✅ Email sent successfully!")
        print(f"   Email ID: {email['id']}")
        print(f"\n📌 The email will be processed by:")
        print(f"   1. AgentMail receives it at {to_email}")
        print(f"   2. Webhook triggers to your FastAPI backend")
        print(f"   3. LangGraph agent processes the bid")
        print(f"   4. PDF gets analyzed and uploaded to Google Drive")
        
        return email
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return None


if __name__ == "__main__":
    result = send_bid_email_with_attachment()
    
    if result:
        print("\n" + "="*60)
        print("📊 NEXT STEPS TO MONITOR:")
        print("="*60)
        print("1. Check LangGraph Studio: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024")
        print("2. Check FastAPI logs in terminal")
        print("3. Check Google Drive for uploaded file")
        print("4. Query database for new bid entry")