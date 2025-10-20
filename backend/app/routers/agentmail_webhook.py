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
            # Initialize AgentMail client
            client = AgentMail(api_key=os.getenv("AGENTMAIL_API_KEY"))

            # Fetch the full email message
            message = client.inboxes.messages.get(
                inbox_id=webhook_payload.message.inbox_id,
                message_id=webhook_payload.message.message_id
            )

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

