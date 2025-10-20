import os
from supabase import create_client, Client
from functools import lru_cache


@lru_cache()
def get_supabase_client() -> Client:
    """Get Supabase client instance (cached)"""
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set")

    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
