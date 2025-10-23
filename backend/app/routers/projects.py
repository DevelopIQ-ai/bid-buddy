from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
import logging

from app.utils.auth import get_current_user
from app.utils.database import get_supabase_client
from app.models import ProjectToggle

router = APIRouter(prefix="/api/projects", tags=["Projects"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_projects(user: Dict = Depends(get_current_user)):
    """Get all projects for the current user"""
    try:
        supabase = get_supabase_client(user.get('access_token'))

        response = supabase.table('projects').select(
            'id, user_id, name, enabled, drive_folder_id, drive_folder_name, is_drive_folder, last_modified_time, created_at, updated_at'
        ).eq('user_id', user['id']).order('created_at').execute()

        return response.data or []

    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects")


@router.patch("/{project_id}/toggle")
async def toggle_project(
    project_id: str,
    toggle_data: ProjectToggle,
    user: Dict = Depends(get_current_user)
):
    """Toggle project enabled/disabled status"""
    try:
        supabase = get_supabase_client(user.get('access_token'))

        # First, check if this is the "Uncertain Bids" folder
        project_response = supabase.table('projects').select('name').eq(
            'id', project_id
        ).eq('user_id', user['id']).execute()

        if not project_response.data:
            raise HTTPException(status_code=404, detail="Project not found")

        project_name = project_response.data[0]['name']

        # Prevent disabling "Uncertain Bids" folder
        if project_name == "Uncertain Bids" and not toggle_data.enabled:
            raise HTTPException(
                status_code=400,
                detail="The 'Uncertain Bids' folder cannot be disabled as it's required for unmatched bid proposals"
            )

        response = supabase.table('projects').update({
            'enabled': toggle_data.enabled
        }).eq('id', project_id).eq('user_id', user['id']).execute()

        if response.data:
            return {"success": True, "enabled": toggle_data.enabled}
        else:
            raise HTTPException(status_code=404, detail="Project not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling project: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle project")
