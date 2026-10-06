# agents/llm.py -- ask the model, get validated JSON
import os, re, json
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

load_dotenv()
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                api_key=os.environ.get("NEBIUS_API_KEY", "missing"),
                timeout=300.0)
MODEL = os.environ.get("NEBIUS_MODEL", "nvidia/nemotron-3-super-120b-a12b")
# NEBIUS_THINKING=on turns the model's reasoning mode back on (default: off)
THINKING = os.environ.get("NEBIUS_THINKING", "off").lower() == "on"

def extract_json(text: str) -> str:
    # Drop <think>...</think> reasoning, then keep everything from first { to last }
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return text[start:end + 1]

def ask_json(system: str, user: str, schema: type[BaseModel], retries: int = 2,
             max_tokens: int = 8000, pre=None):
    """Ask the model, validate with Pydantic, retry on bad or truncated output.
    pre: optional function(dict) -> dict that cleans the parsed JSON BEFORE validation
    (used to drop items the schema would reject, since temperature 0 repeats the same mistake)."""
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
    extra = {} if THINKING else {"extra_body": {"chat_template_kwargs": {"enable_thinking": False}}}
    last_err = None
    for attempt in range(retries + 1):
        print(f"  calling model (thinking={'on' if THINKING else 'off'}, max_tokens={max_tokens})...", flush=True)
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, temperature=0, max_tokens=max_tokens, **extra)
        choice = resp.choices[0]
        raw = choice.message.content or ""
        print(f"  finish_reason={choice.finish_reason}, reply_chars={len(raw)}")
        if choice.finish_reason == "length":
            # Ran out of tokens: retry the SAME prompt with a bigger budget
            last_err = ValueError("output truncated (finish_reason=length)")
            max_tokens = min(int(max_tokens * 1.5), 16000)
            continue
        try:
            data = json.loads(extract_json(raw))
            if pre is not None:
                data = pre(data)                      # clean before validating
            return schema.model_validate(data), attempt
        except (ValueError, ValidationError) as e:
            last_err = e
            print(f"  retry reason: {str(e)[:300]}")
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content":
                          f"Your JSON was invalid: {e}\n"
                          "Fix ONLY the problem named above. If an item uses a value the schema does not allow, "
                          "DELETE that item instead of renaming it. Return ONLY the corrected JSON."}]
    raise RuntimeError(f"Failed after {retries + 1} attempts: {last_err}")
