-- Update to QSR (Quick Service Restaurant) trades

-- First, update the create_default_trades function with new QSR trades
CREATE OR REPLACE FUNCTION create_default_trades(p_user_id UUID)
RETURNS void AS $$
DECLARE
  qsr_trades TEXT[] := ARRAY[
    'Architecture',
    'Bathrooms',
    'Building Materials',
    'Canopies',
    'Caulking',
    'Concrete',
    'Doors & Windows',
    'Drywall',
    'Dumpster Service',
    'Earthwork',
    'Excavation',
    'Final Cleaning',
    'Flooring',
    'Framing',
    'Glasswork',
    'Landscaping',
    'Low Voltage',
    'Masonry',
    'Mechanical',
    'Metals',
    'Painting',
    'Plumbing',
    'Roofing',
    'Steel',
    'Storefront',
    'Striping',
    'TAB',
    'Toilet Accessories',
    'TPO',
    'Trusses',
    'Utilities',
    'Welding',
    'Windows'
  ];
  trade_name TEXT;
BEGIN
  FOREACH trade_name IN ARRAY qsr_trades
  LOOP
    INSERT INTO trades (user_id, name)
    VALUES (p_user_id, trade_name)
    ON CONFLICT (user_id, name) DO NOTHING;
  END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Mark all existing trades as inactive (soft delete)
UPDATE trades SET is_active = false WHERE is_active = true;

-- Re-create trades for all existing users with new QSR list
DO $$
DECLARE
  user_record RECORD;
BEGIN
  FOR user_record IN SELECT id FROM auth.users
  LOOP
    PERFORM create_default_trades(user_record.id);
  END LOOP;
END;
$$;

-- Refresh bidder stats
REFRESH MATERIALIZED VIEW bidder_stats;
