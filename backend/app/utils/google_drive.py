from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload
from google.auth.transport.requests import Request
import logging
import os
import mimetypes
from typing import Optional, Dict, Any, List, Tuple, Callable, TypeVar
from difflib import SequenceMatcher
from supabase import create_client, Client
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

T = TypeVar("T")


def is_authentication_error(error: Exception) -> bool:
    """Determine if a Google API exception is related to authentication."""
    error_str = str(error).lower()
    return any(keyword in error_str for keyword in [
        '401',
        'unauthorized',
        'invalid credentials',
        'token has been expired',
        'expired or revoked',
        'invalid_grant',
    ])


def update_tokens_in_db(email: Optional[str], access_token: str, refresh_token: Optional[str] = None) -> None:
    """Persist refreshed tokens to Supabase."""
    if not email:
        return

    try:
        supabase = get_supabase_service_client()
        update_data: Dict[str, Any] = {'google_access_token': access_token}
        if refresh_token:
            update_data['google_refresh_token'] = refresh_token
        supabase.table('profiles').update(update_data).eq('email', email).execute()
        logger.info(f"Persisted refreshed Google token for {email}")
    except Exception as e:
        logger.error(f"Failed to persist refreshed Google token for {email}: {e}")


def execute_drive_operation(
    operation: Callable[[], T],
    refresh_service_callback: Optional[Callable[[], Any]] = None,
    description: str = "Google Drive operation"
) -> T:
    """Execute a Google Drive API call with automatic token refresh retry."""
    attempts = 2 if refresh_service_callback else 1

    for attempt in range(attempts):
        try:
            return operation()
        except Exception as e:
            should_retry = (
                attempt < attempts - 1 and
                refresh_service_callback is not None and
                is_authentication_error(e)
            )

            if should_retry:
                logger.info(f"Authentication error during {description}, attempting token refresh: {e}")
                refresh_service_callback()
                continue

            raise


def get_supabase_service_client() -> Client:
    """Get Supabase client with service role for bypassing RLS"""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    # Try service role key first, fall back to anon key
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not SUPABASE_SERVICE_KEY:
        # Use anon key as fallback
        SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_ANON_KEY")
    
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_google_token(user_id: str) -> Optional[str]:
    """Get Google access token for user from database"""
    try:
        supabase = get_supabase_service_client()

        # First check if we have stored Google tokens in profiles
        response = supabase.table('profiles').select(
            'google_access_token'
        ).eq('id', user_id).execute()

        result = response.data[0] if response.data else None

        if result and result.get('google_access_token'):
            return result['google_access_token']

        # If not stored, the token might be in the session
        # For now, we'll need to pass it from frontend
        return None

    except Exception as e:
        logger.error(f"Error getting Google token: {e}")
        return None


