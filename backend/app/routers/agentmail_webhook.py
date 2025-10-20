import os
import json
from typing import Optional, List, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from agentmail import AgentMail
from app.agent import classify_email

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
    attachments: Optional[List[Any]] = None

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
            message = webhook_payload.message

            # Print the email
            print("\n" + "="*80)
            print("NEW EMAIL RECEIVED")
 
            # Classify the email using Dedalus AI
            print("\nClassifying email with AI...")
            classification = await classify_email(message.dict())

            # Print classification results
            print("\n" + "-"*80)
            print("CLASSIFICATION RESULTS:")
            print("-"*80)
            print(f"Email Type: {classification.get('email_type')}")
            print(f"Confidence: {classification.get('confidence')}")
            if classification.get('document'):
                print(f"Document: {classification['document'].get('filename')} ({classification['document'].get('status')})")
            print("="*80 + "\n")

            return {
                "status": "ok",
                "classification": classification
            }

        return {"status": "ok", "message": "Event type not handled"}

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

