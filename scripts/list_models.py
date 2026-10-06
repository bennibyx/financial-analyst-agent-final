# scripts/list_models.py -- prints every model your Token Factory key can use
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # reads NEBIUS_API_KEY from .env
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                api_key=os.environ["NEBIUS_API_KEY"])
for m in client.models.list().data:
    print(m.id)
