import base64
import mimetypes
import os
import logging
from email.message import EmailMessage
from backend.modules.mailer.gmail_auth import get_gmail_service

logger = logging.getLogger(__name__)

def create_message_with_attachment(sender: str, to: str, subject: str, message_text: str, attachment_path: str):
    message = EmailMessage()
    message['To'] = to
    message['From'] = sender
    message['Subject'] = subject
    message.set_content(message_text)

    if attachment_path and os.path.exists(attachment_path):
        content_type, encoding = mimetypes.guess_type(attachment_path)

        if content_type is None or encoding is not None:
            content_type = 'application/octet-stream'

        main_type, sub_type = content_type.split('/', 1)

        with open(attachment_path, 'rb') as fp:
            attachment_data = fp.read()

        filename = os.path.basename(attachment_path)
        # Verify size limit (1MB total size limit requested)
        if len(attachment_data) + len(message_text) > 1 * 1024 * 1024:
            raise ValueError("Email payload too large (exceeds 1MB)")
            
        message.add_attachment(attachment_data, maintype=main_type, subtype=sub_type, filename=filename)

    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {'raw': encoded_message}

def send_cold_email(to_email: str, subject: str, body: str, resume_path: str) -> str:
    """
    Sends the cold email via Gmail API and returns the Message ID.
    Raises exception on failure.
    """
    service = get_gmail_service()
    if not service:
        raise ValueError("Gmail service not authenticated.")

    # You could fetch actual user profile info here to use their email
    sender_email = "me" # special keyword in Gmail API

    if not resume_path.lower().endswith(".pdf"):
        raise ValueError("Strict Policy: Only PDF resumes are allowed for cold email outreach.")

    body_with_signature = f"{body}\n\n--\nIsreal\nGitHub | LinkedIn | Portfolio"

    raw_msg = create_message_with_attachment(
        sender=sender_email,
        to=to_email,
        subject=subject,
        message_text=body_with_signature,
        attachment_path=resume_path
    )

    try:
        sent_message = service.users().messages().send(userId="me", body=raw_msg).execute()
        return sent_message['id']
    except Exception as e:
        logger.error(f"[Gmail Sender] Failed to send email to {to_email}: {e}")
        raise
