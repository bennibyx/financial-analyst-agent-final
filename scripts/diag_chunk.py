# scripts/diag_chunk.py -- show what the model returns for ONE chunk, before the verifiers run
import json, sys
from agents.schemas import ExtractionResult
from agents.llm import ask_json
from agents.extraction import SYSTEM
from agents.extract_filing import FILING_RULES, drop_unknown_metrics
from agents.chunking import chunk_document
from agents.verify import clean_text

text = open("data/sample/nvidia_Q4FY26_10K.txt", encoding="utf-8").read()
chunks = chunk_document(clean_text(text), "nvidia_Q4FY26_10K")
chunk = next(c for c in chunks if c.chunk_id == sys.argv[1])   # e.g. nvidia_Q4FY26_10K-mdna-2

schema = json.dumps(ExtractionResult.model_json_schema(), indent=1)
user = ("Extract company, period, key metrics and any forward guidance from this "
        f"section of an SEC filing:\n\n<transcript>\n{chunk.text}\n</transcript>")
result, _ = ask_json(SYSTEM.replace("{schema}", schema) + FILING_RULES, user,
                     ExtractionResult, pre=drop_unknown_metrics)
print("\nRAW METRICS FROM MODEL:")
for m in result.metrics:
    print(" ", m.name, "|", m.value, m.unit, "|", m.period)
