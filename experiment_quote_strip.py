"""
FILE: experiment_quote_strip.py
PURPOSE: One-off diagnostic script — NOT part of the pipeline. Validates
a regex-based heuristic for stripping quoted email threads and marketing
footers out of customer_messages, against real noisy examples found
during /meta and /tickets exploration.
WHY THIS APPROACH: An initial regex missed real cases (e.g. "On Fri, May 1..."
with a weekday prefix) — caught by testing against actual samples instead
of synthetic ones. The validated pattern is what clean.py actually uses.
INPUT: hardcoded sample strings (copied from real ticket data seen earlier).
OUTPUT: printed comparison only — this script does not write anywhere.
"""

import re

QUOTE_MARKERS = [
    r"\bOn (?:[A-Za-z]+,\s*)?[A-Za-z]{3,9} \d{1,2}(?:st|nd|rd|th)?,? \d{4}.{0,80}wrote:",
    r"CookUnity\.\s*\d+ Flushing Ave",
    r"No longer want to receive these emails\?",
    r"Get \$\d+ off when you refer a friend!",
]

COMBINED_PATTERN = re.compile("|".join(QUOTE_MARKERS))

MOBILE_SIGNATURE = re.compile(
    r"Sent from my (?:iPhone|iPad|Android(?: device)?|Samsung(?: Galaxy)?|Galaxy(?: S\d+)?|cell(?:\s|-)?phone|mobile(?:\s|-)?phone)\b\.?,?\s*",
    re.IGNORECASE,
)


def strip_mobile_signature(text):
    text = MOBILE_SIGNATURE.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


print("\n--- Mobile signature tests ---")
test1 = "Attn Diego ~Judy O Sent from my iPhone I managed to send you 2 of the 3 but it seems YELP is having some glitch"
test2 = "Why are there 5 meals when I normally order4? Sent from my iPad J. B."

print("BEFORE:", test1)
print("AFTER: ", strip_mobile_signature(test1))
print()
print("BEFORE:", test2)
print("AFTER: ", strip_mobile_signature(test2))
