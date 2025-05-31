from pydantic import BaseModel, EmailStr, Field
from email_utils import AdvancedEmailManager, EmailConfig
from otp_utils import generate_otp, store_otp, verify_otp
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Contact API with OTP Verification",
    description="Simple contact form with email OTP verification (Testing)",
    version="1.0.0",
)

# CORS Configuration
origins = [
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://localhost:3000",
    "http://localhost:8080",
    "*",  # Allow all origins for testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- In-memory storage for testing ---
otp_store = {}
otp_rate_limit = {}
contact_submissions = []  # Store submissions for testing

# --- Email Configuration ---
email_config = EmailConfig(
    smtp_server=os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    smtp_port=int(os.getenv("SMTP_PORT", 587)),
    timeout=30,
    max_retries=2,
    retry_delay=1,
)

email_sender = AdvancedEmailManager(email_config)


# --- Pydantic Models ---
class ContactForm(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=15)
    message: str = Field(..., min_length=10, max_length=1000)
    company: Optional[str] = Field(None, max_length=100)
    subject: Optional[str] = Field("Contact Form Submission", max_length=200)


class OTPVerify(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)


class ContactSubmission(BaseModel):
    contact_data: ContactForm
    otp: str = Field(..., min_length=6, max_length=6)


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# --- Helper Functions ---
def check_rate_limit(email: str) -> Dict[str, Any]:
    """Simple rate limiting check"""
    now = time.time()
    user_entry = otp_rate_limit.get(email, {})
    last_sent = user_entry.get("last_sent", 0)
    send_count = user_entry.get("send_count", 0)

    # Must wait 60 seconds between requests
    time_since_last = now - last_sent
    if time_since_last < 60:
        return {
            "allowed": False,
            "reason": "too_frequent",
            "wait_time": 60 - int(time_since_last),
        }

    # Max 5 attempts per hour
    if send_count >= 5 and time_since_last < 3600:
        return {
            "allowed": False,
            "reason": "hourly_limit",
            "wait_time": 3600 - int(time_since_last),
        }

    return {"allowed": True}


def update_rate_limit(email: str):
    """Update rate limit counters"""
    now = time.time()
    user_entry = otp_rate_limit.get(email, {})
    last_sent = user_entry.get("last_sent", 0)
    send_count = user_entry.get("send_count", 0)

    # Reset count if more than an hour has passed
    if now - last_sent > 3600:
        send_count = 0

    otp_rate_limit[email] = {"last_sent": now, "send_count": send_count + 1}


def create_simple_otp_email(name: str, otp: str) -> str:
    """Create a styled HTML email for OTP verification"""
    return f"""
    <div style="font-family: 'Segoe UI', Tahoma, sans-serif; max-width: 600px; margin: auto; padding: 24px; background-color: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px;">
        <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">🔐 OTP Verification</h2>
        <p style="font-size: 16px; color: #34495e;">Hi <strong>{name}</strong>,</p>
        <p style="font-size: 15px; color: #555;">Please use the following One-Time Password (OTP) to verify your identity:</p>

        <div style="background-color: #f2f6fc; padding: 16px; border: 2px dashed #3498db; border-radius: 6px; text-align: center; margin: 20px 0;">
            <span style="font-size: 28px; color: #2c3e50; font-weight: bold; letter-spacing: 4px;">{otp}</span>
        </div>

        <p style="font-size: 14px; color: #7f8c8d;">⏳ This OTP is valid for the next <strong>10 minutes</strong>.</p>
        <p style="font-size: 14px; color: #7f8c8d;">❌ If you didn’t request this verification, you can safely ignore this email.</p>

        <hr style="margin: 30px 0;">
        <p style="font-size: 12px; color: #bdc3c7;">This is an automated message from the Stockify system. Please do not reply.</p>
    </div>
    """



# --- API Endpoints ---
@app.get("/", response_model=APIResponse)
async def root():
    """Health check endpoint"""
    return APIResponse(
        success=True,
        message="Contact API is running (Testing Mode)",
        data={"version": "1.0.0", "mode": "testing", "storage": "in-memory"},
    )


@app.post("/contact/send-otp", response_model=APIResponse)
async def send_contact_otp(data: ContactForm, background_tasks: BackgroundTasks):
    """Send OTP for contact form verification"""
    try:
        # Check rate limits
        rate_check = check_rate_limit(data.email)
        if not rate_check["allowed"]:
            if rate_check["reason"] == "too_frequent":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {rate_check['wait_time']} seconds before requesting another OTP",
                )
            elif rate_check["reason"] == "hourly_limit":
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Hourly limit exceeded. Try again in {rate_check['wait_time']//60} minutes",
                )

        # Generate and store OTP
        otp = generate_otp()
        store_otp(data.email, otp)

        # Update rate limiting
        update_rate_limit(data.email)

        # Prepare email
        subject = f"OTP Verification - {data.subject}"
        html_message = create_simple_otp_email(data.name, otp)

        # Send email in background
        def send_otp_email():
            try:
                result = email_sender.send_email(
                    to_emails=data.email,
                    subject=subject,
                    message_body=html_message,
                    is_html=True,
                    sender_name="Contact Form",
                )
                logger.info(f"OTP email result: {result}")
            except Exception as e:
                logger.error(f"Error sending OTP email: {e}")

        background_tasks.add_task(send_otp_email)

        return APIResponse(
            success=True,
            message="OTP sent successfully",
            data={
                "email": data.email,
                "otp_for_testing": otp,
            },  # Include OTP in response for testing
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in send_contact_otp: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send OTP",
        )


