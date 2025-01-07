import os
import json

import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_TOKEN")
openai.api_base = os.getenv("OPENAI_API_BASE")


prompts = {}
with open("prompts.json", "r", encoding="utf-8") as file:
    prompts = json.load(file)


def chat_gpt_query(input_str):
    """Выполняет запрос к ChatGPT и обрабатывает ответ"""
    dialog_data = [
        {"role": "system", "content": prompts["start_prompt"]},
        {"role": "user", "content": input_str}
    ]

    try:
        response = ask_gpt(dialog_data)
        # Получаем текст ответа напрямую из response
        if isinstance(response, dict):
            return response.get('content', '')
        return str(response)

    except Exception as e:
        print(f"Error in chat_gpt_query: {e}")
        return None


def ask_gpt(context):
    """Выполняет запрос к API ChatGPT"""
    response = openai.ChatCompletion.create(
        model=os.getenv("gpt_model", "gpt-3.5-turbo"),
        messages=context,
        temperature=0.7,
        n=1,
        max_tokens=500,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
    return response.choices[0].message
