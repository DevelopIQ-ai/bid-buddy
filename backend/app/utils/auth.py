from fastapi import Request, HTTPException
import httpx
import logging
import os
from typing import Optional, Dict, Any
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

logger = logging.getLogger(__name__)


async def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify JWT token using Supabase JWT secret"""
    try:
        SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

        # If no JWT secret is set, fall back to using the anon key
        if not SUPABASE_JWT_SECRET:
            SUPABASE_URL = os.getenv("SUPABASE_URL")
            SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SUPABASE_URL}/auth/v1/user",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "apikey": SUPABASE_ANON_KEY
                    }
                )

                if response.status_code == 200:
                    user_data = response.json()
                    user_data['access_token'] = token
                    return user_data
                else:
                    logger.error(f"Failed to verify token via API: {response.status_code}")
                    return None

        # Decode and verify the JWT token
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )

        # Normalize the payload to match the expected format
        # JWT tokens use 'sub' for user ID, but our code expects 'id'
        if 'sub' in payload and 'id' not in payload:
            payload['id'] = payload['sub']

        # Add the access token for reference
        payload['access_token'] = token

        # Return user data from the token
        return payload

    except ExpiredSignatureError:
        logger.error("Token has expired")
        return None
    except InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        return None


async def get_current_user(request: Request) -> Dict[str, Any]:
    """Dependency to get current user from request"""
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = auth_header.split(" ")[1]
    user = await verify_token(token)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token. Please refresh your session."
        )

    return user