def refresh_and_update_token(email: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Refresh Google OAuth token if expired and update in database.
    
    Args:
        email: User email to refresh token for
        
    Returns:
        Tuple of (access_token, refresh_token) or (None, None) if refresh fails
    """
    try:
        supabase = get_supabase_service_client()
        
        # Get current tokens from database
        response = supabase.table('profiles').select(
            'google_access_token, google_refresh_token'
        ).eq('email', email).execute()
        
        if not response.data:
            logger.error(f"No profile found for {email}")
            return None, None
            
        profile = response.data[0]
        access_token = profile.get('google_access_token')
        refresh_token = profile.get('google_refresh_token')
        
        if not refresh_token:
            logger.error(f"No refresh token found for {email}")
            return None, None
            
        # Get OAuth client credentials
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            logger.error("Google OAuth client credentials not configured")
            return None, None
            
        # Create credentials with refresh token
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Check if token is expired and refresh if needed
        if not credentials.valid:
            logger.info(f"Token expired for {email}, refreshing...")
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                
                # Update the new access token in database
                supabase.table('profiles').update({
                    'google_access_token': credentials.token
                }).eq('email', email).execute()
                
                logger.info(f"Successfully refreshed token for {email}")
                return credentials.token, refresh_token
            else:
                logger.error(f"Unable to refresh token for {email} - missing refresh token or credentials")
                return None, None
        
        return access_token, refresh_token
        
    except Exception as e:
        logger.error(f"Error refreshing token for {email}: {e}")
        return None, None


def get_drive_service(
    access_token: str,
    refresh_token: Optional[str] = None,
    auto_refresh: bool = True,
    profile_email: Optional[str] = None,
    on_refresh: Optional[Callable[[str, Optional[str]], None]] = None
):
    """
    Build Google Drive service with credentials that support auto-refresh.

    Args:
        access_token: Google OAuth access token
        refresh_token: Google OAuth refresh token (optional, but required for auto-refresh)
        auto_refresh: Whether to automatically refresh expired tokens (default: True)
        profile_email: Email used to persist refreshed tokens (optional)
        on_refresh: Callback invoked with updated (access_token, refresh_token) after refresh

    Returns:
        Google Drive service instance
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    # If we have refresh token and client credentials, create full OAuth credentials
    if refresh_token and client_id and client_secret:
        credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret
        )
        
        # Check if token needs refresh
        if auto_refresh and not credentials.valid:
            logger.info("Access token expired, refreshing...")
            try:
                credentials.refresh(Request())
                logger.info("Successfully refreshed access token")
                update_tokens_in_db(profile_email, credentials.token, credentials.refresh_token)
                if on_refresh:
                    on_refresh(credentials.token, credentials.refresh_token)
                
                # Optionally update the token in database (if we have user context)
                # This would need to be handled by the caller
                
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise
    else:
        # Fallback: credentials without refresh (will fail when token expires)
        logger.warning("Creating credentials without refresh token - uploads will fail when token expires")
        credentials = Credentials(token=access_token)

    service = build('drive', 'v3', credentials=credentials)
    return service


