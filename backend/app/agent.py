import asyncio
import json
import os
from typing import Dict, Any, Callable, Optional
from dedalus_labs import AsyncDedalus, DedalusRunner
from dotenv import load_dotenv

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


async def classify_email(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify an email to determine:
    1. If there's a PDF/DOCX document attached
    2. If it's a question about a project
    3. If it's something else
    """
    # Extract email data
    from_ = message_data.get('from_', '')
    subject = message_data.get('subject', '')
    text = message_data.get('text', '')
    attachments = message_data.get('attachments', [])

    # Check for valid attachments (PDF/DOCX only)
    attachment_info = ""
    valid_attachments = []
    if attachments:
        valid_attachments = [att for att in attachments if att.get('filename', '').lower().endswith(('.pdf', '.docx'))]
        if valid_attachments:
            attachment_info = "\nAttachments (PDF/DOCX only): " + ", ".join([att.get('filename', 'unknown') for att in valid_attachments])
        else:
            attachment_info = "\nAttachments: None (no PDF/DOCX files)"

    # Build prompt
    prompt = f"""Analyze this email and respond ONLY with valid JSON:

Email:
- From: {from_}
- Subject: {subject}
- Content: {text[:500] if text else 'No content'}
{attachment_info}

Classify the email into ONE of these types:
- "has_document": Email contains a PDF or DOCX attachment (proposal, bid, etc.)
- "is_question": Email is asking questions about a project that needs clarification
- "other": Anything else (general message, test email, etc.)

Respond with this exact JSON format:
{{
    "email_type": "has_document" or "is_question" or "other",
    "confidence": 0.95
}}

Note: confidence should be a number between 0 and 1 (e.g., 0.85, 0.95, 0.6)"""

    try:
        # Use retry mechanism to get JSON response
        classification = await llm_json_with_retry(prompt)

        # Add metadata
        classification["from"] = from_
        classification["subject"] = subject

        # If email has a document, download it from AgentMail
        if classification.get("email_type") == "has_document" and valid_attachments:
            classification["document"] = await download_document(message_data, valid_attachments[0])

        return classification

    except Exception as e:
        # Fallback if all retries failed
        return {
            "email_type": "other",
            "confidence": 0.0,
            "from": from_,
            "subject": subject,
            "error": f"Classification failed: {str(e)}"
        }


async def download_document(message_data: Dict[str, Any], attachment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Download a document attachment from AgentMail.

    Returns:
        Dict with document info: filename, size, content_type, download_url or content
    """
    try:
        from agentmail import AgentMail

        client = AgentMail(api_key=os.getenv("AGENTMAIL_API_KEY"))
        inbox_id = message_data.get('inbox_id')
        message_id = message_data.get('message_id')

        # Get the full message with attachments
        message = client.inboxes.messages.get(
            inbox_id=inbox_id,
            message_id=message_id
        )

        # Find the attachment and download it
        filename = attachment.get('filename', 'document')

        return {
            "filename": filename,
            "content_type": attachment.get('content_type', 'application/octet-stream'),
            "size": attachment.get('size', 0),
            "status": "downloaded"
        }
    except Exception as e:
        return {
            "filename": attachment.get('filename', 'unknown'),
            "status": "error",
            "error": str(e)
        }
