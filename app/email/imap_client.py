import email
import imaplib
import os
from datetime import datetime, timedelta
from email.header import decode_header
from typing import Dict, List


class IMAPClient:
    def __init__(self):
        self.host = os.getenv("IMAP_HOST", "127.0.0.1")
        self.port = int(os.getenv("IMAP_PORT", "1143"))
        self.user = os.getenv("IMAP_USER")
        self.password = os.getenv("IMAP_PASSWORD")
        self.connection = None

    def connect(self):
        # Connect to IMAP server (Proton Bridge)
        try:
            self.connection = imaplib.IMAP4(self.host, self.port)
            self.connection.login(self.user, self.password)
            print(f"✓ Connected to IMAP server at {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"✗ IMAP connection failed: {e}")
            raise

    def disconnect(self):
        # Close IMAP connection
        if self.connection:
            try:
                self.connection.logout()
                print("✓ Disconnected from IMAP server")
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

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if "attachment" in content_disposition:
                    continue

                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")
                            break
                    except Exception:
                        continue

                elif content_type == "text/html" and not html_body:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            html_body = payload.decode("utf-8", errors="ignore")
                    except Exception:
                        continue
        else:
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    decoded = payload.decode("utf-8", errors="ignore")
                    if content_type == "text/html":
                        html_body = decoded
                    else:
                        body = decoded
            except Exception:
                body = str(msg.get_payload())

        if not body and html_body:
            body = html_body

        return body.strip()

    def get_emails_last_24h(self, days: int = 1) -> List[Dict]:
        # Fetch emails from the last N days across multiple folders
        if not self.connection:
            self.connect()

        folders = [
            "INBOX",
            "Folders/Not Flood",
            "Folders/VCG-In",
            "Folders/Kitsui",
            "Folders/Distro",
            "Folders/VCG-Biz",
            "Folders/Madpoof",
            "Folders/VCG-Prod",
        ]

        all_emails = []
        email_ids_seen = set()

        try:
            since_date = (datetime.now() - timedelta(days=days)).strftime("%d-%b-%Y")

            for folder in folders:
                try:
                    folder_name = f'"{folder}"' if " " in folder or "-" in folder else folder
                    status, _ = self.connection.select(folder_name)

                    if status != "OK":
                        print(f"⚠️  Skipping folder '{folder}' (not found or inaccessible)")
                        continue

                    status, messages = self.connection.search(None, f"SINCE {since_date}")
                    if status != "OK" or not messages[0]:
                        continue

                    email_ids = messages[0].split()
                    print(f"✓ Found {len(email_ids)} emails in '{folder}'")

                    for email_id in email_ids:
                        if email_id in email_ids_seen:
                            continue
                        email_ids_seen.add(email_id)

                        status, msg_data = self.connection.fetch(email_id, "(RFC822)")
                        if status != "OK":
                            continue

                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)

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
                    print(f"✗ Error processing folder '{folder}': {e}")
                    continue

            print(f"✓ Total: {len(all_emails)} emails from {len(folders)} folders (last {days} day(s))")
            return all_emails

        except Exception as e:
            print(f"✗ Error fetching emails: {e}")
            raise


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    client = IMAPClient()
    client.connect()
    emails = client.get_emails_last_24h()

    print(f"\n{'='*80}")
    print(f"EMAILS FROM LAST 24H: {len(emails)}")
    print(f"{'='*80}\n")

    for idx, email_data in enumerate(emails, 1):
        print(f"[{idx}] From: {email_data['from']}")
        print(f"    Subject: {email_data['subject']}")
        print(f"    Date: {email_data['date']}")
        print(f"    Body Preview: {email_data['body'][:200]}...")
        print(f"{'-'*80}\n")

    client.disconnect()
