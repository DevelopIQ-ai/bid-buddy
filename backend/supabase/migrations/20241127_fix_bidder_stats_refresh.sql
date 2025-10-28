-- Update refresh function to use standard refresh instead of concurrent
-- This allows refreshing without a unique index
CREATE OR REPLACE FUNCTION refresh_bidder_stats()
RETURNS void AS $$
BEGIN
  -- Use standard refresh instead of concurrent
  -- This will lock the view briefly during refresh
  REFRESH MATERIALIZED VIEW bidder_stats;
END;
$$ LANGUAGE plpgsql;
