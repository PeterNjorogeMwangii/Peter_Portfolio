from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
from groq import Groq
from dotenv import load_dotenv
import io
import os
from typing import List, Dict, Any

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

# Store uploaded datasets in memory (use database in production)
datasets: Dict[str, pd.DataFrame] = {}

class QueryRequest(BaseModel):
    dataset_id: str
    question: str
    conversation_history: List[Dict[str, str]] = []

class AnalysisResponse(BaseModel):
    answer: str
    dataset_info: Dict[str, Any] = None

@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)):
    """Upload and parse CSV or Excel file"""
    try:
        # Read file content
        contents = await file.read()
        
        # Parse based on file extension
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        elif file.filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise ValueError("Unsupported file format. Use CSV or Excel files.")
        
        # Generate dataset ID
        dataset_id = f"dataset_{len(datasets)}"
        datasets[dataset_id] = df
        
        # Get basic info
        info = {
            "dataset_id": dataset_id,
            "rows": len(df),
            "columns": len(df.columns),
            "column_names": df.columns.tolist(),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "sample": df.head(5).to_dict(orient='records')
        }
        
        return info
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing CSV: {str(e)}")

@app.post("/query", response_model=AnalysisResponse)
async def query_dataset(request: QueryRequest):
    """Query dataset with natural language"""
    
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = datasets[request.dataset_id]
    
    # Prepare dataset summary
    summary = get_dataset_summary(df)
    
    # Build prompt for Claude
    prompt = build_analysis_prompt(df, request.question, summary)
    
    # Call Groq API
    try:
        # Build messages from conversation history
        messages = []
        for msg in request.conversation_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add current question
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        
        return AnalysisResponse(
            answer=answer,
            dataset_info={
                "rows": len(df),
                "columns": len(df.columns)
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling AI: {str(e)}")

def get_dataset_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Generate comprehensive dataset summary"""
    summary = {
        "shape": df.shape,
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "missing_values": df.isnull().sum().to_dict(),
        "numeric_stats": {},
        "categorical_info": {}
    }
    
    # Numeric columns statistics
    numeric_cols = df.select_dtypes(include=['number']).columns
    for col in numeric_cols:
        summary["numeric_stats"][col] = {
            "mean": float(df[col].mean()),
            "median": float(df[col].median()),
            "std": float(df[col].std()),
            "min": float(df[col].min()),
            "max": float(df[col].max())
        }
    
    # Categorical columns info
    categorical_cols = df.select_dtypes(include=['object']).columns
    for col in categorical_cols:
        value_counts = df[col].value_counts().head(10)
        summary["categorical_info"][col] = {
            "unique_values": int(df[col].nunique()),
            "top_values": value_counts.to_dict()
        }
    
    return summary

def build_analysis_prompt(df: pd.DataFrame, question: str, summary: Dict[str, Any]) -> str:
    """Build prompt for Claude with dataset context"""
    
    # Sample data for context
    sample_data = df.head(10).to_string()
    
    prompt = f"""You are an expert data analyst. Analyze the following dataset and answer the user's question.

Dataset Information:
- Shape: {summary['shape'][0]} rows × {summary['shape'][1]} columns
- Columns: {', '.join(summary['columns'])}
- Data types: {summary['dtypes']}

Numeric Statistics:
{format_dict(summary['numeric_stats'])}

Categorical Information:
{format_dict(summary['categorical_info'])}

Sample Data (first 10 rows):
{sample_data}

User Question: {question}

Provide a clear, detailed analysis. If you need to perform calculations, show your reasoning. If you recommend visualizations, describe what should be plotted and why."""

    return prompt

def format_dict(d: Dict[str, Any], indent: int = 0) -> str:
    """Format dictionary for readable output"""
    lines = []
    for key, value in d.items():
        if isinstance(value, dict):
            lines.append("  " * indent + f"{key}:")
            lines.append(format_dict(value, indent + 1))
        else:
            lines.append("  " * indent + f"{key}: {value}")
    return "\n".join(lines)

@app.get("/datasets")
async def list_datasets():
    """List all uploaded datasets"""
    return {
        "datasets": [
            {
                "id": dataset_id,
                "rows": len(df),
                "columns": len(df.columns)
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
    
    # Optional: Load a default dataset on startup
    file_path = r"C:\Users\Admin\Desktop\Power BI Projects\bi-portfolio\assets\docs\insurance_policies_data.xlsx"
    if os.path.exists(file_path):
        try:
            df = pd.read_excel(file_path)
            datasets["default_insurance"] = df
            print(f"Loaded default dataset: {len(df)} rows, {len(df.columns)} columns")
            print(f"Columns: {', '.join(df.columns.tolist())}")
            print("\n--- Sample Query ---")
            
            # Run a sample query
            summary = get_dataset_summary(df)
            sample_question = "Which car make has the highest claim amount and what insights or recommendations can you provide?"
            
            # Create a more concise prompt with all relevant distributions
            categorical_distributions = {}
            for col in df.select_dtypes(include=['object']).columns:
                categorical_distributions[col] = df[col].value_counts().head(10).to_dict()
            
            sample_prompt = f"""You are a data analyst. Answer concisely and directly.

Dataset has {len(df)} rows and columns: {', '.join(df.columns.tolist())}

Categorical Data Distributions:
{format_dict(categorical_distributions)}

Question: {sample_question}

Provide a direct answer with the number, then a brief 1-2 sentence explanation if needed."""
            
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": sample_prompt}],
                max_tokens=200,
                temperature=0.3
            )
            
            print(f"Question: {sample_question}")
            print(f"Answer: {response.choices[0].message.content}\n")
            
        except Exception as e:
            print(f"Could not load default dataset: {e}")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)