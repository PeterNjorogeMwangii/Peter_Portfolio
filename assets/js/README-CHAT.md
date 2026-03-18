# LLM Chat Feature Setup Guide

## Overview
The chat feature allows users to interact with your dashboards using natural language. It's powered by OpenAI's API (configurable to other LLM providers).

## Setup Instructions

### 1. Get an OpenAI API Key
1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Create a new API key
4. Copy the key (you'll only see it once!)

### 2. Configure the API Key
Open `assets/js/chat-config.js` and replace `YOUR_API_KEY_HERE` with your actual API key:

```javascript
const chatConfig = {
  apiKey: 'sk-your-actual-api-key-here',
  // ... rest of config
};
```

### 3. Customize Dashboard Context (Optional)
In `chat-config.js`, update the `dashboardContext` object with your dashboard-specific information:
- `name`: Dashboard name
- `domain`: Business domain (e.g., "Retail Sales Analytics")
- `businessProblem`: Brief description
- `kpis`: Key metrics tracked
- `dataModel`: Data modeling approach
- `insights`: Key findings

### 4. Test the Chat
1. Open your dashboard page in a browser
2. Click the "💬 Ask AI" button in the bottom-right corner
3. Try asking questions like:
   - "What are the key KPIs in this dashboard?"
   - "Explain the business problem this dashboard solves"
   - "What insights can you share about the data?"

## Security Notes

⚠️ **IMPORTANT**: Never commit your API key to a public repository!

- Add `assets/js/chat-config.js` to `.gitignore` if it contains your real API key
- Or use environment variables for production deployments
- Consider using a backend proxy to hide your API key from the frontend

## Cost Considerations

- **gpt-4o-mini** (default): ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
- **gpt-4o**: Higher quality but more expensive
- Monitor usage at https://platform.openai.com/usage

## Alternative LLM Providers

To use a different LLM provider (e.g., Anthropic Claude, local models), modify:
1. `apiEndpoint` in `chat-config.js`
2. The API request format in `chat.js` (if needed)

## Troubleshooting

**Chat doesn't appear:**
- Check browser console for errors
- Ensure `chat-config.js` and `chat.js` are loaded
- Verify file paths are correct

**API errors:**
- Verify your API key is correct
- Check your OpenAI account has credits
- Ensure API endpoint URL is correct

**Chat responses are slow:**
- Try using `gpt-4o-mini` instead of `gpt-4o`
- Reduce `max_tokens` in `chat.js`
