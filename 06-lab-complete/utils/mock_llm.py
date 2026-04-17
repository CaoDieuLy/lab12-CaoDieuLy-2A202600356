"""Mock LLM for local/offline testing."""
from __future__ import annotations

import random
import time

RESPONSES = {
    "default": [
        "This is a mock AI response used for deployment practice.",
        "Agent is running correctly with a simulated model response.",
        "Mock response returned. Replace with OpenAI in real production.",
    ],
    "docker": ["Docker packages app and dependencies into a portable container."],
    "deploy": ["Deployment moves your app from local machine to cloud service."],
    "health": ["System status is healthy."],
}


def ask(question: str, delay: float = 0.08) -> str:
    time.sleep(delay + random.uniform(0.0, 0.04))
    lowered = question.lower()
    for keyword, choices in RESPONSES.items():
        if keyword in lowered:
            return random.choice(choices)
    return random.choice(RESPONSES["default"])
