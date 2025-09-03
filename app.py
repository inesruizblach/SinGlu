import os
import streamlit as st
import requests


# Configuration
HF_TOKEN = os.getenv("HF_API_KEY")
MODEL_REPO = os.getenv("HF_MODEL_REPO") or "HuggingFaceH4/zephyr-7b-beta:featherless-ai"
API_URL = "https://router.huggingface.co/v1/chat/completions"

if not HF_TOKEN:
    st.error("Missing Hugging Face API key. Set HF_TOKEN as an environment variable.")
    st.stop()

HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# Basic gluten substitutions
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
    Identify gluten-containing ingredients in the provided text.

    Args:
        ingredients_text (str): The list of ingredients as a string.

    Returns:
        list: Tuples of (ingredient, suggested gluten-free substitute) for any gluten-containing items found.
    """
    text = ingredients_text.lower()  # Normalize text for matching
    flags = []
    for k, v in SUBS.items():
        if k in text:  # If gluten ingredient found, add to flags
            flags.append((k, v))
    return flags


# Hugging Face Chat API call
def hf_generate_chat(prompt_text: str):
    """
    Sends a prompt to the Hugging Face chat completion API and returns the generated response.

    Args:
        prompt_text (str): The prompt or user message to send to the model.

    Returns:
        str: The generated message content from the model.

    Raises:
        RuntimeError: If the API response status is not 200 (success).
    """
    messages = [
        {"role": "user", "content": prompt_text}
    ]
    payload = {"model": MODEL_REPO, "messages": messages}
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"HF API error {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"]

# Build prompt
def build_prompt(ingredients: str, avoid: str, servings: int, recipes_count: int):
    """
    Constructs a prompt for the LLM to generate gluten-free recipes.

    Args:
        ingredients (str): Ingredients provided by the user.
        avoid (str): Allergens or diets to avoid.
        servings (int): Number of servings required.
        recipes_count (int): Number of recipe options to generate.

    Returns:
        str: A formatted prompt string for the model.
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


# Streamlit UI
st.set_page_config(page_title="SinGlu", page_icon="🍲", layout="centered")
st.title("🍲 SinGlu - Gluten-Free Recipe Generator")
st.write("Enter what you have and get **gluten-free** recipe ideas with safe substitutions. Powered by Hugging Face.")

with st.expander("Advanced options"):
    recipes_count = st.slider("How many recipe options?", min_value=1, max_value=3, value=2)
    servings = st.slider("Servings", min_value=1, max_value=8, value=2)

ingredients = st.text_area(
    "Ingredients you have (comma or line separated)",
    height=120,
    placeholder="e.g., chicken thighs, tomatoes, onions, garlic, spinach, rice, soy sauce"
)
avoid = st.text_input("Avoid (optional, e.g., dairy, nuts)")

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
            output = hf_generate_chat(prompt)
        except Exception as e:
            st.error(f"Generation error: {e}")
        else:
            st.markdown(output)
            st.caption(f"Model: {MODEL_REPO}")

st.caption("⚠️ Set your Hugging Face API key as an environment variable: HF_TOKEN=...")
