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


def send_to_webhook(payload, webhook_url="https://bid-buddy-production.up.railway.app/webhooks/agentmail"):
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


def assess_result(email, result):
    """Assess if the email was processed adequately."""
    has_attachments = bool(email.attachments)
    bid_included = result.get('analysis', {}).get('bid_proposal_included', False)
    should_forward = result.get('analysis', {}).get('should_forward', False)
    action = result.get('action', 'unknown')

    assessment = {
        'status': 'UNKNOWN',
        'message': '',
        'expected_behavior': '',
        'actual_behavior': ''
    }

    # Determine expected vs actual
    if has_attachments and bid_included and action == 'bid_proposal':
        # Check if attachments were analyzed and uploaded
        att_analysis = result.get('analysis', {}).get('attachment_analysis')
        if att_analysis and att_analysis.get('proposals'):
            proposals = att_analysis.get('proposals', [])
            all_successful = all(
                p.get('status') == 'analyzed' and
                p.get('drive_upload', {}).get('success')
                for p in proposals
            )
            if all_successful:
                assessment['status'] = '✅ PASS'
                assessment['message'] = 'Email properly classified as bid, attachments analyzed and uploaded to Google Drive'
                assessment['expected_behavior'] = 'Classify as bid, extract info, upload to Drive'
                assessment['actual_behavior'] = f'All {len(proposals)} attachment(s) processed successfully'
            else:
                assessment['status'] = '⚠️  PARTIAL'
                assessment['message'] = 'Email classified correctly but some uploads failed'
                assessment['expected_behavior'] = 'All attachments should be uploaded'
                assessment['actual_behavior'] = 'Some uploads failed - check Google Drive credentials'
        else:
            assessment['status'] = '❌ FAIL'
            assessment['message'] = 'Email has attachments and classified as bid, but no analysis performed'
            assessment['expected_behavior'] = 'Analyze attachments with Reducto'
            assessment['actual_behavior'] = 'No attachment analysis found'

    elif has_attachments and not bid_included:
        assessment['status'] = '⚠️  REVIEW'
        assessment['message'] = 'Email has attachments but was not classified as bid proposal'
        assessment['expected_behavior'] = 'May be intentional if attachments are not bids'
        assessment['actual_behavior'] = 'Classified as non-bid despite having attachments'

    elif should_forward and action == 'forwarded':
        forward_result = result.get('analysis', {}).get('forward_result')
        if forward_result and forward_result.get('status') == 'forwarded':
            assessment['status'] = '✅ PASS'
            assessment['message'] = 'Email properly forwarded to admin'
            assessment['expected_behavior'] = 'Forward email to FORWARD_EMAIL_ADDRESS'
            assessment['actual_behavior'] = 'Email forwarded successfully'
        else:
            assessment['status'] = '❌ FAIL'
            assessment['message'] = 'Email should be forwarded but forward failed'
            assessment['expected_behavior'] = 'Forward to admin email'
            assessment['actual_behavior'] = 'Forward operation failed'

    elif action == 'skipped':
        assessment['status'] = '✅ PASS'
        assessment['message'] = 'Email correctly identified as non-actionable (skipped)'
        assessment['expected_behavior'] = 'Skip non-actionable emails'
        assessment['actual_behavior'] = 'Email skipped (no bid, no forward needed)'
    else:
        assessment['status'] = '❓ UNCLEAR'
        assessment['message'] = f'Unexpected state: action={action}, bid={bid_included}, forward={should_forward}'
        assessment['expected_behavior'] = 'Unknown'
        assessment['actual_behavior'] = 'Unexpected workflow result'

    return assessment


