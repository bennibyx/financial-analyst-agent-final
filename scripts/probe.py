import sys, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.llm import client, MODEL

def probe(label, max_tokens, **extra):
    t = time.time()
    try:
        r = client.chat.completions.create(
            model=MODEL, messages=[{"role": "user", "content": "Say hi"}],
            max_tokens=max_tokens, temperature=0, **extra)
    except Exception as e:
        print(f"{label}: ERROR {str(e)[:300]}")
        return
    m = r.choices[0].message
    reasoning = getattr(m, "reasoning_content", None) or (m.model_extra or {}).get("reasoning")
    print(f"{label}: {time.time()-t:.1f}s finish={r.choices[0].finish_reason} "
          f"content={m.content!r} reasoning_chars={len(reasoning or '')} "
          f"tokens={r.usage.completion_tokens}")

probe("A: default, 2000 tokens", 2000)
probe("B: thinking off, 300 tokens", 300,
      extra_body={"chat_template_kwargs": {"enable_thinking": False}})
