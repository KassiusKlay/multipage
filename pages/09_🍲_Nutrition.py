import streamlit as st
import requests
from bs4 import BeautifulSoup
import openai
import ast

EDAMAM_ENDPOINT = "https://api.edamam.com/api/nutrition-details"
EDAMAM_APP_ID = st.secrets["api-keys"]["edamam-app-id"]
EDAMAM_APP_KEY = st.secrets["api-keys"]["edamam-app-key"]
OPENAI_API_KEY = st.secrets["api-keys"]["openai-api-key"]


@st.cache_data
def extract_text_from_url(url):
    """Extracts text content from a given URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text()
    else:
        st.error(f"Error fetching URL: {response.status_code}")
        return None


@st.cache_data
def get_ingredients_from_text(text):
    """Sends text to OpenAI API to extract ingredients."""
    openai.api_key = OPENAI_API_KEY
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {
                    "role": "system",
                    "content": """
                    Extract the ingredients of the recipe in this text as a Python list
                    of strings in the format ['quantity ingredient']
                    (dont give it a variable name)
                    Convert fractions into its numerical value.
                    Convert just ounces into metric (dont convert cups / tsp / tbsp).
                    """,
                },
                {"role": "user", "content": text},
            ],
        )
        ingredients_list = response.choices[0].message.content
        return "\n".join(ast.literal_eval(ingredients_list))
    except openai.OpenAIError as e:
        st.error(f"OpenAI API error: {str(e)}")
        return None


@st.cache_data
def get_nutrition_info(ingredients_list):
    data = {"title": "Recipe", "ingr": ingredients_list}
    params = {"app_id": EDAMAM_APP_ID, "app_key": EDAMAM_APP_KEY}
    response = requests.post(EDAMAM_ENDPOINT, params=params, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error: {response.status_code} - {response.text}")
        return None


def main():
    st.title("Vegan Recipe Nutrition App")
    st.write("Paste a recipe URL below:")
    url_input = st.text_input("Recipe URL")

    if st.button("Extract Ingredients"):
        if url_input:
            text_content = extract_text_from_url(url_input)
            if text_content:
                ingredients_list = get_ingredients_from_text(text_content)
                if ingredients_list:
                    st.session_state["ingredients"] = ingredients_list
                    st.session_state.pop("nutrition_data", None)
        else:
            st.warning("Please enter a valid URL.")

    ingredients_text = st.session_state.get("ingredients", "")
    text_area_height = max(100, min(500, len(ingredients_text.split("\n")) * 25))
    ingredient_text_area = st.text_area(
        "Ingredients",
        value=ingredients_text,
        height=text_area_height,
        key="ingredient_input",
    )

    if st.button("Analyze Recipe"):
        updated_ingredients = [
            line.strip() for line in ingredient_text_area.split("\n") if line.strip()
        ]
        st.session_state["nutrition_data"] = get_nutrition_info(updated_ingredients)

    if "nutrition_data" in st.session_state:
        nutrition_data = st.session_state["nutrition_data"]
        st.subheader("Nutrition Summary")
        total_nutrients = nutrition_data.get("totalNutrients", {})
        servings = st.number_input(
            "Servings", min_value=1, value=1, step=1, key="servings"
        )

        col1, col2 = st.columns(2)
        with col1:
            st.write("**Total Nutrition**")
            st.write(
                f"**Protein:** {total_nutrients.get('PROCNT', {}).get('quantity', 0):.2f} g"
            )
            st.write(
                f"**Carbohydrates:** {total_nutrients.get('CHOCDF', {}).get('quantity', 0):.2f} g"
            )
            st.write(
                f"**Fat:** {total_nutrients.get('FAT', {}).get('quantity', 0):.2f} g"
            )

        with col2:
            st.write("**Per Serving**")
            st.write(
                f"**Protein:** {total_nutrients.get('PROCNT', {}).get('quantity', 0) / servings:.2f} g"
            )
            st.write(
                f"**Carbohydrates:** {total_nutrients.get('CHOCDF', {}).get('quantity', 0) / servings:.2f} g"
            )
            st.write(
                f"**Fat:** {total_nutrients.get('FAT', {}).get('quantity', 0) / servings:.2f} g"
            )


if __name__ == "__main__":
    main()
