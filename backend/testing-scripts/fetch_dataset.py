#!/usr/bin/env python3
"""
Fetch last 30 emails from bids@vanbrunt.developiq.co and create dataset JSON file.
This script fetches real emails and attachments from AgentMail to create test data.
"""

import os
import json
import base64
from typing import Dict, List, Any, Optional
from typing import Any
from dotenv import load_dotenv
from agentmail import AgentMail

load_dotenv()

def fetch_emails_from_agentmail(limit: int = 30):
    """
    Fetch the last N emails from bids@vanbrunt.developiq.co inbox.
    
    Args:
        limit: Number of emails to fetch (default: 30)
    
    Returns:
        Tuple of (list of email messages, inbox_id)
    """
    api_key = os.getenv("AGENTMAIL_API_KEY").strip()
    if not api_key:
        raise ValueError("AGENTMAIL_API_KEY not found in environment variables")
    
    print(f"Using API key: {api_key[:15]}...")
    
    # Initialize client
    client = AgentMail(api_key=api_key)
    
    # Use the inbox ID directly (it's the email address)
    inbox_id = "bids@vanbrunt.developiq.co"
    print(f"Using inbox ID: {inbox_id}")
    
    # Fetch messages from the inbox
    print(f"Fetching last {limit} messages...")
    
    messages_iter = client.inboxes.messages.list(
        inbox_id=inbox_id,
        limit=limit
    )
    
    # Convert iterator to list and collect full message data
    messages_list = []
    count = 0
    for msg in messages_iter:
        count += 1
        print(f"  {count}. {msg.subject[:60]}...")
        
        # Get full message details
        try:
            full_message = client.inboxes.messages.retrieve(
                inbox_id=inbox_id,
                message_id=msg.message_id
            )
            messages_list.append(full_message)
        except:
            # If can't get full details, use what we have
            messages_list.append(msg)
        
        if count >= limit:
            break
    
    print(f"Successfully fetched {len(messages_list)} messages")
    return messages_list, inbox_id, client

def fetch_attachment_bytes(client: AgentMail, inbox_id: str, message_id: str, attachment_id: str) -> bytes:
    """
    Fetch attachment bytes from AgentMail.
    
    Args:
        client: AgentMail client instance
        inbox_id: ID of the inbox
        message_id: ID of the message
        attachment_id: ID of the attachment
    
    Returns:
        Raw bytes of the attachment
    """
    # Use the SDK method that we know works
    attachment_bytes_iter = client.inboxes.messages.get_attachment(
        inbox_id=inbox_id,
        message_id=message_id,
        attachment_id=attachment_id
    )
    
    # Collect bytes from iterator
    return b''.join(attachment_bytes_iter)

def format_message_for_webhook(message: Any, inbox_id: str) -> Dict[str, Any]:
    """
    Format a message object to match the webhook payload structure.
    
    Args:
        message: Message object from SDK
        inbox_id: ID of the inbox
    
    Returns:
        Dict formatted as webhook payload
    """
    # Get message attributes
    msg_id = getattr(message, 'message_id', None)
    thread_id = getattr(message, 'thread_id', msg_id)
    from_addr = getattr(message, 'from_', None) or getattr(message, 'from', None)
    to_addrs = getattr(message, 'to', [f"bids@vanbrunt.developiq.co"])
    subject = getattr(message, 'subject', '')
    text = getattr(message, 'text', '')
    html = getattr(message, 'html', None)
    attachments_raw = getattr(message, 'attachments', [])
    
    # Format attachments list
    attachments = []
    if attachments_raw:
        for att in attachments_raw:
            attachments.append({
                "attachment_id": getattr(att, 'attachment_id', None),
                "filename": getattr(att, 'filename', ''),
                "content_type": getattr(att, 'content_type', 'application/octet-stream'),
                "size": getattr(att, 'size', 0)
            })
    
    # Build the webhook payload structure
    webhook_payload = {
        "event_type": "message.received",
        "event_id": f"evt_{msg_id}",
        "message": {
            "message_id": msg_id,
            "inbox_id": inbox_id,
            "thread_id": thread_id,
            "from_": from_addr,
            "to": to_addrs,
            "subject": subject,
            "text": text,
            "html": html,
            "attachments": attachments
        }
    }
    
    return webhook_payload

