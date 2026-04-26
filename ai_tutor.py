import os
import re
from mistralai.client import Mistral


def strip_markdown(text: str) -> str:
    """Remove markdown formatting symbols so TTS reads cleanly."""
    # Remove bold/italic markers: **, *, __, _
    text = re.sub(r'\*{1,2}|_{1,2}', '', text)
    # Remove heading markers: ##, ###, etc.
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Remove numbered list prefixes like "1.", "2." etc.
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove leading bullet symbols: -, *, •
    text = re.sub(r'^\s*[-*•]\s+', '', text, flags=re.MULTILINE)
    # Collapse multiple spaces
    text = re.sub(r'  +', ' ', text)
    return text.strip()


def generate_explanation(a, b):
    """Returns a dict with 'telugu' steps (for display) and 'english' steps (for TTS)."""
    api_key = os.getenv("MISTRAL_API_KEY")

    # Fallback if no API key
    if not api_key:
        return {
            "telugu": [
                f"మనము {a} కి {b} కలుపుదాం 😊",
                "మణులను జోడించు",
                f"జవాబు {a+b} 🎉"
            ],
            "english": [
                f"Let's add {a} and {b} on the abacus! 😊",
                "Move the beads to add.",
                f"The answer is {a+b} 🎉"
            ]
        }

    client = Mistral(api_key=api_key)

    prompt = f"""Explain {a}+{b} using abacus steps for young kids.
Provide TWO versions:

TELUGU:
(Write the explanation in plain Telugu sentences, no markdown, no **, no #)

ENGLISH:
(Write the same explanation in plain English sentences, no markdown, no **, no #)

Rules for both:
- Use simple words and emojis only
- Maximum 4 short sentences per section
- Each sentence on its own line
- Do NOT use any asterisks or special formatting symbols
"""

    try:
        res = client.chat.complete(
            model="mistral-small-latest",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = res.choices[0].message.content

        # Split into TELUGU and ENGLISH sections
        telugu_steps = []
        english_steps = []
        current_section = None

        for line in raw.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            upper = stripped.upper()
            if upper.startswith("TELUGU") or upper == "TELUGU:":
                current_section = "telugu"
                continue
            if upper.startswith("ENGLISH") or upper == "ENGLISH:":
                current_section = "english"
                continue
            cleaned = strip_markdown(stripped)
            if len(cleaned) > 2:
                if current_section == "telugu":
                    telugu_steps.append(cleaned)
                elif current_section == "english":
                    english_steps.append(cleaned)

        # Fallback if parsing fails
        if not telugu_steps:
            telugu_steps = [f"మనము {a} కి {b} కలుపుదాం 😊", "మణులను జోడించు", f"జవాబు {a+b} 🎉"]
        if not english_steps:
            english_steps = [f"Let's add {a} and {b}! 😊", "Move the beads.", f"The answer is {a+b} 🎉"]

        return {"telugu": telugu_steps, "english": english_steps}

    except Exception as e:
        print(f"Error calling Mistral AI: {e}")
        return {
            "telugu": [
                f"మనము {a} కి {b} కలుపుదాం 😊",
                "మణులను జోడించు",
                f"జవాబు {a+b} 🎉"
            ],
            "english": [
                f"Let's add {a} and {b} on the abacus! 😊",
                "Move the beads to add.",
                f"The answer is {a+b} 🎉"
            ]
        }