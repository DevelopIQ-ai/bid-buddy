import os
import time
import base64
import requests
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv
from app.utils.database import get_supabase_client

load_dotenv()

def process_agentmail_attachment(attachment_content: Union[str, bytes], filename: str, attachment_url: str, active_projects: list[str] = [], table_name: str = "document_extractions", access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Process an attachment from AgentMail and save results to database.
    
    Args:
        attachment_content: Either raw bytes or base64-encoded string from AgentMail
        filename: The name of the file
        attachment_url: The URL/ID where the file is stored in AgentMail
        active_projects: List of active project names to match against
        table_name: Name of the database table to save results to
        access_token: Optional user access token for RLS
    
    Returns:
        Dict containing the database record
    """
    # Convert base64 string to bytes if needed
    if isinstance(attachment_content, str):
        try:
            file_data = base64.b64decode(attachment_content)
        except Exception as e:
            # If it's not base64, assume it's already bytes
            file_data = attachment_content.encode('utf-8')
    else:
        file_data = attachment_content
    
    # Use the existing save_extraction_to_db function
    return save_extraction_to_db(file_data, filename, attachment_url, active_projects, table_name, access_token)

def extract_from_file(file_data: bytes, filename: str, timeout: int = 600, active_projects: list[str] = []) -> Dict[str, Any]:
    """
    Extract file contents from raw file data using Reducto API.
    
    Args:
        file_data: The raw file bytes to process
        filename: The name of the file
        timeout: Maximum time to wait for processing (in seconds)
        active_projects: List of active project names
    
    Returns:
        Dict containing the extracted fields
    """
    api_key = os.getenv("REDUCTO_API_KEY")
    if not api_key:
        raise ValueError("REDUCTO_API_KEY not found in environment variables")
    
    # Step 1: Upload file to Reducto
    upload_url = "https://platform.reducto.ai/upload"
    
    files = {
        'file': (filename, file_data, 'application/octet-stream')
    }
    
    upload_headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    # Upload the file
    upload_response = requests.post(upload_url, files=files, headers=upload_headers)
    
    if upload_response.status_code != 200:
        raise Exception(f"Failed to upload file: {upload_response.status_code} - {upload_response.text}")
    
    upload_data = upload_response.json()
    file_id = upload_data.get("id") or upload_data.get("file_id")
    
    if not file_id:
        raise Exception("No file ID returned from upload")
    
    # Step 2: Submit extraction job with the uploaded file ID (using async endpoint)
    extract_url = "https://platform.reducto.ai/extract_async"
    
    payload = {
        "async": {"priority": False},
        "input": file_id,
        "instructions": {
            "schema": {
                "type": "object",
                "properties": {
                    "company_name": {
                        "type": "string",
                        "description": "The company name that prepared this bid/estimate. Look for company letterhead, logos, or signature blocks."
                    },
                    "trade": {
                        "type": "string", 
                        "description": "Type of construction work (e.g., Electrical, Plumbing, HVAC, Drywall & Painting). Base on actual work items in the document."
                    },
                    "is_bid_proposal": {
                        "type": "boolean",
                        "description": "True if document has line items with prices or is labeled as estimate/proposal/bid. False if it's a flyer or general info."
                    },
                    "project_name": {
                        "type": "string",
                        "description": f"The specific project name or property address. Common projects: {', '.join(active_projects) if active_projects else 'Panda Express, O\'Reilly Auto Parts, Yogurtland, Church projects'}"
                    }
                },
                "required": ["company_name", "trade", "is_bid_proposal", "project_name"]
            },
            "system_prompt": "You are analyzing a construction bid document. Extract the company submitting the bid, the type of work (trade), whether it's a formal bid proposal, and the project name. Be precise and only extract information explicitly stated in the document."
        },
        "settings": {
            "include_images": False,
            "optimize_for_latency": False,
            "array_extract": False,
            "citations": {
                "enabled": True,
                "numerical_confidence": True
            }
        },
        "parsing": {
            "enhance": {
                "agentic": [],
                "summarize_figures": True
            },
            "retrieval": {
                "chunking": {"chunk_mode": "disabled"},
                "embedding_optimized": False,
                "filter_blocks": []
            },
            "formatting": {
                "add_page_markers": False,
                "include": [],
                "merge_tables": False,
                "table_output_format": "dynamic"
            },
            "spreadsheet": {
                "clustering": "accurate",
                "exclude": [],
                "include": [],
                "split_large_tables": {
                    "enabled": True,
                    "size": 50
                }
            },
            "settings": {
                "embed_pdf_metadata": False,
                "force_url_result": False,
                "ocr_system": "standard",
                "persist_results": False,
                "return_images": [],
                "return_ocr_data": False,
                "timeout": 900
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Step 3: Submit the extraction job (async)
    response = requests.post(extract_url, json=payload, headers=headers)
    
    if response.status_code == 422:
        raise ValueError(f"Invalid request: {response.json()}")
    
    if response.status_code != 200:
        raise Exception(f"Failed to submit extraction job: {response.status_code} - {response.text}")
    
    initial_response = response.json()
    
    # Get the job_id from async response
    job_id = initial_response.get("job_id")
    if not job_id:
        raise Exception("No job_id returned from async extraction request")
    
    # Step 4: Poll for job completion
    poll_url = f"https://platform.reducto.ai/job/{job_id}"
    poll_headers = {"Authorization": f"Bearer {api_key}"}
    
    start_time = time.time()
    poll_interval = 10  # seconds
    
    while time.time() - start_time < timeout:
        time.sleep(poll_interval)
        
        poll_response = requests.get(poll_url, headers=poll_headers)
        
        if poll_response.status_code == 422:
            raise ValueError(f"Invalid poll request: {poll_response.json()}")
        
        if poll_response.status_code != 200:
            raise Exception(f"Failed to poll job status: {poll_response.status_code} - {poll_response.text}")
        
        poll_data = poll_response.json()
        status = poll_data.get("status")
        
        if status == "Completed" or status == "Complete":
            # Return the extracted fields
            # The result structure might be nested differently
            result = poll_data.get("result")
            
            # Debug logging
            print(f"    [DEBUG] Poll data keys: {poll_data.keys()}")
            print(f"    [DEBUG] Result type: {type(result)}")
            
            # Handle nested result.result structure
            if isinstance(result, dict) and "result" in result:
                extracted = result["result"]
                # If result is an array, get the first item
                if isinstance(extracted, list) and len(extracted) > 0:
                    return extracted[0]
                return extracted
            # If result is directly an array, get first item
            elif isinstance(result, list) and len(result) > 0:
                return result[0]
            elif result:
                return result
            else:
                raise Exception("Job completed but no result found")
        
        elif status == "Failed":
            reason = poll_data.get("reason", "Unknown error")
            raise Exception(f"Extraction failed: {reason}")
        
        # Continue polling if status is "Pending" or other
        print(f"Job {job_id} status: {status}, progress: {poll_data.get('progress', 0)}%")
    
    raise TimeoutError(f"Extraction timed out after {timeout} seconds")

def save_extraction_to_db(file_data: bytes, filename: str, attachment_url: str, active_projects: list[str] = [], table_name: str = "document_extractions", access_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract document from raw file and save results to database.
    
    Args:
        file_data: The raw file bytes to process
        filename: The name of the file
        attachment_url: The URL where the file is stored (e.g., S3 URL)
        active_projects: List of active project names to match against
        table_name: Name of the database table to save results to
        access_token: Optional user access token for RLS
    
    Returns:
        Dict containing the database record
    """
    record = {
        "attachment_url": attachment_url,
        "active_projects": active_projects,
        "company_name": None,
        "trade": None, 
        "is_bid_proposal": None,
        "project_name": None,
        "error": None
    }
    
    try:
        # Extract the document
        result = extract_from_file(file_data, filename, active_projects=active_projects)
        
        # Update record with extraction results
        record["company_name"] = result.get("company_name")
        record["trade"] = result.get("trade")
        record["is_bid_proposal"] = result.get("is_bid_proposal")
        record["project_name"] = result.get("project_name")
    except Exception as e:
        # Save error message if extraction fails
        record["error"] = str(e)
    
    # Save to database
    try:
        client = get_supabase_client(access_token)
        response = client.table(table_name).insert(record).execute()
        
        if response.data:
            return response.data[0]
        else:
            raise Exception("Failed to insert record into database")
            
    except Exception as db_error:
        # If we can't save to DB, at least return what we have
        record["db_error"] = str(db_error)
        return record