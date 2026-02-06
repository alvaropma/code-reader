# code_explainer.py

"""
Utilities to send code to an LLM and get a human-friendly explanation.

This implementation uses OpenAI's Chat Completions API via the `openai` library.
You can adapt it to another provider if you prefer.
"""

import os
from typing import Optional

from openai import OpenAI


class LLMConfigError(Exception):
    """Raised when LLM configuration is missing or invalid."""
    pass


class CodeExplainer:
    """
    Small wrapper around an LLM client to explain code from a single file.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini") -> None:
        """
        :param api_key: OpenAI API key. If None, reads from OPENAI_API_KEY env var.
        :param model: Model name to use.
        """
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMConfigError(
                "OPENAI_API_KEY not found. Set it in your .env file as OPENAI_API_KEY=..."
            )

        self.model = model
        # Initialize OpenAI client
        self.client = OpenAI(api_key=key)

    def explain_code(self, code: str, file_path: str) -> str:
        """
        Send the given code to the LLM and return a plain-text explanation.
        """
        if not code.strip():
            return "The file appears to be empty; there is no code to explain."

        prompt = (
            "You are a helpful senior Python developer. "
            "Explain the following Python file clearly and concisely for an intermediate developer.\n\n"
            f"File path: {file_path}\n\n"
            "Focus on:\n"
            "- What the main purpose of the file is\n"
            "- What the key functions/classes do\n"
            "- Any interesting implementation details\n"
            "- How it might be used in the overall project\n\n"
            "Here is the file content:\n\n"
            f"{code}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.2,
        )

        # Extract the assistant's message text
        return response.choices[0].message.content.strip()
