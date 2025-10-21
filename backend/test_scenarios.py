import os
from dotenv import load_dotenv
import resend

load_dotenv('.env')
resend.api_key = os.environ.get("RESEND_API_KEY")

from_email = "bids@atlas.developiq.bid"
to_email = "bidbuddy@agentmail.to"


def test_question_no_attachment():
    """Test: Email with question, no attachment -> Should trigger Node 2b"""
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": "Question about the project timeline",
        "html": """
        <p>Hi,</p>
        <p>I have a few questions about the electrical work scope:</p>
        <ul>
            <li>What is the project timeline?</li>
            <li>Are materials included or bid separately?</li>
            <li>When do you need the bid by?</li>
        </ul>
        <p>Thanks,<br>John from ABC Electric</p>
        """,
    }

    try:
        email = resend.Emails.send(params)
        print("✅ QUESTION EMAIL sent successfully!")
        print(f"   Expected: relevant=true, needs_clarification=true, bid_proposal_included=false")
        print(f"   Should trigger: Node 2b (forward to subcontractor)")
        print(f"   Email ID: {email}\n")
        return email
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return None


def test_irrelevant_email():
    """Test: Irrelevant email -> Should skip/break"""
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": "Your LinkedIn profile was viewed",
        "html": """
        <p>Hi there,</p>
        <p>Your profile was viewed by 15 people this week!</p>
        <p>Upgrade to LinkedIn Premium to see who viewed your profile.</p>
        <p>Best,<br>LinkedIn Team</p>
        """,
    }

    try:
        email = resend.Emails.send(params)
        print("✅ IRRELEVANT EMAIL sent successfully!")
        print(f"   Expected: relevant=false")
        print(f"   Should: Skip and return action='skipped'")
        print(f"   Email ID: {email}\n")
        return email
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return None


def test_bid_proposal_mention():
    """Test: Email mentioning bid proposal (but no actual attachment) -> Might trigger Node 2a"""
    params: resend.Emails.SendParams = {
        "from": from_email,
        "to": [to_email],
        "subject": "Bid Proposal for Electrical Work",
        "html": """
        <p>Hi,</p>
        <p>Please find attached our bid proposal for the electrical work on your project.</p>
        <p>Our price is $45,000 for the full scope including materials and labor.</p>
        <p>Company: XYZ Electrical<br>
        Trade: Electrical<br>
        Project: Downtown Office Building</p>
        <p>Let us know if you have any questions.</p>
        <p>Thanks,<br>Mike from XYZ Electrical</p>
        """,
    }

    try:
        email = resend.Emails.send(params)
        print("✅ BID MENTION EMAIL sent successfully!")
        print(f"   Expected: relevant=true, bid_proposal_included=true (maybe false due to no attachment)")
        print(f"   Should trigger: Node 2a or might detect as question")
        print(f"   Email ID: {email}\n")
        return email
    except Exception as e:
        print(f"❌ Error: {e}\n")
        return None


if __name__ == "__main__":
    print("=" * 80)
    print("TESTING EMAIL FLOW - Watch your backend logs in the uvicorn terminal")
    print("=" * 80 + "\n")

    print("TEST 1: Question with no attachment")
    test_question_no_attachment()

    print("TEST 2: Irrelevant email")
    test_irrelevant_email()

    print("TEST 3: Bid proposal mention (no attachment)")
    test_bid_proposal_mention()

    print("=" * 80)
    print("All test emails sent! Check your backend logs for results.")
    print("=" * 80)
