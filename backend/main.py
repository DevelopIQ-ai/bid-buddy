from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import httpx
import logging
from dotenv import load_dotenv
from jose import jwt
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bid Buddy API",
    description="FastAPI backend for Bid Buddy dashboard",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database connection
def get_db_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

# Verify token with Supabase and get session data
async def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify token with Supabase Auth API and get full session data"""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": SUPABASE_ANON_KEY
                }
            )
            
            if response.status_code == 200:
                user_data = response.json()
                # Also try to get the session to extract provider_token
                user_data['access_token'] = token
                return user_data
            else:
                logger.error(f"Failed to verify token: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None

# Get Google access token from database
async def get_google_token(user_id: str) -> Optional[str]:
    """Get Google access token for user from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check if we have stored Google tokens in profiles
        cursor.execute("""
            SELECT google_access_token 
            FROM profiles 
            WHERE id = %s
        """, (user_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result['google_access_token']:
            return result['google_access_token']
        
        # If not stored, the token might be in the session
        # For now, we'll need to pass it from frontend
        return None
        
    except Exception as e:
        logger.error(f"Error getting Google token: {e}")
        return None

# Build Google Drive service
def get_drive_service(access_token: str):
    """Build Google Drive service with access token"""
    credentials = Credentials(token=access_token)
    service = build('drive', 'v3', credentials=credentials)
    return service

# Dependency to get current user
async def get_current_user(request: Request) -> Dict[str, Any]:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = auth_header.split(" ")[1]
    user = await verify_token(token)
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return user

# Models
class Project(BaseModel):
    id: Optional[str] = None
    user_id: Optional[str] = None
    name: str
    enabled: bool = False
    drive_folder_id: Optional[str] = None
    drive_folder_name: Optional[str] = None
    is_drive_folder: bool = False

class ProjectToggle(BaseModel):
    enabled: bool

# Routes
@app.get("/")
async def root():
    return {"message": "Bid Buddy API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/api/projects")
async def get_projects(user: Dict = Depends(get_current_user)):
    """Get all projects for the current user"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, user_id, name, enabled, drive_folder_id, drive_folder_name, 
                   is_drive_folder, last_modified_time, created_at, updated_at
            FROM projects 
            WHERE user_id = %s 
            ORDER BY created_at ASC
        """, (user['id'],))
        
        projects = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return projects or []
        
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects")

@app.patch("/api/projects/{project_id}/toggle")
async def toggle_project(
    project_id: str,
    toggle_data: ProjectToggle,
    user: Dict = Depends(get_current_user)
):
    """Toggle project enabled/disabled status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE projects 
            SET enabled = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id
        """, (toggle_data.enabled, project_id, user['id']))
        
        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        if result:
            return {"success": True, "enabled": toggle_data.enabled}
        else:
            raise HTTPException(status_code=404, detail="Project not found")
            
    except Exception as e:
        logger.error(f"Error toggling project: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle project")

@app.get("/api/drive/root-folder")
async def get_root_folder(user: Dict = Depends(get_current_user)):
    """Get user's configured root folder"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT drive_root_folder_id, drive_root_folder_name, last_sync_at
            FROM profiles 
            WHERE id = %s
        """, (user['id'],))
        
        profile = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if profile and profile['drive_root_folder_id']:
            return {
                "rootFolder": {
                    "id": profile['drive_root_folder_id'],
                    "name": profile['drive_root_folder_name']
                },
                "lastSync": profile['last_sync_at']
            }
        else:
            return {"rootFolder": None, "lastSync": None}
            
    except Exception as e:
        logger.error(f"Error getting root folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to get root folder")

@app.post("/api/drive/root-folder")
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
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if profile exists
        cursor.execute("SELECT id FROM profiles WHERE id = %s", (user['id'],))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute("""
                UPDATE profiles 
                SET drive_root_folder_id = %s, drive_root_folder_name = %s, updated_at = NOW()
                WHERE id = %s
            """, (folder_id, folder_name, user['id']))
        else:
            cursor.execute("""
                INSERT INTO profiles (id, email, drive_root_folder_id, drive_root_folder_name)
                VALUES (%s, %s, %s, %s)
            """, (user['id'], user.get('email'), folder_id, folder_name))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error setting root folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to set root folder")

@app.post("/api/drive/sync")
async def sync_drive_folders(
    request: Request,
    user: Dict = Depends(get_current_user)
):
    """Sync Google Drive folders as projects"""
    try:
        # Get user's root folder configuration
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT drive_root_folder_id, drive_root_folder_name
            FROM profiles 
            WHERE id = %s
        """, (user['id'],))
        
        profile = cursor.fetchone()
        
        if not profile or not profile['drive_root_folder_id']:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=400, detail="No root folder configured")
        
        root_folder_id = profile['drive_root_folder_id']
        
        # Get Google access token
        google_token_header = request.headers.get("x-google-token")
        
        if not google_token_header:
            google_token = await get_google_token(user['id'])
            if not google_token:
                cursor.close()
                conn.close()
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
            cursor.execute("""
                UPDATE profiles 
                SET google_access_token = %s, updated_at = NOW()
                WHERE id = %s
            """, (google_token, user['id']))
        
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
            cursor.close()
            conn.close()
            
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
        cursor.execute("""
            SELECT drive_folder_id, name, id
            FROM projects 
            WHERE user_id = %s AND is_drive_folder = true
        """, (user['id'],))
        
        existing_projects = cursor.fetchall()
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
                    cursor.execute("""
                        UPDATE projects 
                        SET name = %s, last_modified_time = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (folder_name, modified_time, existing_map[folder_id]['id']))
                    updated += 1
            else:
                # Add new project
                cursor.execute("""
                    INSERT INTO projects 
                    (user_id, name, drive_folder_id, drive_folder_name, is_drive_folder, last_modified_time, enabled)
                    VALUES (%s, %s, %s, %s, true, %s, false)
                """, (user['id'], folder_name, folder_id, folder_name, modified_time))
                added += 1
        
        # Remove projects for deleted folders
        removed = 0
        for existing_id, existing_project in existing_map.items():
            if existing_id not in drive_folder_ids:
                cursor.execute("""
                    DELETE FROM projects 
                    WHERE id = %s
                """, (existing_project['id'],))
                removed += 1
        
        # Update last sync timestamp
        cursor.execute("""
            UPDATE profiles 
            SET last_sync_at = NOW()
            WHERE id = %s
        """, (user['id'],))
        
        conn.commit()
        cursor.close()
        conn.close()
        
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

@app.get("/api/drive/folders")
async def list_folders(
    request: Request,
    parent: Optional[str] = Query(None),
    page_token: Optional[str] = Query(None),
    user: Dict = Depends(get_current_user)
):
    """List real Google Drive folders"""
    try:
        # Get Google access token from request header
        auth_header = request.headers.get("authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="No authorization header")
        
        # Extract the Supabase access token
        supabase_token = auth_header.split(" ")[1]
        
        # Get the provider token (Google access token) from Supabase session
        # For now, we'll need the frontend to pass the Google token
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

@app.get("/api/drive/folders/search")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)