import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from pydantic import ValidationError
from agents.schemas import ExtractionResult

good = {"company": "ExampleCorp", "period": "Q2 FY2026",
        "metrics": [{"name": "revenue", "value": 26.0, "unit": "USD_billion",
                     "period": "Q2 FY2026", "source_quote": "Revenue was $26.0 billion."}]}
print("GOOD:", ExtractionResult.model_validate(good).metrics[0].value)

bad = {**good, "metrics": [{**good["metrics"][0], "name": "vibes"}]}
try:
    ExtractionResult.model_validate(bad)
except ValidationError as e:
    print("BAD correctly rejected")
