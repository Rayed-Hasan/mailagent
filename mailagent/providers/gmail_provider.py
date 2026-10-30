"""
Gmail provider with OAuth2 authentication
"""

import base64
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import re
import logging
from email.message import EmailMessage as MIMEEmailMessage

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from mailagent.providers.base import EmailProviderInterface
from mailagent.core.types import EmailMessage, EmailProvider
from mailagent.core.config import settings


READONLY_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
]

DEFAULT_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
]

FULL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.send',
]

SCOPES = DEFAULT_SCOPES
logger = logging.getLogger("mailagent.gmail")


class GmailProvider(EmailProviderInterface):
    """Gmail provider with OAuth2 authentication"""

    def __init__(self, credentials: Dict[str, Any], scopes: Optional[List[str]] = None):
        super().__init__(credentials)
        self.provider = EmailProvider.GMAIL
        self.service = None
        self.credentials = None
        self.active_scopes = scopes or SCOPES

        # Initialize credentials from stored token or credentials dict
        token_info = credentials.get('token') if isinstance(credentials.get('token'), dict) else credentials
        if token_info and ('token' in token_info or 'refresh_token' in token_info):
            try:
                self.credentials = Credentials.from_authorized_user_info(token_info, self.active_scopes)
            except Exception as exc:
                logger.warning("Failed to load stored Gmail credentials (%s)", type(exc).__name__)

    async def connect(self) -> bool:
        """Connect to Gmail API, refreshing credentials if expired"""
        try:
            if not self.credentials:
                return False

            if not self.credentials.valid:
                if self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                else:
                    return False

            self.service = build('gmail', 'v1', credentials=self.credentials)
            return True
        except Exception as exc:
            logger.warning("Gmail connection failed (%s)", type(exc).__name__)
            return False

    async def disconnect(self) -> None:
        """Disconnect from Gmail API"""
        self.service = None

    async def get_user_profile(self) -> Optional[Dict[str, Any]]:
        """Get the authorized user's profile info (e.g. email address)"""
        if not self.service:
            if not await self.connect():
                return None
        try:
            profile = self.service.users().getProfile(userId='me').execute()
            return profile
        except Exception as exc:
            logger.warning("Gmail profile request failed (%s)", type(exc).__name__)
            return None

    async def fetch_emails(
        self,
        since: Optional[datetime] = None,
        limit: int = 100,
        folder: str = "INBOX"
    ) -> List[EmailMessage]:
        """Fetch emails from Gmail"""
        if not self.service:
            await self.connect()

        messages = []

        try:
            # Build search query
            query = f"in:{folder.lower()}"
            if since:
                date_str = since.strftime("%Y/%m/%d")
                query += f" after:{date_str}"

            # Search for messages
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=limit
            ).execute()

            message_ids = results.get('messages', [])

            # Fetch full message details
            for msg_id in message_ids:
                try:
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=msg_id['id'],
                        format='full'
                    ).execute()

                    email_message = self._parse_gmail_message(msg)
                    if email_message:
                        messages.append(email_message)
                except Exception as exc:
                    logger.warning("Gmail message fetch failed (%s)", type(exc).__name__)
                    continue

        except HttpError as exc:
            logger.warning(
                "Gmail message list request failed (HTTP %s)",
                getattr(getattr(exc, "resp", None), "status", "unknown"),
            )
            raise RuntimeError("Unable to list messages from Gmail") from exc

        return messages

    async def fetch_thread(self, thread_id: str) -> List[EmailMessage]:
        """Fetch all messages in a Gmail thread"""
        if not self.service:
            await self.connect()

        messages = []

        try:
            thread = self.service.users().threads().get(
                userId='me',
                id=thread_id
            ).execute()

            for msg in thread.get('messages', []):
                email_message = self._parse_gmail_message(msg)
                if email_message:
                    messages.append(email_message)

        except HttpError as exc:
            logger.warning("Gmail thread request failed (%s)", type(exc).__name__)

        return messages

    async def fetch_sender_history(
        self,
        sender_email: str,
        limit: int = 50
    ) -> List[EmailMessage]:
        """Fetch historical emails from a specific sender"""
        if not self.service:
            await self.connect()

        messages = []

        try:
            query = f"from:{sender_email}"
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=limit
            ).execute()

            message_ids = results.get('messages', [])

            for msg_id in message_ids:
                try:
                    msg = self.service.users().messages().get(
                        userId='me',
                        id=msg_id['id'],
                        format='full'
                    ).execute()

                    email_message = self._parse_gmail_message(msg)
                    if email_message:
                        messages.append(email_message)
                except Exception:
                    continue

        except HttpError as exc:
            logger.warning("Gmail sender history request failed (%s)", type(exc).__name__)

        return messages

    async def apply_label(self, message_id: str, label: str) -> bool:
        """Apply a label to a Gmail message"""
        if not self.service:
            await self.connect()

        try:
            # First, get or create the label
            labels = self.service.users().labels().list(userId='me').execute()
            label_id = None

            for lbl in labels.get('labels', []):
                if lbl['name'].upper() == label.upper():
                    label_id = lbl['id']
                    break

            if not label_id:
                # Create the label
                new_label = self.service.users().labels().create(
                    userId='me',
                    body={'name': label}
                ).execute()
                label_id = new_label['id']

            # Apply the label
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': [label_id]}
            ).execute()

            return True

        except HttpError as exc:
            logger.warning("Gmail label request failed (%s)", type(exc).__name__)
            return False

    async def move_to_folder(self, message_id: str, folder: str) -> bool:
        """Move email to folder (Gmail uses labels)"""
        return await self.apply_label(message_id, folder)

    async def archive(self, message_id: str) -> bool:
        """Archive email (remove from INBOX)"""
        if not self.service:
            await self.connect()

        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            return True
        except HttpError as exc:
            logger.warning("Gmail archive request failed (%s)", type(exc).__name__)
            return False

    async def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: Optional[str] = None,
        thread_id: Optional[str] = None,
        references: Optional[List[str]] = None
    ) -> str:
        """Create a Gmail draft"""
        if not body or not body.strip():
            raise ValueError("Refusing to create an empty email draft")
        if not self.service:
            if not await self.connect():
                return ""

        try:
            mime_message = MIMEEmailMessage()
            mime_message["To"] = to
            mime_message["Subject"] = subject
            if in_reply_to:
                mime_message["In-Reply-To"] = in_reply_to
                reference_chain = list(references or [])
                if in_reply_to not in reference_chain:
                    reference_chain.append(in_reply_to)
                mime_message["References"] = " ".join(reference_chain)
            mime_message.set_content(body)
            message = {
                "raw": base64.urlsafe_b64encode(mime_message.as_bytes()).decode().rstrip("=")
            }

            if thread_id:
                message['threadId'] = thread_id

            draft = self.service.users().drafts().create(
                userId='me',
                body={'message': message}
            ).execute()

            return draft['id']

        except HttpError as exc:
            logger.warning("Gmail draft creation failed (%s)", type(exc).__name__)
            return ""

    async def send_reply(self, draft_id: str) -> bool:
        """Send a Gmail draft"""
        if not self.service:
            await self.connect()

        try:
            self.service.users().drafts().send(
                userId='me',
                body={'id': draft_id}
            ).execute()
            return True
        except HttpError as exc:
            logger.warning("Gmail draft send failed (%s)", type(exc).__name__)
            return False

    async def delete_draft(self, draft_id: str) -> bool:
        """Delete a Gmail draft"""
        if not self.service:
            await self.connect()

        try:
            self.service.users().drafts().delete(
                userId='me',
                id=draft_id
            ).execute()
            return True
        except HttpError as exc:
            logger.warning("Gmail draft deletion failed (%s)", type(exc).__name__)
            return False

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

    def _parse_gmail_message(self, msg: Dict) -> Optional[EmailMessage]:
        """Parse Gmail API message into EmailMessage"""
        try:
            payload = msg['payload']
            headers = {h['name']: h['value'] for h in payload.get('headers', [])}

            # Extract basic info
            message_id = msg['id']
            thread_id = msg.get('threadId', message_id)

            sender = headers.get('From', '')
            sender_email = self._extract_email(sender)

            subject = headers.get('Subject', '')

            # Parse date
            date_str = headers.get('Date')
            received_at = datetime.fromtimestamp(int(msg['internalDate']) / 1000) if msg.get('internalDate') else datetime.utcnow()

            # Extract body
            body = self._extract_gmail_body(payload)

            # Extract recipients
            to = headers.get('To', '')
            recipients = self._extract_emails(to)
            cc = headers.get('Cc', '')
            cc_list = self._extract_emails(cc)

            # Extract in-reply-to and references
            in_reply_to = headers.get('In-Reply-To')
            references = headers.get('References', '').split()

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

        except Exception as exc:
            logger.warning("Gmail message parsing failed (%s)", type(exc).__name__)
            return None

    def _extract_gmail_body(self, payload: Dict) -> str:
        """Extract body from Gmail message payload"""
        body = ""

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        break
                elif part['mimeType'] == 'text/html' and not body:
                    data = part['body'].get('data', '')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
        else:
            data = payload['body'].get('data', '')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

        return body

    def _extract_email(self, text: str) -> str:
        """Extract email address from text"""
        match = re.search(r"<([^>]+)>", text)
        if match:
            return match.group(1)
        return text.strip()

    def _extract_emails(self, text: str) -> List[str]:
        """Extract all email addresses from text"""
        return re.findall(r"<([^>]+)>", text) or [text.strip()] if text else []