def find_best_matching_folder(
    service,
    parent_folder_id: str,
    project_name: str,
    refresh_service_callback: Optional[Callable[[], Any]] = None
) -> Optional[Dict[str, str]]:
    """
    Find the best matching folder within the parent folder based on project name similarity.
    
    Args:
        service: Google Drive API service instance
        parent_folder_id: The ID of the parent folder to search in
        project_name: The project name to match against
    
    Returns:
        Dict with folder 'id' and 'name' if found, None otherwise
    """
    try:
        # List all folders in the parent folder
        query = f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        
        attempts = 2 if refresh_service_callback else 1
        results: Optional[Dict[str, Any]] = None

        for attempt in range(attempts):
            try:
                results = service.files().list(
                    q=query,
                    fields='files(id, name)',
                    pageSize=100,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute()
                break
            except Exception as e:
                is_auth_error = is_authentication_error(e)

                if attempt < attempts - 1 and is_auth_error and refresh_service_callback:
                    logger.info(f"Authentication error in find_best_matching_folder, attempting service refresh: {e}")
                    service = refresh_service_callback()
                    continue

                raise
        
        if results is None:
            logger.error(f"Failed to retrieve folders for parent {parent_folder_id}")
            return None

        folders = results.get('files', [])
        
        if not folders:
            logger.warning(f"No folders found in parent folder {parent_folder_id}")
            return None
        
        # Find best match using string similarity
        best_match = None
        best_score = 0.0
        
        # Normalize project name for comparison
        normalized_project = project_name.lower().strip()
        
        for folder in folders:
            folder_name = folder['name']
            normalized_folder = folder_name.lower().strip()
            
            # Calculate similarity score
            score = SequenceMatcher(None, normalized_project, normalized_folder).ratio()
            
            # Also check if one contains the other (partial match)
            if normalized_project in normalized_folder or normalized_folder in normalized_project:
                score = max(score, 0.8)  # Boost score for partial matches
            
            if score > best_score:
                best_score = score
                best_match = folder
        
        # Only return if we have a reasonable match (threshold of 0.5)
        if best_score >= 0.5:
            logger.info(f"Found matching folder '{best_match['name']}' for project '{project_name}' (score: {best_score:.2f})")
            return best_match
        else:
            logger.warning(f"No good match found for project '{project_name}' (best score: {best_score:.2f})")
            return None
            
    except Exception as e:
        logger.error(f"Error finding matching folder: {e}")
        return None


def upload_attachment_to_drive_with_retry(
    file_data: bytes,
    original_filename: str,
    company_name: str,
    trade: str,
    project_name: str
) -> Dict[str, Any]:
    """
    Wrapper function that handles token refresh and retries for Google Drive uploads.
    This is the main function that should be called from the webhook handler.
    
    Args:
        file_data: The raw file bytes to upload
        original_filename: The original filename (for extension extraction)
        company_name: The company name extracted from the document
        trade: The trade/work type extracted from the document
        project_name: The project name the document belongs to
        
    Returns:
        Dict containing the Google Drive file ID and web link
    """
    max_retries = 2
    last_error = None
    
    for attempt in range(max_retries):
        try:
            # First attempt with existing tokens
            if attempt == 0:
                return upload_attachment_to_drive(
                    file_data=file_data,
                    original_filename=original_filename,
                    company_name=company_name,
                    trade=trade,
                    project_name=project_name,
                    access_token=None,  # Will be fetched from DB
                    refresh_token=None,  # Will be fetched from DB
                    drive_root_folder_id=None  # Will be fetched from DB
                )
            else:
                # Subsequent attempts: force token refresh first
                PRIMARY_USER_EMAIL = os.getenv("PRIMARY_USER_EMAIL")
                if PRIMARY_USER_EMAIL:
                    logger.info(f"Attempt {attempt + 1}: Forcing token refresh before retry")
                    access_token, refresh_token = refresh_and_update_token(PRIMARY_USER_EMAIL)
                    
                    if access_token:
                        return upload_attachment_to_drive(
                            file_data=file_data,
                            original_filename=original_filename,
                            company_name=company_name,
                            trade=trade,
                            project_name=project_name,
                            access_token=access_token,
                            refresh_token=refresh_token,
                            drive_root_folder_id=None  # Will be fetched from DB
                        )
                    else:
                        logger.error("Failed to refresh token on retry")
                        
        except Exception as e:
            last_error = e
            logger.error(f"Upload attempt {attempt + 1} failed: {e}")
            
            # Check if it's an auth error and we should retry
            error_str = str(e).lower()
            if ('401' in error_str or 'unauthorized' in error_str or 
                'invalid credentials' in error_str or 'token' in error_str):
                if attempt < max_retries - 1:
                    logger.info(f"Authentication error detected, will retry (attempt {attempt + 1}/{max_retries})")
                    continue
            
            # For non-auth errors, don't retry
            break
    
    # All retries failed
    return {
        'success': False,
        'error': f"Failed after {max_retries} attempts: {str(last_error)}"
    }


def upload_attachment_to_drive(
    file_data: bytes,
    original_filename: str,
    company_name: str,
    trade: str,
    project_name: str,
    access_token: Optional[str] = None,
    refresh_token: Optional[str] = None,
    drive_root_folder_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload an attachment to Google Drive with proper naming and folder structure.

    Args:
        file_data: The raw file bytes to upload
        original_filename: The original filename (for extension extraction)
        company_name: The company name extracted from the document
        trade: The trade/work type extracted from the document
        project_name: The project name the document belongs to
        access_token: Google OAuth access token. If not provided, will fetch from database
        refresh_token: Google OAuth refresh token. If not provided, will fetch from database
        drive_root_folder_id: Root folder ID in Google Drive. If not provided, will get from database

    Returns:
        Dict containing the Google Drive file ID and web link
    """
    try:
        PRIMARY_USER_EMAIL = os.getenv("PRIMARY_USER_EMAIL")
        if not PRIMARY_USER_EMAIL:
            raise ValueError("PRIMARY_USER_EMAIL not configured in environment")
            
        # Get tokens and Drive folder from database if not provided
        if not access_token or not drive_root_folder_id:
            supabase = get_supabase_service_client()

            # Get user's profile with tokens and Drive folder
            response = supabase.table('profiles').select(
                'google_access_token, google_refresh_token, drive_root_folder_id'
            ).eq('email', PRIMARY_USER_EMAIL).execute()

            if not response.data:
                raise RuntimeError(f"No profile found for {PRIMARY_USER_EMAIL}")

            profile = response.data[0]

            if not access_token:
                access_token = profile.get('google_access_token')
            if not refresh_token:
                refresh_token = profile.get('google_refresh_token')
            if not drive_root_folder_id:
                drive_root_folder_id = profile.get('drive_root_folder_id')

            if not drive_root_folder_id:
                raise RuntimeError(f"No Drive root folder configured for {PRIMARY_USER_EMAIL}. Please configure it in the dashboard.")

        # If we still don't have tokens, try to refresh them
        if not access_token or not refresh_token:
            logger.info(f"Missing tokens, attempting to refresh for {PRIMARY_USER_EMAIL}")
            access_token, refresh_token = refresh_and_update_token(PRIMARY_USER_EMAIL)
            
            if not access_token:
                raise RuntimeError(f"No valid Google access token for {PRIMARY_USER_EMAIL}. Please sign in to the dashboard to reconnect Google Drive.")

        logger.info(f"Using Google Drive root folder: {drive_root_folder_id}")

        service = None

        def on_service_refresh(new_access_token: str, new_refresh_token: Optional[str]) -> None:
            nonlocal access_token, refresh_token
            if new_access_token:
                access_token = new_access_token
            if new_refresh_token:
                refresh_token = new_refresh_token

        def build_service() -> Any:
            return get_drive_service(
                access_token,
                refresh_token,
                auto_refresh=True,
                profile_email=PRIMARY_USER_EMAIL,
                on_refresh=on_service_refresh
            )

        # Create Drive service with auto-refresh capability
        try:
            service = build_service()
        except Exception as e:
            # If initial service creation fails, try to refresh token
            logger.warning(f"Initial Drive service creation failed: {e}, attempting token refresh")
            access_token, refresh_token = refresh_and_update_token(PRIMARY_USER_EMAIL)

            if not access_token:
                raise RuntimeError(f"Failed to refresh Google token for {PRIMARY_USER_EMAIL}. Please sign in to the dashboard to reconnect Google Drive.")

            # Try again with refreshed token
            service = build_service()

        def refresh_service():
            nonlocal access_token, refresh_token, service
            access_token, refresh_token = refresh_and_update_token(PRIMARY_USER_EMAIL)
            if not access_token:
                raise RuntimeError(f"Failed to refresh Google token for {PRIMARY_USER_EMAIL}. Please sign in to the dashboard to reconnect Google Drive.")
            service = build_service()
            return service
        
        # Extract file extension from original filename
        _, extension = os.path.splitext(original_filename)
        if not extension or extension.lower() not in ['.pdf', '.docx', '.doc']:
            extension = '.pdf'  # Default to PDF if no valid extension
        
        # Clean company name and trade for filename
        clean_company = (company_name or "unknown").replace('/', '-').replace('\\', '-').replace(':', '-').strip()
        clean_trade = (trade or "unknown").replace('/', '-').replace('\\', '-').replace(':', '-').strip()
        
        # Create filename: {trade}_{company_name}.pdf (or appropriate extension)
        new_filename = f"{clean_trade}_{clean_company}{extension}"
        
        # Find best matching project folder within the root folder
        folder_id = None
        matched_folder = None
        
        if project_name and drive_root_folder_id:
            matched_folder = find_best_matching_folder(
                service,
                drive_root_folder_id,
                project_name,
                refresh_service_callback=refresh_service
            )
            if matched_folder:
                # Look for existing "Sub Bids" folder within the project folder
                project_folder_id = matched_folder['id']
                
                # Search for "Sub Bids" folder in project folder
                query = f"'{project_folder_id}' in parents and name='Sub Bids' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = execute_drive_operation(
                    lambda: service.files().list(
                        q=query,
                        fields='files(id, name)',
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True
                    ).execute(),
                    refresh_service_callback=refresh_service,
                    description="listing 'Sub Bids' folder"
                )
                
                sub_bids_folders = results.get('files', [])
                
                if sub_bids_folders:
                    # Use existing "Sub Bids" folder
                    folder_id = sub_bids_folders[0]['id']
                    logger.info(f"Found and using 'Sub Bids' folder in project '{matched_folder['name']}'")
                else:
                    # No "Sub Bids" folder found - use project folder directly
                    folder_id = project_folder_id
                    logger.warning(f"'Sub Bids' folder not found in project '{matched_folder['name']}', using project folder directly")
            else:
                # If no match found, create or use "Uncertain Bids" folder
                logger.warning(f"No matching folder found for project '{project_name}', checking for Uncertain Bids folder")
                
                # Check if "Uncertain Bids" folder exists in root folder
                query = f"'{drive_root_folder_id}' in parents and name='Uncertain Bids' and mimeType='application/vnd.google-apps.folder' and trashed=false"
                results = execute_drive_operation(
                    lambda: service.files().list(
                        q=query,
                        fields='files(id, name)',
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True
                    ).execute(),
                    refresh_service_callback=refresh_service,
                    description="listing 'Uncertain Bids' folder"
                )
                
                uncertain_folders = results.get('files', [])
                
                if uncertain_folders:
                    # Use existing "Uncertain Bids" folder
                    folder_id = uncertain_folders[0]['id']
                    matched_folder = {'id': folder_id, 'name': 'Uncertain Bids'}
                    logger.info("Using existing 'Uncertain Bids' folder")
                else:
                    # Create "Uncertain Bids" folder in root folder
                    folder_metadata = {
                        'name': 'Uncertain Bids',
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [drive_root_folder_id]
                    }
                    folder = execute_drive_operation(
                        lambda: service.files().create(
                            body=folder_metadata,
                            fields='id, name',
                            supportsAllDrives=True
                        ).execute(),
                        refresh_service_callback=refresh_service,
                        description="creating 'Uncertain Bids' folder"
                    )
                    folder_id = folder.get('id')
                    matched_folder = {'id': folder_id, 'name': 'Uncertain Bids'}
                    logger.info("Created new 'Uncertain Bids' folder")
        else:
            # No project name provided, use "Uncertain Bids" folder
            logger.info("No project name provided, using Uncertain Bids folder")
            
            # Check if "Uncertain Bids" folder exists
            query = f"'{drive_root_folder_id}' in parents and name='Uncertain Bids' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = execute_drive_operation(
                lambda: service.files().list(
                    q=query,
                    fields='files(id, name)',
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True
                ).execute(),
                refresh_service_callback=refresh_service,
                description="listing 'Uncertain Bids' folder"
            )
            
            uncertain_folders = results.get('files', [])
            
            if uncertain_folders:
                folder_id = uncertain_folders[0]['id']
                matched_folder = {'id': folder_id, 'name': 'Uncertain Bids'}
            else:
                # Create "Uncertain Bids" folder
                folder_metadata = {
                    'name': 'Uncertain Bids',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [drive_root_folder_id]
                }
                folder = execute_drive_operation(
                    lambda: service.files().create(
                        body=folder_metadata,
                        fields='id, name',
                        supportsAllDrives=True
                    ).execute(),
                    refresh_service_callback=refresh_service,
                    description="creating 'Uncertain Bids' folder"
                )
                folder_id = folder.get('id')
                matched_folder = {'id': folder_id, 'name': 'Uncertain Bids'}
        
        # Detect MIME type
        mime_type, _ = mimetypes.guess_type(original_filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        # Prepare file metadata
        file_metadata = {
            'name': new_filename
        }
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        # Upload file with retry on auth failure
        def upload_file():
            media = MediaInMemoryUpload(
                file_data,
                mimetype=mime_type,
                resumable=True
            )
            return service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name, webViewLink, webContentLink',
                supportsAllDrives=True
            ).execute()

        file = execute_drive_operation(
            upload_file,
            refresh_service_callback=refresh_service,
            description="uploading file"
        )
        
        logger.info(f"Successfully uploaded file to Google Drive: {new_filename} in folder: {matched_folder['name'] if matched_folder else 'Unknown'}")
        
        return {
            'success': True,
            'file_id': file.get('id'),
            'file_name': file.get('name'),
            'web_view_link': file.get('webViewLink'),
            'web_content_link': file.get('webContentLink'),
            'folder_id': folder_id,
            'folder_name': matched_folder['name'] if matched_folder else 'root',
            'project_name': project_name
        }
        
    except Exception as e:
        logger.error(f"Error uploading to Google Drive: {e}")
        return {
            'success': False,
            'error': str(e)
        }
