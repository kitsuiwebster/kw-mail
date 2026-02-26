import email
import imaplib
import os
import ssl
import html as html_lib
import re
from html.parser import HTMLParser
from datetime import datetime, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime
from email import policy
from typing import Dict, List

from app.logger import logger


class IMAPClient:
    FOLDERS = [
        "INBOX",
        "Folders/Not Flood",
        "Folders/VCG-In",
        "Folders/Kitsui",
        "Folders/Distro",
        "Folders/VCG-Biz",
        "Folders/Madpoof",
        "Folders/VCG-Prod",
    ]

    def __init__(self):
        self.host = os.getenv("IMAP_HOST", "127.0.0.1")
        self.port = int(os.getenv("IMAP_PORT", "1143"))
        self.security = os.getenv("IMAP_SECURITY", "STARTTLS").upper()
        self.tls_verify = os.getenv("IMAP_TLS_VERIFY", "true").lower() == "true"
        self.user = os.getenv("IMAP_USER")
        self.password = os.getenv("IMAP_PASSWORD")
        self.connection = None

    def connect(self):
        # Connect to IMAP server (Proton Bridge)
        try:
            if self.security == "SSL":
                self.connection = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                self.connection = imaplib.IMAP4(self.host, self.port)
                if self.security == "STARTTLS":
                    # Upgrade connection to TLS when supported (e.g., Proton Bridge)
                    if self.tls_verify:
                        context = ssl.create_default_context()
                    else:
                        # Proton Bridge uses a self-signed cert by default
                        context = ssl._create_unverified_context()
                    self.connection.starttls(ssl_context=context)
            self.connection.login(self.user, self.password)
            logger.info(f"IMAP connected | host={self.host}:{self.port} | user={self.user}")
            return True
        except Exception as e:
            logger.error(f"IMAP connection failed | host={self.host}:{self.port} | error={e}")
            raise

    def disconnect(self):
        # Close IMAP connection
        if self.connection:
            try:
                self.connection.logout()
                logger.info("IMAP disconnected")
            except Exception:
                pass

    def _decode_header(self, header_value):
        # Decode an email header value
        if header_value is None:
            return ""

        decoded_parts = decode_header(header_value)
        result = []

        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="ignore"))
            else:
                result.append(str(part))

        return "".join(result)

    def _extract_body(self, msg):
        # Extract text body from email message
        body = ""
        html_body = ""

        def decode_payload(payload: bytes | None, charset: str | None) -> str:
            if not payload:
                return ""
            encodings = []
            if charset:
                encodings.append(charset)
            encodings.extend(["utf-8", "iso-8859-1", "cp1252"])
            for enc in encodings:
                try:
                    return payload.decode(enc, errors="replace")
                except Exception:
                    continue
            try:
                return payload.decode("utf-8", errors="replace")
            except Exception:
                return ""

        # Prefer structured selection if available (handles multipart/alternative correctly)
        try:
            body_part = msg.get_body(preferencelist=("html", "plain"))
        except Exception:
            body_part = None

        if body_part is not None:
            try:
                content = body_part.get_content() or ""
                if body_part.get_content_type() == "text/html":
                    return self._html_to_text(content).strip()
                return content.strip()
            except Exception:
                pass

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        try:
                            if not body:
                                body = part.get_content() or ""
                        except Exception:
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset()
                                if not body:
                                    body = decode_payload(payload, charset)
                    except Exception:
                        continue

                elif content_type == "text/html" and not html_body:
                    try:
                        try:
                            html_body = part.get_content() or ""
                        except Exception:
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset()
                                html_body = decode_payload(payload, charset)
                    except Exception:
                        continue
        else:
            content_type = msg.get_content_type()
            try:
                try:
                    decoded = msg.get_content() or ""
                except Exception:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        charset = msg.get_content_charset()
                        decoded = decode_payload(payload, charset)
                    else:
                        decoded = ""
                if decoded:
                    if content_type == "text/html":
                        html_body = decoded
                    else:
                        body = decoded
            except Exception:
                body = str(msg.get_payload())

        if html_body:
            # Prefer HTML conversion when available (plain text is often degraded)
            body = self._html_to_text(html_body)

        return body.strip()

    def _html_to_text(self, html: str) -> str:
        # HTML to text conversion with structure preservation
        if not html:
            return ""

        # Prefer html2text if available (better handling for email HTML)
        try:
            import html2text  # type: ignore

            h = html2text.HTML2Text()
            h.ignore_images = True
            h.ignore_emphasis = True
            h.ignore_links = False
            h.body_width = 0
            text = h.handle(html) or ""
            text = text.replace("\r", "")
        except Exception:
            text = ""

        if not text.strip():
            text = self._html_to_text_fallback(html)

        text = html_lib.unescape(text)
        text = self._clean_text(text)
        # Remove soft hyphens / zero-width spaces that fragment words
        text = (
            text.replace("\u00ad", "")
            .replace("\u200b", "")
            .replace("\u2060", "")
            .replace("\u00a0", " ")
        )
        text = re.sub(r"[\t\r]+", " ", text)
        text = re.sub(r"\n[ \t]+\n", "\n\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ ]{2,}", " ", text)
        return text.strip()

    def _html_to_text_fallback(self, html: str) -> str:
        class _EmailHTMLParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.parts: list[str] = []
                self._skip = False
                self._block_tags = {
                    "p",
                    "div",
                    "section",
                    "article",
                    "header",
                    "footer",
                    "table",
                    "tr",
                    "td",
                    "th",
                    "ul",
                    "ol",
                    "li",
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5",
                    "h6",
                }

            def handle_starttag(self, tag, attrs):
                tag = tag.lower()
                if tag in {"script", "style", "noscript"}:
                    self._skip = True
                    return
                if tag == "br":
                    self.parts.append("\n")
                elif tag == "li":
                    self.parts.append("\n- ")
                elif tag in self._block_tags:
                    self.parts.append("\n")

            def handle_endtag(self, tag):
                tag = tag.lower()
                if tag in {"script", "style", "noscript"}:
                    self._skip = False
                    return
                if tag in {"p", "div", "section", "article", "header", "footer", "tr"}:
                    self.parts.append("\n")

            def handle_data(self, data):
                if self._skip:
                    return
                if data:
                    self.parts.append(data)

        parser = _EmailHTMLParser()
        parser.feed(html)
        text = "".join(parser.parts)
        return text.strip()

    def _clean_text(self, text: str) -> str:
        # Remove markdown links, table noise, and excess separators
        if not text:
            return ""

        # Convert markdown links to plain text
        text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"\1", text)

        lines = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                lines.append("")
                continue
            # Drop separator-only lines and table artifacts
            if re.fullmatch(r"[-| ]{3,}", stripped):
                continue
            # Drop lines with almost no alphanumerics (tracking junk)
            alnum = sum(ch.isalnum() for ch in stripped)
            if alnum == 0:
                continue
            if alnum / max(len(stripped), 1) < 0.2:
                continue
            lines.append(stripped)

        # Collapse multiple blank lines
        cleaned = []
        blank = False
        for line in lines:
            if line == "":
                if not blank:
                    cleaned.append("")
                blank = True
            else:
                cleaned.append(line)
                blank = False

        return "\n".join(cleaned).strip()

    def _looks_corrupted(self, text: str) -> bool:
        # Heuristic: too many very short tokens often means broken decoding
        if not text:
            return True
        tokens = re.findall(r"\b[\wÀ-ÖØ-öø-ÿ]+\b", text)
        if not tokens:
            return True
        short_tokens = sum(1 for t in tokens if len(t) <= 2)
        ratio = short_tokens / max(len(tokens), 1)
        return ratio > 0.45

    def get_emails_last_24h(self, days: int = 1) -> List[Dict]:
        # Fetch emails from the last N days across multiple folders
        if not self.connection:
            self.connect()

        folders = self.FOLDERS

        all_emails = []
        email_ids_seen = set()

        try:
            since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

            for folder in folders:
                try:
                    folder_name = f'"{folder}"' if " " in folder or "-" in folder else folder
                    status, _ = self.connection.select(folder_name)

                    if status != "OK":
                        logger.warning(f"Folder skipped | folder='{folder}' | reason=inaccessible")
                        continue

                    status, messages = self.connection.search(None, f"SINCE {since_date}")
                    if status != "OK" or not messages[0]:
                        continue

                    email_ids = messages[0].split()
                    logger.info(f"Emails fetched | folder='{folder}' | count={len(email_ids)}")

                    for email_id in email_ids:
                        if email_id in email_ids_seen:
                            continue
                        email_ids_seen.add(email_id)

                        status, msg_data = self.connection.fetch(email_id, "(RFC822)")
                        if status != "OK":
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email, policy=policy.default)

                        email_from = self._decode_header(msg.get("From", ""))
                        subject = self._decode_header(msg.get("Subject", ""))
                        date = msg.get("Date", "")
                        cc = self._decode_header(msg.get("Cc", ""))
                        body = self._extract_body(msg)

                        all_emails.append(
                            {
                                "id": email_id.decode(),
                                "from": email_from,
                                "subject": subject,
                                "date": date,
                                "cc": cc,
                                "body": body,
                                "folder": folder,
                            }
                        )

                except Exception as e:
                    logger.error(f"Folder processing failed | folder='{folder}' | error={e}")
                    continue

            # Sort by date (oldest first)
            def get_email_datetime(email_dict):
                try:
                    date_str = email_dict.get('date', '')
                    dt = parsedate_to_datetime(date_str)
                    # Remove timezone info to avoid comparison issues
                    if dt.tzinfo is not None:
                        dt = dt.replace(tzinfo=None)
                    return dt
                except Exception:
                    # If parsing fails, put at the end
                    return datetime.max

            all_emails.sort(key=get_email_datetime)

            logger.info(f"Email fetch complete | total={len(all_emails)} | folders={len(folders)} | days={days}")
            return all_emails

        except Exception as e:
            logger.error(f"Email fetch failed | error={e}")
            raise

    def get_email_raw_by_id(self, email_id: str, folder: str | None = None) -> bytes | None:
        # Fetch raw RFC822 bytes for a specific email ID (optionally within a folder)
        if not self.connection:
            self.connect()

        folders = [folder] if folder else self.FOLDERS

        for target in folders:
            if not target:
                continue
            try:
                folder_name = f'"{target}"' if " " in target or "-" in target else target
                status, _ = self.connection.select(folder_name)
                if status != "OK":
                    continue
                status, msg_data = self.connection.fetch(email_id, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw_email = msg_data[0][1]
                if raw_email:
                    return raw_email
            except Exception:
                continue

        return None


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    client = IMAPClient()
    client.connect()
    emails = client.get_emails_last_24h()

    logger.info(f"\n{'='*80}")
    logger.info(f"EMAILS FROM LAST 24H: {len(emails)}")
    logger.info(f"{'='*80}\n")

    for idx, email_data in enumerate(emails, 1):
        logger.info(f"[{idx}] From: {email_data['from']}")
        logger.info(f"    Subject: {email_data['subject']}")
        logger.info(f"    Date: {email_data['date']}")
        logger.info(f"    Body Preview: {email_data['body'][:200]}...")
        logger.info(f"{'-'*80}\n")

    client.disconnect()
