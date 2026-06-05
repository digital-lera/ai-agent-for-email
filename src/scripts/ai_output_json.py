from pathlib import Path
import ollama
from ollama import chat
from ollama import ChatResponse

scripts_dir = Path(__file__).resolve().parent.parent / "scripts"

def process_text_with_ai():
    def is_model_running(model_name):
        # Retrieve models currently loaded into memory
        running_models = ollama.ps()
        
        # Check if any running model name matches yours
        for model in running_models.get('models', []):
            if model['name'] == model_name or model['model'] == model_name:
                return True
        return False

    prompt_text=" Произошла ошибка при загрузке промпта."
    email_content="Оповести пользователя, что текст письма не предоставлен"

    try:
        with open(scripts_dir / "prompts/prompt_for_preprocessing.txt", 'r', encoding='utf-8') as prompt:
            prompt_text = prompt.read()
            print("prompt 1 read")
    except FileNotFoundError:
        print("Ошибка: не предоставлен текст промпта.")
    except Exception as e:
        print(f"An error occured: {e}")

    try:
        with open(scripts_dir / "input_data/email.txt", 'r', encoding='utf-8') as email:
            email_content = email.read()
            print("email read")
    except FileNotFoundError:
        print("Ошибка: текст письма не предоставлен.")
    except Exception as e:
        print(f"An error occured: {e}")

    filename_message = ""

    try:
        with open(scripts_dir / "filename.txt", 'r') as filename:
            filename_message = filename.read()
    except FileNotFoundError:
        print("Ошибка: не найдено имя файла")
    except Exception as e:
        print(f"An error occured: {e}")

    message = f"{prompt_text}\n\n{filename_message}\n{email_content}"

    if (not is_model_running('bambucha/saiga-llama3:latest')):
        print('Ollama не запущена.')

    response: ChatResponse = chat(model='bambucha/saiga-llama3:latest', messages=[
        {
            'role': 'user',
            'content': message,
            
            },
        ],
        options={
            'temperature': 0.35
            }
                                )
    print("Первичная обработка ИИ завершена.")

    try:
        with open(scripts_dir / "prompts/prompt_for_json.txt", 'r', encoding='utf-8') as prompt:
            prompt_text = prompt.read()
            print("Прочтен промпт для json")
    except FileNotFoundError:
        print("Ошибка: промпт для json не предоставлен")
    except Exception as e:
        print(f"An error occured: {e}")

    message_for_json = f"{prompt_text}\n{response['message']['content']}"

    response_with_json: ChatResponse = chat(model='bambucha/saiga-llama3:latest', messages=[
        {
            'role': 'user',
            'content': message_for_json,
            },
        ],
        options={
            'temperature': 0.35
            }
    )
    print("Обработка ИИ завершена.")



    with open(scripts_dir / "processed_data.json","w") as data:
        data.write(response_with_json['message']['content'])

