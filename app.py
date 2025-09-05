import os
import json
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

# Load affiliate links
try:
    with open("affiliate_links.json", "r", encoding="utf-8") as f:
        AFFILIATE_LINKS = json.load(f)
except FileNotFoundError:
    AFFILIATE_LINKS = {}

# Gluten substitutions
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

# Helper functions
def get_affiliate_link(product_name: str, region: str = "uk"):
    """
    Retrieve the affiliate link for a given product and region.

    Args:
        product_name (str): The name of the product to look up.
        region (str, optional): The affiliate region code (default is "uk").

    Returns:
        str or None: The affiliate link if available, otherwise None.
    """
    product = product_name.lower()
    if product in AFFILIATE_LINKS and region in AFFILIATE_LINKS[product]:
        base_url = AFFILIATE_LINKS[product][region]
        tag = st.secrets.get(f"affiliate_tag_{region}", "")
        return f"{base_url}?tag={tag}" if tag else base_url
    return None

def possible_gluten_flags_with_links(ingredients_text: str, region: str = "uk"):
    """
    Identify gluten-containing ingredients in the input text and suggest gluten-free substitutes,
    including affiliate links where available.

    Args:
        ingredients_text (str): The list of ingredients as a string.
        region (str, optional): The affiliate region code (default is "uk").

    Returns:
        list: A list of dictionaries with keys 'ingredient', 'substitute', and 'link'.
    """
    text = ingredients_text.lower()
    flagged = []
    for k, v in SUBS.items():
        if k in text:
            link = get_affiliate_link(v, region)
            flagged.append({
                "ingredient": k,
                "substitute": v,
                "link": link
            })
    return flagged

def get_affiliate_recommendations(ingredients_text: str, region: str = "uk"):
    """
    Recommend affiliate products based on the user's ingredients.

    Args:
        ingredients_text (str): The list of ingredients as a string.
        region (str, optional): The affiliate region code (default is "uk").

    Returns:
        list: A list of tuples (product, affiliate_link) for recommended products.
    """
    recs = []
    text = ingredients_text.lower()
    for product, links in AFFILIATE_LINKS.items():
        if product in text and region in links:
            recs.append((product, get_affiliate_link(product, region)))
    return recs

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
    messages = [{"role": "user", "content": prompt_text}]
    payload = {"model": MODEL_REPO, "messages": messages}
    resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"HF API error {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"]

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
st.write("Enter your ingredients and get **gluten-free** recipes with substitutions and recommended products.")

with st.expander("Advanced options"):
    recipes_count = st.slider("How many recipe options?", min_value=1, max_value=3, value=2)
    servings = st.slider("Servings", min_value=1, max_value=8, value=2)
    region = st.selectbox("Affiliate region", options=["uk", "es"], index=0)

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

    # Show substitutions with affiliate links
    flags = possible_gluten_flags_with_links(ingredients, region)
    if flags:
        st.info("Heads up! We detected potential gluten-containing items and suggested swaps:")
        for f in flags:
            sub_text = f"**{f['ingredient']}** → {f['substitute']}"
            if f['link']:
                sub_text += f" ([try here]({f['link']}))"
            st.markdown(f"- {sub_text}")

    # Generate recipe from HF
    with st.spinner("Cooking up ideas..."):
        prompt = build_prompt(ingredients, avoid, servings, recipes_count)
        try:
            output = hf_generate_chat(prompt)
        except Exception as e:
            st.error(f"Generation error: {e}")
        else:
            st.markdown(output)
            st.caption(f"Model: {MODEL_REPO}")

    # Show general affiliate recommendations
    recs = get_affiliate_recommendations(ingredients, region)
    if recs:
        st.subheader("🛒 Recommended Gluten-Free Products")
        for product, link in recs:
            st.markdown(f"- [{product.title()}]({link})")

st.caption("⚠️ Set your Hugging Face API key as an environment variable: HF_TOKEN=...")
