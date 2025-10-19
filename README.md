# Bid Buddy

A dashboard application for managing projects with Google Drive integration and webhook support for agentmail.

## Architecture

- **Frontend**: Next.js 15 with React 19, Tailwind CSS, and Supabase authentication
- **Backend**: FastAPI with Python, Google Drive API integration
- **Database**: Supabase (PostgreSQL)
- **Authentication**: Supabase Auth with Google OAuth

## Project Structure

```
bid-buddy/
├── app/                    # Next.js frontend
├── backend/               # FastAPI backend
│   ├── app/
│   │   ├── routers/      # API endpoints
│   │   ├── models/       # Pydantic models
│   │   ├── services/     # Business logic
│   │   ├── middleware/   # Authentication middleware
│   │   └── database/     # Database clients
│   ├── requirements.txt
│   ├── main.py
│   └── Dockerfile
├── components/           # React components
├── lib/                 # Utilities and API clients
└── supabase/           # Database migrations
```

## Features

- **Google OAuth Authentication** - Secure sign-in with Google Drive permissions
- **Project Management** - Toggle projects on/off with real-time sync
- **Google Drive Integration** - Sync Drive folders as projects automatically
- **Root Directory Configuration** - Set a specific Drive folder as project root
- **Webhook Support** - Ready for agentmail integration
- **Real-time Updates** - Optimistic UI updates with error handling

## Setup

### 1. Database Setup

Run the migrations in your Supabase dashboard:

```sql
-- Copy and run each migration file in order:
-- supabase/migrations/001_initial_schema.sql
-- supabase/migrations/002_fix_user_creation.sql  
-- supabase/migrations/003_drive_integration.sql
```

### 2. Environment Configuration

Update the environment files with your credentials:

**Frontend (.env.local):**
```env
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**Backend (backend/.env):**
```env
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
JWT_SECRET=your-jwt-secret
```

### 3. Google OAuth Setup

1. Go to Google Cloud Console
2. Enable Google Drive API
3. Create OAuth 2.0 credentials
4. Add redirect URI: `https://your-supabase-url/auth/v1/callback`
5. Configure in Supabase Auth settings

### 4. Running the Application

**Backend (Terminal 1):**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
# Or use: ./start.sh
```

**Frontend (Terminal 2):**
```bash
npm install
npm run dev
# Frontend runs on http://localhost:3000
```

## API Endpoints

### Authentication
- `GET /api/auth/user` - Get current user
- `POST /api/auth/signout` - Sign out user
- `GET /api/auth/callback` - OAuth callback

### Projects
- `GET /api/projects/` - List all projects
- `POST /api/projects/` - Create project
- `PATCH /api/projects/{id}` - Update project
- `PATCH /api/projects/{id}/toggle` - Toggle project status
- `DELETE /api/projects/{id}` - Delete project

### Google Drive
- `GET /api/drive/folders` - List Drive folders
- `GET /api/drive/folders/search` - Search folders
- `GET /api/drive/root-folder` - Get root folder config
- `POST /api/drive/root-folder` - Set root folder
- `POST /api/drive/sync` - Sync Drive folders as projects

### Webhooks
- `POST /api/webhooks/` - General webhook endpoint
- `POST /api/webhooks/agentmail` - Agentmail specific webhook
- `GET /api/webhooks/` - Webhook health check

## Usage

1. **Sign in** with your Google account
2. **Configure root directory** by clicking "Configure" in the Drive section
3. **Search and select** a Google Drive folder as your project root
4. **Sync projects** - subfolders become toggleable projects
5. **Manage projects** - enable/disable projects as needed

## Docker Support

```bash
cd backend
docker-compose up --build
```

## Development

The application uses:
- **TypeScript** for type safety
- **Tailwind CSS** for styling  
- **Pydantic** for API validation
- **SQLAlchemy** patterns via Supabase
- **Async/await** throughout for performance

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request
