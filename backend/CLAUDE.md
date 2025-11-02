# Bid Buddy System - Testing Guide

## System Overview
Bid Buddy is an automated bid processing system that:
1. Receives bid emails via AgentMail
2. Processes them through a LangGraph agent workflow
3. Analyzes PDF attachments using Reducto API
4. Uploads processed bids to Google Drive
5. Stores metadata in Supabase

## Environment Configuration
The system is configured for:
- **Primary User**: evan@developiq.ai
- **AgentMail Inbox**: bids@vanbrunt.developiq.co
- **Test Sender**: ryane@developiq.ai

## Running the System

### 1. Start LangGraph Dev Server
```bash
cd /Users/evanbrooks/Desktop/bid-buddy/backend
langgraph dev
```
- Runs on port 2024
- Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024

### 2. Start FastAPI Backend
```bash
cd /Users/evanbrooks/Desktop/bid-buddy/backend
uvicorn main:app --reload --port 8000
```
- API runs on port 8000
- Health check: http://localhost:8000/health

## Testing Instructions

### Send Test Email with Attachment
Use the provided script `send_test_bid.py` to send a test email:
```bash
python send_test_bid.py
```

This script:
- Sends from ryane@developiq.ai
- Sends to bids@vanbrunt.developiq.co  
- Attaches bid.pdf
- Includes bid metadata in email body

### Trigger Webhook Processing
If webhook doesn't auto-trigger, manually process the latest email:
```bash
python trigger_webhook.py
```

This script:
- Fetches the latest email from AgentMail
- Formats it as a webhook payload
- Sends to localhost:8000/webhooks/agentmail

## Expected System Behavior

### Successful Processing Flow:
1. **Email Reception**: AgentMail receives email at inbox
2. **Webhook Trigger**: Backend processes webhook at `/webhooks/agentmail`
3. **LangGraph Processing**: Agent analyzes email and identifies bid
4. **PDF Analysis**: Reducto extracts:
   - Company name
   - Trade type
   - Project name
   - Bid details
5. **Google Drive Upload**: Files uploaded to:
   - Project folder → Sub Bids → [Trade]_[Company].pdf
   - Example: `Yogurtland- Flower Mound/Sub Bids/Construction Clean Up_J&S Construction Clean Up, Inc..pdf`

### Monitoring Points:
- LangGraph Studio: View agent execution flow
- FastAPI logs: Check processing status
- Google Drive: Verify file upload and folder structure
- Response payload: Confirms processing details

## Test Results Summary

### Working Components:
- ✅ Email reception via AgentMail
- ✅ Webhook processing
- ✅ PDF analysis with Reducto
- ✅ Google Drive uploads to Sub Bids folder
- ✅ Bid metadata extraction

### Known Issues:
- Database proposals table has RLS policy restrictions (non-critical)
- Webhook may need manual triggering for testing

## Folder Structure
```
Google Drive Root/
├── Project Folders/
│   ├── Yogurtland- Flower Mound/
│   │   ├── Sub Bids/
│   │   │   ├── [Trade]_[Company].pdf
│   │   │   └── ...
│   │   └── Other project files
│   └── Other projects...
```

## Test Verification Checklist
- [ ] LangGraph server running (port 2024)
- [ ] FastAPI backend running (port 8000)
- [ ] Email sent successfully (check email ID in response)
- [ ] Email received by AgentMail (verify with latest message check)
- [ ] Webhook processed (200 OK response)
- [ ] PDF analyzed (check extracted metadata)
- [ ] File uploaded to Google Drive (verify web_view_link)
- [ ] File in correct Sub Bids folder

## Sample Test Output
Successful processing returns:
```json
{
  "status": "ok",
  "action": "bid_proposal",
  "analysis": {
    "bid_proposal_included": true,
    "attachment_analysis": {
      "proposals": [{
        "filename": "bid_proposal.pdf",
        "company_name": "Company Name",
        "trade": "Trade Type",
        "project_name": "Project Name",
        "drive_upload": {
          "success": true,
          "folder_name": "Project Folder",
          "file_name": "Trade_Company.pdf"
        }
      }]
    }
  }
}
```

## Commands Reference
```bash
# Start services
langgraph dev
uvicorn main:app --reload --port 8000

# Test email flow
python send_test_bid.py
python trigger_webhook.py

# Check services
curl http://127.0.0.1:2024/ok
curl http://localhost:8000/health
```