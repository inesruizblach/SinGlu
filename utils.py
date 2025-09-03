# utils.py
import requests

def call_hf_model(prompt: str, api_key: str, model_repo: str):
    """Call Hugging Face text-generation API."""
    url = f"https://api-inference.huggingface.co/models/{model_repo}"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 500}}
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()[0]["generated_text"]
