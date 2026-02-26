import json
import os
from typing import Dict, List

import httpx

from app.logger import logger


class MistralClient:
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not set in environment")

        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.model = "mistral-large-latest"
        self.timeout = float(os.getenv("MISTRAL_HTTP_TIMEOUT", "60"))
        self.force_ipv4 = os.getenv("MISTRAL_FORCE_IPV4", "false").lower() == "true"

    def _client(self) -> httpx.Client:
        if self.force_ipv4:
            transport = httpx.HTTPTransport(local_address="0.0.0.0")
            return httpx.Client(transport=transport, timeout=self.timeout)
        return httpx.Client(timeout=self.timeout)

    def _build_email_digest(self, emails: List[Dict]) -> str:
        # Build a lightweight digest with only email headers (no body)
        digest_lines = []

        for idx, email in enumerate(emails, 1):
            from_addr = email.get("from", "Unknown")
            subject = email.get("subject", "No Subject")
            date = email.get("date", "Unknown Date")
            cc = email.get("cc", "")

            email_entry = f"[Email {idx}]\nFrom: {from_addr}\nSubject: {subject}\nDate: {date}"
            if cc:
                email_entry += f"\nCC: {cc}"
            email_entry += "\n---"
            digest_lines.append(email_entry)

        return "\n\n".join(digest_lines)

    def _build_email_digest_with_preview(self, emails: List[Dict], preview_len: int = 240) -> str:
        # Build a digest with headers + short body preview
        digest_lines = []
        for idx, email in enumerate(emails, 1):
            from_addr = email.get("from", "Unknown")
            subject = email.get("subject", "No Subject")
            date = email.get("date", "Unknown Date")
            cc = email.get("cc", "")
            body = (email.get("body", "") or "").strip()
            preview = body[:preview_len] + ("…" if len(body) > preview_len else "")

            email_entry = (
                f"[Email {idx}]\nFrom: {from_addr}\nSubject: {subject}\nDate: {date}"
            )
            if cc:
                email_entry += f"\nCC: {cc}"
            if preview:
                email_entry += f"\nPreview: {preview}"
            email_entry += "\n---"
            digest_lines.append(email_entry)

        return "\n\n".join(digest_lines)

    def summarize_emails(self, emails: List[Dict], window_label: str = "24h") -> str:
        # Generate a summary of emails using Mistral
        if not emails:
            return f"Aucun email reçu dans les dernières {window_label}."

        digest = self._build_email_digest(emails)
        prompt = (
            f"Résume ces {len(emails)} emails ({window_label}).\n\n"
            f"{digest}\n\n"
            "Format:\n"
            "1. Résumé (2-3 phrases)\n"
            "2. Urgents (liste ou \"Aucun\")\n"
            "3. Actions (liste ou \"Rien\")\n\n"
            "INTERDICTIONS:\n"
            "- ZERO markdown (* ** # _ ` [ ])\n"
            "- ZERO gras, italique, code\n"
            "Emojis OK. Ton respectueux, aucune insulte."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        with self._client() as client:
            response = client.post(
                self.api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    def summarize_email(self, email: Dict) -> str:
        # Generate a short summary of a single email
        if not email:
            return "Email introuvable."

        subject = email.get("subject", "Sans sujet")
        from_addr = email.get("from", "Unknown")
        date = email.get("date", "Unknown")
        body = (email.get("body", "") or "").strip()
        preview = body[:4000] + ("…" if len(body) > 4000 else "")

        prompt = (
            "Tu dois résumer UN email.\n\n"
            f"Objet: {subject}\n"
            f"De: {from_addr}\n"
            f"Date: {date}\n"
            f"Contenu:\n{preview}\n\n"
            "Réponds exactement au format suivant:\n"
            "Objet : <objet>\n\n"
            "Résumé :\n"
            "- <point 1>\n"
            "- <point 2>\n"
            "- <point 3>\n\n"
            "Besoin d'un détail précis ?\n\n"
            "Règles:\n"
            "- Réponse en français\n"
            "- 3 à 7 points max\n"
            "- Pas de markdown sauf les tirets\n"
            "- Pas de HTML\n"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        with self._client() as client:
            response = client.post(
                self.api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    def classify_important_emails(self, emails: List[Dict], window_label: str = "12h") -> Dict:
        # Identify important emails and provide short explanations
        if not emails:
            return {"important": []}

        digest = self._build_email_digest_with_preview(emails)
        prompt = (
            f"Tu reçois {len(emails)} emails ({window_label}).\n"
            "Ta tâche: identifier les emails importants et pertinents à traiter rapidement.\n"
            "Important = action requise, finance, clients, sécurité, rendez-vous, délais.\n"
            "Ignore newsletters, promotions, automatisés sans action.\n\n"
            f"{digest}\n\n"
            "Réponds en JSON strict, uniquement le JSON, sans texte.\n"
            "Format:\n"
            "{\"important\":[{\"index\":1,\"explanation\":\"phrase courte\"}]}\n"
            "Règles:\n"
            "- index commence à 1 (Email 1 = index 1)\n"
            "- explanation: 8-15 mots max, français, factuel\n"
            "- si aucun important: {\"important\":[]}\n"
            "- ton respectueux, aucune insulte\n"
            "- pas de markdown"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        with self._client() as client:
            response = client.post(
                self.api_url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        try:
            return json.loads(content)
        except Exception:
            # Try to extract JSON block if the model added extra text
            try:
                start = content.index("{")
                end = content.rindex("}") + 1
                return json.loads(content[start:end])
            except Exception:
                return {"important": []}

    def chat_with_tools(
        self,
        user_message: str = None,
        messages: List[Dict] = None,
        tools: List[Dict] = None,
        tool_executor: callable = None,
        max_iterations: int = 5,
    ) -> str:
        # Chat with Mistral with tool calling support
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if messages is None:
            messages = [{"role": "user", "content": user_message}]
        else:
            messages = messages.copy()

        iterations = 0

        while iterations < max_iterations:
            iterations += 1

            payload = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
            }

            with self._client() as client:
                response = client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

            message = data["choices"][0]["message"]
            messages.append(message)

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                final_content = message.get("content", "")
                logger.info(f"AI response complete | preview={final_content[:80]}...")
                return final_content

            if message.get("content"):
                logger.debug(f"AI intermediate content | preview={message.get('content')[:80]}...")

            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])
                tool_id = tool_call["id"]

                logger.info(f"Tool called | tool={tool_name} | args={tool_args}")

                try:
                    tool_result = tool_executor(tool_name, tool_args)
                    if isinstance(tool_result, (list, dict)):
                        tool_result_str = json.dumps(tool_result, ensure_ascii=False)
                    else:
                        tool_result_str = str(tool_result)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": tool_result_str,
                        }
                    )
                except Exception as e:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": tool_name,
                            "content": f"Error: {str(e)}",
                        }
                    )

        return "Désolé, je n'ai pas pu répondre à votre question dans le temps imparti."


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    client = MistralClient()

    test_emails = [
        {
            "from": "john@example.com",
            "subject": "Urgent: Server Down",
            "date": "2026-02-23 10:00:00",
            "body": "The production server is down. Need immediate attention.",
        },
        {
            "from": "newsletter@marketing.com",
            "subject": "50% off sale today only!",
            "date": "2026-02-23 09:00:00",
            "body": "Amazing deals on products you don't need. Buy now!",
        },
    ]

    logger.info("Testing Mistral summarization...")
    summary = client.summarize_emails(test_emails)
    logger.info(summary)
