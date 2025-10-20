-- Create document_extractions table
CREATE TABLE IF NOT EXISTS document_extractions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Required fields
    attachment_url TEXT NOT NULL,
    active_projects TEXT[] NOT NULL,
    
    -- Extracted fields (all nullable)
    company_name TEXT,
    trade TEXT,
    is_bid_proposal BOOLEAN,
    project_name TEXT,
    
    -- Error field (nullable)
    error TEXT
);

-- Create indexes for better query performance
CREATE INDEX idx_document_extractions_created_at ON document_extractions(created_at DESC);
CREATE INDEX idx_document_extractions_attachment_url ON document_extractions(attachment_url);
CREATE INDEX idx_document_extractions_project_name ON document_extractions(project_name);
CREATE INDEX idx_document_extractions_is_bid_proposal ON document_extractions(is_bid_proposal);

-- Add RLS policies if needed (uncomment if using Row Level Security)
-- ALTER TABLE document_extractions ENABLE ROW LEVEL SECURITY;

-- Add trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_document_extractions_updated_at
    BEFORE UPDATE ON document_extractions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Add comment on table
COMMENT ON TABLE document_extractions IS 'Stores extracted information from documents processed via Reducto API';

-- Add comments on columns
COMMENT ON COLUMN document_extractions.attachment_url IS 'Reference URL or ID of the original document (e.g., AgentMail attachment ID, S3 URL, etc.)';
COMMENT ON COLUMN document_extractions.active_projects IS 'Array of active project names at the time of extraction';
COMMENT ON COLUMN document_extractions.company_name IS 'Extracted company name from the document';
COMMENT ON COLUMN document_extractions.trade IS 'Type of work/trade identified in the document';
COMMENT ON COLUMN document_extractions.is_bid_proposal IS 'Whether the document is identified as a bid proposal';
COMMENT ON COLUMN document_extractions.project_name IS 'Matched project name from active projects list';
COMMENT ON COLUMN document_extractions.error IS 'Error message if extraction failed';