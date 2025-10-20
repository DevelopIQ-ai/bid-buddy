import os
import json
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from agentmail import AgentMail

load_dotenv()

router = APIRouter()

class MessageData(BaseModel):
    message_id: str
    inbox_id: str
    thread_id: str
    from_: Optional[str] = None
    to: Optional[list] = None
    subject: Optional[str] = None
    text: Optional[str] = None
    html: Optional[str] = None

class WebhookPayload(BaseModel):
    event_type: str
    event_id: str
    message: MessageData

@router.post("/agentmail")
async def handle_agentmail_webhook(request: Request):
    try:
        payload = await request.body()
        event_data = json.loads(payload.decode('utf-8'))
        webhook_payload = WebhookPayload(**event_data)

        if webhook_payload.event_type == "message.received":
            # Use the message data from the webhook payload directly
            # No need to fetch it again since body_included is true
            message = webhook_payload.message

            # Print the email
            print("\n" + "="*80)
            print("NEW EMAIL RECEIVED")
            print("="*80)
            print(f"From: {message.from_}")
            print(f"To: {message.to}")
            print(f"Subject: {message.subject}")
            print(f"Text: {message.text}")
            if message.html:
                print(f"HTML: {message.html[:200]}...")
            print("="*80 + "\n")

            return {"status": "ok"}

        return {"status": "ok", "message": "Event type not handled"}

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

