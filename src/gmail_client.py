"""Gmail API client for fetching emails and attachments"""
import os
import base64
from datetime import datetime
from typing import List, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


class GmailClient:
    """Client for interacting with Gmail API"""

    def __init__(self, credentials_path: str, token_path: str):
        """Initialize Gmail client with OAuth credentials

        Args:
            credentials_path: Path to OAuth credentials JSON file
            token_path: Path to save/load token file
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2

        Returns:
            Gmail API service object
        """
        creds = None

        # Load existing token if available
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        return build('gmail', 'v1', credentials=creds)

    def get_emails_since(self, sender: str, subject: str, since_date: datetime) -> List[Dict]:
        """Search for emails matching criteria

        Args:
            sender: Email address to filter by
            subject: Subject line to filter by
            since_date: Only return emails after this date

        Returns:
            List of message dictionaries with 'id' and metadata
        """
        # Format date for Gmail query (YYYY/MM/DD)
        date_str = since_date.strftime('%Y/%m/%d')

        # Build query
        query = f'from:{sender} subject:"{subject}" after:{date_str}'

        messages = []
        page_token = None

        # Handle pagination
        while True:
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                pageToken=page_token
            ).execute()

            if 'messages' in results:
                messages.extend(results['messages'])

            page_token = results.get('nextPageToken')
            if not page_token:
                break

        return messages

    def list_attachments(self, message_id: str) -> List[Dict]:
        """Get list of attachments for a message

        Args:
            message_id: Gmail message ID

        Returns:
            List of attachment dictionaries with 'id' and 'filename'
        """
        message = self.service.users().messages().get(
            userId='me',
            id=message_id
        ).execute()

        attachments = []

        # Check message parts for attachments
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part.get('filename'):
                    attachments.append({
                        'id': part['body']['attachmentId'],
                        'filename': part['filename']
                    })

        return attachments

    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment content

        Args:
            message_id: Gmail message ID
            attachment_id: Attachment ID within the message

        Returns:
            Attachment content as bytes
        """
        attachment = self.service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=attachment_id
        ).execute()

        # Decode base64 data
        data = attachment['data']
        file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))

        return file_data
