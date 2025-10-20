from fastapi import APIRouter, Request, HTTPException, Depends, Query
from typing import Optional, Dict, Any
from googleapiclient.errors import HttpError
import logging

from app.utils.auth import get_current_user
from app.utils.database import get_supabase_client
from app.utils.google_drive import get_google_token, get_drive_service

router = APIRouter(prefix="/api/drive", tags=["Google Drive"])
logger = logging.getLogger(__name__)


@router.get("/root-folder")
async def get_root_folder(user: Dict = Depends(get_current_user)):
    """Get user's configured root folder"""
    try:
        supabase = get_supabase_client(user.get('access_token'))

        response = supabase.table('profiles').select(
            'drive_root_folder_id, drive_root_folder_name, last_sync_at'
        ).eq('id', user['id']).execute()

        profile = response.data[0] if response.data else None

        if profile and profile.get('drive_root_folder_id'):
            return {
                "rootFolder": {
                    "id": profile['drive_root_folder_id'],
                    "name": profile['drive_root_folder_name']
                },
                "lastSync": profile.get('last_sync_at')
            }
        else:
            return {"rootFolder": None, "lastSync": None}

    except Exception as e:
        logger.error(f"Error getting root folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to get root folder")


@router.post("/root-folder")
async def set_root_folder(
    request: Request,
    user: Dict = Depends(get_current_user)
):
    """Set user's root folder"""
    try:
        data = await request.json()
        folder_id = data.get('folderId')
        folder_name = data.get('folderName')

        if not folder_id or not folder_name:
            raise HTTPException(status_code=400, detail="Folder ID and name are required")

        supabase = get_supabase_client(user.get('access_token'))

        # Check if profile exists
        response = supabase.table('profiles').select('id').eq('id', user['id']).execute()
        exists = len(response.data) > 0

        if exists:
            supabase.table('profiles').update({
                'drive_root_folder_id': folder_id,
                'drive_root_folder_name': folder_name
            }).eq('id', user['id']).execute()
        else:
            supabase.table('profiles').insert({
                'id': user['id'],
                'email': user.get('email'),
                'drive_root_folder_id': folder_id,
                'drive_root_folder_name': folder_name
            }).execute()

        return {"success": True}

    except Exception as e:
        logger.error(f"Error setting root folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to set root folder")


