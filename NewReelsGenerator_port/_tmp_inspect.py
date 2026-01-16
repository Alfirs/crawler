from app.env_loader import load_env
load_env()
from openai import OpenAI
client = OpenAI(api_key='sk-aitunnel-3Kj1AXU4kerNpsUBeEhRv8rhx40H2iKS', base_url='https://api.aitunnel.ru/v1/')
messages = [
    {'role': 'system', 'content': 'Верни строго JSON {\\"reply\\": true}'},
    {'role': 'user', 'content': 'Просто ответь {\\"reply\\": true}'}
]
resp = client.chat.completions.create(model='gpt-5-nano', messages=messages, max_tokens=2500, reasoning={'effort': 'low'})
import pprint
print('finish_reason:', resp.choices[0].finish_reason)
print('content:', resp.choices[0].message.content)
