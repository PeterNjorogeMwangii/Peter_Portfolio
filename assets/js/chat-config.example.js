// Chat Configuration Template
// Copy this file to chat-config.js and add your API key
// DO NOT commit chat-config.js to version control

const chatConfig = {
  // Your OpenAI API key (keep this secure - don't commit to public repos)
  // Get your API key from: https://platform.openai.com/api-keys
  apiKey: 'YOUR_API_KEY_HERE',
  
  // API endpoint (default: OpenAI)
  apiEndpoint: 'https://api.openai.com/v1/chat/completions',
  
  // Model to use (gpt-4o-mini is cost-effective, gpt-4o for better quality)
  model: 'gpt-4o-mini',
  
  // Dashboard-specific context (customize per dashboard)
  dashboardContext: {
    name: 'Sales Data Modelling Dashboard',
    domain: 'Retail Sales Analytics',
    businessProblem: 'The business required a centralized view of sales performance to track revenue, product performance, regional trends, and time-based patterns.',
    kpis: 'Total Revenue, Quantity Sold, Average Selling Price, Profit Contribution, YoY Growth, Market Share',
    dataModel: 'Star schema with central sales fact table and dimension tables (Date, Product, Customer, Region). DAX measures for Revenue, YoY Growth, Market Share, and Rank.',
    insights: 'Top-performing products drive disproportionate revenue share. Strong Q3 seasonality. High-volume products with low margins suggest pricing issues. Significant regional performance variation.'
  }
};
