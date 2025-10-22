import os
import json
from typing import Optional, List, Any
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from agentmail import AgentMail
from app.agent import node_1_email_analysis, node_2a_analyze_attachment, node_2b_forward_email_to_subcontractor

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
            print(f"From: {message.from_}")
            print(f"Subject: {message.subject}")

            # Node 1: Surface level analysis
            print("\n[Node 1] Analyzing email relevance...")
            node1_result = await node_1_email_analysis(message.dict())

            print(f"  Relevant: {node1_result.get('relevant')}")
            print(f"  Needs Clarification: {node1_result.get('needs_clarification')}")
            print(f"  Bid Proposal Included: {node1_result.get('bid_proposal_included')}")

            # If irrelevant, skip
            if not node1_result.get('relevant'):
                print("\n❌ Email is irrelevant. Skipping.")
                print("="*80 + "\n")
                return {
                    "status": "ok",
                    "action": "skipped",
                    "reason": "irrelevant",
                    "analysis": {
                        "relevant": False,
                        "needs_clarification": False,
                        "bid_proposal_included": False,
                        "forward_result": None,
                        "attachment_analysis": None
                    }
                }

            # Extract node1 results
            needs_clarification = node1_result.get('needs_clarification')
            bid_proposal_included = node1_result.get('bid_proposal_included')

            # Handle string-to-boolean conversion
            if isinstance(needs_clarification, str):
                needs_clarification = needs_clarification.lower() == 'true'
            if isinstance(bid_proposal_included, str):
                bid_proposal_included = bid_proposal_included.lower() == 'true'

            final_result = {
                "relevant": True,
                "needs_clarification": needs_clarification,
                "bid_proposal_included": bid_proposal_included,
                "forward_result": None,  # Always include these keys
                "attachment_analysis": None
            }

            # Branch based on node1 results
            if needs_clarification:
                # Node 2b: Forward email to subcontractor for clarification
                print("\n[Node 2b] Email needs clarification. Forwarding to subcontractor...")
                node2b_result = await node_2b_forward_email_to_subcontractor(message.dict())
                print(f"  Status: {node2b_result.get('status')}")
                print(f"  Message ID: {node2b_result.get('message_id')}")
                final_result["forward_result"] = node2b_result

            elif bid_proposal_included:
                # Node 2a: Analyze bid proposal attachments
                print("\n[Node 2a] Analyzing attachments with Reducto...")
                node2a_result = await node_2a_analyze_attachment(message.dict())

                proposals = node2a_result.get('proposals', [])
                print(f"  Total attachments analyzed: {node2a_result.get('total_count', 0)}")

                for i, proposal in enumerate(proposals, 1):
                    print(f"\n  Proposal {i}:")
                    print(f"    Filename: {proposal.get('filename')}")
                    print(f"    Is Bid Proposal: {proposal.get('is_bid_proposal')}")
                    print(f"    Company: {proposal.get('company_name')}")
                    print(f"    Trade: {proposal.get('trade')}")
                    print(f"    Project: {proposal.get('project_name')}")
                    if proposal.get('error'):
                        print(f"    Error: {proposal.get('error')}")

                final_result["attachment_analysis"] = node2a_result

            print("="*80 + "\n")

            return {
                "status": "ok",
                "analysis": final_result
            }

        return {"status": "ok", "message": "Event type not handled"}

    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

