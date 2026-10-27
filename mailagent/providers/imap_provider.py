"""
IMAP email provider implementation (Yahoo, generic IMAP)
"""

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Optional, Dict, Any
from datetime import datetime
import re

from mailagent.providers.base import EmailProviderInterface
from mailagent.core.types import EmailMessage, EmailProvider


class IMAPProvider(EmailProviderInterface):
    """IMAP provider for Yahoo and generic IMAP accounts"""

    def __init__(self, credentials: Dict[str, Any], provider: EmailProvider = EmailProvider.IMAP):
        super().__init__(credentials)
        self.provider = provider
        self.imap_client: Optional[imaplib.IMAP4] = None
        self.smtp_client = None  # To be implemented for sending

        # Extract credentials
        self.email_address = credentials.get("email_address")
        self.password = credentials.get("password")
        self.imap_server = credentials.get("imap_server")
        self.imap_port = credentials.get("imap_port", 993)
        self.smtp_server = credentials.get("smtp_server")
        self.smtp_port = credentials.get("smtp_port", 587)

    async def connect(self) -> bool:
        """Connect to IMAP server"""
        try:
            self.imap_client = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.imap_client.login(self.email_address, self.password)
            self.imap_client.select("INBOX")
            return True
        except Exception as e:
            print(f"IMAP connection failed: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from IMAP server"""
        if self.imap_client:
            try:
                self.imap_client.close()
                self.imap_client.logout()
            except:
                pass
            self.imap_client = None

    async def fetch_emails(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
        folder: str = "INBOX"
    ) -> List[EmailMessage]:
        """Fetch emails from IMAP server"""
        if not self.imap_client:
            await self.connect()

        messages = []

        try:
            # Search for emails
            search_criteria = ["ALL"]
            if since:
                date_str = since.strftime("%d-%b-%Y")
                search_criteria = [f"SINCE {date_str}"]

            status, message_ids = self.imap_client.search(None, *search_criteria)

            if status != "OK":
                return messages

            # Fetch messages (limit to most recent)
            id_list = message_ids[0].split()
            id_list = id_list[-limit:]  # Get most recent

            for msg_id in id_list:
                try:
                    status, msg_data = self.imap_client.fetch(msg_id, "(RFC822)")
                    if status == "OK":
                        raw_email = msg_data[0][1]
                        email_message = self._parse_email(raw_email)
                        if email_message:
                            messages.append(email_message)
                except Exception as e:
                    print(f"Error fetching message {msg_id}: {e}")
                    continue

        except Exception as e:
            print(f"Error fetching emails: {e}")

        return messages

    async def fetch_thread(self, thread_id: str) -> List[EmailMessage]:
        """Fetch all messages in a thread (by References header)"""
        # IMAP doesn't have native thread support, so we search by references
        if not self.imap_client:
            await self.connect()

        messages = []
        try:
            # Search for messages with matching references
            status, message_ids = self.imap_client.search(None, f'HEADER "References" "{thread_id}"')
            if status != "OK":
                return messages

            for msg_id in message_ids[0].split():
                try:
                    status, msg_data = self.imap_client.fetch(msg_id, "(RFC822)")
                    if status == "OK":
                        raw_email = msg_data[0][1]
                        email_message = self._parse_email(raw_email)
                        if email_message:
                            messages.append(email_message)
                except Exception as e:
                    continue

        except Exception as e:
            print(f"Error fetching thread: {e}")

        return sorted(messages, key=lambda x: x.received_at)

    async def fetch_sender_history(
        self,
        sender_email: str,
        limit: int = 50
    ) -> List[EmailMessage]:
        """Fetch historical emails from a specific sender"""
        if not self.imap_client:
            await self.connect()

        messages = []
        try:
            status, message_ids = self.imap_client.search(None, f'FROM "{sender_email}"')
            if status != "OK":
                return messages

            id_list = message_ids[0].split()
            id_list = id_list[-limit:]  # Get most recent

            for msg_id in id_list:
                try:
                    status, msg_data = self.imap_client.fetch(msg_id, "(RFC822)")
                    if status == "OK":
                        raw_email = msg_data[0][1]
                        email_message = self._parse_email(raw_email)
                        if email_message:
                            messages.append(email_message)
                except Exception as e:
                    continue

        except Exception as e:
            print(f"Error fetching sender history: {e}")

        return messages

    async def apply_label(self, message_id: str, label: str) -> bool:
        """Apply a label (IMAP uses flags)"""
        if not self.imap_client:
            await self.connect()

        try:
            # Convert label to flag
            flag = label.replace(" ", "_").upper()
            self.imap_client.store(message_id, "+FLAGS", f"\\{flag}")
            return True
        except Exception as e:
            print(f"Error applying label: {e}")
            return False

    async def move_to_folder(self, message_id: str, folder: str) -> bool:
        """Move email to folder"""
        if not self.imap_client:
            await self.connect()

        try:
            self.imap_client.copy(message_id, folder)
            self.imap_client.store(message_id, "+FLAGS", "\\Deleted")
            self.imap_client.expunge()
            return True
        except Exception as e:
            print(f"Error moving to folder: {e}")
            return False

    async def archive(self, message_id: str) -> bool:
        """Archive email (move to Archive folder or mark as archived)"""
        return await self.move_to_folder(message_id, "Archive")

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> str:
        """Create a draft email"""
        raise NotImplementedError("SMTP integration is not implemented for IMAP accounts")

    async def send_reply(self, draft_id: str) -> bool:
        """Send a draft reply"""
        raise NotImplementedError("SMTP integration is not implemented for IMAP accounts")

    async def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft"""
        raise NotImplementedError("SMTP integration is not implemented for IMAP accounts")

    def is_no_reply_address(self, email: str) -> bool:
        """Check if email is a no-reply address"""
        no_reply_patterns = [
            r"noreply@",
            r"no-reply@",
            r"donotreply@",
            r"do-not-reply@",
            r"notifications@",
            r"alert@",
            r"mailer@",
            r"bounce@"
        ]
        email_lower = email.lower()
        return any(re.search(pattern, email_lower) for pattern in no_reply_patterns)

    def has_unsubscribe_header(self, headers: Dict[str, Any]) -> bool:
        """Check if email has unsubscribe header"""
        unsubscribe_headers = [
            "List-Unsubscribe",
            "List-Unsubscribe-Post"
        ]
        return any(header in headers for header in unsubscribe_headers)

    def is_automated(self, headers: Dict[str, Any]) -> bool:
        """Check if email is automated"""
        automated_indicators = [
            "Auto-Submitted",
            "X-Auto-Response-Suppress",
            "X-Mailer",
            "X-Priority"
        ]
        return any(header in headers for header in automated_indicators)

    def _parse_email(self, raw_email: bytes) -> Optional[EmailMessage]:
        """Parse raw email bytes into EmailMessage"""
        try:
            msg = email.message_from_bytes(raw_email)

            # Extract headers
            headers = dict(msg.items())

            # Decode subject
            subject = ""
            if msg["Subject"]:
                subject_parts = decode_header(msg["Subject"])
                subject = ""
                for part, encoding in subject_parts:
                    if isinstance(part, bytes):
                        subject += part.decode(encoding or "utf-8", errors="ignore")
                    else:
                        subject += part

            # Extract sender
            sender = msg["From"] or ""
            sender_email = self._extract_email(sender)

            # Extract message ID and thread ID
            message_id = msg["Message-ID"] or ""
            thread_id = msg.get("References", message_id)
            if isinstance(thread_id, str):
                thread_id = thread_id.split()[-1] if thread_id else message_id

            # Extract date
            date_str = msg["Date"]
            received_at = parsedate_to_datetime(date_str) if date_str else datetime.utcnow()

            # Extract body
            body = self._extract_body(msg)

            # Extract recipients
            to = msg.get("To", "")
            recipients = self._extract_emails(to)
            cc = msg.get("Cc", "")
            cc_list = self._extract_emails(cc)

            # Extract in-reply-to and references
            in_reply_to = msg.get("In-Reply-To")
            references = msg.get("References", "").split()

            return EmailMessage(
                message_id=message_id,
                thread_id=thread_id,
                sender=sender,
                sender_email=sender_email,
                subject=subject,
                body=body,
                received_at=received_at,
                raw_headers=headers,
                recipients=recipients,
                cc=cc_list,
                in_reply_to=in_reply_to,
                references=references
            )

        except Exception as e:
            print(f"Error parsing email: {e}")
            return None

    def _extract_email(self, text: str) -> str:
        """Extract email address from text"""
        match = re.search(r"<([^>]+)>", text)
        if match:
            return match.group(1)
        return text.strip()

    def _extract_emails(self, text: str) -> List[str]:
        """Extract all email addresses from text"""
        return re.findall(r"<([^>]+)>", text) or [text.strip()] if text else []

    def _extract_body(self, msg) -> str:
        """Extract email body (prefer plain text)"""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                    break
                elif content_type == "text/html" and not body:
                    payload = part.get_payload(decode=True)
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
        else:
            payload = msg.get_payload(decode=True)
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="ignore")

        return body
