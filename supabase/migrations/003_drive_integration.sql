-- Add root directory configuration to profiles
ALTER TABLE profiles 
ADD COLUMN drive_root_folder_id TEXT,
ADD COLUMN drive_root_folder_name TEXT,
ADD COLUMN last_sync_at TIMESTAMP WITH TIME ZONE;

-- Update projects table to store Drive folder information
ALTER TABLE projects 
ADD COLUMN drive_folder_id TEXT UNIQUE,
ADD COLUMN drive_folder_name TEXT,
ADD COLUMN is_drive_folder BOOLEAN DEFAULT false,
ADD COLUMN last_modified_time TIMESTAMP WITH TIME ZONE;

-- Add index for better performance on Drive folder lookups
CREATE INDEX IF NOT EXISTS idx_projects_drive_folder_id ON projects(drive_folder_id);
CREATE INDEX IF NOT EXISTS idx_projects_user_drive ON projects(user_id, is_drive_folder);

-- Remove the old trigger that creates default projects
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS handle_new_user();

-- Create a simpler trigger that only creates the profile
CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name, avatar_url)
  VALUES (
    NEW.id,
    NEW.email,
    COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name'),
    NEW.raw_user_meta_data->>'avatar_url'
  );
  RETURN NEW;
EXCEPTION
  WHEN OTHERS THEN
    RAISE WARNING 'Error in handle_new_user: %', SQLERRM;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Recreate the trigger
CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();