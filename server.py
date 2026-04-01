from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd
import numpy as np
from groq import Groq
from dotenv import load_dotenv
import io
import os
import json
import re
from typing import List, Dict, Any
import traceback
from datetime import datetime, date

# Load environment variables
load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store uploaded datasets in memory
datasets: Dict[str, pd.DataFrame] = {}



class QueryRequest(BaseModel):
    dataset_id: str
    question: str
    conversation_history: List[Dict[str, str]] = []

class AnalysisResponse(BaseModel):
    answer: str
    code_executed: str = None
    execution_result: Any = None
    dataset_info: Dict[str, Any] = None

def convert_to_serializable(obj):
    """Convert numpy/pandas/datetime objects to JSON-serializable types"""
    if isinstance(obj, dict):
        return {str(key): convert_to_serializable(value) for key, value in obj.items()}  # ← Convert keys to strings
    elif isinstance(obj, list):
        return [convert_to_serializable(item) for item in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, (pd.Timestamp, datetime, date)):  # ← Added datetime handling
        return str(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Series):
        return obj.to_dict()
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient='records')
    elif pd.isna(obj):
        return None
    else:
        return obj

@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload and parse CSV or Excel file"""
    try:
        contents = await file.read()
        
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise ValueError("Unsupported file format. Use CSV or Excel files.")
        
        dataset_id = f"dataset_{len(datasets)}"
        datasets[dataset_id] = df
        
        info = {
            "dataset_id": dataset_id,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "sample": convert_to_serializable(df.head(5).to_dict(orient='records'))
        }
        
        return info
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing file: {str(e)}")

@app.post("/query", response_model=AnalysisResponse)
async def query_dataset(request: QueryRequest):
    """Query dataset with natural language - generates and executes Python code"""

    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = datasets[request.dataset_id]
    question_lower = request.question.lower().strip()

    # Check for greetings
    greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "howdy", "greetings"]
    if question_lower in greetings or any(greet in question_lower for greet in greetings):
        return AnalysisResponse(
            answer="Hello! How can I help you with the data today?",
            dataset_info={"rows": len(df), "columns": len(df.columns)}
        )

    columns_lower = [col.lower() for col in df.columns]

    stopwords = set(['the', 'of', 'for', 'in', 'and', 'to', 'is', 'on', 'with', 'by', 'at', 'from', 'as', 'that', 'this', 'it', 'an', 'a'])
    keywords = [word for word in re.findall(r'\b[a-zA-Z_]+\b', question_lower) if word not in stopwords]

    matched = False
    # Check for column match
    for word in keywords:
        for col in columns_lower:
            if word == col or word.rstrip('s') == col.rstrip('s'):
                matched = True
                break
        if matched:
            break

    # If no column match, check for value match in categorical columns or year in date columns
    if not matched:
        # Check for value match in categorical columns
        for col in df.select_dtypes(include=['object']).columns:
            values = df[col].dropna().unique()
            values_lower = [str(v).lower() for v in values]
            for word in keywords:
                if word in values_lower:
                    matched = True
                    break
            if matched:
                break

        # Check for year match in date columns
        if not matched:
            for col in df.select_dtypes(include=['datetime', 'datetime64']).columns:
                years = df[col].dropna().dt.year.unique()
                years_str = [str(y) for y in years]
                for word in keywords:
                    if word in years_str:
                        matched = True
                        break
                if matched:
                    break

    # Proceed as usual (allow derived fields)
    code = generate_analysis_code(df, request.question)

    # Print the user question and generated code for debugging
    print("\n" + "="*80)
    print("USER QUESTION:")
    print(request.question)
    print("\nGENERATED CODE:")
    print(code)
    print("="*80)

    # Execute the generated code and print the results
    execution_result = execute_code_safely(df, code)
    print("\nRESULTS:")
    print(json.dumps(execution_result, indent=2))
    print("="*80)

    explanation = generate_explanation(request.question, code, execution_result, dataset_id=request.dataset_id)
    return AnalysisResponse(
        answer=explanation,
        code_executed=code,
        execution_result=execution_result,
        dataset_info={
            "rows": len(df),
            "columns": len(df.columns)
        }
    )

def generate_analysis_code(df: pd.DataFrame, question: str) -> str:
    """Use AI to generate Python code that answers the question"""

    # Get dataset schema and sample
    schema_info = {
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "shape": df.shape,
        "sample_data": convert_to_serializable(df.head(3).to_dict(orient='records')),
        "numeric_columns": df.select_dtypes(include=['number']).columns.tolist(),
        "categorical_columns": df.select_dtypes(include=['object']).columns.tolist()
    }

    categorical_examples = {}
    for col in schema_info["categorical_columns"][:5]:
        categorical_examples[col] = df[col].value_counts().head(5).to_dict()

    prompt = f"""You are a Python data analysis code generator. 
    Generate ONLY executable Python code to answer the user's question, 
    but DO NOT attempt to answer questions that require information outside the columns and data provided in the dataset.

Dataset Schema:
- Shape: {schema_info['shape'][0]} rows × {schema_info['shape'][1]} columns
- Columns: {schema_info['columns']}
- Data Types: {json.dumps(schema_info['dtypes'], indent=2)}
- Numeric Columns: {schema_info['numeric_columns']}
- Categorical Columns: {schema_info['categorical_columns']}

Sample Categorical Values:
{json.dumps(categorical_examples, indent=2)}

