import asyncio
import json
import os
from typing import Dict, Any, Optional, TypedDict, Literal, List
from dedalus_labs import AsyncDedalus, DedalusRunner
from dotenv import load_dotenv
from agentmail import AgentMail
from app.utils.reducto import extract_from_file
from app.utils.google_drive import upload_attachment_to_drive, get_supabase_service_client
from app.utils.building_connected_email_extractor import (
    BuildingConnectedEmailExtractor,
    should_process_buildingconnected
)
from langgraph.graph import StateGraph, START, END
from supabase import create_client, Client
import logging

load_dotenv()

logger = logging.getLogger(__name__)


def get_enabled_projects() -> List[str]:
    """
    Fetch all enabled projects from the database for the primary user.

    Returns:
        List of project names that are enabled

    Raises:
        ValueError: If PRIMARY_USER_EMAIL is not configured
        RuntimeError: If unable to fetch projects from database
    """
    from app.utils.google_drive import get_supabase_service_client

    PRIMARY_USER_EMAIL = os.getenv("PRIMARY_USER_EMAIL")

    if not PRIMARY_USER_EMAIL:
        raise ValueError("PRIMARY_USER_EMAIL must be set in environment - this is the email of the account that owns the Google Drive")

    try:
        # Use service role client to bypass RLS policies
        supabase = get_supabase_service_client()

        # First get the user ID from email via profiles table
        profile_response = supabase.table('profiles').select('id').eq('email', PRIMARY_USER_EMAIL).execute()

        if not profile_response.data:
            raise RuntimeError(f"No user found with email {PRIMARY_USER_EMAIL}. Please ensure the user has signed in at least once.")

        user_id = profile_response.data[0]['id']
        logger.info(f"Found user_id: {user_id} for email: {PRIMARY_USER_EMAIL}")

        # Query enabled projects for the primary user
        response = supabase.table('projects').select('name').eq('enabled', True).eq('user_id', user_id).execute()
        logger.info(f"Projects query returned {len(response.data) if response.data else 0} results")

        if not response.data:
            raise RuntimeError(f"No enabled projects found for user {PRIMARY_USER_EMAIL}. Please enable at least one project in the dashboard.")

        project_names = [project['name'] for project in response.data]
        logger.info(f"Loaded {len(project_names)} enabled projects from database for {PRIMARY_USER_EMAIL}")
        return project_names

    except Exception as e:
        logger.error(f"Error fetching enabled projects: {e}")
        raise RuntimeError(f"Failed to fetch enabled projects from database: {str(e)}")


# Define the state schema for the email processing workflow
class EmailProcessingState(TypedDict, total=False):
    """State for the email processing workflow. All fields optional except message_data."""
    message_data: Dict[str, Any]  # Required
    file_data: bytes
    bid_proposal_included: bool
    should_forward: bool
    proposals: list
    total_count: int
    forward_status: str
    forward_message_id: str
    error: str
    is_buildingconnected: bool
    buildingconnected_data: Dict[str, Any]


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


