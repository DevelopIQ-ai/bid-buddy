# Bid Buddy Session Changes Summary

This document consolidates all the documentation and changes made during this development session.

---

## 1. QSR Trades Migration

### Overview
Migrated from generic construction trades to QSR (Quick Service Restaurant) specific trades.

### Files Changed
- `backend/app/utils/qsr_trades.py` - New file with QSR trade configuration
- `backend/app/utils/filename_parser.py` - Updated to use QSR trade aliases
- `backend/supabase/migrations/20241127_update_to_qsr_trades.sql` - Migration script
- `backend/supabase/migrations/20241027_trades_and_proposals.sql` - Updated trades list

### Key Features
- 33 trades optimized for QSR construction
- Trade aliases (e.g., "bath" → "Bathrooms", "cleanup" → "Final Cleaning")
- Auto-creates missing trades
- Soft-deletes old trades (preserves history)

### Trade Aliases
```python
TRADE_ALIASES = {
    'bathrooms': 'Bathrooms',
    'bath': 'Bathrooms',
    'cleanup': 'Final Cleaning',
    'dumpster': 'Dumpster Service',
    # ... and more
}
```

---

## 2. Filename Parser System

### Overview
Flexible filename parsing system that handles various naming conventions and trade aliases.

### Supported Formats
- Single trade: `{trade}_{company}.pdf`
- Multiple trades: `{trade, trade, & trade}_{company}.pdf`
- With aliases: `bath_ABC_Company.pdf` → "Bathrooms"

### Files
- `backend/app/utils/filename_parser.py` - Parser implementation
- `backend/app/utils/qsr_trades.py` - Trade aliases configuration

### Configuration
- Trade aliases hardcoded (no DB needed)
- Customizable delimiters
- Easy to add new aliases

---

## 3. Multiple Trades Handling

### Overview
Files with multiple trades now create separate proposal records for each trade.

### Example
Filename: `framing, painting, drywall_ABC_Company.pdf`
Creates 3 proposals:
- Framing → ABC Company
- Painting → ABC Company
- Drywall → ABC Company

### Benefits
- Accurate bidder counts per trade
- No double-counting
- Proper statistics

---

## 4. Skipped Files Handling

### Overview
Previously synced files are now parsed to ensure trades are added to projects.

### What Changed
Before: Skipped files were completely ignored
Now: Parse skipped files and add trades to project

### Benefits
- Automatic trade setup
- Accurate stats even for old files
- No manual configuration needed

---

## 5. Auto-Sync Feature

### Overview
Projects automatically sync with Google Drive when opened.

### User Experience
1. Open project → See cached data instantly
2. "Syncing..." indicator appears
3. Background sync pulls latest files
4. Stats refresh automatically

### Implementation
- Loads from database first (fast)
- Syncs in background
- Shows visual indicator
- Refreshes stats when complete

---

## 6. BuildingConnected Email Sync

### Overview
Syncs BuildingConnected emails alongside Google Drive files for complete bidder statistics.

### Email Requirements
- FROM: team@buildingconnected.com
- SUBJECT: "Proposal Submitted - {project_name}"

### Implementation
- New endpoint: `POST /api/projects/{id}/sync-buildingconnected`
- Queries `document_extractions` table
- Creates proposal records
- Uses same trade alias system

### Integration
Called automatically with Drive sync when opening project.

---

## 7. Materialized View Fix

### Problem
`REFRESH MATERIALIZED VIEW CONCURRENTLY` requires unique index.

### Solution
Changed to standard refresh (non-concurrent):
```sql
CREATE OR REPLACE FUNCTION refresh_bidder_stats()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW bidder_stats;
END;
$$ LANGUAGE plpgsql;
```

### Migration
`backend/supabase/migrations/20241127_fix_bidder_stats_refresh.sql`

---

## 8. Trade Alias Token Fix

### Problem
Sync endpoint was using Supabase JWT instead of Google OAuth token.

### Solution
Updated to retrieve Google token from headers or database:
```python
google_token = request.headers.get("x-google-token")
if not google_token:
    google_token = get_google_token(user['id'])
```

