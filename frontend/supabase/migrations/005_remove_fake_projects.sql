-- Remove the trigger that creates fake projects
DROP TRIGGER IF EXISTS on_user_created ON auth.users;

-- Create a simpler trigger that just creates the profile
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    -- Insert profile for new user
    INSERT INTO public.profiles (id, email, created_at, updated_at)
    VALUES (
        NEW.id,
        NEW.email,
        NEW.created_at,
        NEW.created_at
    )
    ON CONFLICT (id) DO NOTHING;
    
    -- No more fake projects!
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Recreate the trigger
CREATE TRIGGER on_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- Delete all existing fake projects
DELETE FROM projects 
WHERE name IN ('Project Alpha', 'Project Beta', 'Project Charlie')
  AND is_drive_folder = false;