@app.post("/contact/verify-otp", response_model=APIResponse)
async def verify_contact_otp(data: OTPVerify):
    """Verify OTP code"""
    try:
        if verify_otp(data.email, data.otp):
            return APIResponse(
                success=True,
                message="OTP verified successfully",
                data={"email": data.email, "verified": True},
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in verify_contact_otp: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OTP verification failed",
        )


@app.post("/contact/submit", response_model=APIResponse)
async def submit_contact_form(
    data: ContactSubmission, background_tasks: BackgroundTasks
):
    """Submit contact form after OTP verification"""
    try:
        # Verify OTP first
        email = data.contact_data.email
        if not verify_otp(email, data.otp):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired OTP",
            )

        # Store submission
        submission = {
            "id": f"CF_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "data": data.contact_data.dict(),
        }
        contact_submissions.append(submission)

        # Send emails in background
        def process_submission():
            try:
                # Admin notification
                admin_message = f"""
<div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: auto; padding: 20px; background-color: #fefefe; border: 1px solid #ddd; border-radius: 10px; color: #2c3e50;">
    <h2 style="color: #c0392b; border-bottom: 2px solid #c0392b; padding-bottom: 10px;">📥 New Contact Form Submission</h2>

    <table style="width: 100%; border-collapse: collapse;">
        <tr>
            <td style="padding: 8px 0;"><strong>Name:</strong></td>
            <td style="padding: 8px 0;">{data.contact_data.name}</td>
        </tr>
        <tr style="background-color: #f9f9f9;">
            <td style="padding: 8px 0;"><strong>Email:</strong></td>
            <td style="padding: 8px 0;">{data.contact_data.email}</td>
        </tr>
        <tr>
            <td style="padding: 8px 0;"><strong>Phone:</strong></td>
            <td style="padding: 8px 0;">{data.contact_data.phone}</td>
        </tr>
        <tr style="background-color: #f9f9f9;">
            <td style="padding: 8px 0;"><strong>Company:</strong></td>
            <td style="padding: 8px 0;">{data.contact_data.company or 'Not provided'}</td>
        </tr>
        <tr>
            <td style="padding: 8px 0; vertical-align: top;"><strong>Message:</strong></td>
            <td style="padding: 8px 0; white-space: pre-wrap;">{data.contact_data.message}</td>
        </tr>
    </table>

    <p style="margin-top: 20px; font-size: 12px; color: #999;">📬 This message was automatically generated from the Stockify contact form.</p>
</div>
"""

                admin_email = os.getenv("ADMIN_EMAIL", "svm.singh.01@gmail.com")
                email_sender.send_email(
                    to_emails=admin_email,
                    subject=f"New Contact: {data.contact_data.subject}",
                    message_body=admin_message,
                    is_html=True,
                )

                # User confirmation
                user_message = f"""
                    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #2c3e50; line-height: 1.6; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px; background-color: #f9f9f9;">
                        <h2 style="color: #2980b9; border-bottom: 2px solid #2980b9; padding-bottom: 10px;">📩 Thank You for Contacting Us!</h2>
                        <p>Hi <strong>{data.contact_data.name}</strong>,</p>
                        <p>We sincerely appreciate you reaching out. We've received your message and our support team will get back to you within <strong>24–48 hours</strong>.</p>
                        <div style="background-color: #ffffff; padding: 15px; border-left: 4px solid #3498db; margin: 20px 0;">
                            <p style="margin: 0;"><strong>Your message:</strong></p>
                            <p style="margin: 5px 0 0;">{data.contact_data.message}</p>
                        </div>
                        <p>If your matter is urgent, feel free to reply to this email or contact us directly through the chat support on our website.</p>
                        <p>Warm regards,</p>
                        <p style="margin-top: 10px;"><strong>— Stockify Support Team</strong></p>
                    </div>
                    """

                email_sender.send_email(
                    to_emails=data.contact_data.email,
                    subject="Thank you for contacting us",
                    message_body=user_message,
                    is_html=True,
                )

            except Exception as e:
                logger.error(f"Error processing submission: {e}")

        background_tasks.add_task(process_submission)

        return APIResponse(
            success=True,
            message="Contact form submitted successfully!",
            data={"submission_id": submission["id"], "email": data.contact_data.email},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in submit_contact_form: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit contact form",
        )


@app.get("/contact/submissions", response_model=APIResponse)
async def get_submissions():
    """Get all contact submissions (testing only)"""
    return APIResponse(
        success=True,
        message="Contact submissions retrieved",
        data={
            "total": len(contact_submissions),
            "submissions": contact_submissions[-10:],  # Last 10 submissions
        },
    )


@app.get("/contact/test-email")
async def test_email():
    """Test email service"""
    try:
        if email_sender.test_connection():
            return APIResponse(success=True, message="Email service is working")
        else:
            return APIResponse(success=False, message="Email service connection failed")
    except Exception as e:
        return APIResponse(success=False, message=f"Email test error: {str(e)}")


@app.get("/contact/debug")
async def debug_info():
    """Debug information (testing only)"""
    return APIResponse(
        success=True,
        message="Debug information",
        data={
            "otp_store_count": len(otp_store),
            "rate_limit_count": len(otp_rate_limit),
            "submissions_count": len(contact_submissions),
            "current_otps": {
                email: "***" + otp[-3:] for email, otp in otp_store.items()
            },
            "rate_limits": otp_rate_limit,
        },
    )


# --- Exception Handlers ---
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
        content=APIResponse(success=False, message="Internal server error").dict(),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
