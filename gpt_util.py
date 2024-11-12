import os
import json

import openai
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_TOKEN")
openai.api_base = os.getenv("OPENAI_API_BASE")

# Если используете прокси для доступа к openai -
# раскоментируйте следующую строку и отредактируйте в соответствии своими данными
# openai.api_base = f"http://127.0.0.1:5000"

prompts = {}
with open("prompts.json", "r", encoding="utf-8") as file:
    prompts = json.load(file)


# def ask_gpt(context):
#     """
#     Выполняет запрос по апи к ChatGPT
#     """
#     response = openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",
#         messages=context,
#         max_tokens=256,
#         temperature=0.6,
#         top_p=1,
#         stop=None
#     )
#
#     for choice in response.choices:
#         if "text" in choice:
#             return choice.text
#
#     return response.choices[0].message.content

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

