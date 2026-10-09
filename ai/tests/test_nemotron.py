from dotenv import load_dotenv
import os
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/", api_key=os.environ["NEBIUS_API_KEY"])
for m in client.models.list():
    print(m.id)