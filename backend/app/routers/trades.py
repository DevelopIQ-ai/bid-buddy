from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from app.utils.database import get_supabase_client
from app.utils.auth import get_current_user
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class Trade(BaseModel):
    id: Optional[str] = None
    name: str
    is_active: Optional[bool] = True

class ProjectTrade(BaseModel):
    trade_id: str
    custom_name: Optional[str] = None
    is_active: Optional[bool] = True

class Proposal(BaseModel):
    id: Optional[str] = None
    project_id: str
    trade_id: Optional[str] = None
    company_name: str
    drive_file_id: Optional[str] = None
    drive_file_name: Optional[str] = None

class BidderStats(BaseModel):
    trade_id: str
    trade_name: str
    display_name: str
    bidder_count: int
    proposal_count: int
    last_bid_received: Optional[str] = None

@router.get("/trades")
async def get_user_trades(user = Depends(get_current_user)):
    """Get all trades for the current user"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        response = supabase.table('trades').select('*').eq(
            'user_id', user['id']
        ).order('name').execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/trades")
async def create_trade(trade: Trade, user = Depends(get_current_user)):
    """Create a new trade for the current user"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        data = {
            'user_id': user['id'],
            'name': trade.name,
            'is_active': trade.is_active
        }
        
        response = supabase.table('trades').insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error creating trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/trades/{trade_id}")
async def update_trade(trade_id: str, trade: Trade, user = Depends(get_current_user)):
    """Update an existing trade"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        data = {
            'name': trade.name,
            'is_active': trade.is_active
        }
        
        response = supabase.table('trades').update(data).eq(
            'id', trade_id
        ).eq('user_id', user['id']).execute()
        
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error updating trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/trades/{trade_id}")
async def delete_trade(trade_id: str, user = Depends(get_current_user)):
    """Delete a trade (soft delete by setting is_active=false)"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        response = supabase.table('trades').update({
            'is_active': False
        }).eq('id', trade_id).eq('user_id', user['id']).execute()
        
        return {"success": bool(response.data)}
    except Exception as e:
        logger.error(f"Error deleting trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/trades")
async def get_project_trades(project_id: str, user = Depends(get_current_user)):
    """Get all trades for a specific project"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Verify user owns the project
        project = supabase.table('projects').select('id').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get project trades with trade details
        response = supabase.table('project_trades').select(
            '*, trades!inner(*)'
        ).eq('project_id', project_id).execute()
        
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/trades")
async def add_project_trade(
    project_id: str, 
    project_trade: ProjectTrade,
    user = Depends(get_current_user)
):
    """Add a trade to a project"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Verify user owns the project
        project = supabase.table('projects').select('id').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        data = {
            'project_id': project_id,
            'trade_id': project_trade.trade_id,
            'custom_name': project_trade.custom_name,
            'is_active': project_trade.is_active
        }
        
        response = supabase.table('project_trades').insert(data).execute()
        return response.data[0] if response.data else None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding project trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/projects/{project_id}/trades/{project_trade_id}")
async def update_project_trade(
    project_id: str,
    project_trade_id: str,
    project_trade: ProjectTrade,
    user = Depends(get_current_user)
):
    """Update a project trade (e.g., change custom name or active status)"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Verify user owns the project
        project = supabase.table('projects').select('id').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        data = {
            'trade_id': project_trade.trade_id,
            'custom_name': project_trade.custom_name,
            'is_active': project_trade.is_active
        }
        
        response = supabase.table('project_trades').update(data).eq(
            'id', project_trade_id
        ).eq('project_id', project_id).execute()
        
        return response.data[0] if response.data else None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating project trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/projects/{project_id}/trades/{project_trade_id}")
async def remove_project_trade(
    project_id: str,
    project_trade_id: str,
    user = Depends(get_current_user)
):
    """Remove a trade from a project"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Verify user owns the project
        project = supabase.table('projects').select('id').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        response = supabase.table('project_trades').delete().eq(
            'id', project_trade_id
        ).eq('project_id', project_id).execute()
        
        return {"success": bool(response.data)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing project trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/stats")
async def get_project_bidder_stats(project_id: str, user = Depends(get_current_user)):
    """Get bidder statistics for a project"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Verify user owns the project
        project = supabase.table('projects').select('id').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Get stats from materialized view
        response = supabase.table('bidder_stats').select('*').eq(
            'project_id', project_id
        ).order('display_name').execute()
        
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching bidder stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/proposals")
async def get_project_proposals(
    project_id: str,
    trade_id: Optional[str] = None,
    user = Depends(get_current_user)
):
    """Get all proposals for a project, optionally filtered by trade"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Verify user owns the project
        project = supabase.table('projects').select('id').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        query = supabase.table('proposals').select(
            '*, trades(name)'
        ).eq('project_id', project_id)
        
        if trade_id:
            query = query.eq('trade_id', trade_id)
        
        response = query.order('received_at', desc=True).execute()
        
        return response.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching proposals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/proposals")
async def create_proposal(
    project_id: str,
    proposal: Proposal,
    user = Depends(get_current_user)
):
    """Create a new proposal (usually called by email webhook)"""
    try:
        supabase = get_supabase_client(user['access_token'])
        
        # Verify user owns the project
        project = supabase.table('projects').select('id').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()
        
        if not project.data:
            raise HTTPException(status_code=404, detail="Project not found")
        
        data = {
            'project_id': project_id,
            'trade_id': proposal.trade_id,
            'company_name': proposal.company_name,
            'drive_file_id': proposal.drive_file_id,
            'drive_file_name': proposal.drive_file_name
        }
        
        response = supabase.table('proposals').insert(data).execute()
        
        # Refresh materialized view
        supabase.rpc('refresh_bidder_stats').execute()
        
        return response.data[0] if response.data else None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))