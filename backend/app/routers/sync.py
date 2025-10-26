from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from app.utils.google_drive import get_drive_service
from app.utils.database import get_supabase_client
from app.utils.auth import get_current_user
import logging
import re

logger = logging.getLogger(__name__)
router = APIRouter()

def parse_proposal_filename(filename: str) -> Dict[str, str]:
    """
    Parse a proposal filename to extract company, trade, and project.
    Expected formats:
    - "{Company} - {Trade} - {Project}.pdf"
    - "{Company} - {Trade}.pdf"
    - "{Company}.pdf"
    """
    result = {
        'company_name': None,
        'trade_name': None,
        'project_name': None
    }
    
    # Remove file extension
    name_without_ext = filename.rsplit('.', 1)[0]
    
    # Split by ' - ' delimiter
    parts = [part.strip() for part in name_without_ext.split(' - ')]
    
    if len(parts) >= 1:
        result['company_name'] = parts[0]
    if len(parts) >= 2:
        result['trade_name'] = parts[1]
    if len(parts) >= 3:
        result['project_name'] = parts[2]
    
    return result

@router.post("/projects/{project_id}/sync-drive")
async def sync_project_drive_folder(project_id: str, user = Depends(get_current_user)):
    """
    Sync existing proposals from a project's Google Drive folder.
    This scans the folder and creates proposal records for any files not already tracked.
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
        
        if not project.get('drive_folder_id'):
            raise HTTPException(status_code=400, detail="Project has no Google Drive folder")
        
        # Get Drive service
        drive_service = get_drive_service(user['access_token'])
        
        # List all PDF files in the folder
        query = f"'{project['drive_folder_id']}' in parents and mimeType='application/pdf' and trashed=false"
        results = drive_service.files().list(
            q=query,
            fields="files(id, name, createdTime, modifiedTime)",
            pageSize=1000
        ).execute()
        
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
        
        for file in files:
            file_id = file['id']
            filename = file['name']
            
            # Skip if already tracked
            if file_id in existing_file_ids:
                skipped_files.append(filename)
                continue
            
            # Parse filename
            parsed = parse_proposal_filename(filename)
            
            if not parsed['company_name']:
                errors.append(f"Could not parse company name from: {filename}")
                continue
            
            # Match trade to database
            trade_id = None
            if parsed['trade_name']:
                trade_name_lower = parsed['trade_name'].lower()
                
                # Try exact match first
                if trade_name_lower in trades_by_name:
                    trade_id = trades_by_name[trade_name_lower]
                else:
                    # Try partial match
                    for trade_name, tid in trades_by_name.items():
                        if trade_name in trade_name_lower or trade_name_lower in trade_name:
                            trade_id = tid
                            break
                    
                    # If still no match, create new trade
                    if not trade_id:
                        new_trade = supabase.table('trades').insert({
                            'user_id': user['id'],
                            'name': parsed['trade_name']
                        }).execute()
                        
                        if new_trade.data:
                            trade_id = new_trade.data[0]['id']
                            trades_by_name[parsed['trade_name'].lower()] = trade_id
                            
                            # Add to project_trades
                            supabase.table('project_trades').insert({
                                'project_id': project_id,
                                'trade_id': trade_id
                            }).execute()
            
            # Create proposal record
            proposal_data = {
                'project_id': project_id,
                'trade_id': trade_id,
                'company_name': parsed['company_name'],
                'drive_file_id': file_id,
                'drive_file_name': filename,
                'metadata': {
                    'parsed_trade': parsed['trade_name'],
                    'parsed_project': parsed['project_name'],
                    'created_time': file.get('createdTime'),
                    'modified_time': file.get('modifiedTime')
                }
            }
            
            try:
                supabase.table('proposals').insert(proposal_data).execute()
                new_proposals.append(filename)
            except Exception as e:
                errors.append(f"Error inserting {filename}: {str(e)}")
        
        # Refresh materialized view
        if new_proposals:
            supabase.rpc('refresh_bidder_stats').execute()
        
        return {
            'success': True,
            'project_name': project['name'],
            'files_processed': len(files),
            'new_proposals': len(new_proposals),
            'skipped_existing': len(skipped_files),
            'errors': errors,
            'summary': {
                'new_files': new_proposals[:10],  # First 10 for preview
                'total_new': len(new_proposals)
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