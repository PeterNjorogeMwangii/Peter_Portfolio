import pandas as pd
from groq import Groq
from dotenv import load_dotenv
import os
import re

# Load environment variables
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ----------------------------
# Load dataset
# ----------------------------
file_path = r"C:\Users\Admin\Desktop\Power BI Projects\bi-portfolio\assets\docs\insurance_policies_data.xlsx"
df = pd.read_excel(file_path)

print(f"📊 Dataset loaded successfully: {len(df)} rows, {len(df.columns)} columns")
print(f"📋 Columns: {', '.join(df.columns)}")

# ----------------------------
# Function to answer questions dynamically
# ----------------------------
def answer_question(df, question):
    """
    Dynamically compute answers for common dataset questions.
    """
    q = question.lower()

    # ---- Total number of policies for a specific gender ----
    gender_match = re.search(r"total number of policies for (\w+)", q)
    if gender_match and 'Gender' in df.columns:
        gender = gender_match.group(1).capitalize()
        count = (df['Gender'].str.lower() == gender.lower()).sum()
        return f"Total number of {gender} policies: {count}"

    # ---- Total claim amount for any car make ----
    car_make_match = re.search(r"total claim amount for (\w+)", q)
    if car_make_match and 'Car Make' in df.columns and 'Claim Amount' in df.columns:
        car_make = car_make_match.group(1).capitalize()
        total = df.loc[df['Car Make'].str.lower() == car_make.lower(), 'Claim Amount'].sum()
        return f"Total claim amount for {car_make} cars: {total}"

    # ---- Average claim amount ----
    if "average claim amount" in q and 'Claim Amount' in df.columns:
        avg = df['Claim Amount'].mean()
        return f"Average claim amount: {round(avg, 2)}"

    # ---- Gender with highest total claim amount ----
    if "highest total claim amount" in q and 'Gender' in df.columns and 'Claim Amount' in df.columns:
        sums = df.groupby('Gender')['Claim Amount'].sum()
        top_gender = sums.idxmax()
        top_amount = sums.max()
        return f"Gender with highest total claim amount: {top_gender} (${top_amount})"

    # ---- Default fallback ----
    return "Sorry, I cannot compute that question automatically."


# ----------------------------
# Optional: AI explanation
# ----------------------------
def explain_with_ai(answer, question):
    prompt = f"""
Business question: {question}
Computed answer: {answer}
Explain the result in clear business language, concise and factual.
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a senior data analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=200
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI explanation failed: {e}"


# ----------------------------
# Example usage
# ----------------------------
questions = [
    "What is the total number of policies?"
]

for q in questions:
    ans = answer_question(df, q)
    print("\n💬 Question:", q)
    print("📊 Computed Answer:", ans)

    ai_exp = explain_with_ai(ans, q)
    print("🤖 AI Explanation:", ai_exp)
    print("\n" + "-" * 60)
