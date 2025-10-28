# Uncommitted Changes Summary

This document covers all uncommitted changes in the bid-buddy project as of the current session.

## Overview

This update implements a comprehensive trade management system with project-specific trade configuration, removing the `display_order` field from trades, and adding full CRUD operations for trades at both the user and project levels.

---

## Backend Changes

### New Files

#### 1. `backend/app/routers/trades.py`
**Purpose**: Full REST API for trade management
- **Endpoints**:
  - `GET /api/trades` - List all user trades (ordered by name)
  - `POST /api/trades` - Create new trade
  - `PUT /api/trades/{trade_id}` - Update trade
  - `DELETE /api/trades/{trade_id}` - Soft delete trade (sets is_active=false)
  - `GET /api/projects/{project_id}/trades` - Get trades for a project
  - `POST /api/projects/{project_id}/trades` - Add trade to project
  - `PUT /api/projects/{project_id}/trades/{project_trade_id}` - Update project trade (custom name)
  - `DELETE /api/projects/{project_id}/trades/{project_trade_id}` - Remove trade from project
  - `GET /api/projects/{project_id}/stats` - Get bidder statistics
  - `GET /api/projects/{project_id}/proposals` - Get project proposals
  - `POST /api/projects/{project_id}/proposals` - Create proposal
- **Models**: Trade, ProjectTrade, Proposal, BidderStats
- **Authentication**: All endpoints require user authentication via JWT

#### 2. `backend/app/routers/sync.py`
**Purpose**: Google Drive synchronization for existing proposals
- `POST /api/projects/{project_id}/sync-drive` - Sync existing PDF proposals from Drive folder
- Parses filenames in format: `Company Name - Trade - Project.pdf`
- Auto-creates trades if they don't exist
- Tracks proposals in database

#### 3. `backend/supabase/migrations/20241027_trades_and_proposals.sql`
**Purpose**: Initial database schema for trades and proposals system
- Creates `trades` table (master list per user)
- Creates `project_trades` table (trades enabled per project with optional custom names)
- Creates `proposals` table (track all bid proposals)
- Creates `bidder_stats` materialized view for performance
- Adds RLS policies for all tables
- Initializes default trades for existing users
- Functions: `create_default_trades()`, `initialize_project_trades()`, `refresh_bidder_stats()`

#### 4. `backend/supabase/migrations/20241127_remove_display_order.sql`
**Purpose**: Remove display_order column from trades table
- Drops `display_order` column from trades table
- Updates `create_default_trades()` function to not use display_order
- Migration to clean up schema

#### 5. `backend/database_schema_proposal.md`
**Purpose**: Documentation of the database schema design
- Complete schema documentation
- Implementation strategy
- Benefits and migration path

### Modified Files

#### 1. `backend/app/agent.py`
**Changes**:
- Removed `display_order` when creating new trades in `track_proposal()` function
- Trade creation now only uses `name` field

#### 2. `backend/main.py`
**Changes**:
- Added trades router to FastAPI app
- Registered all new endpoints

---

## Frontend Changes

### New Files

#### 1. `frontend/components/TradesFlyout.tsx`
**Purpose**: Global trades management flyout
- Slide-out panel for managing user's master trade list
- Features:
  - View all trades
  - Edit trade names (inline editing)
  - Add new trades
  - Delete trades (soft delete)
  - Removed display_order UI elements
  - Simplified ordering (alphabetical by name)
- Used on the main dashboard page

#### 2. `frontend/components/ProjectTradesFlyout.tsx`
**Purpose**: Project-specific trades management flyout
- Slide-out panel for managing trades for individual projects
- Features:
  - View project-specific trades with custom names
  - Edit custom names for trades in project
  - Add existing trades to project (dropdown)
  - Create new trades and add to project simultaneously
  - Remove trades from project
- Used on project detail pages

### Modified Files

#### 1. `frontend/lib/api-client.ts`
**Changes**:
- Removed `display_order` from trade API methods
- Added `getProjectTrades(projectId)` - Fetch trades for a project
- Added `addProjectTrade(projectId, tradeId, customName)` - Add trade to project
- Added `updateProjectTrade(projectId, projectTradeId, tradeId, customName)` - Update project trade
- Added `removeProjectTrade(projectId, projectTradeId)` - Remove trade from project
- Added `getProjectStats(projectId)` - Fetch bidder statistics

#### 2. `frontend/app/page.tsx`
**Changes**:
- Added TradesFlyout component integration
- "Manage Trades" button in settings section
- State management for trade flyout open/close

#### 3. `frontend/app/projects/[id]/page.tsx`
**Changes**:
- Replaced demo data with real bidder statistics
- Added `BidderStat` interface
- Integrated ProjectTradesFlyout component
- Made table rows clickable to open trades management
- Added "Manage Trades" button in header
- Fetch and display real bidder stats from API
- Auto-refresh stats when trades flyout closes
- Shows empty state when no trades configured

---

## Key Features

### 1. Trade Management Hierarchy
- **Global Trades**: Master list of trades available to all projects
- **Project Trades**: Trades enabled for specific projects with optional custom names
- **Proposals**: Track actual bids received for each trade in each project

### 2. Bidder Statistics
- Real-time bidder counts per trade per project
- Materialized view for fast queries
- Automatic refresh on proposal creation

### 3. User Experience
- Intuitive flyout panels for trade management
- Inline editing of trade names
- Create and add trades in one action
- Visual feedback with loading states
- Confirmation dialogs for destructive actions

### 4. Data Model
```
User
  └── Trades (master list)
       └── Project Trades (enabled per project)
            └── Proposals (actual bids)
```

---

## Database Schema

### Tables
1. **trades** - Master trades list (per user)
2. **project_trades** - Trades enabled per project
3. **proposals** - Track all bid proposals
4. **bidder_stats** - Materialized view for quick statistics

### Key Design Decisions
- Removed `display_order` in favor of alphabetical sorting by name
- Support for custom trade names per project
- Materialized view for performance
- Row-level security on all tables

---

## Migration Notes

### Breaking Changes
- `display_order` column removed from trades table
- Trades now ordered alphabetically by name

### Migration Path
1. Run `20241027_trades_and_proposals.sql` to create schema
2. Run `20241127_remove_display_order.sql` to remove deprecated column
3. Existing users get default trades initialized
4. Existing projects get trades initialized

---

## API Changes

### New Endpoints
- 11 new endpoints for trade and proposal management
- All endpoints require authentication
- Follow RESTful conventions

### Response Formats
- Consistent JSON responses
- Error handling with appropriate HTTP status codes
- Detailed error messages

---

## TODO

- parse bidding docs to understand bidding stats per trade
- when email comes in, log it into the system
- display stats in frontend
