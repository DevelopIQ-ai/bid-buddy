import os
from supabase import create_client, Client
from typing import Optional


def get_supabase_client(access_token: Optional[str] = None) -> Client:
    """Get Supabase client instance with optional user authentication"""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")

    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # If an access token is provided, set it for RLS authentication
    if access_token:
        client.auth.set_session(access_token, access_token)

    return client
