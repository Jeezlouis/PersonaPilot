import re
import urllib.parse
from typing import Tuple

def extract_email_info(job_description: str, job_url: str, company_name: str = "") -> Tuple[str, str]:
    """
    Identifies the target email from the job.
    Returns: (email_address, confidence)
    confidence: "direct", "inferred", or "none"
    """
    # 1. Broad regex for standard email structures found in JD
    # (Matches email-like patterns but skips some noise)
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    matches = re.findall(email_pattern, job_description or "")
    
    # Filter out common false positives (e.g., example@domain.com)
    valid_matches = [m for m in matches if not any(x in (m or "").lower() for x in ['example.', 'test.', 'yourname@', 'email.com', 'domain.com'])]
    
    if valid_matches:
        return valid_matches[0], "direct"

    # 2. Domain-based Inference (fallback)
    # Extracts domain from the URL to formulate a generic careers/hiring email.
    domain = None
    try:
        parsed = urllib.parse.urlparse(job_url)
        hostname = parsed.hostname
        if hostname:
            # Drop www.
            domain = hostname.replace("www.", "")
    except Exception:
        pass
        
    if domain and domain not in ["greenhouse.io", "lever.co", "workable.com", "myworkdayjobs.com", "linkedin.com", "indeed.com", "remoteok.com"]:
        return f"careers@{domain}", "inferred"
        
    if company_name:
        sanitized_company = re.sub(r'[^a-zA-Z0-9]', '', company_name.lower())
        if sanitized_company:
            return f"hiring@{sanitized_company}.com", "inferred"

    return "", "none"
