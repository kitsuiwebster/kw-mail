import os
import httpx
import json
from typing import List, Dict, Optional, Any


class MistralClient:
    def __init__(self):
        self.api_key = os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY not set in environment")

        self.api_url = "https://api.mistral.ai/v1/chat/completions"
        self.model = "mistral-large-latest"

    def _build_email_digest(self, emails: List[Dict]) -> str:
        """
        Build a lightweight digest with only email headers (no body).
        Headers only: From, Subject, Date, CC (if available).
        """
        digest_lines = []

        for idx, email in enumerate(emails, 1):
            # Extract headers only
            from_addr = email.get('from', 'Unknown')
            subject = email.get('subject', 'No Subject')
            date = email.get('date', 'Unknown Date')
            cc = email.get('cc', '')

            # Build email entry (headers only)
            email_entry = f"[Email {idx}]\nFrom: {from_addr}\nSubject: {subject}\nDate: {date}"

            if cc:
                email_entry += f"\nCC: {cc}"

            email_entry += "\n---"

            digest_lines.append(email_entry)

        return "\n\n".join(digest_lines)

    def summarize_emails(self, emails: List[Dict]) -> str:
        """
        Generate a summary of emails using Mistral.

        Returns a structured summary identifying:
        - Overall summary
        - Urgent items
        - Potential actions
        """
        if not emails:
            return "Aucun email reçu dans les dernières 24h."

        # Build digest
        digest = self._build_email_digest(emails)

        # Build prompt
        prompt = f"""Résume ces {len(emails)} emails (24h).

{digest}

Format:
1. Résumé (2-3 phrases)
2. Urgents (liste ou "Aucun")
3. Actions (liste ou "Rien")

INTERDICTIONS:
- ZERO markdown (* ** # _ ` [ ])
- ZERO gras, italique, code
Emojis OK. Spam vs important."""

        # Call Mistral API
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        with httpx.Client() as client:
            response = client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30.0
            )

            response.raise_for_status()
            data = response.json()

        summary = data["choices"][0]["message"]["content"]
        return summary

    def chat_with_tools(
        self,
        user_message: str = None,
        messages: List[Dict] = None,
        tools: List[Dict] = None,
        tool_executor: callable = None,
        max_iterations: int = 5
    ) -> str:
        """
        Chat with Mistral with tool calling support.

        Args:
            user_message: User's question or query (used if messages not provided)
            messages: Full conversation history (alternative to user_message)
            tools: List of tool definitions (OpenAI format)
            tool_executor: Function to execute tools (signature: tool_name, arguments -> result)
            max_iterations: Maximum number of tool call iterations (default: 5)

        Returns:
            Final response from Mistral
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Initialize conversation
        if messages is None:
            messages = [
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        else:
            # Use provided message history
            messages = messages.copy()

        iterations = 0

        while iterations < max_iterations:
            iterations += 1

            # Call Mistral with tools
            payload = {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto"
            }

            with httpx.Client() as client:
                response = client.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

            message = data["choices"][0]["message"]

            # Add assistant message to conversation
            messages.append(message)

            # Check if tool calls are requested
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                # No more tool calls, return final response
                final_content = message.get("content", "")
                print(f"  ✓ Final response: {final_content[:100]}...")
                return final_content

            # Log intermediate content if present (should be ignored)
            if message.get("content"):
                print(f"  ⚠️ Intermediate content (ignored): {message.get('content')[:100]}...")

            # Execute each tool call
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                tool_args = json.loads(tool_call["function"]["arguments"])
                tool_id = tool_call["id"]

                print(f"  → Executing tool: {tool_name}({tool_args})")

                try:
                    # Execute tool
                    tool_result = tool_executor(tool_name, tool_args)

                    # Convert result to string
                    if isinstance(tool_result, (list, dict)):
                        tool_result_str = json.dumps(tool_result, ensure_ascii=False)
                    else:
                        tool_result_str = str(tool_result)

                    # Add tool result to conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": tool_name,
                        "content": tool_result_str
                    })

                except Exception as e:
                    # Tool execution failed
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": tool_name,
                        "content": f"Error: {str(e)}"
                    })

        # Max iterations reached
        return "Désolé, je n'ai pas pu répondre à votre question dans le temps imparti."


if __name__ == "__main__":
    # Quick test
    from dotenv import load_dotenv
    load_dotenv()

    client = MistralClient()

    # Test with dummy emails
    test_emails = [
        {
            "from": "john@example.com",
            "subject": "Urgent: Server Down",
            "date": "2026-02-23 10:00:00",
            "body": "The production server is down. Need immediate attention."
        },
        {
            "from": "newsletter@marketing.com",
            "subject": "50% off sale today only!",
            "date": "2026-02-23 09:00:00",
            "body": "Amazing deals on products you don't need. Buy now!"
        }
    ]

    print("Testing Mistral summarization...")
    summary = client.summarize_emails(test_emails)
    print(summary)