def test_multiple_emails(count=5):
    """Test multiple emails from the inbox."""
    api_key = os.getenv("AGENTMAIL_API_KEY")
    if not api_key:
        raise ValueError("AGENTMAIL_API_KEY not found")

    api_key = api_key.strip()
    client = AgentMail(api_key=api_key)
    inbox_id = "bids@vanbrunt.developiq.co"

    print("\n" + "=" * 80)
    print(f"TESTING {count} EMAILS FROM AGENTMAIL")
    print("=" * 80)

    # List messages - fetch MORE than we need so we can randomly sample
    print("\nFetching messages from inbox...")
    messages_iter = client.inboxes.messages.list(
        inbox_id=inbox_id,
        limit=50  # Fetch 50 messages for a good pool
    )

    # Collect all available messages
    all_messages = []
    for msg_item in messages_iter:
        # Get full message details
        full_msg = client.inboxes.messages.get(
            inbox_id=inbox_id,
            message_id=msg_item.message_id
        )
        all_messages.append(full_msg)

    print(f"Found {len(all_messages)} messages in pool")

    # Randomly sample the requested count
    if len(all_messages) > count:
        messages = random.sample(all_messages, count)
        print(f"Randomly selected {count} message(s) to test\n")
    else:
        messages = all_messages
        print(f"Using all {len(messages)} available messages\n")

    if not messages:
        raise ValueError("No messages found in inbox!")

    results = []

    for idx, email in enumerate(messages, 1):
        print("=" * 80)
        print(f"EMAIL #{idx} OF {len(messages)}")
        print("=" * 80)
        print(f"From: {email.from_}")
        print(f"Subject: {email.subject}")
        print(f"Attachments: {len(email.attachments) if email.attachments else 0}")
        if email.attachments:
            for att in email.attachments:
                print(f"  - {att.filename}")

        # Transform to webhook format
        payload = transform_to_webhook_format(email)

        # Send to webhook
        result = send_to_webhook(payload)

        if result:
            # Assess the result
            assessment = assess_result(email, result)

            print(f"\n📊 ASSESSMENT: {assessment['status']}")
            print(f"   {assessment['message']}")
            print(f"\n   Expected: {assessment['expected_behavior']}")
            print(f"   Actual: {assessment['actual_behavior']}")

            # Detailed results
            if result.get('analysis', {}).get('attachment_analysis'):
                att_analysis = result['analysis']['attachment_analysis']
                if att_analysis.get('proposals'):
                    print(f"\n   📄 Attachments Processed:")
                    for proposal in att_analysis['proposals']:
                        print(f"      • {proposal.get('filename')}")
                        print(f"        Company: {proposal.get('company_name', 'N/A')}")
                        print(f"        Trade: {proposal.get('trade', 'N/A')}")
                        print(f"        Project: {proposal.get('project_name', 'N/A')}")
                        if proposal.get('drive_upload', {}).get('success'):
                            drive = proposal['drive_upload']
                            print(f"        ✓ Drive: {drive.get('folder_name')}/{drive.get('file_name')}")
                        else:
                            print(f"        ✗ Drive upload failed")

            results.append({
                'email_num': idx,
                'from': email.from_,
                'subject': email.subject,
                'result': result,
                'assessment': assessment
            })
        else:
            print(f"\n❌ WEBHOOK FAILED")
            results.append({
                'email_num': idx,
                'from': email.from_,
                'subject': email.subject,
                'result': None,
                'assessment': {'status': '❌ FAIL', 'message': 'Webhook request failed'}
            })

        print()

    return results


def main():
    """Main test function."""
    print("\n" + "=" * 80)
    print("TEST: Process 5 Emails Through Webhook")
    print("=" * 80)

    try:
        # Test 5 emails
        results = test_multiple_emails(count=5)

        # Final Summary
        print("=" * 80)
        print("FINAL TEST REPORT")
        print("=" * 80)

        pass_count = sum(1 for r in results if r['assessment']['status'] == '✅ PASS')
        fail_count = sum(1 for r in results if '❌' in r['assessment']['status'])
        partial_count = sum(1 for r in results if '⚠️' in r['assessment']['status'])

        print(f"\nResults Summary:")
        print(f"  ✅ Pass: {pass_count}/{len(results)}")
        print(f"  ❌ Fail: {fail_count}/{len(results)}")
        print(f"  ⚠️  Partial/Review: {partial_count}/{len(results)}")

        print(f"\n\nDetailed Results:")
        for r in results:
            print(f"\n{r['email_num']}. {r['assessment']['status']} - {r['subject'][:60]}")
            print(f"   From: {r['from']}")
            print(f"   {r['assessment']['message']}")

    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
