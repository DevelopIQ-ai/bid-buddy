# Google Drive Integration

## Overview
This application integrates with Google Drive API v3 to fetch and sync folders as projects.

## Authentication Flow
1. User signs in with Google OAuth through Supabase
2. Supabase provides `provider_token` (Google access token) in the session
3. Frontend passes this token via `x-google-token` header to backend
4. Backend uses the token to call Google Drive API

## API Endpoints

### List Drive Folders
```
GET /api/drive/folders?parent=<folder_id>&pageToken=<token>
```
Lists folders from Google Drive. If no parent specified, shows root folders.

### Search Drive Folders
```
GET /api/drive/folders/search?q=<query>
```
Searches for folders by name.

### Get/Set Root Folder
```
GET /api/drive/root-folder
POST /api/drive/root-folder
```
Configure which Drive folder to use as the root for project syncing.

### Sync Drive Folders
```
POST /api/drive/sync
```
Syncs all folders from the configured root directory as projects in the database.

## Database Schema

### profiles table
- `drive_root_folder_id`: Selected root folder for syncing
- `drive_root_folder_name`: Name of the root folder
- `google_access_token`: Stored Google token (optional)
- `last_sync_at`: Timestamp of last sync

### projects table  
- `drive_folder_id`: Google Drive folder ID
- `drive_folder_name`: Original Drive folder name
- `is_drive_folder`: Boolean flag for Drive-synced projects
- `last_modified_time`: Drive folder modification time

## Error Handling
- 401 errors: Token expired, user needs to reconnect
- 403 errors: Insufficient permissions
- 500 errors: API failures

## Required Google OAuth Scopes
- `https://www.googleapis.com/auth/drive` - Full Drive access
- Or `https://www.googleapis.com/auth/drive.readonly` - Read-only access

## Environment Variables
```
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

## Testing
1. Sign in with Google OAuth
2. Configure a root folder in the dashboard
3. Click "Sync Now" to pull folders as projects
4. Toggle projects on/off as needed