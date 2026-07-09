"""
FILE: experiment_quote_strip.py
PURPOSE: One-off diagnostic script — NOT part of the pipeline. Validates
regex-based heuristics for cleaning customer_messages before embedding:
(1) stripping quoted email threads / marketing footers, and (2) removing
mobile-client signatures. Tested against real noisy examples found during
/meta and /tickets exploration before being folded into clean.py.
WHY THIS APPROACH: Two real bugs were caught by testing against actual
data instead of trusting a plausible-looking regex:
  - v1 of quote-stripping assumed real customer text always comes BEFORE
    the quoted block, so it truncated everything from the first "wrote:"
    marker onward. This silently destroyed real customer content on
    tickets where the quote comes FIRST and the customer's real message
    follows it (discovered via 17 tickets that ended up with an empty
    clean_message in Step 4 — should have had real content).
  - v2 fixes this by finding where the quoted block ENDS (using known
    footer/unsubscribe markers) and removing only that inner span,
    preserving any real text before AND after it. Falls back to v1's
    truncate-from-start behavior only when no clear end-of-quote marker
    is found.
  - Mobile-signature removal required two iterations after measuring
    real incidence (2.7% of tickets) — see clean.py's docstring for
    the full history.
INPUT: hardcoded sample strings (copied from real ticket data seen earlier).
OUTPUT: printed comparison only — this script does not write anywhere.
"""

import re

# ---------------------------------------------------------------------------
# Quote/footer stripping — v1 (truncate from first marker) kept as fallback
# ---------------------------------------------------------------------------

QUOTE_MARKERS = [
    r"\bOn (?:[A-Za-z]+,\s*)?[A-Za-z]{3,9} \d{1,2}(?:st|nd|rd|th)?,? \d{4}.{0,80}wrote:",
    r"CookUnity\.\s*\d+ Flushing Ave",
    r"No longer want to receive these emails\?",
    r"Get \$\d+ off when you refer a friend!",
]
QUOTE_PATTERN = re.compile("|".join(QUOTE_MARKERS))


def strip_quoted_content_v1(text):
    """Original approach: truncate everything from the first marker onward.
    Only correct when real content comes BEFORE the quote. Kept as a
    fallback for v2 when no end-of-quote marker is found."""
    match = QUOTE_PATTERN.search(text)
    return text[: match.start()].strip() if match else text.strip()


# ---------------------------------------------------------------------------
# Quote/footer stripping — v2 (remove the quoted block, preserve both sides)
# ---------------------------------------------------------------------------

QUOTE_BLOCK_PATTERN = re.compile(
    r"On (?:[A-Za-z]+,\s*)?[A-Za-z]{3,9} \d{1,2}(?:st|nd|rd|th)?,? \d{4}.{0,80}wrote:.*"
    r"(?:No longer want to receive these emails\?|CookUnity\.\s*\d+ Flushing Ave|"
    r"Cookin Inc\.\s*\(DBA Cook Unity Inc\.\)|Get \$\d+ off when you refer a friend!)",
    re.DOTALL,
)


def strip_quoted_content_v2(text):
    """Removes the quoted block itself (start-of-quote to end-of-quote
    marker), keeping any real text on either side. Falls back to v1's
    truncate-from-start if no clear end-of-quote marker is found."""
    block_match = QUOTE_BLOCK_PATTERN.search(text)
    if block_match:
        text = text[: block_match.start()] + " " + text[block_match.end() :]
        return re.sub(r"\s{2,}", " ", text).strip()
    return strip_quoted_content_v1(text)


# ---------------------------------------------------------------------------
# Mobile-client signature removal
# ---------------------------------------------------------------------------

MOBILE_SIGNATURE = re.compile(
    r"Sent from my (?:iPhone|iPad|Android(?: device)?|Samsung(?: Galaxy)?|Galaxy(?: S\d+)?|cell(?:\s|-)?phone|mobile(?:\s|-)?phone)\b\.?,?\s*",
    re.IGNORECASE,
)


def strip_mobile_signature(text):
    text = MOBILE_SIGNATURE.sub(" ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Original validated cases: real content FIRST, quote AFTER
    samples = [
        "I thought I was ordering my weekly cancel this please Nicole Poteete Assoc Dir RSS-VCG Chl Mgt EM, Big Box, OTM, and Asurion Verizon Consumer Group My Clifton Strengths Top 5 Achiever I Strategic I Responsibility I Competition I Ideation M On Fri, May 1, 2026 at 2:57 PM CookUnity <email> wrote: We've adjusted your pricing based on account eligibility...",
        "Hey there! I ordered the premium because I got the subscription and it said I was supposed to get a certain amount of premium meals free a month but it looks like I was charged? Best, Ryn Kalos Sent with Proton Mail secure email. On Friday, May 1st, 2026 at 12:36 PM, CookUnity <email> wrote: We're on it!...",
        "I can't reset my password",  # control: nothing should be stripped
    ]

    # New case: quote FIRST, real content AFTER — this is what v1 got wrong
    new_case = (
        "On Wed, Apr 29, 2026 at 8:34 AM CookUnity wrote: You can still order for next week. "
        "Cookin Inc. (DBA Cook Unity Inc.) 88 Madison Avenue, Toronto ON M5R2S4 "
        "No longer want to receive these emails? "
        "My daughter, Carri Eliesen Bleuer, informed you of a skip as I am out of the country "
        "and only return to Montreal on May 9th. i can place a smaller order BUT ONLY FOR "
        "DELIVERY ON MAY 10th Please confirm Ruth Eliesen"
    )

    print("=== v2 quote-stripping ===\n")

    print("NEW CASE (quote first, real content after — the bug we're fixing):")
    print(strip_quoted_content_v2(new_case))
    print()

    print("ORIGINAL CASE 1 (real content first, quote after — must not regress):")
    print(strip_quoted_content_v2(samples[0]))
    print()

    print("ORIGINAL CASE 2 (must not regress):")
    print(strip_quoted_content_v2(samples[1]))
    print()

    print("CONTROL (no quote at all — must stay unchanged):")
    print(strip_quoted_content_v2(samples[2]))
    print()

    print("=== Mobile signature tests ===\n")

    test1 = "Attn Diego ~Judy O Sent from my iPhone I managed to send you 2 of the 3 but it seems YELP is having some glitch"
    test2 = "Why are there 5 meals when I normally order4? Sent from my iPad J. B."

    print("BEFORE:", test1)
    print("AFTER: ", strip_mobile_signature(test1))
    print()
    print("BEFORE:", test2)
    print("AFTER: ", strip_mobile_signature(test2))
