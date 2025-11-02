import os
import requests
import json
from agentmail import AgentMail
from dotenv import load_dotenv

load_dotenv()

def trigger_webhook_for_latest_email():
    """Fetch latest email and manually trigger webhook."""
    
    # Get AgentMail client
    api_key = os.getenv("AGENTMAIL_API_KEY").strip()
    client = AgentMail(api_key=api_key)
    inbox_id = "bids@vanbrunt.developiq.co"
    
    print("Fetching latest email from AgentMail...")
    
    # Get latest message
    messages = list(client.inboxes.messages.list(inbox_id=inbox_id, limit=1))
    
    if not messages:
        print("No messages found!")
        return
    
    # Get full message details
    msg_id = messages[0].message_id
    full_message = client.inboxes.messages.get(
        inbox_id=inbox_id,
        message_id=msg_id
    )
    
    print(f"Found email: {full_message.subject}")
    print(f"From: {full_message.from_}")
    
    # Convert to webhook format
    attachments = None
    if full_message.attachments:
        attachments = []
        for att in full_message.attachments:
            att_dict = {
                "attachment_id": getattr(att, 'attachment_id', None),
                "filename": getattr(att, 'filename', ''),
                "content_type": getattr(att, 'content_type', 'application/octet-stream'),
                "size": getattr(att, 'size', 0)
            }
            attachments.append(att_dict)
            print(f"  Attachment: {att_dict['filename']} ({att_dict['size']} bytes)")
    
    webhook_payload = {
        "event_type": "message.received",
        "event_id": f"test_evt_{msg_id[:20]}",
        "message": {
            "message_id": msg_id,
            "inbox_id": inbox_id,
            "thread_id": getattr(full_message, 'thread_id', None),
            "from_": full_message.from_,
            "to": full_message.to,
            "subject": full_message.subject,
            "text": full_message.text,
            "html": full_message.html,
            "attachments": attachments
        }
    }
    
    # Send to local webhook
    webhook_url = "http://localhost:8000/webhooks/agentmail"
    print(f"\nTriggering webhook at {webhook_url}...")
    
    try:
        response = requests.post(
            webhook_url,
            json=webhook_payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Webhook processed successfully!")
            result = response.json()
            print("\nResponse Data:")
            print(json.dumps(result, indent=2))
            
            # Show key results
            if 'analysis' in result:
                analysis = result['analysis']
                print("\n📊 Analysis Results:")
                print(f"  - Bid Proposal: {analysis.get('bid_proposal_included', False)}")
                print(f"  - Should Forward: {analysis.get('should_forward', False)}")
                print(f"  - Action Taken: {result.get('action', 'unknown')}")
                
                if analysis.get('attachment_analysis'):
                    att_analysis = analysis['attachment_analysis']
                    if att_analysis.get('proposals'):
                        print("\n📄 Processed Attachments:")
                        for prop in att_analysis['proposals']:
                            print(f"  - {prop.get('filename')}")
                            print(f"    Status: {prop.get('status')}")
                            if prop.get('drive_upload', {}).get('success'):
                                print(f"    ✓ Uploaded to Drive")
            
        else:
            print(f"❌ Error: {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    trigger_webhook_for_latest_email()