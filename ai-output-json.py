from ollama import chat
from ollama import ChatResponse

prompt_text=" Произошла ошибка при загрузке промпта."
email_content="Оповести пользователя, что текст письма не предоставлен"

try:
    with open("prompt.txt", 'r', encoding='utf-8') as prompt:
        prompt_text = prompt.read()
except FileNotFoundError:
    print("Error: prompt text was not provided.")
except Exception as e:
    print(f"An error occured: {e}")

try:
    with open("email.txt", 'r', encoding='utf-8') as email:
        email_content = email.read()
except FileNotFoundError:
    print("Error: file with text output of the email was not provided.")
except Exception as e:
    print(f"An error occured: {e}")

message = f"{prompt_text}\n{email_content}"


response: ChatResponse = chat(model='akdengi/saiga-llama3-8b', messages=[
    {
        'role': 'user',
        'content': message,
        },
    ])

with open("processed_data.txt","a") as data:
    data.write(response['message']['content'])

