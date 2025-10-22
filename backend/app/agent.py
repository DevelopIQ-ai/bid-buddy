import asyncio
import json
import os
from typing import Dict, Any, Optional
from dedalus_labs import AsyncDedalus, DedalusRunner
from dotenv import load_dotenv
from agentmail import AgentMail
from app.utils.reducto import extract_from_file

load_dotenv()


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


async def node_1_email_analysis(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Check if email is relevant, and if so, is it requesting clarification about the project, and is it a bid proposal.

    Args:
        message_data: Email message data from AgentMail

    Returns:
        Dict with:
        - relevant: bool
        - needs_clarification: bool
        - bid_proposal_included: bool
    """
    from_ = message_data.get('from_', '')
    subject = message_data.get('subject', '')
    text = message_data.get('text', '')
    attachments = message_data.get('attachments') or []

    has_attachment = False
    if attachments:
        for att in attachments:
            filename = att.get('filename', '')
            if filename.lower().endswith(('.pdf', '.docx')):
                has_attachment = True
                break

    prompt = f"""You are a general contractor's assistant sorting emails from subcontractors bidding on construction projects.

    CLASSIFICATION RULES:

    RELEVANT emails are:
    - Bid proposals or estimates from construction companies
    - Questions about specific construction projects
    - Updates on submitted bids or proposals
    - Communications from BuildingConnected, PlanHub about specific projects
    - Emails mentioning specific projects (Panda Express, O'Reilly, Yogurtland, etc.)

    IRRELEVANT emails are:
    - Marketing emails about software tools (Reducto, Autodesk, etc.)
    - Welcome/signup confirmation emails
    - Generic product announcements
    - Newsletter-style content
    - Emails not related to construction bidding

    BID PROPOSAL RULES:
    1. bid_proposal_included = true ONLY if there is a PDF/DOCX attachment AND the email mentions submitting a bid/proposal
    2. If NO attachment, bid_proposal_included MUST be false
    3. "Proposal Submitted" without attachment means they submitted elsewhere, not included here

    NEEDS CLARIFICATION:
    - True if the email is asking questions about project details
    - True if requesting more information about the project

    Email:
    - From: {from_}
    - Subject: {subject}
    - Content: {text[:1000] if text else 'No content'}
    - Has PDF/DOCX attachment: {has_attachment}

    Determine if this email is relevant, and if so, is it requesting clarification about the project, and is it a bid proposal.

    Respond with ONLY this JSON format:
    {{
        "relevant": true or false,
        "needs_clarification": true or false,
        "bid_proposal_included": {"true (ONLY if has_attachment is True)" if has_attachment else "false (MUST be false - no attachment)"}
    }}"""

    try:
        result = await llm_json_with_retry(prompt)

        if not has_attachment:
            result["bid_proposal_included"] = False

        return result
    except Exception as e:
        return {
            "relevant": False,
            "needs_clarification": False,
            "bid_proposal_included": False,
            "error": f"Error analyzing email: {str(e)}"
        }


async def node_2b_forward_email_to_subcontractor(message_data: Dict[str, Any]) -> Dict[str, Any]:

    return {
        "status": "forwarded",
        "message_id": message_data.get('message_id')
    }

async def node_2a_analyze_attachment(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Download all PDF/DOCX attachments and analyze them with Reducto.

    Args:
        message_data: Email message data from AgentMail

    Returns:
        Dict with list of proposal analyses from Reducto
    """

    attachments = message_data.get('attachments') or []
    inbox_id = message_data.get('inbox_id')
    message_id = message_data.get('message_id')

    # Find all PDF/DOCX attachments
    valid_attachments = []
    for att in attachments:
        filename = att.get('filename', '')
        if filename.lower().endswith(('.pdf', '.docx')):
            valid_attachments.append(att)

    client = AgentMail(api_key=os.getenv("AGENTMAIL_API_KEY"))
    proposals = []

    # Process each attachment
    for attachment in valid_attachments:
        try:
            attachment_id = attachment.get('attachment_id')

            # Get attachment bytes (iterator)
            attachment_bytes_iter = client.inboxes.messages.get_attachment(
                inbox_id=inbox_id,
                message_id=message_id,
                attachment_id=attachment_id
            )

            # Collect bytes from iterator
            file_data = b''.join(attachment_bytes_iter)

            # Process with Reducto
            filename = attachment.get('filename', 'document.pdf')
            result = extract_from_file(file_data, filename, active_projects=[])

            # Debug: print what Reducto returned
            print(f"    [DEBUG] Raw Reducto result: {result}")

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
                "status": "analyzed"
            })

        except Exception as e:
            proposals.append({
                "error": str(e),
                "filename": attachment.get('filename', 'unknown'),
                "status": "error"
            })

    return {
        "proposals": proposals,
        "total_count": len(proposals)
    }
