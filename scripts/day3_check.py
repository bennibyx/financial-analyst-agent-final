import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.extraction import extract
from agents.verify import verify, clean_text

raw = pathlib.Path("data/samples/transcript1.txt").read_text()
text = clean_text(raw)
print(f"Transcript chars: {len(raw)} raw -> {len(text)} after header cleanup")
N, valid, result = 3, 0, None
for i in range(N):
    try:
        result, retries_used = extract(text)
        valid += 1
        print(f"run {i+1}: valid (retries used: {retries_used})")
    except RuntimeError as e:
        print(f"run {i+1}: FAILED {e}")
print(f"JSON validity: {valid}/{N}")

if result:
    result, issues, fixes = verify(result, text)
    nonnull = sum(1 for m in result.metrics if m.value is not None)
    print(f"Metrics with a value: {nonnull}/{len(result.metrics)}")
    print(f"Guidance items: {len(result.guidance)}")
    print("Auto-fixes by verifier:", fixes or "none")
    print("Unresolved issues:", issues or "none")
    print(result.model_dump_json(indent=2))