@router.post("/sync")
async def sync_drive_folders(
    request: Request,
    user: Dict = Depends(get_current_user)
):
    """Sync Google Drive folders as projects"""
    try:
        # Get user's root folder configuration
        supabase = get_supabase_client(user.get('access_token'))

        response = supabase.table('profiles').select(
            'drive_root_folder_id, drive_root_folder_name'
        ).eq('id', user['id']).execute()

        profile = response.data[0] if response.data else None

        if not profile or not profile.get('drive_root_folder_id'):
            raise HTTPException(status_code=400, detail="No root folder configured")

        root_folder_id = profile['drive_root_folder_id']

        # Get Google access token
        google_token_header = request.headers.get("x-google-token")

        if not google_token_header:
            google_token = await get_google_token(user['id'])
            if not google_token:
                return {
                    "success": False,
                    "error": "Please reconnect Google Drive",
                    "added": 0,
                    "removed": 0,
                    "total": 0
                }
        else:
            google_token = google_token_header

            # Store the Google token for future use
            supabase.table('profiles').update({
                'google_access_token': google_token
            }).eq('id', user['id']).execute()

        # Build Drive service
        service = get_drive_service(google_token)

        # List all folders in the root directory
        query = f"'{root_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"

        all_folders = []
        page_token = None

        try:
            while True:
                results = service.files().list(
                    q=query,
                    fields='nextPageToken, files(id, name, modifiedTime)',
                    pageSize=100,
                    pageToken=page_token,
                    orderBy='name'
                ).execute()

                folders = results.get('files', [])
                all_folders.extend(folders)

                page_token = results.get('nextPageToken')
                if not page_token:
                    break
        except HttpError as e:
            logger.error(f"Google API error: {e}")

            if e.resp.status == 401:
                return {
                    "success": False,
                    "error": "Google Drive authentication expired. Please reconnect.",
                    "added": 0,
                    "removed": 0,
                    "total": 0
                }
            else:
                raise HTTPException(status_code=500, detail=f"Google Drive API error: {str(e)}")

        # Get existing Drive projects from database
        response = supabase.table('projects').select(
            'drive_folder_id, name, id'
        ).eq('user_id', user['id']).eq('is_drive_folder', True).execute()

        existing_projects = response.data
        existing_map = {p['drive_folder_id']: p for p in existing_projects}

        # Process folders - add new ones, update existing
        added = 0
        updated = 0
        drive_folder_ids = set()

        for folder in all_folders:
            folder_id = folder['id']
            folder_name = folder['name']
            modified_time = folder.get('modifiedTime')
            drive_folder_ids.add(folder_id)

            if folder_id in existing_map:
                # Update if name changed
                if existing_map[folder_id]['name'] != folder_name:
                    supabase.table('projects').update({
                        'name': folder_name,
                        'last_modified_time': modified_time
                    }).eq('id', existing_map[folder_id]['id']).execute()
                    updated += 1
            else:
                # Add new project
                supabase.table('projects').insert({
                    'user_id': user['id'],
                    'name': folder_name,
                    'drive_folder_id': folder_id,
                    'drive_folder_name': folder_name,
                    'is_drive_folder': True,
                    'last_modified_time': modified_time,
                    'enabled': False
                }).execute()
                added += 1

        # Remove projects for deleted folders
        removed = 0
        for existing_id, existing_project in existing_map.items():
            if existing_id not in drive_folder_ids:
                supabase.table('projects').delete().eq(
                    'id', existing_project['id']
                ).execute()
                removed += 1

        # Update last sync timestamp
        from datetime import datetime, timezone
        supabase.table('profiles').update({
            'last_sync_at': datetime.now(timezone.utc).isoformat()
        }).eq('id', user['id']).execute()

        return {
            "success": True,
            "added": added,
            "removed": removed,
            "updated": updated,
            "total": len(drive_folder_ids)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing Drive folders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync folders: {str(e)}")


@router.get("/folders")
async def list_folders(
    request: Request,
    parent: Optional[str] = Query(None),
    page_token: Optional[str] = Query(None),
    user: Dict = Depends(get_current_user)
):
    """List real Google Drive folders"""
    try:
        # Get the provider token (Google access token) from Supabase session
        google_token_header = request.headers.get("x-google-token")

        if not google_token_header:
            # Try to get from database
            google_token = await get_google_token(user['id'])
            if not google_token:
                logger.warning("No Google token available, returning empty list")
                return {"folders": [], "message": "Please reconnect Google Drive"}
        else:
            google_token = google_token_header

        # Build Drive service
        service = get_drive_service(google_token)

        # Build query
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent:
            query += f" and '{parent}' in parents"

        # List folders
        try:
            results = service.files().list(
                q=query,
                fields='nextPageToken, files(id, name, modifiedTime, parents)',
                pageSize=100,
                pageToken=page_token,
                orderBy='name'
            ).execute()
        except HttpError as e:
            logger.error(f"Google API error in list_folders: {e}")
            if e.resp.status == 401:
                return {"folders": [], "error": "Google Drive authentication expired. Please reconnect."}
            else:
                return {"folders": [], "error": str(e)}

        folders = results.get('files', [])

        return {
            "folders": [
                {
                    "id": folder['id'],
                    "name": folder['name'],
                    "modifiedTime": folder.get('modifiedTime'),
                    "parents": folder.get('parents', [])
                }
                for folder in folders
            ],
            "nextPageToken": results.get('nextPageToken')
        }

    except Exception as e:
        logger.error(f"Error listing Drive folders: {e}")
        # Return empty list instead of error to allow UI to function
        return {"folders": [], "error": str(e)}


@router.get("/folders/search")
async def search_folders(
    q: str,
    request: Request,
    user: Dict = Depends(get_current_user)
):
    """Search real Google Drive folders"""
    try:
        # Get Google access token
        google_token_header = request.headers.get("x-google-token")

        if not google_token_header:
            google_token = await get_google_token(user['id'])
            if not google_token:
                return {"folders": [], "message": "Please reconnect Google Drive"}
        else:
            google_token = google_token_header

        # Build Drive service
        service = get_drive_service(google_token)

        # Search query
        search_query = f"name contains '{q}' and mimeType='application/vnd.google-apps.folder' and trashed=false"

        # Search folders
        try:
            results = service.files().list(
                q=search_query,
                fields='files(id, name, modifiedTime, parents)',
                pageSize=50,
                orderBy='name'
            ).execute()
        except HttpError as e:
            logger.error(f"Google API error in search_folders: {e}")
            if e.resp.status == 401:
                return {"folders": [], "error": "Google Drive authentication expired. Please reconnect."}
            else:
                return {"folders": [], "error": str(e)}

        folders = results.get('files', [])

        return {
            "folders": [
                {
                    "id": folder['id'],
                    "name": folder['name'],
                    "modifiedTime": folder.get('modifiedTime'),
                    "parents": folder.get('parents', [])
                }
                for folder in folders
            ]
        }

    except Exception as e:
        logger.error(f"Error searching Drive folders: {e}")
        return {"folders": [], "error": str(e)}
