import os
import time
import requests
import streamlit as st

# Configuration
API_KEY = os.getenv("HF_API_KEY")  # API key should be set as an environment variable
MODEL_REPO = os.getenv("HF_MODEL_REPO") or "mistralai/Mistral-7B-Instruct-v0.2"
MODEL_URL = f"https://api-inference.huggingface.co/models/{MODEL_REPO}"

if not API_KEY:
    st.error("Missing Hugging Face API key. Set HF_API_KEY as an environment variable.")
    st.stop()

HEADERS = {"Authorization": f"Bearer {API_KEY}"}

# Basic gluten substitutions (local heuristic – the LLM will also propose swaps)
SUBS = {
    "wheat flour": "gluten-free all-purpose flour or rice flour",
    "flour": "gluten-free all-purpose flour",
    "breadcrumbs": "gluten-free breadcrumbs or crushed cornflakes",
    "soy sauce": "tamari (gluten-free) or coconut aminos",
    "pasta": "gluten-free pasta (rice/corn/quinoa)",
    "noodles": "rice noodles or glass noodles",
    "tortilla": "corn tortilla (check GF certified)",
    "barley": "brown rice or quinoa",
    "rye": "buckwheat groats (naturally GF)",
    "couscous": "quinoa or millet",
    "bulgur": "quinoa or cauliflower rice",
    "semolina": "rice flour or cornmeal",
    "malt": "omit or use maple syrup (for flavoring)",
    "beer": "gluten-free beer or stock"
}

def possible_gluten_flags(ingredients_text: str):
    """
    Checks the provided ingredients text for any known gluten-containing items.
    Returns a list of tuples with (ingredient, suggested gluten-free substitute).
    """
    text = ingredients_text.lower()  # Normalize text for matching
    flags = []
    for k, v in SUBS.items():
        if k in text:  # If gluten ingredient found, add to flags
            flags.append((k, v))
    return flags

def hf_generate(prompt: str, max_new_tokens: int = 550, temperature: float = 0.7, top_p: float = 0.95):
    """
    Calls the Hugging Face Inference API to generate text from a prompt.
    Implements basic retry logic for model loading (503) and rate limit (429/408) errors.
    Returns the generated text or raises an error after several failed attempts.
    """
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "return_full_text": False
        }
    }
    backoff = 2  # Initial backoff time for rate limiting
    for attempt in range(6):  # Retry up to 6 times
        resp = requests.post(MODEL_URL, headers=HEADERS, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            # Typical HF text-generation response: list[{"generated_text": "..."}]
            if isinstance(data, list) and data and isinstance(data[0], dict) and "generated_text" in data[0]:
                return data[0]["generated_text"]
            # Fallback pretty-print if unexpected response
            return str(data)
        elif resp.status_code == 503:
            # Model loading – wait estimated time if provided
            try:
                eta = float(resp.json().get("estimated_time", 5))
            except Exception:
                eta = 5.0
            time.sleep(min(eta, 10))  # Wait for model to load
            continue
        elif resp.status_code in (429, 408):
            time.sleep(backoff)  # Wait and retry for rate limiting
            backoff *= 2
            continue
        else:
            raise RuntimeError(f"HF API error {resp.status_code}: {resp.text[:500]}")
    raise RuntimeError("Hugging Face API failed after retries. Try again in a moment.")

def build_prompt(ingredients: str, avoid: str, servings: int, recipes_count: int):
    """
    Constructs a prompt for the LLM to generate gluten-free recipes.
    Includes user ingredients, allergens to avoid, servings, and recipe count.
    Returns a formatted string for the model.
    """
    return f"""
You are a culinary assistant specialized in gluten-free cooking. Ensure every recipe is 100% gluten-free. 
If any provided ingredient contains gluten, automatically swap it for safe alternatives and mention the swap.

User ingredients: {ingredients}
Allergens/diet to avoid (besides gluten): {avoid if avoid.strip() else "None specified"}
Servings: {servings}

TASK: Create {recipes_count} distinct gluten-free recipe OPTIONS that primarily use the user's ingredients.
Each option must follow EXACTLY this Markdown format:

# Recipe Title
Servings: <number>
Prep: <minutes> | Cook: <minutes>

## Ingredients
- <bullet list of GF ingredients only>

## Method
1. <step>
2. <step>
3. <step>

## Substitutions & Notes
- <list any swaps or GF cautions>
- <tips for variations or storage>

Keep it concise but practical. Avoid brand names. Always ensure substitutes are safe for celiac/gluten intolerance.
"""

# UI
st.set_page_config(page_title="Gluten-Free Recipe Generator", page_icon="🍲", layout="centered")

st.title("🍲 Gluten-Free Recipe Generator (Free)")
st.write("Enter what you have and get **gluten-free** recipe ideas with safe substitutions. Powered by a free Hugging Face model.")

with st.expander("Advanced options"):
    model_repo_input = st.text_input(
        "Hugging Face model repo (optional)",
        value=MODEL_REPO,
        help="Try other instruct models like 'HuggingFaceH4/zephyr-7b-beta' or 'Qwen/Qwen2.5-3B-Instruct'."
    )
    recipes_count = st.slider("How many recipe options?", min_value=1, max_value=3, value=2)
    servings = st.slider("Servings", min_value=1, max_value=8, value=2)

ingredients = st.text_area(
    "Ingredients you have (comma or line separated)",
    height=120,
    placeholder="e.g., chicken thighs, tomatoes, onions, garlic, spinach, rice, soy sauce"
)
avoid = st.text_input("Avoid (optional, e.g., dairy, nuts)")

if model_repo_input and model_repo_input != MODEL_REPO:
    MODEL_REPO = model_repo_input.strip()
    MODEL_URL = f"https://api-inference.huggingface.co/models/{MODEL_REPO}"

if st.button("Generate recipe(s)"):
    if not ingredients.strip():
        st.warning("Please enter some ingredients first.")
        st.stop()

    flags = possible_gluten_flags(ingredients)
    if flags:
        st.info(
            "Heads up! We detected potential gluten-containing items. We'll auto-swap them:\n" +
            "\n".join([f"- **{k}** → {v}" for k, v in flags])
        )

    with st.spinner("Cooking up ideas..."):
        prompt = build_prompt(ingredients, avoid, servings, recipes_count)
        try:
            output = hf_generate(prompt)
        except Exception as e:
            st.error(f"Generation error: {e}")
        else:
            st.markdown(output)
            st.caption(f"Model: {MODEL_REPO}")

# Reminder for public repo users
st.caption("⚠️ Set your Hugging Face API key as an environment variable: HF_API_KEY=...")
