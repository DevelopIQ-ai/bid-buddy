"""
Test script to sample a real email from AgentMail and send it to the webhook endpoint.
This simulates what happens when a real webhook is triggered.
"""
import os
import random
import requests
import json
from agentmail import AgentMail
from dotenv import load_dotenv

load_dotenv()


def sample_random_email():
    """Sample a random email from AgentMail inbox."""
    api_key = os.getenv("AGENTMAIL_API_KEY")
    if not api_key:
        raise ValueError("AGENTMAIL_API_KEY not found")

    api_key = api_key.strip()
    client = AgentMail(api_key=api_key)
    inbox_id = "bids@vanbrunt.developiq.co"

    print("=" * 80)
    print("SAMPLING RANDOM EMAIL FROM AGENTMAIL")
    print("=" * 80)

    # List messages
    print("\n1. Fetching messages from inbox...")
    messages_iter = client.inboxes.messages.list(
        inbox_id=inbox_id,
        limit=50  # Get 50 messages to have a good pool
    )

    messages = list(messages_iter)
    print(f"   Found {len(messages)} messages")

    if not messages:
        raise ValueError("No messages found in inbox!")

    # Pick random message
    random_msg = random.choice(messages)
    print(f"\n2. Randomly selected message:")
    print(f"   ID: {random_msg.message_id}")
    print(f"   Subject: {random_msg.subject}")
    print(f"   From: {random_msg.from_}")

    # Get full message details
    print(f"\n3. Fetching full message details...")
    full_message = client.inboxes.messages.get(
        inbox_id=inbox_id,
        message_id=random_msg.message_id
    )

    return full_message


def transform_to_webhook_format(message):
    """Transform AgentMail message to webhook payload format."""
    print("\n4. Transforming to webhook format...")

    # Convert attachments to dict format
    attachments = None
    if message.attachments:
        attachments = []
        for att in message.attachments:
            # Convert Attachment object to dict
            att_dict = {
                "attachment_id": getattr(att, 'attachment_id', None),
                "filename": getattr(att, 'filename', ''),
                "content_type": getattr(att, 'content_type', 'application/octet-stream'),
                "size": getattr(att, 'size', 0)
            }
            attachments.append(att_dict)

    webhook_payload = {
        "event_type": "message.received",
        "event_id": f"test_evt_{message.message_id[:20]}",
        "message": {
            "message_id": message.message_id,
            "inbox_id": message.inbox_id,
            "thread_id": message.thread_id,
            "from_": message.from_,
            "to": message.to,
            "subject": message.subject,
            "text": message.text,
            "html": message.html,
            "attachments": attachments
        }
    }

    print(f"   ✓ Payload created")
    print(f"   Event ID: {webhook_payload['event_id']}")
    print(f"   Message has attachments: {bool(attachments)}")
    if attachments:
        print(f"   Attachment count: {len(attachments)}")
        for att in attachments:
            print(f"     - {att['filename']}")

    return webhook_payload


def send_to_webhook(payload, webhook_url="http://localhost:8000/webhooks/agentmail"):
    """Send the payload to the webhook endpoint."""
    print(f"\n5. Sending to webhook: {webhook_url}")

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60  # 60 second timeout for processing
        )

        print(f"   Response Status: {response.status_code}")

        if response.status_code == 200:
            print(f"   ✓ Webhook processed successfully!")
            result = response.json()
            print(f"\n   Response Data:")
            print(json.dumps(result, indent=4))
            return result
        else:
            print(f"   ✗ Webhook returned error")
            print(f"   Error: {response.text}")
            return None

    except requests.exceptions.ConnectionError:
        print(f"   ✗ Could not connect to webhook endpoint")
        print(f"   Make sure the server is running on {webhook_url}")
        return None
    except Exception as e:
        print(f"   ✗ Error: {str(e)}")
        return None


def main():
    """Main test function."""
    print("\n" + "=" * 80)
    print("TEST: Send Real Email to Webhook Endpoint")
    print("=" * 80)

    try:
        # Step 1: Sample random email
        email = sample_random_email()

        # Step 2: Transform to webhook format
        payload = transform_to_webhook_format(email)

        # Step 3: Send to webhook
        result = send_to_webhook(payload)

        # Summary
        print("\n" + "=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)

        if result:
            print("\n✅ Test successful!")
            print(f"\nSummary:")
            print(f"  - Action: {result.get('action', 'unknown')}")
            print(f"  - Bid proposal included: {result.get('analysis', {}).get('bid_proposal_included', 'N/A')}")
            print(f"  - Should forward: {result.get('analysis', {}).get('should_forward', 'N/A')}")

            # Show forward result if present
            if result.get('analysis', {}).get('forward_result'):
                forward_result = result['analysis']['forward_result']
                print(f"\n  Forward Result:")
                print(f"    - Status: {forward_result.get('status')}")

            # Show attachment analysis if present
            if result.get('analysis', {}).get('attachment_analysis'):
                att_analysis = result['analysis']['attachment_analysis']
                print(f"\n  Attachments analyzed: {att_analysis.get('total_count', 0)}")
                if att_analysis.get('proposals'):
                    print(f"  Proposals:")
                    for proposal in att_analysis['proposals']:
                        print(f"    - {proposal.get('filename')}: {proposal.get('company_name', 'N/A')} ({proposal.get('trade', 'N/A')})")
        else:
            print("\n✗ Test failed - check errors above")

    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
