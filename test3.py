from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
    
    # Step 1: Generate Python code to answer the question
    code = generate_analysis_code(df, request.question)
    
    print(f"\n{'='*80}")
    print("GENERATED CODE:")
    print(code)
    print('='*80)
    
    # Step 2: Execute the generated code
    execution_result = execute_code_safely(df, code)
    
    print(f"\nEXECUTION RESULT:")
    print(json.dumps(execution_result, indent=2))
    print('='*80)
    
    # Step 3: Generate natural language explanation
    explanation = generate_explanation(request.question, code, execution_result)
    
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
        "sample_data": convert_to_serializable(df.head(3).to_dict(orient='records')),  # ← Fixed
        "numeric_columns": df.select_dtypes(include=['number']).columns.tolist(),
        "categorical_columns": df.select_dtypes(include=['object']).columns.tolist()
    }
    
    # Add value examples for categorical columns
    categorical_examples = {}
    for col in schema_info["categorical_columns"][:5]:  # Limit to first 5
        categorical_examples[col] = df[col].value_counts().head(5).to_dict()
    
    prompt = f"""You are a Python data analysis code generator. Generate ONLY executable Python code to answer the user's question.

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
3. Handle data cleaning (strip whitespace, convert to lowercase for matching, handle data types)
4. Store ALL results in a dictionary called 'result'
5. Include the actual numbers, counts, and any relevant breakdowns
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
        
        # Clean up the code - remove markdown blocks if present
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

def generate_explanation(question: str, code: str, execution_result: Dict[str, Any]) -> str:
    """Generate natural language explanation of the results"""
    
    if execution_result["status"] == "error":
        return f"Error executing analysis: {execution_result['error']}\n\nPlease try rephrasing your question."
    
    # Filter out verbose categorical counts from results
    filtered_data = execution_result['data'].copy()
    
    # Remove detailed count breakdowns - keep only summary stats
    keys_to_remove = [k for k in filtered_data.keys() if 'Count' in k or 'Distribution' in k]
    for key in keys_to_remove:
        if isinstance(filtered_data.get(key), dict):
            # Replace with summary instead of full breakdown
            count_dict = filtered_data[key]
            filtered_data[key] = {
                "total_categories": len(count_dict),
                "summary": f"Multiple categories - see dashboard for details"
            }
    
    prompt = f"""You are a professional data analyst presenting findings. Generate a clear, concise explanation of the analysis results.

User Question: {question}

Execution Results Summary:
{json.dumps(filtered_data, indent=2)}

Instructions:
1. Start with the DIRECT ANSWER using exact numbers from the results
2. Highlight the KEY INSIGHTS and TRENDS (not raw counts)
3. Format large numbers with commas (e.g., 871,049.12)
4. Focus on what the data MEANS, not just the numbers
5. For categorical data, mention the diversity but skip listing all values
6. Be professional, conversational, and action-oriented
7. Provide 3-5 key insights maximum

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
        # Fallback to raw results if AI fails
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
    
    # Load default dataset for testing
    file_path = r"C:\Users\Admin\Desktop\Power BI Projects\bi-portfolio\assets\docs\Car Sales.xlsx"
    if os.path.exists(file_path):
        try:
            df = pd.read_excel(file_path)
            datasets["default_insurance"] = df
            print(f"✓ Loaded dataset: {len(df)} rows × {len(df.columns)} columns")
            print(f"Columns: {', '.join(df.columns.tolist())}\n")
            
            # Test question
            question = "what is the total amount of revenue generated from the sales of cars?"
            
            print(f"{'='*80}")
            print(f"Question: {question}")
            
            # Generate code
            code = generate_analysis_code(df, question)
            
            # Execute code
            execution_result = execute_code_safely(df, code)
            
            # Generate explanation
            explanation = generate_explanation(question, code, execution_result)
            
            print(f"\nAnswer:\n{explanation}")
            
        except Exception as e:
            print(f"Error: {e}")
            traceback.print_exc()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)