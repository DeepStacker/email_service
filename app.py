from fastapi import (
    FastAPI,
    HTTPException,
    BackgroundTasks,
    Depends,
    Query,
    UploadFile,
    File,
    Form,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
import os
import json
import logging
from pathlib import Path
import tempfile
import uuid

# Import our advanced email manager
from email_utils import AdvancedEmailManager, EmailConfig, EmailAttachment, EmailMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Advanced Email Management API",
    description="Complete email sending and receiving solution with advanced features",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Configuration
origins = [
    "https://email-service-1-7bm2.onrender.com",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "*",  # Allow all origins for development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize email manager
email_manager = AdvancedEmailManager()

# ==================== PYDANTIC MODELS ====================


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class EmailSendRequest(BaseModel):
    to_emails: Union[str, List[str]]
    subject: str = Field(..., min_length=1, max_length=200)
    message_body: str = Field(..., min_length=1)
    is_html: bool = False
    cc_emails: Optional[Union[str, List[str]]] = None
    bcc_emails: Optional[Union[str, List[str]]] = None
    sender_name: Optional[str] = None
    reply_to: Optional[EmailStr] = None
    priority: str = Field("normal", pattern="^(high|normal|low)$")
    track_delivery: bool = False
    save_to_sent: bool = True


class BulkEmailRequest(BaseModel):
    emails: List[Dict[str, Any]]
    delay_between_emails: float = Field(1.0, ge=0.1, le=10.0)
    batch_size: int = Field(50, ge=1, le=100)


class EmailSearchRequest(BaseModel):
    query: Optional[str] = None
    folder: str = "INBOX"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sender: Optional[str] = None
    subject_contains: Optional[str] = None
    limit: int = Field(50, ge=1, le=200)


class EmailActionRequest(BaseModel):
    email_ids: List[str]
    folder: str = "INBOX"


class EmailMoveRequest(BaseModel):
    email_ids: List[str]
    from_folder: str
    to_folder: str


class EmailConfigUpdate(BaseModel):
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    imap_server: Optional[str] = None
    imap_port: Optional[int] = None
    timeout: Optional[int] = None
    max_retries: Optional[int] = None


# ==================== DEPENDENCY FUNCTIONS ====================


async def get_email_manager():
    """Dependency to get email manager instance"""
    return email_manager


def validate_email_manager():
    """Validate email manager configuration"""
    if not email_manager.email_user or not email_manager.email_pass:
        raise HTTPException(
            status_code=500,
            detail="Email configuration not properly set. Check EMAIL_USER and EMAIL_PASS environment variables.",
        )


# ==================== SENDING ENDPOINTS ====================


@app.post("/email/send", response_model=APIResponse)
async def send_email(
    request: EmailSendRequest,
    background_tasks: BackgroundTasks,
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Send a single email with advanced options"""
    try:
        validate_email_manager()

        def send_email_task():
            result = manager.send_email(
                to_emails=request.to_emails,
                subject=request.subject,
                message_body=request.message_body,
                is_html=request.is_html,
                cc_emails=request.cc_emails,
                bcc_emails=request.bcc_emails,
                sender_name=request.sender_name,
                reply_to=request.reply_to,
                priority=request.priority,
                track_delivery=request.track_delivery,
                save_to_sent=request.save_to_sent,
            )
            logger.info(f"Email send result: {result}")

        background_tasks.add_task(send_email_task)

        return APIResponse(
            success=True,
            message="Email queued for sending",
            data={
                "recipients": (
                    request.to_emails
                    if isinstance(request.to_emails, list)
                    else [request.to_emails]
                ),
                "subject": request.subject,
            },
        )

    except Exception as e:
        logger.error(f"Error in send_email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/email/send-with-attachments", response_model=APIResponse)
async def send_email_with_attachments(
    to_emails: str = Form(...),
    subject: str = Form(...),
    message_body: str = Form(...),
    is_html: bool = Form(False),
    cc_emails: Optional[str] = Form(None),
    bcc_emails: Optional[str] = Form(None),
    sender_name: Optional[str] = Form(None),
    priority: str = Form("normal"),
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Send email with file attachments"""
    try:
        validate_email_manager()

        # Save uploaded files temporarily
        temp_files = []
        attachments = []

        for file in files:
            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, suffix=f"_{file.filename}"
            )
            content = await file.read()
            temp_file.write(content)
            temp_file.close()

            temp_files.append(temp_file.name)
            attachments.append(
                EmailAttachment(file_path=temp_file.name, filename=file.filename)
            )

        def send_email_with_attachments_task():
            try:
                result = manager.send_email(
                    to_emails=to_emails.split(","),
                    subject=subject,
                    message_body=message_body,
                    is_html=is_html,
                    cc_emails=cc_emails.split(",") if cc_emails else None,
                    bcc_emails=bcc_emails.split(",") if bcc_emails else None,
                    attachments=attachments,
                    sender_name=sender_name,
                    priority=priority,
                )
                logger.info(f"Email with attachments result: {result}")
            finally:
                # Clean up temporary files
                for temp_file in temp_files:
                    try:
                        os.unlink(temp_file)
                    except:
                        pass

        background_tasks.add_task(send_email_with_attachments_task)

        return APIResponse(
            success=True,
            message="Email with attachments queued for sending",
            data={
                "recipients": to_emails.split(","),
                "subject": subject,
                "attachments": [file.filename for file in files],
            },
        )

    except Exception as e:
        logger.error(f"Error in send_email_with_attachments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/email/send-bulk", response_model=APIResponse)
async def send_bulk_emails(
    request: BulkEmailRequest,
    background_tasks: BackgroundTasks,
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Send bulk emails with batching and rate limiting"""
    try:
        validate_email_manager()

        def send_bulk_task():
            results = manager.send_bulk_emails(
                email_list=request.emails,
                delay_between_emails=request.delay_between_emails,
                batch_size=request.batch_size,
            )

            # Log summary
            successful = sum(1 for r in results if r.get("success", False))
            failed = len(results) - successful
            logger.info(f"Bulk email results: {successful} successful, {failed} failed")

        background_tasks.add_task(send_bulk_task)

        return APIResponse(
            success=True,
            message=f"Bulk email job queued for {len(request.emails)} emails",
            data={
                "total_emails": len(request.emails),
                "batch_size": request.batch_size,
                "estimated_duration": len(request.emails)
                * request.delay_between_emails,
            },
        )

    except Exception as e:
        logger.error(f"Error in send_bulk_emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== RECEIVING ENDPOINTS ====================


@app.get("/email/folders", response_model=APIResponse)
async def get_email_folders(manager: AdvancedEmailManager = Depends(get_email_manager)):
    """Get list of available email folders"""
    try:
        validate_email_manager()
        folders = manager.get_folders()

        return APIResponse(
            success=True,
            message="Email folders retrieved successfully",
            data={"folders": folders},
        )

    except Exception as e:
        logger.error(f"Error getting folders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/email/list", response_model=APIResponse)
async def get_emails(
    folder: str = Query("INBOX", description="Email folder to retrieve from"),
    limit: int = Query(10, ge=1, le=100, description="Number of emails to retrieve"),
    search_criteria: str = Query("ALL", description="IMAP search criteria"),
    include_attachments: bool = Query(
        False, description="Include attachment information"
    ),
    mark_as_read: bool = Query(
        False, description="Mark emails as read when retrieving"
    ),
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Get emails from specified folder"""
    try:
        validate_email_manager()
        emails = manager.get_emails(
            folder=folder,
            limit=limit,
            search_criteria=search_criteria,
            include_attachments=include_attachments,
            mark_as_read=mark_as_read,
        )

        # Convert EmailMessage objects to dictionaries
        email_data = []
        for email_msg in emails:
            email_dict = {
                "message_id": email_msg.message_id,
                "subject": email_msg.subject,
                "sender": email_msg.sender,
                "recipients": email_msg.recipients,
                "date": email_msg.date.isoformat(),
                "body_text": (
                    email_msg.body_text[:500] + "..."
                    if len(email_msg.body_text) > 500
                    else email_msg.body_text
                ),
                "body_html": (
                    email_msg.body_html[:500] + "..."
                    if email_msg.body_html and len(email_msg.body_html) > 500
                    else email_msg.body_html
                ),
                "attachments": email_msg.attachments,
                "is_read": email_msg.is_read,
                "folder": email_msg.folder,
            }
            email_data.append(email_dict)

        return APIResponse(
            success=True,
            message=f"Retrieved {len(emails)} emails from {folder}",
            data={
                "emails": email_data,
                "folder": folder,
                "total_retrieved": len(emails),
            },
        )

    except Exception as e:
        logger.error(f"Error getting emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/email/search", response_model=APIResponse)
async def search_emails(
    request: EmailSearchRequest,
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Advanced email search with multiple criteria"""
    try:
        validate_email_manager()
        emails = manager.search_emails(
            query=request.query,
            folder=request.folder,
            date_from=request.date_from,
            date_to=request.date_to,
            sender=request.sender,
            subject_contains=request.subject_contains,
            limit=request.limit,
        )

        # Convert to dictionaries (simplified view for search results)
        email_data = []
        for email_msg in emails:
            email_dict = {
                "message_id": email_msg.message_id,
                "subject": email_msg.subject,
                "sender": email_msg.sender,
                "date": email_msg.date.isoformat(),
                "body_preview": (
                    email_msg.body_text[:200] + "..."
                    if len(email_msg.body_text) > 200
                    else email_msg.body_text
                ),
                "has_attachments": bool(email_msg.attachments),
            }
            email_data.append(email_dict)

        return APIResponse(
            success=True,
            message=f"Found {len(emails)} emails matching search criteria",
            data={
                "emails": email_data,
                "search_criteria": request.dict(),
                "total_found": len(emails),
            },
        )

    except Exception as e:
        logger.error(f"Error searching emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/email/unread", response_model=APIResponse)
async def get_unread_emails(
    folder: str = Query("INBOX", description="Folder to check for unread emails"),
    limit: int = Query(
        20, ge=1, le=100, description="Maximum number of unread emails to retrieve"
    ),
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Get unread emails from specified folder"""
    try:
        validate_email_manager()
        emails = manager.get_unread_emails(folder=folder, limit=limit)

        # Convert to dictionaries
        email_data = []
        for email_msg in emails:
            email_dict = {
                "message_id": email_msg.message_id,
                "subject": email_msg.subject,
                "sender": email_msg.sender,
                "date": email_msg.date.isoformat(),
                "body_preview": (
                    email_msg.body_text[:200] + "..."
                    if len(email_msg.body_text) > 200
                    else email_msg.body_text
                ),
                "has_attachments": bool(email_msg.attachments),
            }
            email_data.append(email_dict)

        return APIResponse(
            success=True,
            message=f"Retrieved {len(emails)} unread emails",
            data={"emails": email_data, "folder": folder, "unread_count": len(emails)},
        )

    except Exception as e:
        logger.error(f"Error getting unread emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== EMAIL MANAGEMENT ENDPOINTS ====================


@app.post("/email/mark-read", response_model=APIResponse)
async def mark_emails_as_read(
    request: EmailActionRequest,
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Mark emails as read"""
    try:
        validate_email_manager()
        success = manager.mark_as_read(request.email_ids, request.folder)

        return APIResponse(
            success=success,
            message=(
                f"Marked {len(request.email_ids)} emails as read"
                if success
                else "Failed to mark emails as read"
            ),
            data={
                "email_ids": request.email_ids,
                "folder": request.folder,
                "count": len(request.email_ids),
            },
        )

    except Exception as e:
        logger.error(f"Error marking emails as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/email/delete", response_model=APIResponse)
async def delete_emails(
    request: EmailActionRequest,
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Delete emails"""
    try:
        validate_email_manager()
        success = manager.delete_emails(request.email_ids, request.folder)

        return APIResponse(
            success=success,
            message=(
                f"Deleted {len(request.email_ids)} emails"
                if success
                else "Failed to delete emails"
            ),
            data={
                "email_ids": request.email_ids,
                "folder": request.folder,
                "count": len(request.email_ids),
            },
        )

    except Exception as e:
        logger.error(f"Error deleting emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/email/move", response_model=APIResponse)
async def move_emails(
    request: EmailMoveRequest,
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Move emails between folders"""
    try:
        validate_email_manager()
        success = manager.move_emails(
            request.email_ids, request.from_folder, request.to_folder
        )

        return APIResponse(
            success=success,
            message=(
                f"Moved {len(request.email_ids)} emails from {request.from_folder} to {request.to_folder}"
                if success
                else "Failed to move emails"
            ),
            data={
                "email_ids": request.email_ids,
                "from_folder": request.from_folder,
                "to_folder": request.to_folder,
                "count": len(request.email_ids),
            },
        )

    except Exception as e:
        logger.error(f"Error moving emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CONFIGURATION & TESTING ENDPOINTS ====================


@app.get("/email/test-connections", response_model=APIResponse)
async def test_email_connections(
    manager: AdvancedEmailManager = Depends(get_email_manager),
):
    """Test both SMTP and IMAP connections"""
    try:
        connections = manager.test_all_connections()

        return APIResponse(
            success=all(connections.values()),
            message="Connection tests completed",
            data={
                "smtp_connection": connections["smtp"],
                "imap_connection": connections["imap"],
                "all_working": all(connections.values()),
            },
        )

    except Exception as e:
        logger.error(f"Error testing connections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/email/config", response_model=APIResponse)
async def get_email_config(manager: AdvancedEmailManager = Depends(get_email_manager)):
    """Get current email configuration (without sensitive data)"""
    try:
        config_data = {
            "smtp_server": manager.config.smtp_server,
            "smtp_port": manager.config.smtp_port,
            "imap_server": manager.config.imap_server,
            "imap_port": manager.config.imap_port,
            "use_tls": manager.config.use_tls,
            "use_ssl": manager.config.use_ssl,
            "timeout": manager.config.timeout,
            "max_retries": manager.config.max_retries,
            "retry_delay": manager.config.retry_delay,
            "email_user": manager.email_user,
            "email_configured": bool(manager.email_user and manager.email_pass),
        }

        return APIResponse(
            success=True, message="Email configuration retrieved", data=config_data
        )

    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/email/stats", response_model=APIResponse)
async def get_email_stats(manager: AdvancedEmailManager = Depends(get_email_manager)):
    """Get email statistics and folder information"""
    try:
        validate_email_manager()

        # Get folder list
        folders = manager.get_folders()

        # Get unread count from INBOX
        unread_emails = manager.get_unread_emails(limit=100)  # Get count

        stats_data = {
            "total_folders": len(folders),
            "folders": folders,
            "unread_count": len(unread_emails),
            "last_checked": datetime.now().isoformat(),
            "connection_status": manager.test_all_connections(),
        }

        return APIResponse(
            success=True, message="Email statistics retrieved", data=stats_data
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== UTILITY ENDPOINTS ====================


@app.get("/", response_model=APIResponse)
async def root():
    """API health check and information"""
    return APIResponse(
        success=True,
        message="Advanced Email Management API is running",
        data={
            "version": "2.0.0",
            "features": [
                "Send emails with attachments",
                "Bulk email sending",
                "Receive and search emails",
                "Email management (read, delete, move)",
                "Advanced configuration",
                "Connection testing",
            ],
            "endpoints": {
                "send": "/email/send",
                "receive": "/email/list",
                "search": "/email/search",
                "docs": "/docs",
            },
        },
    )


@app.get("/health")
async def health_check():
    """Simple health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# ==================== ERROR HANDLERS ====================


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content=APIResponse(success=False, message=exc.detail).dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=APIResponse(
            success=False, message="Internal server error occurred"
        ).dict(),
    )


# ==================== STARTUP/SHUTDOWN EVENTS ====================


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    logger.info("🚀 Advanced Email Management API starting up...")

    # Test email configuration
    try:
        validate_email_manager()
        connections = email_manager.test_all_connections()
        if connections["smtp"]:
            logger.info("✅ SMTP connection working")
        else:
            logger.warning("⚠️ SMTP connection failed")

        if connections["imap"]:
            logger.info("✅ IMAP connection working")
        else:
            logger.warning("⚠️ IMAP connection failed")

    except Exception as e:
        logger.error(f"❌ Email configuration error: {e}")

    logger.info("🎉 API startup complete!")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown"""
    logger.info("📧 Advanced Email Management API shutting down...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
