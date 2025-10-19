-- Add column to store Google access token in profiles table
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS google_access_token TEXT;

-- Also store refresh token for token renewal
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS google_refresh_token TEXT;

-- Token expiration time
ALTER TABLE profiles 
ADD COLUMN IF NOT EXISTS google_token_expires_at TIMESTAMP WITH TIME ZONE;