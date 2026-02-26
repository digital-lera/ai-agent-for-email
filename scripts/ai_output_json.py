from ollama import chat
from ollama import ChatResponse

prompt_text=" Произошла ошибка при загрузке промпта."
email_content="Оповести пользователя, что текст письма не предоставлен"

try:
    with open("prompts/prompt_for_preprocessing.txt", 'r', encoding='utf-8') as prompt:
        prompt_text = prompt.read()
except FileNotFoundError:
    print("Error: prompt text was not provided.")
except Exception as e:
    print(f"An error occured: {e}")

try:
    with open("input_data/email.txt", 'r', encoding='utf-8') as email:
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

try:
    with open("prompts/prompt_for_json.txt", 'r', encoding='utf-8') as prompt:
        prompt_text = prompt.read()
except FileNotFoundError:
    print("Error: prompt for json text was not provided.")
except Exception as e:
    print(f"An error occured: {e}")

message_for_json = f"{prompt_text}\n{response['message']['content']}"

response_with_json: ChatResponse = chat(model='akdengi/saiga-llama3-8b', messages=[
    {
        'role': 'user',
        'content': message_for_json,
        },
    ])


with open("processed_data.json","w") as data:
    data.write(response_with_json['message']['content'])

