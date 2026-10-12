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

MAX_CHARS = 90000  # crude guard; Sandeep's chunker can replace this later
CHALLENGE = ("concern", "aggressive", "doesn't answer", "worried", "skeptic", "unconvinced", "doubt", "too optimistic")
PROBE = ("how confident", "are you confident", "why are you", "can you justify", "how do you reconcile", "how can you")


def _norm(s: str) -> str:
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'), ("\u2014", "-"), ("\u2013", "-")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s).strip().lower()


def _analyze_sentiment_model(transcript: str, qa_text: str | None = None):
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
        kept, seen, dropped, repaired = [], set(), [], 0
        for q in quotes:
            if not isinstance(q, str) or q in seen:
                continue
            seen.add(q)
            label = re.match(r"^(HEDGING|PUSHBACK|TONE):\s*", q)
            prefix = label.group(0) if label else ""
            body_q = q[len(prefix):]
            if _norm(body_q) in haystack:
                kept.append(q)
                continue
            pieces = [x.strip() for x in re.split(r"(?<=[.?!])\s+|\s*\.\.\.\s*|\s*\u2026\s*", body_q)
                      if len(x.strip()) >= 30 and not re.match(r"(?i)(thanks?|great|yeah|hi|hello)\b", x.strip())]
            good = [x for x in pieces if _norm(x) in haystack]
            if good:
                kept.append(prefix + " ".join(good))
                repaired += 1
            else:
                dropped.append(q)
        if repaired:
            print(f"  repaired {repaired} quote(s): kept only the sentences found word for word in the transcript")
        if dropped:
            print(f"  dropped {len(dropped)} unverifiable quote(s):", [q[:70] for q in dropped])
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


from .hedging import hedging_stats as _hedging_stats


def hedging_level_from_density(per_1000):
    """Provisional bands from 3 NVIDIA calls: low < 0.2, medium 0.2-0.5, high > 0.5 strong-hedge sentences per 1000 words."""
    return "low" if per_1000 < 0.2 else "medium" if per_1000 <= 0.5 else "high"


def analyze_sentiment(transcript: str, qa_text: str | None = None):
    """The model rates tone and pushback; hedging is MEASURED in code (stable) and shown with real sentences."""
    sent, retries = _analyze_sentiment_model(transcript, qa_text)
    st = _hedging_stats(transcript if not qa_text else transcript + "\n" + qa_text)
    level = hedging_level_from_density(st["strong_per_1000"])
    quotes = [q for q in sent.evidence_quotes if not q.startswith("HEDGING:")]
    quotes += ["HEDGING: " + x for x in st["strong"][:3]]
    return sent.model_copy(update={"hedging_level": level, "evidence_quotes": quotes}), retries


_analyze_sentiment_once = analyze_sentiment


def analyze_sentiment(transcript: str, qa_text: str | None = None):
    """The model sometimes returns malformed JSON several times in a row; try a fresh call once more."""
    last = None
    for attempt in range(2):
        try:
            return _analyze_sentiment_once(transcript, qa_text)
        except RuntimeError as e:
            last = e
            print(f"  sentiment attempt {attempt + 1} failed; {'retrying' if attempt == 0 else 'giving up'}", flush=True)
    raise last
