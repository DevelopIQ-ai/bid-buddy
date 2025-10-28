from fastapi import APIRouter, HTTPException, Depends
from fastapi import Request
from typing import Dict, Any
from app.utils.google_drive import get_drive_service, refresh_and_update_token, get_supabase_service_client
from app.utils.database import get_supabase_client
from app.utils.auth import get_current_user
from app.utils.filename_parser import parse_filename
import logging
import re
import os

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/projects/{project_id}/sync-drive")
async def sync_project_drive_folder(
    project_id: str, 
    request: Request,
    user = Depends(get_current_user)
):
    """
    Sync existing proposals from a project's Google Drive folder.
    This scans the folder and creates proposal records for any files not already tracked.
    """
    try:
        from app.utils.google_drive import get_google_token
        
        supabase = get_supabase_client(user['access_token'])
        
        # Get project details
        project_response = supabase.table('projects').select('*').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project_response.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project = project_response.data[0]
        
        if not project.get('drive_folder_id'):
            raise HTTPException(status_code=400, detail="Project has no Google Drive folder")
        
        # Get Google tokens from headers or database
        google_token = request.headers.get("x-google-token")
        google_refresh_token = request.headers.get("x-google-refresh-token")
        profile_response = None
        user_email = None
        
        # If no tokens in headers, get from database
        if not google_token or not google_refresh_token:
            # Get the user's email to fetch tokens
            supabase_service = get_supabase_service_client()
            
            # Get user's profile with tokens
            profile_response = supabase_service.table('profiles').select(
                'email, google_access_token, google_refresh_token'
            ).eq('id', user['id']).execute()
            
            if profile_response.data:
                profile = profile_response.data[0]
                user_email = profile.get('email')
                
                if not google_token:
                    google_token = profile.get('google_access_token')
                if not google_refresh_token:
                    google_refresh_token = profile.get('google_refresh_token')
                    
                # If still no valid token, try to refresh
                if not google_token and user_email and google_refresh_token:
                    logger.info(f"Access token missing, attempting refresh for user {user['id']}")
                    google_token, google_refresh_token = refresh_and_update_token(user_email)
            
            if not google_token:
                raise HTTPException(
                    status_code=401, 
                    detail="Google Drive authentication not available. Please reconnect."
                )
        
        # Store refresh token if we got it from headers
        if google_refresh_token and request.headers.get("x-google-refresh-token"):
            try:
                supabase.table('profiles').update({
                    'google_refresh_token': google_refresh_token
                }).eq('id', user['id']).execute()
            except:
                pass  # Non-critical, continue
        
        # Get Drive service with refresh capability
        try:
            drive_service = get_drive_service(google_token, google_refresh_token, auto_refresh=True)
        except Exception as e:
            # If service creation fails, try to refresh token
            if google_refresh_token and profile_response.data:
                user_email = profile_response.data[0].get('email')
                if user_email:
                    logger.warning(f"Drive service creation failed, attempting token refresh: {e}")
                    google_token, google_refresh_token = refresh_and_update_token(user_email)
                    
                    if google_token:
                        drive_service = get_drive_service(google_token, google_refresh_token, auto_refresh=True)
                    else:
                        raise HTTPException(
                            status_code=401,
                            detail="Failed to refresh Google Drive authentication. Please reconnect."
                        )
                else:
                    raise
            else:
                raise
        
        # List all PDF files in the folder with error handling
        query = f"'{project['drive_folder_id']}' in parents and mimeType='application/pdf' and trashed=false"
        
        try:
            results = drive_service.files().list(
                q=query,
                fields="files(id, name, createdTime, modifiedTime)",
                pageSize=1000
            ).execute()
        except Exception as e:
            error_str = str(e)
            # Check if it's an authentication error
            if '401' in error_str or 'unauthorized' in error_str.lower():
                # Try to refresh token one more time
                if profile_response.data:
                    user_email = profile_response.data[0].get('email')
                    if user_email:
                        logger.warning(f"Drive API call failed with auth error, attempting final refresh: {e}")
                        google_token, google_refresh_token = refresh_and_update_token(user_email)
                        
                        if google_token:
                            drive_service = get_drive_service(google_token, google_refresh_token, auto_refresh=True)
                            # Retry the API call
                            results = drive_service.files().list(
                                q=query,
                                fields="files(id, name, createdTime, modifiedTime)",
                                pageSize=1000
                            ).execute()
                        else:
                            raise HTTPException(
                                status_code=401,
                                detail="Google Drive authentication expired. Please reconnect from the dashboard."
                            )
                    else:
                        raise HTTPException(status_code=401, detail="Authentication failed. Please reconnect Google Drive.")
                else:
                    raise HTTPException(status_code=401, detail="Authentication failed. Please reconnect Google Drive.")
            else:
                # Re-raise non-auth errors
                raise
        
        files = results.get('files', [])
        
        # Get existing proposals for this project to avoid duplicates
        existing_proposals = supabase.table('proposals').select(
            'drive_file_id'
        ).eq('project_id', project_id).execute()
        
        existing_file_ids = {p['drive_file_id'] for p in existing_proposals.data if p['drive_file_id']}
        
        # Get user's trades for matching
        trades_response = supabase.table('trades').select('id, name').eq(
            'user_id', user['id']
        ).execute()
        
        trades_by_name = {t['name'].lower(): t['id'] for t in trades_response.data}
        
        # Process each file
        new_proposals = []
        skipped_files = []
        errors = []
        processed_skipped = []
        
        for file in files:
            file_id = file['id']
            filename = file['name']
            
            # Handle skipped files - parse them to ensure trades are added to project
            if file_id in existing_file_ids:
                skipped_files.append(filename)
                
                # Parse the skipped file to ensure trade is in project
                parsed = parse_filename(filename)
                if parsed.get('trades') and not parsed.get('error'):
                    for trade_name in parsed['trades']:
                        trade_name_lower = trade_name.lower()
                        if trade_name_lower in trades_by_name:
                            trade_id = trades_by_name[trade_name_lower]
                            # Ensure trade is in project_trades
                            try:
                                supabase.table('project_trades').insert({
                                    'project_id': project_id,
                                    'trade_id': trade_id
                                }).execute()
                                processed_skipped.append({
                                    'file': filename,
                                    'trade': trade_name
                                })
                            except:
                                # Already exists, that's fine
                                pass
                continue
            
            # Parse filename using new parser
            parsed = parse_filename(filename)
            
            if parsed.get('error'):
                errors.append(f"{filename}: {parsed['error']}")
                continue
            
            if not parsed.get('company_name'):
                errors.append(f"Could not parse company name from: {filename}")
                continue
            
            if not parsed.get('trades'):
                errors.append(f"Could not parse any trades from: {filename}")
                continue
            
            # Process each trade separately
            # This ensures trades like "framing, painting, drywall" create 3 separate proposal records
            proposals_created = 0
            
            for trade_name in parsed['trades']:
                # Match individual trade to database
                trade_id = None
                unmatched_trades = []
                
                # Try to find matching trade
                trade_name_lower = trade_name.lower()
                if trade_name_lower in trades_by_name:
                    trade_id = trades_by_name[trade_name_lower]
                else:
                    unmatched_trades.append(trade_name)
                
                # If no match found, create new trade
                if not trade_id:
                    new_trade = supabase.table('trades').insert({
                        'user_id': user['id'],
                        'name': trade_name
                    }).execute()
                    
                    if new_trade.data:
                        trade_id = new_trade.data[0]['id']
                        trades_by_name[trade_name_lower] = trade_id
                        
                        # Add to project_trades
                        supabase.table('project_trades').insert({
                            'project_id': project_id,
                            'trade_id': trade_id
                        }).execute()
                
                # Create proposal record for this trade
                # Note: We use a unique constraint on (project_id, company_name, trade_id)
                # to prevent true duplicates
                proposal_data = {
                    'project_id': project_id,
                    'trade_id': trade_id,
                    'company_name': parsed['company_name'],
                    'drive_file_id': file_id,
                    'drive_file_name': filename,
                    'metadata': {
                        'parsed_trades': parsed['trades'],
                        'raw_trades': parsed['raw_trades'],
                        'matched_trade': trade_name,
                        'matched_trade_id': trade_id,
                        'unmatched_trades': unmatched_trades,
                        'created_time': file.get('createdTime'),
                        'modified_time': file.get('modifiedTime')
                    }
                }
                
                try:
                    supabase.table('proposals').insert(proposal_data).execute()
                    proposals_created += 1
                except Exception as e:
                    # If it's a duplicate constraint error, that's okay
                    if 'duplicate' not in str(e).lower():
                        errors.append(f"Error inserting {filename} for {trade_name}: {str(e)}")
            
            if proposals_created > 0:
                new_proposals.append(filename)
        
        # Refresh materialized view if we have new proposals or processed skipped files
        if new_proposals or processed_skipped:
            supabase.rpc('refresh_bidder_stats').execute()
        
        return {
            'success': True,
            'project_name': project['name'],
            'files_processed': len(files),
            'new_proposals': len(new_proposals),
            'skipped_existing': len(skipped_files),
            'trades_added_from_skipped': len(processed_skipped),
            'errors': errors,
            'summary': {
                'new_files': new_proposals[:10],  # First 10 for preview
                'total_new': len(new_proposals),
                'trades_added': processed_skipped[:10],  # First 10 trades added
                'all_files': [f['name'] for f in files],  # All files for debugging
                'skipped_files': skipped_files  # All skipped files
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing Drive folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/sync-status")
async def get_sync_status(project_id: str, user = Depends(get_current_user)):
    """Get the current sync status for a project"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Get project
        project_response = supabase.table('projects').select('name').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project_response.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get proposal count
        proposals_count = supabase.table('proposals').select(
            'id', count='exact'
        ).eq('project_id', project_id).execute()
        
        # Get unique bidders count
        proposals = supabase.table('proposals').select(
            'company_name'
        ).eq('project_id', project_id).execute()
        
        unique_companies = set(p['company_name'] for p in proposals.data)
        
        # Get trade counts
        stats = supabase.table('bidder_stats').select('*').eq(
            'project_id', project_id
        ).execute()
        
        return {
            'project_name': project_response.data[0]['name'],
            'total_proposals': proposals_count.count,
            'unique_bidders': len(unique_companies),
            'trades_with_bids': len([s for s in stats.data if s['bidder_count'] > 0]),
            'total_trades': len(stats.data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/sync-buildingconnected")
async def sync_buildingconnected_emails(
    project_id: str,
    user = Depends(get_current_user)
):
    """
    Sync BuildingConnected emails for a project.
    Looks for emails from team@buildingconnected.com with subject "Proposal Submitted - ..."
    """
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Get project details
        project_response = supabase.table('projects').select('*').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project_response.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        project = project_response.data[0]
        
        # Get BuildingConnected emails from document_extractions
        # These should have been processed when emails came in
        bc_extractions = supabase.table('document_extractions').select('*').eq(
            'project_name', project['name']
        ).execute()
        
        # Get existing proposals for this project
        existing_proposals = supabase.table('proposals').select(
            'company_name, trade_id, email_source'
        ).eq('project_id', project_id).execute()
        
        # Create a set of existing proposals for deduplication
        existing_set = {
            (p['company_name'], p['trade_id'], p.get('email_source'))
            for p in existing_proposals.data
        }
        
        # Get user's trades for matching
        trades_response = supabase.table('trades').select('id, name').eq(
            'user_id', user['id']
        ).execute()
        
        trades_by_name = {t['name'].lower(): t['id'] for t in trades_response.data}
        
        new_proposals = 0
        skipped_proposals = 0
        errors = []
        
        # Process each BuildingConnected extraction
        for extraction in bc_extractions.data:
            company_name = extraction.get('company_name')
            trade_name = extraction.get('trade')
            attachment_url = extraction.get('attachment_url')
            
            if not company_name or not trade_name:
                errors.append(f"Missing data in extraction: {attachment_url}")
                continue
            
            # Find matching trade
            trade_name_lower = trade_name.lower()
            trade_id = trades_by_name.get(trade_name_lower)
            
            if not trade_id:
                # Try to find by alias
                from app.utils.qsr_trades import TRADE_ALIASES
                normalized_trade = TRADE_ALIASES.get(trade_name_lower)
                if normalized_trade:
                    trade_id = trades_by_name.get(normalized_trade.lower())
                
                if not trade_id:
                    # Create new trade
                    new_trade = supabase.table('trades').insert({
                        'user_id': user['id'],
                        'name': trade_name
                    }).execute()
                    
                    if new_trade.data:
                        trade_id = new_trade.data[0]['id']
                        trades_by_name[trade_name.lower()] = trade_id
                        
                        # Add to project_trades
                        supabase.table('project_trades').insert({
                            'project_id': project_id,
                            'trade_id': trade_id
                        }).execute()
            
            # Check if already exists
            if (company_name, trade_id, 'buildingconnected') in existing_set:
                skipped_proposals += 1
                continue
            
            # Create proposal record
            try:
                supabase.table('proposals').insert({
                    'project_id': project_id,
                    'trade_id': trade_id,
                    'company_name': company_name,
                    'email_source': 'buildingconnected',
                    'metadata': {
                        'source': 'buildingconnected',
                        'attachment_url': attachment_url
                    }
                }).execute()
                
                existing_set.add((company_name, trade_id, 'buildingconnected'))
                new_proposals += 1
            except Exception as e:
                if 'duplicate' not in str(e).lower():
                    errors.append(f"Error inserting {company_name} - {trade_name}: {str(e)}")
        
        # Refresh materialized view if we have new proposals
        if new_proposals > 0:
            supabase.rpc('refresh_bidder_stats').execute()
        
        return {
            'success': True,
            'project_name': project['name'],
            'new_proposals': new_proposals,
            'skipped_existing': skipped_proposals,
            'errors': errors
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing BuildingConnected emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))