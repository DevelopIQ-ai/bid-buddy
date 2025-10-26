-- Remove display_order column from trades table
ALTER TABLE trades DROP COLUMN IF EXISTS display_order;

-- Update create_default_trades function to remove display_order
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
    VALUES (p_user_id, trade_name)
    ON CONFLICT (user_id, name) DO NOTHING;
  END LOOP;
END;
$$ LANGUAGE plpgsql;
