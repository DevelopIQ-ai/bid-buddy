-- Create trades table (master list per user)
CREATE TABLE IF NOT EXISTS trades (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  name VARCHAR(100) NOT NULL,
  display_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, name)
);

-- Create project_trades table (trades enabled per project)
CREATE TABLE IF NOT EXISTS project_trades (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
  trade_id UUID REFERENCES trades(id) ON DELETE CASCADE NOT NULL,
  is_active BOOLEAN DEFAULT true,
  custom_name VARCHAR(100), -- Optional override of trade name for this project
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id, trade_id)
);

-- Create proposals table (track all bid proposals)
CREATE TABLE IF NOT EXISTS proposals (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
  trade_id UUID REFERENCES trades(id) ON DELETE SET NULL,
  company_name VARCHAR(255) NOT NULL,
  drive_file_id VARCHAR(255),
  drive_file_name VARCHAR(255),
  drive_folder_path TEXT,
  email_source VARCHAR(255),
  received_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB DEFAULT '{}',
  UNIQUE(project_id, company_name, trade_id) -- Prevent duplicate entries
);

-- Create indexes for performance
CREATE INDEX idx_proposals_project_trade ON proposals(project_id, trade_id);
CREATE INDEX idx_proposals_company ON proposals(company_name);
CREATE INDEX idx_trades_user ON trades(user_id);
CREATE INDEX idx_project_trades_project ON project_trades(project_id);

-- Create materialized view for bidder statistics
CREATE MATERIALIZED VIEW bidder_stats AS
SELECT 
  pt.project_id,
  pt.trade_id,
  t.name as trade_name,
  COALESCE(pt.custom_name, t.name) as display_name,
  COUNT(DISTINCT p.company_name) as bidder_count,
  COUNT(p.id) as proposal_count,
  MAX(p.received_at) as last_bid_received
FROM project_trades pt
LEFT JOIN trades t ON pt.trade_id = t.id
LEFT JOIN proposals p ON p.project_id = pt.project_id AND p.trade_id = pt.trade_id
WHERE pt.is_active = true
GROUP BY pt.project_id, pt.trade_id, t.name, pt.custom_name;

CREATE INDEX ON bidder_stats (project_id);

-- Function to refresh bidder stats
CREATE OR REPLACE FUNCTION refresh_bidder_stats()
RETURNS void AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY bidder_stats;
END;
$$ LANGUAGE plpgsql;

-- Function to create default trades for a user
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
  i INTEGER := 0;
BEGIN
  FOREACH trade_name IN ARRAY default_trades
  LOOP
    INSERT INTO trades (user_id, name, display_order)
    VALUES (p_user_id, trade_name, i)
    ON CONFLICT (user_id, name) DO NOTHING;
    i := i + 10; -- Use increments of 10 for easier reordering
  END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Function to initialize trades for a project (copies all user's active trades)
CREATE OR REPLACE FUNCTION initialize_project_trades(p_project_id UUID, p_user_id UUID)
RETURNS void AS $$
BEGIN
  INSERT INTO project_trades (project_id, trade_id)
  SELECT p_project_id, id
  FROM trades
  WHERE user_id = p_user_id AND is_active = true
  ON CONFLICT (project_id, trade_id) DO NOTHING;
END;
$$ LANGUAGE plpgsql;

-- Enable Row Level Security
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE proposals ENABLE ROW LEVEL SECURITY;

-- RLS Policies for trades
CREATE POLICY "Users can view their own trades" ON trades
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own trades" ON trades
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own trades" ON trades
  FOR UPDATE USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own trades" ON trades
  FOR DELETE USING (auth.uid() = user_id);

-- RLS Policies for project_trades
CREATE POLICY "Users can view project trades for their projects" ON project_trades
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM projects 
      WHERE projects.id = project_trades.project_id 
      AND projects.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can manage project trades for their projects" ON project_trades
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM projects 
      WHERE projects.id = project_trades.project_id 
      AND projects.user_id = auth.uid()
    )
  );

-- RLS Policies for proposals
CREATE POLICY "Users can view proposals for their projects" ON proposals
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM projects 
      WHERE projects.id = proposals.project_id 
      AND projects.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can manage proposals for their projects" ON proposals
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM projects 
      WHERE projects.id = proposals.project_id 
      AND projects.user_id = auth.uid()
    )
  );

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trades
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Initialize default trades for existing users
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

-- Initialize project trades for existing projects
DO $$
DECLARE
  project_record RECORD;
BEGIN
  FOR project_record IN SELECT id, user_id FROM projects WHERE enabled = true
  LOOP
    PERFORM initialize_project_trades(project_record.id, project_record.user_id);
  END LOOP;
END;
$$;

-- Create initial materialized view
REFRESH MATERIALIZED VIEW bidder_stats;