# Database Schema Proposal for Trade & Bidder Management

## Overview
This document outlines the database changes needed to support trade management and bidder tracking across projects.

## New Tables

### 1. `trades` - Master list of trades per user
```sql
CREATE TABLE trades (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  name VARCHAR(100) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, name)
);
```

### 2. `project_trades` - Trades enabled for each project
```sql
CREATE TABLE project_trades (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  trade_id UUID REFERENCES trades(id) ON DELETE CASCADE,
  is_active BOOLEAN DEFAULT true,
  custom_name VARCHAR(100), -- Optional override of trade name for this project
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id, trade_id)
);
```

### 3. `proposals` - Track all bid proposals
```sql
CREATE TABLE proposals (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
  trade_id UUID REFERENCES trades(id) ON DELETE SET NULL,
  company_name VARCHAR(255) NOT NULL,
  drive_file_id VARCHAR(255),
  drive_file_name VARCHAR(255),
  drive_folder_path TEXT,
  email_source VARCHAR(255), -- Email address it came from
  received_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}', -- Store additional extracted data
  INDEX idx_proposals_project_trade (project_id, trade_id)
);
```

### 4. `bidder_stats` - Materialized view for quick stats
```sql
CREATE MATERIALIZED VIEW bidder_stats AS
SELECT 
  pt.project_id,
  pt.trade_id,
  t.name as trade_name,
  COUNT(DISTINCT p.company_name) as bidder_count,
  COUNT(p.id) as proposal_count,
  MAX(p.received_at) as last_bid_received
FROM project_trades pt
LEFT JOIN trades t ON pt.trade_id = t.id
LEFT JOIN proposals p ON p.project_id = pt.project_id AND p.trade_id = pt.trade_id
GROUP BY pt.project_id, pt.trade_id, t.name;

CREATE INDEX ON bidder_stats (project_id);
```

## Default Trades Initialization
```sql
-- Function to create default trades for a new user
CREATE OR REPLACE FUNCTION create_default_trades(p_user_id UUID)
RETURNS void AS $$
DECLARE
  default_trades TEXT[] := ARRAY[
    'Concrete', 'Framing', 'Electrical', 'Plumbing', 'HVAC',
    'Roofing', 'Drywall', 'Flooring', 'Painting', 'Landscaping',
    'Masonry', 'Steel/Structural', 'Windows & Doors', 'Insulation', 
    'Site Work', 'Millwork', 'Fire Protection', 'Elevators', 
    'Demolition', 'Earthwork'
  ];
  trade_name TEXT;
BEGIN
  FOREACH trade_name IN ARRAY default_trades
  LOOP
    INSERT INTO trades (user_id, name)
    VALUES (p_user_id, trade_name);
  END LOOP;
END;
$$ LANGUAGE plpgsql;
```

## Implementation Strategy

### Phase 1: Database Setup
1. Run migrations to create new tables
2. Initialize default trades for existing users
3. Create RLS policies for multi-tenant security

### Phase 2: Proposal Processing Flow
When an email with a proposal comes in:
1. Extract: company_name, trade, project_name (already doing this)
2. Match project_name to projects table
3. Match trade to trades table (fuzzy match or AI)
4. Insert into proposals table
5. Refresh bidder_stats materialized view

### Phase 3: Google Drive Sync
For existing proposals in Drive:

```python
async def sync_existing_proposals(project_id: str, folder_id: str):
    """
    Scan Google Drive folder and parse existing proposals
    Expected naming convention: {Company Name} - {Trade} - {Project}.pdf
    """
    files = drive_service.list_files(folder_id)
    
    for file in files:
        # Parse filename
        parts = file['name'].replace('.pdf', '').split(' - ')
        if len(parts) >= 2:
            company_name = parts[0].strip()
            trade_name = parts[1].strip()
            
            # Match trade to database
            trade = match_trade(trade_name, user_id)
            
            # Insert proposal if not exists
            insert_proposal({
                'project_id': project_id,
                'trade_id': trade.id,
                'company_name': company_name,
                'drive_file_id': file['id'],
                'drive_file_name': file['name']
            })
    
    # Refresh stats
    refresh_materialized_view('bidder_stats')
```

### Phase 4: API Endpoints

```python
# Trade Management
GET    /api/trades                 # List user's trades
POST   /api/trades                 # Create new trade
PUT    /api/trades/{id}           # Update trade
DELETE /api/trades/{id}           # Delete trade

# Project Trade Management  
GET    /api/projects/{id}/trades  # List trades for project
POST   /api/projects/{id}/trades  # Add trades to project
DELETE /api/projects/{id}/trades/{trade_id}  # Remove trade from project

# Bidder Statistics
GET    /api/projects/{id}/stats   # Get bidder stats for project
POST   /api/projects/{id}/sync    # Sync with Google Drive

# Proposals
GET    /api/projects/{id}/proposals  # List all proposals for project
GET    /api/projects/{id}/trades/{trade_id}/proposals  # Proposals by trade
```

### Phase 5: Frontend Updates
1. Add trade management UI in settings
2. Show real bidder counts in project page
3. Add sync button to refresh from Drive
4. Add ability to customize trades per project

## Benefits
1. **Flexibility**: Users can customize trades globally and per-project
2. **Performance**: Materialized view for fast stats queries
3. **Accuracy**: Track actual proposals, not estimates
4. **Historical**: Keep record of all bids received
5. **Scalability**: Efficient structure for large numbers of proposals

## Migration Path
1. Create tables with zero downtime
2. Populate default trades for existing users
3. Run initial sync for existing Drive folders
4. Update webhook to use new proposal tracking
5. Update frontend to show real data