class GmailOAuthFlow:
    """Handle Gmail OAuth2 authentication flow"""

    @staticmethod
    def get_authorization_url(
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        state: Optional[str] = None,
    ) -> str:
        """Generate OAuth2 authorization URL with offline access to obtain refresh token"""
        c_id = client_id or settings.google_client_id
        c_secret = client_secret or settings.google_client_secret
        r_uri = redirect_uri or settings.google_redirect_uri
        auth_scopes = scopes or SCOPES

        if not c_id or not c_secret:
            raise ValueError("Google Client ID and Client Secret must be configured")

        flow = InstalledAppFlow.from_client_config(
            {
                "web": {
                    "client_id": c_id,
                    "client_secret": c_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [r_uri]
                }
            },
            auth_scopes
        )
        flow.redirect_uri = r_uri
        kwargs = {"prompt": "consent", "access_type": "offline"}
        if state:
            kwargs["state"] = state
        auth_url, _ = flow.authorization_url(**kwargs)
        return auth_url

    @staticmethod
    def exchange_code_for_token(
        code: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token and refresh token"""
        c_id = client_id or settings.google_client_id
        c_secret = client_secret or settings.google_client_secret
        r_uri = redirect_uri or settings.google_redirect_uri
        auth_scopes = scopes or SCOPES

        if not c_id or not c_secret:
            raise ValueError("Google Client ID and Client Secret must be configured")

        client_type = "web" if "web" in [r_uri] or r_uri.startswith("http") else "installed"
        flow = InstalledAppFlow.from_client_config(
            {
                "web": {
                    "client_id": c_id,
                    "client_secret": c_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [r_uri]
                }
            },
            auth_scopes
        )
        flow.redirect_uri = r_uri
        flow.fetch_token(code=code)

        credentials = flow.credentials
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None
        }
