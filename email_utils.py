import smtplib
import imaplib
import ssl
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr, parseaddr
from email.header import decode_header
from dotenv import load_dotenv
import os
import logging
from typing import List, Optional, Dict, Union, Tuple
from pathlib import Path
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


@dataclass
class EmailConfig:
    """Email configuration class"""

    # SMTP Configuration
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    use_tls: bool = True

    # IMAP Configuration
    imap_server: str = "imap.gmail.com"
    imap_port: int = 993
    use_ssl: bool = True

    # General settings
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 2


@dataclass
class EmailAttachment:
    """Email attachment class"""

    file_path: str
    filename: Optional[str] = None
    content_type: Optional[str] = None


@dataclass
class EmailMessage:
    """Email message structure"""

    message_id: str
    subject: str
    sender: str
    recipients: List[str]
    date: datetime
    body_text: str
    body_html: Optional[str] = None
    attachments: List[str] = None
    is_read: bool = False
    folder: str = "INBOX"


class AdvancedEmailManager:
    def __init__(self, config: Optional[EmailConfig] = None):
        self.email_user = os.getenv("EMAIL_USER")
        self.email_pass = os.getenv("EMAIL_PASS")
        self.config = config or EmailConfig()

        if not self.email_user or not self.email_pass:
            raise ValueError(
                "EMAIL_USER and EMAIL_PASS must be set in environment variables"
            )

    # ==================== SENDING EMAILS ====================

    def send_email(
        self,
        to_emails: Union[str, List[str]],
        subject: str,
        message_body: str,
        is_html: bool = False,
        cc_emails: Optional[Union[str, List[str]]] = None,
        bcc_emails: Optional[Union[str, List[str]]] = None,
        attachments: Optional[List[EmailAttachment]] = None,
        sender_name: Optional[str] = "Stockify",
        reply_to: Optional[str] = None,
        priority: str = "normal",
        track_delivery: bool = False,
        save_to_sent: bool = True,
    ) -> Dict[str, Union[bool, str, List[str]]]:
        """Advanced email sending with comprehensive features"""
        try:
            # Normalize email lists
            to_emails = self._normalize_email_list(to_emails)
            cc_emails = self._normalize_email_list(cc_emails) if cc_emails else []
            bcc_emails = self._normalize_email_list(bcc_emails) if bcc_emails else []

            # Validate email addresses
            all_emails = to_emails + cc_emails + bcc_emails
            invalid_emails = [
                email for email in all_emails if not self._is_valid_email(email)
            ]
            if invalid_emails:
                raise ValueError(f"Invalid email addresses: {invalid_emails}")

            # Create message
            msg = self._create_message(
                to_emails,
                cc_emails,
                subject,
                message_body,
                is_html,
                sender_name,
                reply_to,
                priority,
                track_delivery,
            )

            # Add attachments
            if attachments:
                self._add_attachments(msg, attachments)

            # Send email with retry logic
            success = self._send_with_retry(msg, to_emails + cc_emails + bcc_emails)

            # Save to sent folder if requested
            if success and save_to_sent:
                self._save_to_sent_folder(msg)

            result = {
                "success": success,
                "timestamp": datetime.now().isoformat(),
                "recipients": to_emails + cc_emails + bcc_emails,
                "subject": subject,
                "message_id": msg.get("Message-ID"),
            }

            if success:
                logger.info(
                    f"✅ Email sent successfully to {len(all_emails)} recipients"
                )
            else:
                logger.error(
                    f"❌ Failed to send email after {self.config.max_retries} attempts"
                )

            return result

        except Exception as e:
            logger.error(f"❌ Email sending failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def send_bulk_emails(
        self,
        email_list: List[Dict],
        delay_between_emails: float = 1.0,
        batch_size: int = 50,
    ) -> List[Dict]:
        """Send bulk emails with batching and rate limiting"""
        results = []
        total_emails = len(email_list)

        for batch_start in range(0, total_emails, batch_size):
            batch_end = min(batch_start + batch_size, total_emails)
            batch = email_list[batch_start:batch_end]

            logger.info(
                f"Processing batch {batch_start//batch_size + 1}: emails {batch_start+1}-{batch_end}"
            )

            for i, email_data in enumerate(batch):
                try:
                    result = self.send_email(**email_data)
                    results.append(
                        {
                            **result,
                            "batch": batch_start // batch_size + 1,
                            "email_index": batch_start + i,
                        }
                    )

                    # Add delay between emails
                    if i < len(batch) - 1:
                        time.sleep(delay_between_emails)

                except Exception as e:
                    logger.error(
                        f"Failed to send bulk email {batch_start + i + 1}: {e}"
                    )
                    results.append(
                        {
                            "success": False,
                            "error": str(e),
                            "batch": batch_start // batch_size + 1,
                            "email_index": batch_start + i,
                        }
                    )

            # Longer delay between batches
            if batch_end < total_emails:
                time.sleep(delay_between_emails * 5)

        return results

    # ==================== RECEIVING EMAILS ====================

    _imap_connection = None

    def connect_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server, reusing existing connection if available"""
        try:
            if self._imap_connection and self._is_valid_imap_connection(self._imap_connection):
                logger.info("✅ Reusing existing IMAP connection")
                return self._imap_connection

            if self.config.use_ssl:
                mail = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port, timeout=self.config.timeout)
            else:
                mail = imaplib.IMAP4(self.config.imap_server, self.config.imap_port, timeout=self.config.timeout)

            mail.login(self.email_user, self.email_pass)
            self._imap_connection = mail
            logger.info("✅ IMAP connection established")
            return mail
        except Exception as e:
            logger.error(f"❌ IMAP connection failed: {e}")
            raise

    def _is_valid_imap_connection(self, mail) -> bool:
        """Check if the IMAP connection is still valid"""
        try:
            mail.noop()  # Check if the connection is still alive
            return True
        except Exception:
            return False

    def disconnect_imap(self):
        """Disconnect from IMAP server"""
        if self._imap_connection:
            try:
                self._imap_connection.close()
                self._imap_connection.logout()
                logger.info("✅ IMAP connection closed")
            except Exception as e:
                logger.error(f"❌ Error disconnecting from IMAP: {e}")
            finally:
                self._imap_connection = None

    def get_folders(self) -> List[str]:
        """Get list of available email folders"""
        try:
            mail = self.connect_imap()
            status, folders = mail.list()
            mail.logout()

            folder_names = []
            for folder in folders:
                # Parse folder name from IMAP response
                folder_name = (
                    folder.decode().split('"')[-2]
                    if '"' in folder.decode()
                    else folder.decode().split()[-1]
                )
                folder_names.append(folder_name)

            return folder_names
        except Exception as e:
            logger.error(f"Error getting folders: {e}")
            return []

    def get_emails(
        self,
        folder: str = "INBOX",
        limit: int = 10,
        search_criteria: str = "ALL",
        include_attachments: bool = False,
        mark_as_read: bool = False,
    ) -> List[EmailMessage]:
        """Retrieve emails from specified folder"""
        try:
            mail = self.connect_imap()
            mail.select(folder)

            # Search for emails
            status, messages = mail.search(None, search_criteria)
            email_ids = messages[0].split()

            # Get latest emails (reverse order)
            email_ids = email_ids[-limit:] if limit else email_ids
            email_ids.reverse()

            emails = []
            for email_id in email_ids:
                try:
                    email_msg = self._fetch_email(
                        mail, email_id, include_attachments, mark_as_read
                    )
                    if email_msg:
                        emails.append(email_msg)
                except Exception as e:
                    logger.error(f"Error processing email {email_id}: {e}")
                    continue

            mail.logout()
            logger.info(f"✅ Retrieved {len(emails)} emails from {folder}")
            return emails

        except Exception as e:
            logger.error(f"❌ Error retrieving emails: {e}")
            return []

    def search_emails(
        self,
        query: str,
        folder: str = "INBOX",
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        sender: Optional[str] = None,
        subject_contains: Optional[str] = None,
        limit: int = 50,
    ) -> List[EmailMessage]:
        """Advanced email search with multiple criteria"""
        try:
            # Build search criteria
            search_parts = []

            if query:
                search_parts.append(f'TEXT "{query}"')

            if sender:
                search_parts.append(f'FROM "{sender}"')

            if subject_contains:
                search_parts.append(f'SUBJECT "{subject_contains}"')

            if date_from:
                search_parts.append(f'SINCE "{date_from.strftime("%d-%b-%Y")}"')

            if date_to:
                search_parts.append(f'BEFORE "{date_to.strftime("%d-%b-%Y")}"')

            search_criteria = " ".join(search_parts) if search_parts else "ALL"

            return self.get_emails(
                folder=folder,
                limit=limit,
                search_criteria=search_criteria,
                include_attachments=True,
            )

        except Exception as e:
            logger.error(f"❌ Email search failed: {e}")
            return []

    def get_unread_emails(
        self, folder: str = "INBOX", limit: int = 20
    ) -> List[EmailMessage]:
        """Get unread emails"""
        return self.get_emails(folder=folder, limit=limit, search_criteria="UNSEEN")

    def mark_as_read(self, email_ids: List[str], folder: str = "INBOX") -> bool:
        """Mark emails as read"""
        try:
            mail = self.connect_imap()
            mail.select(folder)

            for email_id in email_ids:
                mail.store(email_id, "+FLAGS", "\\Seen")

            mail.logout()
            logger.info(f"✅ Marked {len(email_ids)} emails as read")
            return True
        except Exception as e:
            logger.error(f"❌ Error marking emails as read: {e}")
            return False

    def delete_emails(self, email_ids: List[str], folder: str = "INBOX") -> bool:
        """Delete emails"""
        try:
            mail = self.connect_imap()
            mail.select(folder)

            for email_id in email_ids:
                mail.store(email_id, "+FLAGS", "\\Deleted")

            mail.expunge()
            mail.logout()
            logger.info(f"✅ Deleted {len(email_ids)} emails")
            return True
        except Exception as e:
            logger.error(f"❌ Error deleting emails: {e}")
            return False

    def move_emails(
        self, email_ids: List[str], from_folder: str, to_folder: str
    ) -> bool:
        """Move emails between folders"""
        try:
            mail = self.connect_imap()
            mail.select(from_folder)

            for email_id in email_ids:
                mail.move(email_id, to_folder)

            mail.logout()
            logger.info(
                f"✅ Moved {len(email_ids)} emails from {from_folder} to {to_folder}"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Error moving emails: {e}")
            return False

    # ==================== HELPER METHODS ====================

    def _fetch_email(
        self, mail, email_id, include_attachments: bool, mark_as_read: bool
    ) -> Optional[EmailMessage]:
        """Fetch and parse individual email"""
        try:
            status, msg_data = mail.fetch(email_id, "(RFC822)")

            if status != "OK":
                return None

            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)

            # Extract email details
            subject = self._decode_header(email_message.get("Subject", ""))
            sender = self._decode_header(email_message.get("From", ""))
            recipients = self._parse_recipients(email_message)
            date = self._parse_date(email_message.get("Date"))
            message_id = email_message.get("Message-ID", "")

            # Extract body
            body_text, body_html = self._extract_body(email_message)

            # Extract attachments if requested
            attachments = []
            if include_attachments:
                attachments = self._extract_attachments(
                    email_message, email_id.decode()
                )

            # Mark as read if requested
            if mark_as_read:
                mail.store(email_id, "+FLAGS", "\\Seen")

            return EmailMessage(
                message_id=message_id,
                subject=subject,
                sender=sender,
                recipients=recipients,
                date=date,
                body_text=body_text,
                body_html=body_html,
                attachments=attachments,
                is_read=False,  # Would need to check flags to determine this
                folder="INBOX",  # Current folder
            )

        except Exception as e:
            logger.error(f"Error fetching email {email_id}: {e}")
            return None

    def _decode_header(self, header: str) -> str:
        """Decode email header"""
        if not header:
            return ""

        decoded_parts = decode_header(header)
        decoded_string = ""

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                decoded_string += part.decode(encoding or "utf-8", errors="ignore")
            else:
                decoded_string += part

        return decoded_string

    def _parse_recipients(self, email_message) -> List[str]:
        """Parse recipient email addresses"""
        recipients = []

        for header in ["To", "Cc", "Bcc"]:
            header_value = email_message.get(header)
            if header_value:
                addresses = [addr.strip() for addr in header_value.split(",")]
                recipients.extend(addresses)

        return recipients

    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date"""
        try:
            return email.utils.parsedate_to_datetime(date_str)
        except:
            return datetime.now()

    def _extract_body(self, email_message) -> Tuple[str, Optional[str]]:
        """Extract email body (text and HTML)"""
        body_text = ""
        body_html = None

        if email_message.is_multipart():
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" not in content_disposition:
                    if content_type == "text/plain":
                        body_text = part.get_payload(decode=True).decode(
                            "utf-8", errors="ignore"
                        )
                    elif content_type == "text/html":
                        body_html = part.get_payload(decode=True).decode(
                            "utf-8", errors="ignore"
                        )
        else:
            content_type = email_message.get_content_type()
            if content_type == "text/plain":
                body_text = email_message.get_payload(decode=True).decode(
                    "utf-8", errors="ignore"
                )
            elif content_type == "text/html":
                body_html = email_message.get_payload(decode=True).decode(
                    "utf-8", errors="ignore"
                )

        return body_text, body_html

    def _extract_attachments(self, email_message, email_id: str) -> List[str]:
        """Extract attachment information"""
        attachments = []

        if email_message.is_multipart():
            for part in email_message.walk():
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        # Decode filename if needed
                        filename = self._decode_header(filename)
                        attachments.append(filename)

        return attachments

    def _create_message(
        self,
        to_emails,
        cc_emails,
        subject,
        message_body,
        is_html,
        sender_name,
        reply_to,
        priority,
        track_delivery,
    ) -> MIMEMultipart:
        """Create email message with headers"""
        msg = MIMEMultipart("alternative")

        # Basic headers
        sender_address = (
            formataddr((sender_name, self.email_user))
            if sender_name
            else self.email_user
        )
        msg["From"] = sender_address
        msg["To"] = ", ".join(to_emails)
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        msg["Subject"] = subject
        msg["Date"] = email.utils.formatdate(localtime=True)
        msg["Message-ID"] = email.utils.make_msgid()

        # Optional headers
        if reply_to:
            msg["Reply-To"] = reply_to

        # Priority header
        priority_map = {
            "high": ("1", "High"),
            "normal": ("3", "Normal"),
            "low": ("5", "Low"),
        }
        if priority in priority_map:
            msg["X-Priority"] = priority_map[priority][0]
            msg["X-MSMail-Priority"] = priority_map[priority][1]

        # Delivery tracking
        if track_delivery:
            msg["Disposition-Notification-To"] = self.email_user
            msg["Return-Receipt-To"] = self.email_user

        # Message body
        mime_type = "html" if is_html else "plain"
        msg.attach(MIMEText(message_body, mime_type, "utf-8"))

        return msg

    def _add_attachments(self, msg: MIMEMultipart, attachments: List[EmailAttachment]):
        """Add attachments to email message"""
        for attachment in attachments:
            try:
                file_path = Path(attachment.file_path)
                if not file_path.exists():
                    logger.warning(f"Attachment file not found: {file_path}")
                    continue

                with open(file_path, "rb") as attachment_file:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment_file.read())

                encoders.encode_base64(part)

                filename = attachment.filename or file_path.name
                part.add_header(
                    "Content-Disposition", f"attachment; filename= {filename}"
                )

                msg.attach(part)
                logger.info(f"Added attachment: {filename}")

            except Exception as e:
                logger.error(f"Failed to add attachment {attachment.file_path}: {e}")

    def _send_with_retry(self, msg: MIMEMultipart, all_recipients: List[str]) -> bool:
        """Send email with retry logic"""
        for attempt in range(1, self.config.max_retries + 1):
            try:
                context = ssl.create_default_context()
                with smtplib.SMTP(
                    self.config.smtp_server,
                    self.config.smtp_port,
                    timeout=self.config.timeout,
                ) as server:
                    if self.config.use_tls:
                        server.starttls(context=context)
                    server.login(self.email_user, self.email_pass)
                    server.send_message(msg, to_addrs=all_recipients)
                logger.info("✅ Email sent successfully")
                return True
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP Authentication failed: {e}")
                break
            except smtplib.SMTPRecipientsRefused as e:
                logger.error(f"Recipients refused: {e}")
                break
            except (smtplib.SMTPException, ConnectionError, TimeoutError) as e:
                logger.warning(f"Attempt {attempt} failed: {e}")
                if attempt < self.config.max_retries:
                    time.sleep(self.config.retry_delay)
                    continue
                else:
                    logger.error(f"❌ Max retries reached. Email failed: {e}")
                    return False
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break
        return False

    def _save_to_sent_folder(self, msg: MIMEMultipart):
        """Save sent email to Sent folder"""
        try:
            mail = self.connect_imap()
            mail.append("Sent", None, None, msg.as_bytes())
            mail.logout()
            logger.info("✅ Email saved to Sent folder")
        except Exception as e:
            logger.warning(f"⚠️ Could not save to Sent folder: {e}")

    def _normalize_email_list(self, emails: Union[str, List[str]]) -> List[str]:
        """Convert email input to list format"""
        if isinstance(emails, str):
            return [email.strip() for email in emails.split(",")]
        return emails

    def _is_valid_email(self, email: str) -> bool:
        """Basic email validation"""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email.strip()) is not None

    # ==================== CONNECTION TESTING ====================

    def test_smtp_connection(self) -> bool:
        """Test SMTP connection"""
        try:
            with smtplib.SMTP(
                self.config.smtp_server, self.config.smtp_port, timeout=10
            ) as server:
                if self.config.use_tls:
                    server.starttls()
                server.login(self.email_user, self.email_pass)
            logger.info("✅ SMTP connection test successful")
            return True
        except Exception as e:
            logger.error(f"❌ SMTP connection test failed: {e}")
            return False

    def test_imap_connection(self) -> bool:
        """Test IMAP connection"""
        try:
            mail = self.connect_imap()
            mail.logout()
            logger.info("✅ IMAP connection test successful")
            return True
        except Exception as e:
            logger.error(f"❌ IMAP connection test failed: {e}")
            return False

    def test_all_connections(self) -> Dict[str, bool]:
        """Test both SMTP and IMAP connections"""
        return {
            "smtp": self.test_smtp_connection(),
            "imap": self.test_imap_connection(),
        }


