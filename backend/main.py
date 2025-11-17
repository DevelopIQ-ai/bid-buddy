from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import os

from app.routers import projects, drive, agentmail_webhook, admin, trades, sync

load_dotenv()

# Configure Sentry (only if DSN is provided)
SENTRY_DSN = os.getenv("SENTRY_DSN")

if SENTRY_DSN:
    sentry_logging = LoggingIntegration(
        level=logging.INFO,        # Capture info and above as breadcrumbs
        event_level=logging.ERROR   # Send errors as events
    )

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            StarletteIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=[400, 401, 403, 404, 405, 500, 502, 503, 504],
            ),
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=[400, 401, 403, 404, 405, 500, 502, 503, 504],
            ),
            sentry_logging,
        ],
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "1.0")),  # Configurable sampling
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "1.0")),  # Configurable profiling
        send_default_pii=os.getenv("SENTRY_SEND_PII", "true").lower() == "true",  # Configurable PII
        attach_stacktrace=True,  # Attach stack traces to all events
        environment=os.getenv("ENVIRONMENT", "development"),
        release=os.getenv("RELEASE_VERSION", "unknown"),
    )
    logger.info(f"Sentry initialized for environment: {os.getenv('ENVIRONMENT', 'development')}")
else:
    logger.info("Sentry DSN not configured, error tracking disabled")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bid Buddy API",
    description="FastAPI backend for Bid Buddy dashboard",
    version="1.0.0"
)

# CORS middleware - allow multiple localhost ports for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "https://bid-buddy-nu.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects.router)
app.include_router(drive.router)
app.include_router(trades.router, prefix="/api", tags=["trades"])
app.include_router(sync.router, prefix="/api", tags=["sync"])
app.include_router(agentmail_webhook.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])


@app.get("/")
async def root():
    return {"message": "Bid Buddy API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
