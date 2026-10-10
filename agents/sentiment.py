# agents/sentiment.py -- Day 8: management tone, hedging, Q&A pushback (Sentiment prompt v1)
import re, sys, json
from agents.llm import ask_json
from agents.schemas import Sentiment

SENTIMENT_SYSTEM_V1 = """You are a financial analyst who reads earnings-call transcripts for TONE.
Return ONLY one JSON object, no prose, with exactly these keys:

{
  "overall": "positive" | "neutral" | "negative",
  "score": number between -1.0 and 1.0,
  "hedging_level": "low" | "medium" | "high",
  "qa_pushback": "none" | "mild" | "strong",
  "evidence_quotes": [string, ...]
}

Definitions:
- overall / score: MANAGEMENT's tone about the business, results and outlook (not the analysts').
  score guide: -1.0 = alarmed or defensive, -0.5 = clearly cautious, 0 = balanced,
  +0.5 = confident, +1.0 = exuberant. "overall" must agree with score:
  positive if score > 0.25, negative if score < -0.25, otherwise neutral.
- hedging_level: how often management uses hedging or softening language
  ("we believe", "approximately", "subject to", "uncertain", "we hope", "depending on", "visibility is limited").
  Look at the forward-looking statements only. low = fewer than 1 in 4 are hedged; medium = about half are hedged;
  high = most (3 in 4 or more) are hedged or conditional. Do not pick medium by default, count first.
- qa_pushback: in the Q&A section only, do analysts challenge management?
  none = friendly or clarifying questions only; mild = ONE analyst challenges or doubts something;
  strong = TWO OR MORE analysts challenge, or one analyst presses a second time, or an analyst states concern,
  doubts guidance, margins or credibility, or says an answer did not address the question.
  If there is no Q&A section in the text, use "none".
- evidence_quotes: 3 to 6 SHORT quotes (under 25 words each) that justify your ratings.
  Each quote must be ONE sentence copied exactly. Never quote a long multi-sentence passage.
  Start each quote with a label: "TONE: ", "HEDGING: " or "PUSHBACK: " (the label is not part of the quote).
  Give at least one HEDGING quote if hedging_level is not low; it must contain an actual hedging phrase
  (e.g. "may", "approximately", "subject to", "depends", "uncertain"), not a confident statement.
  Give at least one PUSHBACK quote if qa_pushback is not "none"; it must be an ANALYST's QUESTION (contains "?"),
  never a management answer. If you cannot find an analyst quote showing a challenge, set qa_pushback
  to "none". Never repeat a quote.

Rules:
- Use the full range of each scale. Pick the category the counting rules give, even if it is an extreme one.
- Quotes must be copied EXACTLY, word for word, from the transcript. Never paraphrase or invent.
- Judge only what is in the text. Do not use outside knowledge about the company.
- Count silently. Do not explain or show your counting. Output JSON only."""

MAX_CHARS = 60000  # crude guard; Sandeep's chunker can replace this later
CHALLENGE = ("concern", "aggressive", "doesn't answer", "worried", "skeptic", "unconvinced", "doubt", "too optimistic")
PROBE = ("how confident", "are you confident", "why are you", "can you justify", "how do you reconcile", "how can you")


def _norm(s: str) -> str:
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'), ("\u2014", "-"), ("\u2013", "-")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().lower()


def analyze_sentiment(transcript: str, qa_text: str | None = None):
    """transcript = full call text, or prepared remarks if qa_text is given separately.
    Returns (Sentiment, retries_used)."""
    if qa_text:
        body = f"PREPARED REMARKS:\n{transcript}\n\nQ&A SECTION:\n{qa_text}"
    else:
        body = transcript
    body = body[:MAX_CHARS]
    haystack = _norm(body)

    def drop_fake_quotes(data: dict) -> dict:
        # Hallucination guard: keep only quotes that really appear in the transcript
        quotes = data.get("evidence_quotes", [])
        kept, seen = [], set()
        for q in quotes:
            if not isinstance(q, str) or q in seen:
                continue
            seen.add(q)
            if _norm(re.sub(r"^(HEDGING|PUSHBACK|TONE):\s*", "", q)) in haystack:
                kept.append(q)
        if len(kept) < len(quotes):
            print(f"  dropped {len(quotes) - len(kept)} unverifiable quote(s):", [q[:70] for q in quotes if q not in kept])
        HEDGE = ("approximately", " may ", "might", "could", "subject to", "uncertain", "depends", "depending", "hope", "limited", "no assurance", "too early", "very tight", "do believe")
        def backed(label, test):
            return any(q.startswith(label) and test(q.lower()) for q in kept)
        if data.get("qa_pushback", "none") != "none" and not backed("PUSHBACK:", lambda t: any(c in t for c in CHALLENGE + PROBE)):
            print("  downgraded qa_pushback to none: no analyst question quoted")
            data["qa_pushback"] = "none"
        if data.get("hedging_level", "low") != "low" and not backed("HEDGING:", lambda t: any(h in t for h in HEDGE)):
            print("  downgraded hedging_level to low: no hedging phrase quoted")
            data["hedging_level"] = "low"
        n_push = sum(1 for q in kept if q.startswith("PUSHBACK:") and any(c in q.lower() for c in CHALLENGE))
        if data.get("qa_pushback") == "strong" and n_push < 2:
            print("  capped qa_pushback at mild: fewer than 2 analyst challenges quoted")
            data["qa_pushback"] = "mild"
        data["evidence_quotes"] = kept
        # Keep overall consistent with score even if the model drifts
        s = data.get("score")
        if isinstance(s, (int, float)):
            data["overall"] = "positive" if s > 0.25 else "negative" if s < -0.25 else "neutral"
        return data

    user = f"Analyze the tone of this earnings call.\n\n{body}"
    return ask_json(SENTIMENT_SYSTEM_V1, user, Sentiment, max_tokens=1500, pre=drop_fake_quotes)


if __name__ == "__main__":
    # usage: python -m agents.sentiment path/to/transcript.txt
    text = open(sys.argv[1], encoding="utf-8").read()
    result, retries = analyze_sentiment(text)
    print(json.dumps(result.model_dump(), indent=2))
    print(f"retries used: {retries}")
    if len(result.evidence_quotes) < 2:
        print("WARNING: fewer than 2 verified quotes. Check the prompt or transcript.")
