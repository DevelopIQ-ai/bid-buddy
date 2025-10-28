-- Add unique index to bidder_stats for concurrent refresh
-- The combination of project_id and trade_id should be unique

-- First, drop the existing non-unique index
DROP INDEX IF EXISTS bidder_stats_project_id_idx;

-- Create a unique index on (project_id, trade_id, display_name) which makes each row unique
CREATE UNIQUE INDEX bidder_stats_unique_idx ON bidder_stats (project_id, trade_id, display_name);

-- Recreate the non-unique index on project_id for faster filtering
CREATE INDEX bidder_stats_project_id_idx ON bidder_stats (project_id);