---

## 9. Total Bidders Display

### Feature
Table header now shows total bidder count: "Number of Bidders (56 Total)"

### Implementation
```typescript
const totalBidders = bidderStats.reduce((sum, stat) => sum + stat.bidder_count, 0)
```

---

## 10. Debugging Enhancements

### File Tracking
Sync response now includes:
- `all_files`: Complete list from Drive
- `skipped_files`: Files already in DB
- `errors`: Files that failed to parse

### Console Logging
Frontend logs detailed sync information for debugging.

---

## Database Migrations

### Created
1. `20241127_remove_display_order.sql` - Removes display_order field
2. `20241127_update_to_qsr_trades.sql` - Updates to QSR trades
3. `20241127_fix_bidder_stats_refresh.sql` - Fixes refresh function

### Updated
- `20241027_trades_and_proposals.sql` - Updated with QSR trades

---

## API Endpoints Added

### Project Sync
- `POST /api/projects/{id}/sync-drive` - Sync Google Drive files
- `POST /api/projects/{id}/sync-buildingconnected` - Sync BuildingConnected emails
- `GET /api/projects/{id}/sync-status` - Get sync status

---

## Frontend Changes

### Components
- `ProjectTradesFlyout.tsx` - New component for project trade management
- `TradesFlyout.tsx` - Removed display_order UI
- `projects/[id]/page.tsx` - Auto-sync, real stats, total bidders

### API Client
- Added `syncProjectDrive()`
- Added `syncBuildingConnected()`
- Added project trade management methods

---

## Configuration Files

### Trade Configuration
- `backend/app/utils/qsr_trades.py` - Central trade configuration
- Trade aliases
- Delimiter rules

### Parser Configuration
- `backend/app/utils/filename_parser.py`
- Configurable delimiters
- Trade alias support

---

## Complete Trade List (33 Trades)

Architecture, Bathrooms, Building Materials, Canopies, Caulking, Concrete,
Doors & Windows, Drywall, Dumpster Service, Earthwork, Excavation,
Final Cleaning, Flooring, Framing, Glasswork, Landscaping, Low Voltage,
Masonry, Mechanical, Metals, Painting, Plumbing, Roofing, Steel,
Storefront, Striping, TAB, Toilet Accessories, TPO, Trusses, Utilities,
Welding, Windows

---

## How to Use

### Sync Files
Files are automatically synced when you open a project. Manual sync can be triggered by refreshing the page.

### Add Trade Aliases
Edit `backend/app/utils/qsr_trades.py` and add to `TRADE_ALIASES` dict.

### Change Delimiters
Edit `backend/app/utils/filename_parser.py` and update delimiter constants.

### View Stats
Open any project to see real-time bidder statistics with total counts.

---

## Testing

### Test Filename Parser
```bash
cd backend
python app/utils/filename_parser.py
```

### Check Database
```sql
SELECT * FROM proposals WHERE project_id = 'your-id';
SELECT * FROM bidder_stats WHERE project_id = 'your-id';
```

---

## Debugging

### Missing Files
Check console for:
- `all_files` - All files found
- `skipped_files` - Files already in DB
- `errors` - Files that failed to parse

### Sync Errors
Check backend logs for detailed error messages.

### Stats Not Updating
Run: `REFRESH MATERIALIZED VIEW bidder_stats;`

---

## Next Steps

1. Apply database migrations
2. Test filename parsing with actual files
3. Verify BuildingConnected email sync
4. Monitor for missing files in console

---

## Files to Commit

### Backend
- `backend/app/utils/qsr_trades.py`
- `backend/app/utils/filename_parser.py`
- `backend/app/routers/sync.py`
- `backend/app/routers/trades.py`
- `backend/app/agent.py`
- `backend/supabase/migrations/*.sql`

### Frontend
- `frontend/components/ProjectTradesFlyout.tsx`
- `frontend/app/projects/[id]/page.tsx`
- `frontend/lib/api-client.ts`

### Documentation
- This file consolidates all documentation
