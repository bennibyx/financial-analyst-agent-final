# scripts/test_embed.py -- one embedding call to confirm the model works
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                api_key=os.environ["NEBIUS_API_KEY"])
resp = client.embeddings.create(
    model=os.environ["NEBIUS_EMBED_MODEL"],
    input=["supply chain risks", "export restrictions on China"],  # two texts in one call
)
for item in resp.data:
    print("vector length:", len(item.embedding), "first 3 numbers:", item.embedding[:3])
