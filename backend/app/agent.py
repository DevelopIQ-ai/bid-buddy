import asyncio
import json
import os
from typing import Dict, Any, Optional, TypedDict, Literal
from dedalus_labs import AsyncDedalus, DedalusRunner
from dotenv import load_dotenv
from agentmail import AgentMail
from app.utils.reducto import extract_from_file
from langgraph.graph import StateGraph, START, END

load_dotenv()


# Define the state schema for the email processing workflow
class EmailProcessingState(TypedDict, total=False):
    """State for the email processing workflow. All fields optional except message_data."""
    message_data: Dict[str, Any]  # Required
    bid_proposal_included: bool
    should_forward: bool
    proposals: list
    total_count: int
    forward_status: str
    forward_message_id: str
    error: str


async def llm_json_with_retry(
    prompt: str,
    model: str = "openai/gpt-4o-mini",
    max_retries: int = 3,
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Call LLM and parse JSON response with automatic retry on parsing failures.

    Args:
        prompt: The prompt to send to the LLM
        model: Model to use (default: openai/gpt-4o-mini)
        max_retries: Maximum number of retry attempts (default: 3)
        api_key: Optional API key (defaults to DEDALUS_API_KEY from env)

    Returns:
        Parsed JSON dict from LLM response

    Raises:
        ValueError: If JSON parsing fails after all retries
    """
    client = AsyncDedalus(api_key=api_key or os.getenv("DEDALUS_API_KEY"))
    runner = DedalusRunner(client)

    working_prompt = prompt

    for attempt in range(max_retries):
        try:
            result = await runner.run(input=working_prompt, model=model)
            response_text = result.final_output

            # Extract JSON from response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1

            if start >= 0 and end > start:
                json_str = response_text[start:end]
                return json.loads(json_str)
            else:
                raise ValueError("No JSON found in response")

        except Exception as e:
            if attempt < max_retries - 1:
                # Add error to prompt for next retry
                working_prompt += f"\n\nPrevious attempt failed with error: {str(e)}\nPlease respond with ONLY valid JSON, nothing else."
            else:
                # Final attempt failed
                raise ValueError(f"JSON parsing failed after {max_retries} attempts: {str(e)}")

    raise ValueError("Unexpected error in JSON retry mechanism")


async def email_analysis_node(state: EmailProcessingState) -> EmailProcessingState:
    """
    LangGraph Node: Analyze email to determine relevance and classification.

    This function now analyzes the ENTIRE email thread, not just the latest message.
    It checks all messages in the thread for PDF/DOCX attachments.

    Args:
        state: Current workflow state

    Returns:
        Updated state with analysis results

    Raises:
        ValueError: If thread_id or inbox_id is missing from message_data
    """
    message_data = state["message_data"]
    from_ = message_data.get('from_', '')
    subject = message_data.get('subject', '')
    text = message_data.get('text', '')
    thread_id = message_data.get('thread_id')
    inbox_id = message_data.get('inbox_id')

    # Validate required fields
    if not thread_id:
        raise ValueError("thread_id is required in message_data")
    if not inbox_id:
        raise ValueError("inbox_id is required in message_data")

    # Initialize AgentMail client to fetch complete thread
    client = AgentMail(api_key=os.getenv("AGENTMAIL_API_KEY"))

    # Fetch complete thread to check all messages for attachments
    thread_messages = []
    all_thread_attachments = []

    # Fetch complete thread with all messages
    thread = client.inboxes.threads.get(
        inbox_id=inbox_id,
        thread_id=thread_id
    )

    # Collect all messages and attachments from entire thread
    for msg in thread.messages:
        msg_attachments = msg.attachments or []
        thread_messages.append({
            "from": msg.from_,
            "subject": msg.subject,
            "text": msg.text[:500] if msg.text else "",
            "timestamp": str(msg.timestamp),
            "attachments": [getattr(att, 'filename', '') for att in msg_attachments]
        })

        # Collect all attachments from this message
        for att in msg_attachments:
            filename = getattr(att, 'filename', '')
            if filename.lower().endswith(('.pdf', '.docx', '.doc')):
                all_thread_attachments.append({
                    "filename": filename,
                    "message_id": msg.message_id,
                    "from": msg.from_
                })

    has_attachment = len(all_thread_attachments) > 0

    # Build thread context for prompt
    thread_context = "\n\n".join([
        f"Message from {msg['from']} at {msg['timestamp']}:\n"
        f"Subject: {msg['subject']}\n"
        f"Content: {msg['text']}\n"
        f"Attachments: {', '.join(msg['attachments']) if msg['attachments'] else 'None'}"
        for msg in thread_messages[:5]  # Include last 5 messages to avoid token limits
    ])

    attachment_list = "\n".join([
        f"  - {att['filename']} (from {att['from']})"
        for att in all_thread_attachments
    ])

    prompt = f"""You are a general contractor's assistant sorting emails from subcontractors bidding on construction projects.

    CLASSIFICATION RULES - You must classify emails into TWO categories:

    1. BID PROPOSAL INCLUDED (bid_proposal_included):
       - True ONLY if:
         * There is atleast one PDF/DOCX attachment in the thread 
         * There is some indication of the attachment being a bid proposal
       - False if:
         * No attachments in thread
         * "Proposal Submitted" without attachment (submitted elsewhere)
         * Attachments are images, signatures, or non-bid documents

    2. SHOULD FORWARD (should_forward):
       - True if email is:
         * A clarifying question from a subcontractor about project details
         * High-impact communication from subcontractor that admin should see
         * Request for information or clarification about bidding

       - False if email is:
         * Generic automated notifications from BuildingConnected/PlanHub
         * Simple "Bid Submitted" confirmations (no question or issue)
         * Marketing emails, spam, or newsletters
         * Welcome/signup emails
         * System-generated status updates with no action needed

    ENTIRE EMAIL THREAD CONTEXT:
    {thread_context if thread_context else f"Single message:\n- From: {from_}\n- Subject: {subject}\n- Content: {text[:1000] if text else 'No content'}"}

    ALL ATTACHMENTS IN THREAD (PDF/DOCX):
    {attachment_list if has_attachment else "No PDF/DOCX attachments found in thread"}

    Analyze this email thread and classify it.

    Respond with ONLY this JSON format:
    {{
        "bid_proposal_included": {"true (ONLY if has_attachment is True)" if has_attachment else "false (MUST be false - no attachment in thread)"},
        "should_forward": true or false
    }}"""

    try:
        result = await llm_json_with_retry(prompt)

        if not has_attachment:
            result["bid_proposal_included"] = False

        return {
            "bid_proposal_included": result.get("bid_proposal_included", False),
            "should_forward": result.get("should_forward", False)
        }
    except Exception as e:
        return {
            "bid_proposal_included": False,
            "should_forward": False,
            "error": f"Error analyzing email: {str(e)}"
        }

async def forward_email_node(state: EmailProcessingState) -> EmailProcessingState:
    """
    LangGraph Node: Forward email to subcontractor for clarification.

    Args:
        state: Current workflow state

    Returns:
        Updated state with forward results
    """
    message_data = state["message_data"]

    # TODO: Implement actual email forwarding logic
    return {
        "forward_status": "forwarded",
        "forward_message_id": message_data.get('message_id')
    }

async def analyze_attachment_node(state: EmailProcessingState) -> EmailProcessingState:
    """
    LangGraph Node: Download and analyze PDF/DOCX attachments with Reducto.

    This function now processes ALL attachments from the ENTIRE email thread,
    not just attachments from the latest message.

    Args:
        state: Current workflow state

    Returns:
        Updated state with attachment analysis results

    Raises:
        ValueError: If thread_id or inbox_id is missing from message_data
    """
    message_data = state["message_data"]
    inbox_id = message_data.get('inbox_id')
    thread_id = message_data.get('thread_id')

    # Validate required fields
    if not thread_id:
        raise ValueError("thread_id is required in message_data")
    if not inbox_id:
        raise ValueError("inbox_id is required in message_data")

    client = AgentMail(api_key=os.getenv("AGENTMAIL_API_KEY"))
    proposals = []

    # Collect all attachments from entire thread
    all_attachments_to_process = []

    # Fetch complete thread to get ALL attachments
    thread = client.inboxes.threads.get(
        inbox_id=inbox_id,
        thread_id=thread_id
    )

    # Iterate through all messages in thread
    for msg in thread.messages:
        msg_attachments = msg.attachments or []
        for att in msg_attachments:
            filename = getattr(att, 'filename', '')
            if filename.lower().endswith(('.pdf', '.docx', '.doc')):
                all_attachments_to_process.append({
                    "attachment_id": getattr(att, 'attachment_id', None),
                    "filename": filename,
                    "message_id": msg.message_id,
                    "from": msg.from_
                })

    print(f"[INFO] Processing {len(all_attachments_to_process)} attachments from entire thread")

    # Process each attachment from the thread
    for attachment in all_attachments_to_process:
        try:
            attachment_id = attachment.get('attachment_id')
            msg_id = attachment.get('message_id')
            filename = attachment.get('filename', 'document.pdf')

            # Get attachment bytes (iterator)
            attachment_bytes_iter = client.inboxes.messages.get_attachment(
                inbox_id=inbox_id,
                message_id=msg_id,
                attachment_id=attachment_id
            )

            # Collect bytes from iterator
            file_data = b''.join(attachment_bytes_iter)

            # Process with Reducto
            result = extract_from_file(file_data, filename, active_projects=[])

            # Debug: print what Reducto returned
            print(f"[DEBUG] Raw Reducto result for {filename}: {result}")

            # Helper to extract value from citation object or plain value
            def extract_value(field):
                if isinstance(field, dict) and 'value' in field:
                    return field['value']
                return field

            proposals.append({
                "filename": filename,
                "is_bid_proposal": extract_value(result.get("is_bid_proposal", False)),
                "company_name": extract_value(result.get("company_name")),
                "trade": extract_value(result.get("trade")),
                "project_name": extract_value(result.get("project_name")),
                "from_email": attachment.get('from'),
                "message_id": msg_id,
                "status": "analyzed"
            })

        except Exception as e:
            proposals.append({
                "error": str(e),
                "filename": attachment.get('filename', 'unknown'),
                "from_email": attachment.get('from'),
                "message_id": attachment.get('message_id'),
                "status": "error"
            })

    return {
        "proposals": proposals,
        "total_count": len(proposals)
    }

def route_after_analysis(state: EmailProcessingState) -> str:
    """Route based on email analysis: forward, analyze, or end."""
    # If bid proposal included, analyze attachments
    if state.get("bid_proposal_included"):
        return "analyze_attachment"
    # If should forward, forward to admin
    if state.get("should_forward"):
        return "forward_email"
    # Otherwise skip (irrelevant)
    return END


# Build the LangGraph workflow
workflow = StateGraph(EmailProcessingState)
workflow.add_node("email_analysis", email_analysis_node)
workflow.add_node("analyze_attachment", analyze_attachment_node)
workflow.add_node("forward_email", forward_email_node)
workflow.add_edge(START, "email_analysis")
workflow.add_conditional_edges(
    "email_analysis",
    route_after_analysis,
    {
        "forward_email": "forward_email",
        "analyze_attachment": "analyze_attachment",
        END: END
    }
)
workflow.add_edge("forward_email", END)
workflow.add_edge("analyze_attachment", END)
email_workflow = workflow.compile()


# Main entry point for processing emails
async def process_email(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an email through the LangGraph workflow."""
    return await email_workflow.ainvoke({"message_data": message_data})