def create_dataset(limit: int = 30):
    """
    Create the complete dataset with emails and attachments.
    
    Args:
        limit: Number of emails to fetch
    """
    # Fetch emails
    messages, inbox_id, client = fetch_emails_from_agentmail(limit)
    
    # Prepare dataset
    dataset = {
        "metadata": {
            "inbox": "bids@vanbrunt.developiq.co",
            "total_emails": len(messages),
            "description": "Test dataset for bid processing system"
        },
        "test_cases": []
    }
    
    # Process each message
    for i, message in enumerate(messages):
        subject = getattr(message, 'subject', 'No subject')
        print(f"\nProcessing email {i+1}/{len(messages)}: {subject[:60]}...")
        
        # Format message for webhook
        webhook_payload = format_message_for_webhook(message, inbox_id)
        
        # Prepare test case
        test_case = {
            "input": webhook_payload,
            "attachment_contents": {},
            "expected_output": {
                "status": "ok",
                "action": None,  # To be filled manually
                "reason": None,  # To be filled manually  
                "analysis": {
                    "relevant": None,  # To be filled manually
                    "needs_clarification": None,  # To be filled manually
                    "bid_proposal_included": None,  # To be filled manually
                    "forward_result": None,  # To be filled manually if needs_clarification is true
                    "attachment_analysis": None  # To be filled manually if bid_proposal_included is true
                }
            }
        }
        
        # Fetch attachment contents if present
        if webhook_payload["message"]["attachments"]:
            print(f"  Fetching {len(webhook_payload['message']['attachments'])} attachment(s)...")
            
            for att in webhook_payload["message"]["attachments"]:
                attachment_id = att["attachment_id"]
                filename = att["filename"]
                
                # Only fetch PDF and DOCX attachments
                if filename.lower().endswith(('.pdf', '.docx')):
                    try:
                        print(f"    - Fetching {filename}...")
                        attachment_bytes = fetch_attachment_bytes(
                            client,
                            inbox_id,
                            webhook_payload["message"]["message_id"],
                            attachment_id
                        )
                        
                        # Encode to base64 for JSON storage
                        encoded = base64.b64encode(attachment_bytes).decode('utf-8')
                        test_case["attachment_contents"][attachment_id] = encoded
                        
                        print(f"      ✓ Fetched {len(attachment_bytes)} bytes")
                        
                    except Exception as e:
                        print(f"      ✗ Error fetching attachment: {str(e)}")
                        test_case["attachment_contents"][attachment_id] = None
                else:
                    print(f"    - Skipping {filename} (not PDF/DOCX)")
        
        # Add expected output template for manual filling
        if test_case["attachment_contents"]:
            # Template for attachment analysis
            test_case["expected_output"]["analysis"]["attachment_analysis"] = {
                "proposals": [
                    {
                        "filename": att["filename"],
                        "is_bid_proposal": None,  # To be filled manually
                        "company_name": None,  # To be filled manually
                        "trade": None,  # To be filled manually
                        "project_name": None,  # To be filled manually
                        "status": "analyzed"
                    }
                    for att in webhook_payload["message"]["attachments"]
                    if att["filename"].lower().endswith(('.pdf', '.docx'))
                ],
                "total_count": len([a for a in webhook_payload["message"]["attachments"] 
                                   if a["filename"].lower().endswith(('.pdf', '.docx'))])
            }
        
        dataset["test_cases"].append(test_case)
    
    # Save dataset to JSON file
    output_path = "dataset/email_dataset.json"
    os.makedirs("dataset", exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(dataset, f, indent=2)
    
    print(f"\n✅ Dataset saved to {output_path}")
    print(f"Total test cases: {len(dataset['test_cases'])}")
    print(f"Test cases with attachments: {sum(1 for tc in dataset['test_cases'] if tc['attachment_contents'])}")
    print("\n⚠️  Remember to manually fill in the expected_output fields in the JSON file!")

if __name__ == "__main__":
    create_dataset(limit=30)