# ==================== CONVENIENCE FUNCTIONS ====================


def send_simple_email(to_email: str, subject: str, message: str, is_html: bool = False):
    """Simple wrapper for basic email sending"""
    manager = AdvancedEmailManager()
    return manager.send_email(to_email, subject, message, is_html)


def get_recent_emails(limit: int = 10, folder: str = "INBOX"):
    """Get recent emails"""
    manager = AdvancedEmailManager()
    return manager.get_emails(folder=folder, limit=limit)


def search_emails_simple(query: str, limit: int = 20):
    """Simple email search"""
    manager = AdvancedEmailManager()
    return manager.search_emails(query=query, limit=limit)


# ==================== EXAMPLE USAGE ====================

if __name__ == "__main__":
    # Initialize email manager
    email_manager = AdvancedEmailManager()

    # Test connections
    connections = email_manager.test_all_connections()
    print(f"Connection tests: {connections}")

    if connections["smtp"] and connections["imap"]:
        # Send a test email
        result = email_manager.send_email(
            to_emails="code.python.51@gmail.com",
            subject="Test Email from Advanced Manager",
            message_body="<h1>Hello!</h1><p>This is a test email.</p>",
            is_html=True,
            sender_name="Email Manager",
            priority="high",
        )
        print(f"Send result: {result}")

        # Get recent emails
        recent_emails = email_manager.get_emails(limit=5)
        print(f"Recent emails: {len(recent_emails)}")

        for email_msg in recent_emails:
            print(f"- {email_msg.subject} from {email_msg.sender}")

        # Search for emails
        search_results = email_manager.search_emails(
            query="test", subject_contains="important", limit=10
        )
        print(f"Search results: {len(search_results)}")

        # Get unread emails
        unread = email_manager.get_unread_emails(limit=5)
        print(f"Unread emails: {len(unread)}")