Sample Data (first 3 rows):
{json.dumps(schema_info['sample_data'], indent=2)}

User Question: {question}

CRITICAL INSTRUCTIONS:
1. The DataFrame is already loaded as 'df' - DO NOT create or load it
2. Write code that performs the EXACT analysis needed
3. ONLY answer questions that can be answered using the columns and data in the dataset. If the question is outside the dataset's scope, set result = {{'error': 'Question cannot be answered with this dataset.'}}
4. Handle data cleaning (strip whitespace, convert to lowercase for matching, handle data types)
5. Store ALL results in a dictionary called 'result'
6. DO NOT use print statements - only assign to 'result'
7. Make the code robust - handle missing values, type conversions, case sensitivity
8. Extract year from date columns using .dt.year if needed

Example patterns:
- For year extraction: df['Year'] = df['DateColumn'].dt.year
- For filtering: df[(df['Column'].str.lower().str.strip() == 'value') & (df['Year'] == 2013)]
- For aggregation: df.groupby('Category')['Amount'].agg(['sum', 'mean', 'count'])
- For totals: df['Amount'].sum()

Return ONLY the Python code, no explanations, no markdown, no ```python blocks."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.1
        )

        code = response.choices[0].message.content.strip()
        code = re.sub(r'^```python\s*\n', '', code)
        code = re.sub(r'\n```\s*$', '', code)
        code = code.strip()
        return code

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating code: {str(e)}")

def execute_code_safely(df: pd.DataFrame, code: str) -> Dict[str, Any]:
    """Execute the generated code in a controlled environment"""
    
    # Create a safe execution environment
    safe_globals = {
        'df': df.copy(),  # Work on a copy
        'pd': pd,
        'np': np,
        'result': {}
    }
    
    try:
        # Execute the code
        exec(code, safe_globals)
        
        # Get the result
        result = safe_globals.get('result', {})
        
        # Convert numpy/pandas types to native Python types for JSON serialization
        result = convert_to_serializable(result)
        
        return {
            "status": "success",
            "data": result
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }

def generate_explanation(question: str, code: str, execution_result: Dict[str, Any], dataset_id: str = None) -> str:
    """Generate natural language explanation of the results"""

    # If the execution result contains the error key, return a strict domain response
    if execution_result["status"] == "success" and isinstance(execution_result.get("data"), dict):
        if "error" in execution_result["data"]:
            domain = "car sales" if dataset_id == "car_sales" else "insurance"
            return f"Sorry, I can only answer questions related to {domain} based on the provided dataset."

    if execution_result["status"] == "error":
        return f"Error executing analysis: {execution_result['error']}\n\nPlease try rephrasing your question."

    # Use the actual value from execution_result for the main answer
    filtered_data = execution_result['data'].copy()
    main_value = None
    for k, v in filtered_data.items():
        if isinstance(v, (int, float)):
            main_value = v
            break

    if main_value is not None:
        formatted_value = f"${main_value:,.0f}"
        return f"The answer is {formatted_value} based on the dataset."

    # Fallback to LLM-generated explanation if no main value found
    prompt = f"""You are a professional data analyst presenting findings. Generate a clear, concise explanation of the analysis results.

User Question: {question}

Execution Results Summary:
{json.dumps(filtered_data, indent=2)}

Instructions:
1. Provide the answer using exact numbers from the results.
2. Do NOT use phrases like 'I'm pleased', 'I'm happy', or 'I'm excited'. Be neutral and natural.
3. Highlight the KEY INSIGHTS and TRENDS (not raw counts).
4. Format large numbers with commas (e.g., 871,049.12).
5. Focus on what the data MEANS, not just the numbers.
6. For categorical data, mention the diversity but skip listing all values.
7. Be professional, conversational, and action-oriented.
8. Provide 3-5 key insights maximum.

Generate the explanation now:"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Analysis Results:\n{json.dumps(filtered_data, indent=2)}"

@app.get("/datasets")
async def list_datasets():
    """List all uploaded datasets"""
    return {
        "datasets": [
            {
                "id": dataset_id,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": df.columns.tolist()
            }
            for dataset_id, df in datasets.items()
        ]
    }

@app.delete("/dataset/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """Delete a dataset"""
    if dataset_id in datasets:
        del datasets[dataset_id]
        return {"message": "Dataset deleted"}
    raise HTTPException(status_code=404, detail="Dataset not found")

if __name__ == "__main__":
    import uvicorn
    
    # Use relative paths (works on Render and locally)
    car_sales_path = "assets/docs/Car Sales.xlsx"
    insurance_path = "assets/docs/insurance_policies_data.xlsx"
    
    # Load default datasets for testing
    if os.path.exists(car_sales_path):
        try:
            df = pd.read_excel(car_sales_path)
            datasets["car_sales"] = df
            print(f"✓ Loaded Car Sales dataset: {len(df)} rows × {len(df.columns)} columns")
        except Exception as e:
            print(f"Error loading Car Sales: {e}")
    
    if os.path.exists(insurance_path):
        try:
            df = pd.read_excel(insurance_path)
            datasets["insurance"] = df
            print(f"✓ Loaded Insurance dataset: {len(df)} rows × {len(df.columns)} columns")
        except Exception as e:
            print(f"Error loading Insurance: {e}")
    
    # Serve static files (HTML, CSS, JS) from the project root
    app.mount("/", StaticFiles(directory=".", html=True), name="static")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)