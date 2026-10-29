import re

from .schemas import Metric
from .normalize import clean_quote

FUTURE = re.compile(r"\bexpect|outlook|guidance|plus or minus|will be\b", re.I)
NONG = r"non\s*-?\s*GAAP"


def transcript_fallback(text, period):
    flat = re.sub(r"\s+", " ", text)
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if s.strip()]
    out, seen = [], set()

    def add(name, basis, value, unit, sent):
        if (name, basis) in seen:
            return
        seen.add((name, basis))
        out.append(Metric(name=name, basis=basis, value=value, unit=unit,
                          period=period or "", source_quote=clean_quote(sent)))

    for s in sents:
        if "?" in s or FUTURE.search(s):
            continue
        both = re.search(r"GAAP and " + NONG + r" gross margins? (?:were|was) both (\d{2}(?:\.\d)?)\s*%", s, re.I)
        if both:
            v = float(both.group(1))
            add("gross_margin", "GAAP", v, "percent", s)
            add("gross_margin", "non-GAAP", v, "percent", s)
        else:
            ng = re.search(NONG + r" gross margins? (?:was|were) (\d{2}(?:\.\d)?)\s*%", s, re.I)
            rest = s
            if ng:
                add("gross_margin", "non-GAAP", float(ng.group(1)), "percent", s)
                rest = s[:ng.start()] + s[ng.end():]
            g = re.search(r"GAAP gross margins? (?:was|were) (\d{2}(?:\.\d)?)\s*%", rest, re.I)
            if g:
                add("gross_margin", "GAAP", float(g.group(1)), "percent", s)
        # EPS fallback: recover GAAP and non-GAAP earnings per share
        eps = re.search(
            r"(?P<basis>non\s*-?\s*GAAP|GAAP)\s+"
            r"(?:earnings per share|EPS)\s+"
            r"(?:were|was|is|of)\s+\$?(?P<value>\d+(?:\.\d+)?)",
            s,
            re.I,
        )
        if eps:
            basis = "non-GAAP" if re.match(NONG, eps.group("basis"), re.I) else "GAAP"
            add("eps", basis, float(eps.group("value")), "USD", s)

        r = re.search(r"Total revenue (?:of|for .*? was) \$(\d+(?:\.\d+)?) (billion|million)", s, re.I)
        if r:
            v = float(r.group(1)) * (1000 if r.group(2).lower() == "billion" else 1)
            add("revenue", None, v, "USD_million", s)
        f = re.search(r"free cash flow of \$(\d+(?:\.\d+)?) (billion|million) in Q[1-4]", s, re.I)
        if f and "returned" not in s.lower():
            v = float(f.group(1)) * (1000 if f.group(2).lower() == "billion" else 1)
            add("free_cash_flow", None, v, "USD_million", s)
    return out