async def check_buildingconnected_node(state: EmailProcessingState) -> EmailProcessingState:
    """
    LangGraph Node: Check if email is from BuildingConnected
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with BuildingConnected flag
    """
    message_data = state["message_data"]
    
    # Check if it's a BuildingConnected email
    is_buildingconnected = should_process_buildingconnected(message_data)
    
    logger.info(f"BuildingConnected email check: {is_buildingconnected}")
    
    return {
        "is_buildingconnected": is_buildingconnected
    }


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
    try:
        thread = client.inboxes.threads.get(
            inbox_id=inbox_id,
            thread_id=thread_id
        )
    except Exception as e:
        # If thread fetch fails, log the error and return default classification
        logger.error(f"Failed to fetch thread {thread_id} from inbox {inbox_id}: {str(e)}")
        return {
            "bid_proposal_included": False,
            "should_forward": False,
            "error": f"Failed to fetch email thread: {str(e)}"
        }

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
            filename = getattr(att, 'filename', '') or ''
            if filename and filename.lower().endswith(('.pdf', '.docx', '.doc')):
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
    LangGraph Node: Forward email to admin using AgentMail.

    Args:
        state: Current workflow state

    Returns:
        Updated state with forward results
    """
    message_data = state["message_data"]
    forward_to = os.getenv("FORWARD_EMAIL_ADDRESS")
    inbox_id = message_data.get('inbox_id')

    if not forward_to:
        print("[ERROR] FORWARD_EMAIL_ADDRESS not set in environment")
        return {
            "forward_status": "failed",
            "error": "FORWARD_EMAIL_ADDRESS not configured"
        }

    client = AgentMail(api_key=os.getenv("AGENTMAIL_API_KEY"))

    try:
        # Forward using AgentMail send
        result = client.inboxes.messages.send(
            inbox_id=inbox_id,
            to=[forward_to],
            subject=f"[Action Required] {message_data.get('subject', 'No Subject')}",
            text=f"This email requires your attention:\n\n{message_data.get('text', '')}"
        )

        print(f"[INFO] Email forwarded to {forward_to}")
        return {
            "forward_status": "forwarded",
            "forward_message_id": str(result)
        }
    except Exception as e:
        print(f"[ERROR] Failed to forward email: {str(e)}")
        return {
            "forward_status": "failed",
            "error": str(e)
        }

async def extract_buildingconnected_data_node(state: EmailProcessingState) -> EmailProcessingState:
    """
    LangGraph Node: Extract data from BuildingConnected emails
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated state with extracted BuildingConnected data
    """
    message_data = state["message_data"]
    
    try:
        # Extract data from BuildingConnected email
        extractor = BuildingConnectedEmailExtractor()
        extracted_data = extractor.process_buildingconnected_email(message_data)
        
        logger.info(f"BuildingConnected extraction complete: {extracted_data}")
        
        return {
            "buildingconnected_data": extracted_data,
            "bid_proposal_included": False  # We're not downloading/processing proposals
        }
        
    except Exception as e:
        logger.error(f"BuildingConnected extraction failed: {e}")
        return {
            "buildingconnected_data": {
                "success": False,
                "error": str(e)
            },
            "error": f"BuildingConnected extraction failed: {str(e)}"
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
    try:
        thread = client.inboxes.threads.get(
            inbox_id=inbox_id,
            thread_id=thread_id
        )
    except Exception as e:
        # If thread fetch fails, return error state
        logger.error(f"Failed to fetch thread {thread_id} for attachment analysis: {str(e)}")
        return {
            "proposals": [],
            "total_count": 0,
            "error": f"Failed to fetch email thread for attachment analysis: {str(e)}"
        }

    # Iterate through all messages in thread
    for msg in thread.messages:
        msg_attachments = msg.attachments or []
        for att in msg_attachments:
            filename = getattr(att, 'filename', '') or ''
            if filename and filename.lower().endswith(('.pdf', '.docx', '.doc')):
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

            # Get dynamically loaded enabled projects from database
            enabled_projects = get_enabled_projects()
            
            # Process with Reducto
            result = extract_from_file(file_data, filename, active_projects=enabled_projects)

            # Debug: print what Reducto returned
            print(f"[DEBUG] Raw Reducto result for {filename}: {result}")

            # Helper to extract value from citation object or plain value
            def extract_value(field):
                if isinstance(field, dict) and 'value' in field:
                    return field['value']
                return field

            # Extract values from the Reducto result
            is_bid_proposal = extract_value(result.get("is_bid_proposal", False))
            company_name = extract_value(result.get("company_name"))
            trade = extract_value(result.get("trade"))
            project_name = extract_value(result.get("project_name"))
            
            # Upload to Google Drive and track proposal if it's a bid
            drive_upload_result = None
            if is_bid_proposal and company_name and trade:
                try:
                    drive_upload_result = upload_attachment_to_drive(
                        file_data=file_data,
                        original_filename=filename,
                        company_name=company_name,
                        trade=trade,
                        project_name=project_name
                    )
                    print(f"[INFO] Uploaded to Google Drive: {drive_upload_result}")
                    
                    # Track proposal in database
                    track_proposal(
                        company_name=company_name,
                        trade_name=trade,
                        project_name=project_name,
                        drive_file_id=drive_upload_result.get('file_id') if drive_upload_result.get('success') else None,
                        drive_file_name=filename,
                        email_source=attachment.get('from')
                    )
                except Exception as upload_error:
                    print(f"[ERROR] Failed to upload to Google Drive: {upload_error}")
                    drive_upload_result = {"success": False, "error": str(upload_error)}
            
            proposals.append({
                "filename": filename,
                # Don't include file_data in response as it's binary and can't be JSON serialized
                "is_bid_proposal": is_bid_proposal,
                "company_name": company_name,
                "trade": trade,
                "project_name": project_name,
                "from_email": attachment.get('from'),
                "message_id": msg_id,
                "status": "analyzed",
                "drive_upload": drive_upload_result
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

def route_after_buildingconnected_check(state: EmailProcessingState) -> str:
    """Route based on BuildingConnected check."""
    # If it's BuildingConnected, extract data and end
    if state.get("is_buildingconnected"):
        return "extract_buildingconnected"
    # Otherwise, continue with normal analysis
    return "email_analysis"


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
workflow.add_node("check_buildingconnected", check_buildingconnected_node)
workflow.add_node("email_analysis", email_analysis_node)
workflow.add_node("analyze_attachment", analyze_attachment_node)
workflow.add_node("forward_email", forward_email_node)
workflow.add_node("extract_buildingconnected", extract_buildingconnected_data_node)

# Start with BuildingConnected check
workflow.add_edge(START, "check_buildingconnected")

# Route based on BuildingConnected check
workflow.add_conditional_edges(
    "check_buildingconnected",
    route_after_buildingconnected_check,
    {
        "email_analysis": "email_analysis",
        "extract_buildingconnected": "extract_buildingconnected",
    }
)

# Route after normal email analysis
workflow.add_conditional_edges(
    "email_analysis",
    route_after_analysis,
    {
        "forward_email": "forward_email",
        "analyze_attachment": "analyze_attachment",
        END: END
    }
)

# End nodes
workflow.add_edge("forward_email", END)
workflow.add_edge("analyze_attachment", END)
workflow.add_edge("extract_buildingconnected", END)

email_workflow = workflow.compile()


def track_proposal(
    company_name: str,
    trade_name: str,
    project_name: str,
    drive_file_id: Optional[str] = None,
    drive_file_name: Optional[str] = None,
    email_source: Optional[str] = None
) -> bool:
    """
    Track a proposal in the database.
    
    Returns:
        True if successfully tracked, False otherwise
    """
    try:
        supabase = get_supabase_service_client()
        
        # Find the project by name
        project_response = supabase.table('projects').select('id, user_id').eq('name', project_name).execute()
        
        if not project_response.data:
            logger.warning(f"Project not found: {project_name}")
            return False
        
        project = project_response.data[0]
        
        # Find the trade by name for this user
        trade_response = supabase.table('trades').select('id').eq(
            'user_id', project['user_id']
        ).eq('name', trade_name).execute()
        
        trade_id = None
        if trade_response.data:
            trade_id = trade_response.data[0]['id']
        else:
            # Create the trade if it doesn't exist
            new_trade = supabase.table('trades').insert({
                'user_id': project['user_id'],
                'name': trade_name
            }).execute()
            if new_trade.data:
                trade_id = new_trade.data[0]['id']
                
                # Also add to project_trades
                supabase.table('project_trades').insert({
                    'project_id': project['id'],
                    'trade_id': trade_id
                }).execute()
        
        # Insert the proposal
        proposal_data = {
            'project_id': project['id'],
            'trade_id': trade_id,
            'company_name': company_name,
            'drive_file_id': drive_file_id,
            'drive_file_name': drive_file_name,
            'email_source': email_source
        }
        
        supabase.table('proposals').insert(proposal_data).execute()
        
        # Refresh the materialized view
        supabase.rpc('refresh_bidder_stats').execute()
        
        logger.info(f"Tracked proposal: {company_name} - {trade_name} - {project_name}")
        return True
        
    except Exception as e:
        logger.error(f"Error tracking proposal: {e}")
        return False


# Main entry point for processing emails
async def process_email(message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process an email through the LangGraph workflow."""
    return await email_workflow.ainvoke({"message_data": message_data})
