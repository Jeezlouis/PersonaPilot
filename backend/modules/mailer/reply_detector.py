import logging
from datetime import datetime, timezone
from sqlalchemy import select
from backend.models import EmailOutreach, Job
from backend.modules.mailer.gmail_auth import get_gmail_service
from backend.modules.notifier.telegram import _send_message

logger = logging.getLogger(__name__)

async def poll_for_replies(db):
    """
    Checks the Gmail inbox for replies to our outreach threads.
    If a reply is found from the recipient, notify via Telegram.
    """
    service = get_gmail_service()
    if not service:
        logger.warning("Gmail service not available for reply polling.")
        return

    # 1. Fetch all 'sent' outreach records that haven't been 'replied' yet
    result = await db.execute(
        select(EmailOutreach, Job)
        .join(Job, EmailOutreach.job_id == Job.id)
        .where(EmailOutreach.status == "sent")
    )
    sent_items = result.fetchall()

    if not sent_items:
        return

    for outreach, job in sent_items:
        try:
            # Check for messages in the same thread
            # We look for messages FROM the recipient back to us
            query = f"from:{outreach.recipient_email}"
            threads = service.users().threads().list(userId='me', q=query).execute()

            if 'threads' in threads:
                for thread in threads['threads']:
                    # Get full thread detail
                    t_detail = service.users().threads().get(userId='me', id=thread['id']).execute()
                    # Check if there are messages newer than our sent_at
                    # For simplicity, if a message from recipient exists, we flag it.
                    # A more robust check would verify ThreadId matches outreach.gmail_message_id's thread
                    
                    # If we found a thread from them, notify!
                    outreach.status = "replied"
                    outreach.replied_at = datetime.now(timezone.utc)
                    
                    await _send_message(
                        f"🔥 <b>URGENT: Recruiter Replied!</b>\n"
                        f"{'━' * 24}\n"
                        f"👤 <b>{job.company}</b> ({outreach.recipient_email})\n"
                        f"🎯 Job: {job.title}\n\n"
                        f"Check your Gmail thread immediately to follow up!"
                    )
                    await db.commit()
                    logger.info(f"Reply detected for {job.company}")
                    break

        except Exception as e:
            logger.error(f"Error polling replies for {outreach.recipient_email}: {e}")
