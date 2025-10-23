"""
Admin router for viewing agent traces and analytics
"""
import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from langsmith import Client
from datetime import datetime, timedelta

router = APIRouter()


class EmailTrace(BaseModel):
    """Structured trace data for admin view"""
    trace_id: str
    timestamp: str
    email_from: Optional[str] = None
    email_subject: Optional[str] = None
    email_has_attachments: bool = False

    # Email analysis node results
    classification_bid_proposal: Optional[bool] = None
    classification_should_forward: Optional[bool] = None

    # Routing decision
    routed_to: Optional[str] = None  # "analyze_attachment", "forward_email", or "skipped"

    # Node results
    forward_status: Optional[str] = None
    forward_message_id: Optional[str] = None

    attachment_count: Optional[int] = None
    attachments_analyzed: Optional[List[Dict[str, Any]]] = None

    # Overall status
    status: str = "unknown"
    error: Optional[str] = None


@router.get("/traces", response_model=List[EmailTrace])
async def get_email_traces(limit: int = 50):
    """
    Fetch and parse LangSmith traces for email processing workflow.

    Args:
        limit: Maximum number of traces to return (default: 50)

    Returns:
        List of structured EmailTrace objects
    """
    try:
        # Initialize LangSmith client
        api_key = os.getenv("LANGSMITH_API_KEY")
        project_name = os.getenv("LANGSMITH_PROJECT", "pr-memorable-hacienda-59")

        if not api_key:
            raise HTTPException(status_code=500, detail="LANGSMITH_API_KEY not configured")

        client = Client(api_key=api_key)

        # Fetch runs from the project
        # Filter for the root workflow runs (not individual LLM calls)
        runs = client.list_runs(
            project_name=project_name,
            is_root=True,  # Only root runs
            limit=limit
        )

        traces = []

        for run in runs:
            try:
                trace = parse_trace(run)
                traces.append(trace)
            except Exception as e:
                # If we can't parse a trace, add it with error info
                traces.append(EmailTrace(
                    trace_id=str(run.id),
                    timestamp=run.start_time.isoformat() if run.start_time else "",
                    status="error",
                    error=f"Failed to parse trace: {str(e)}"
                ))

        return traces

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch traces: {str(e)}")


def parse_trace(run) -> EmailTrace:
    """
    Parse a LangSmith run into structured EmailTrace data.

    Args:
        run: LangSmith Run object

    Returns:
        EmailTrace object with parsed data
    """
    trace = EmailTrace(
        trace_id=str(run.id),
        timestamp=run.start_time.isoformat() if run.start_time else "",
        status="completed" if run.status == "success" else run.status
    )

    # Extract input data (email details)
    if run.inputs:
        message_data = run.inputs.get("message_data", {})
        if isinstance(message_data, dict):
            trace.email_from = message_data.get("from_")
            trace.email_subject = message_data.get("subject")

            attachments = message_data.get("attachments", [])
            trace.email_has_attachments = len(attachments) > 0 if attachments else False

    # Extract output data (final workflow results)
    if run.outputs:
        # Classification results from email_analysis node
        trace.classification_bid_proposal = run.outputs.get("bid_proposal_included")
        trace.classification_should_forward = run.outputs.get("should_forward")

        # Determine routing
        if trace.classification_bid_proposal:
            trace.routed_to = "analyze_attachment"
        elif trace.classification_should_forward:
            trace.routed_to = "forward_email"
        else:
            trace.routed_to = "skipped"

        # Forward results
        trace.forward_status = run.outputs.get("forward_status")
        trace.forward_message_id = run.outputs.get("forward_message_id")

        # Attachment analysis results
        proposals = run.outputs.get("proposals", [])
        if proposals:
            trace.attachment_count = len(proposals)
            trace.attachments_analyzed = proposals

            # Check if any drive uploads failed
            failed_uploads = [
                p for p in proposals
                if p.get("drive_upload") and not p["drive_upload"].get("success")
            ]
            if failed_uploads:
                trace.status = "error"
                errors = [p["drive_upload"].get("error", "Unknown error") for p in failed_uploads]
                trace.error = f"Drive upload failed for {len(failed_uploads)} attachment(s): {errors[0]}"

        # Check for general errors
        if run.outputs.get("error"):
            trace.error = run.outputs.get("error")
            trace.status = "error"

    return trace


@router.get("/traces/{trace_id}")
async def get_trace_details(trace_id: str):
    """
    Get detailed information for a specific trace.

    Args:
        trace_id: The UUID of the trace to retrieve

    Returns:
        Full trace details including all child runs
    """
    try:
        api_key = os.getenv("LANGSMITH_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="LANGSMITH_API_KEY not configured")

        client = Client(api_key=api_key)

        # Get the specific run
        run = client.read_run(trace_id)

        # Get all child runs (individual nodes)
        child_runs = list(client.list_runs(trace_id=trace_id))

        return {
            "trace_id": str(run.id),
            "timestamp": run.start_time.isoformat() if run.start_time else None,
            "duration_ms": (run.end_time - run.start_time).total_seconds() * 1000 if run.end_time and run.start_time else None,
            "status": run.status,
            "inputs": run.inputs,
            "outputs": run.outputs,
            "child_runs": [
                {
                    "run_id": str(child.id),
                    "name": child.name,
                    "run_type": child.run_type,
                    "start_time": child.start_time.isoformat() if child.start_time else None,
                    "end_time": child.end_time.isoformat() if child.end_time else None,
                    "duration_ms": (child.end_time - child.start_time).total_seconds() * 1000 if child.end_time and child.start_time else None,
                    "inputs": child.inputs,
                    "outputs": child.outputs,
                    "error": child.error
                }
                for child in child_runs
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch trace details: {str(e)}")
