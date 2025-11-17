"""Sentry utilities for consistent error tracking and context management."""

import sentry_sdk
from sentry_sdk import set_user, set_context, add_breadcrumb
from functools import wraps
from typing import Any, Dict, Optional
import logging
import traceback
import inspect

logger = logging.getLogger(__name__)


def capture_error_with_context(
    error: Exception,
    operation: str,
    user_data: Optional[Dict[str, Any]] = None,
    extra_context: Optional[Dict[str, Any]] = None
) -> None:
    """
    Capture an exception with rich context for Sentry.
    
    Args:
        error: The exception to capture
        operation: The operation being performed (e.g., "token_refresh", "list_folders")
        user_data: Optional user information dict with keys like 'id', 'email'
        extra_context: Optional additional context data
    """
    # Get the calling frame information
    frame = inspect.currentframe()
    caller_frame = frame.f_back if frame else None
    
    file_name = caller_frame.f_code.co_filename if caller_frame else "unknown"
    function_name = caller_frame.f_code.co_name if caller_frame else "unknown"
    line_number = caller_frame.f_lineno if caller_frame else 0
    
    # Build context
    context = {
        "operation": operation,
        "file": file_name,
        "function": function_name,
        "line": line_number,
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    
    # Add user data if provided
    if user_data:
        context.update({
            "user_id": user_data.get('id'),
            "user_email": user_data.get('email'),
        })
        # Set Sentry user context
        set_user({
            "id": user_data.get('id'),
            "email": user_data.get('email'),
            "username": user_data.get('email', '').split('@')[0] if user_data.get('email') else None
        })
    
    # Add extra context if provided
    if extra_context:
        context.update(extra_context)
    
    # Capture the exception
    sentry_sdk.capture_exception(error, contexts={
        operation: context
    })


def add_operation_breadcrumb(
    operation: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    level: str = 'info'
) -> None:
    """
    Add a breadcrumb for tracking operation flow.
    
    Args:
        operation: The operation category (e.g., 'auth', 'drive', 'database')
        message: Description of what's happening
        data: Optional additional data
        level: Log level ('debug', 'info', 'warning', 'error', 'critical')
    """
    breadcrumb_data = {
        'category': operation,
        'message': message,
        'level': level,
    }
    
    if data:
        breadcrumb_data['data'] = data
    
    add_breadcrumb(**breadcrumb_data)


def track_google_oauth_issue(
    user_email: str,
    issue_type: str,
    details: Dict[str, Any]
) -> None:
    """
    Specifically track Google OAuth token issues.
    
    Args:
        user_email: Email of the user experiencing the issue
        issue_type: Type of issue (e.g., 'missing_refresh_token', 'token_expired', 'auth_failed')
        details: Additional details about the issue
    """
    # Add breadcrumb
    add_operation_breadcrumb(
        'google_oauth',
        f'OAuth issue for {user_email}: {issue_type}',
        data=details,
        level='warning'
    )
    
    # Set context for the issue
    set_context("google_oauth_issue", {
        "user_email": user_email,
        "issue_type": issue_type,
        **details
    })
    
    # Log and capture
    message = f"Google OAuth issue for {user_email}: {issue_type}"
    logger.warning(message)
    
    sentry_sdk.capture_message(
        message,
        level='warning',
        contexts={
            "oauth_issue": {
                "user_email": user_email,
                "issue_type": issue_type,
                **details
            }
        }
    )


def sentry_track_endpoint(operation_name: str):
    """
    Decorator to automatically track endpoint execution with Sentry.
    
    Args:
        operation_name: Name of the operation for context
    
    Usage:
        @sentry_track_endpoint("list_drive_folders")
        async def list_folders(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Try to extract user from kwargs
            user = kwargs.get('user')
            
            # Add breadcrumb for operation start
            add_operation_breadcrumb(
                operation_name,
                f'Starting {operation_name}',
                data={
                    'user_id': user.get('id') if user else None,
                    'user_email': user.get('email') if user else None
                }
            )
            
            try:
                result = await func(*args, **kwargs)
                
                # Add success breadcrumb
                add_operation_breadcrumb(
                    operation_name,
                    f'Completed {operation_name}',
                    level='info'
                )
                
                return result
                
            except Exception as e:
                # Capture with context
                capture_error_with_context(
                    e,
                    operation_name,
                    user_data=user,
                    extra_context={
                        'args': str(args)[:500],  # Truncate for safety
                        'kwargs_keys': list(kwargs.keys())
                    }
                )
                raise
        
        return wrapper
    return decorator