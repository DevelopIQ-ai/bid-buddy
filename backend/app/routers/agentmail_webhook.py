import json
from typing import Optional, List, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from app.agent import process_email

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
            state = await process_email(webhook_payload.message.model_dump())

            # Determine action based on state
            action = "skipped"
            if state.get("is_buildingconnected"):
                action = "buildingconnected_extracted"
            elif state.get("bid_proposal_included"):
                action = "bid_proposal"
            elif state.get("should_forward"):
                action = "forwarded"

            return {
                "status": "ok",
                "action": action,
                "analysis": {
                    "is_buildingconnected": state.get("is_buildingconnected", False),
                    "bid_proposal_included": state.get("bid_proposal_included", False),
                    "should_forward": state.get("should_forward", False),
                    "forward_result": {
                        "status": state.get("forward_status"),
                        "message_id": state.get("forward_message_id")
                    } if state.get("forward_status") else None,
                    "attachment_analysis": {"proposals": state.get("proposals"), "total_count": state.get("total_count")} if state.get("proposals") else None,
                    "buildingconnected_data": state.get("buildingconnected_data") if state.get("buildingconnected_data") else None
                }
            }

        return {"status": "ok", "message": "Event type not handled"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

