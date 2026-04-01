// LLM Chat Interface for Dashboard Q&A

class DashboardChat {
  constructor(config) {
    this.apiEndpoint = config.apiEndpoint || '/query';  // Changed to server endpoint
    this.dashboardContext = config.dashboardContext || {};
    this.isOpen = false;
    this.messages = [];
    
    this.init();
  }

  init() {
    this.createChatUI();
    this.attachEventListeners();
    this.addWelcomeMessage();
    this.toggleChat();  // Add this to open chat on load
  }

  createChatUI() {
    // Create chat button with modern design
    const chatButton = document.createElement('button');
    chatButton.id = 'chat-toggle-btn';
    chatButton.className = 'chat-toggle-btn';
    chatButton.innerHTML = `
      <svg class="chat-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
      </svg>
      <span class="chat-btn-text">Ask AI</span>
    `;
    document.body.appendChild(chatButton);

    // Create chat container
    const chatContainer = document.createElement('div');
    chatContainer.id = 'chat-container';
    chatContainer.className = 'chat-container';
    chatContainer.innerHTML = `
      <div class="chat-header">
        <div class="chat-header-content">
          <div class="chat-avatar chat-avatar-assistant">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
              <path d="M2 17l10 5 10-5"></path>
              <path d="M2 12l10 5 10-5"></path>
            </svg>
          </div>
          <div class="chat-header-text">
            <h3>Dashboard Assistant</h3>
            <span class="chat-status">Online</span>
          </div>
        </div>
        <button class="chat-close-btn" id="chat-close-btn" aria-label="Close chat">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="chat-messages" id="chat-messages"></div>
      <div class="chat-input-container">
        <div class="chat-input-wrapper">
          <input 
            type="text" 
            id="chat-input" 
            class="chat-input" 
            placeholder="Ask about the dashboard, insights, or data..."
            autocomplete="off"
          />
          <button id="chat-send-btn" class="chat-send-btn" aria-label="Send message">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </div>
      </div>
    `;
    document.body.appendChild(chatContainer);
  }

  attachEventListeners() {
    document.getElementById('chat-toggle-btn').addEventListener('click', () => this.toggleChat());
    document.getElementById('chat-close-btn').addEventListener('click', () => this.toggleChat());
    document.getElementById('chat-send-btn').addEventListener('click', () => this.sendMessage());
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
      if (e.key === 'Enter') this.sendMessage();
    });
  }

  toggleChat() {
    this.isOpen = !this.isOpen;
    const container = document.getElementById('chat-container');
    if (this.isOpen) {
      container.classList.add('chat-open');
      document.getElementById('chat-input').focus();
    } else {
      container.classList.remove('chat-open');
    }
  }

  addWelcomeMessage() {
    const welcomeMsg = `Hi! I'm your dashboard assistant. I can help you explore this dashboard by answering questions about:
• Key metrics and KPIs
• Data insights and trends
• Deep dives into specific areas
• Recommendations and analysis
• Any other dashboard-related queries

What would you like to know about this dashboard?`;
    this.addMessage('assistant', welcomeMsg);
  }

  async sendMessage() {
    const input = document.getElementById('chat-input');
    const userMessage = input.value.trim();
    
    if (!userMessage) return;
    
    // Clear input
    input.value = '';
    
    // Add user message to UI
    this.addMessage('user', userMessage);
    
    // Show loading
    const loadingId = this.addMessage('assistant', 'Thinking...', true);
    
    try {
      // Call server API
      const response = await this.callServerAPI(userMessage);
      
      // Remove loading message and add real response
      this.removeMessage(loadingId);
      this.addMessage('assistant', response);
      this.messages.push({ role: 'assistant', content: response });
      
    } catch (error) {
      this.removeMessage(loadingId);
      this.addMessage('assistant', `Sorry, I encountered an error: ${error.message}. Please check your server configuration.`);
      console.error('Chat error:', error);
    }
  }

  buildSystemPrompt() {
    const context = this.dashboardContext;
    
    return `You are a helpful assistant for a Power BI dashboard portfolio. You help users understand dashboards, business requirements, domain knowledge, and insights.

DASHBOARD CONTEXT:
- Dashboard Name: ${context.name || 'Sales Data Modelling Dashboard'}
- Domain: ${context.domain || 'Retail Sales Analytics'}
- Business Problem: ${context.businessProblem || 'Centralized view of sales performance across different car models, regions, colors, and body styles.'}
- Key KPIs: ${context.kpis || 'Total Sales, Cars Sold, Average Price, Year-over-Year growth'}
- Data Model: ${context.dataModel || 'Star schema with car_data as central fact table, Calendar dimension table'}
- Key Insights: ${context.insights || 'High-volume sales in Austin, premium vs mainstream segments, rolling forecasts'}

Your role:
1. Answer questions about the dashboard, business requirements, and domain context
2. Explain KPIs, metrics, and data modeling concepts
3. Reference actual data from the dataset when relevant
4. Provide insights and recommendations based on the dashboard context
5. Be concise, professional, and helpful

Keep responses clear and actionable.`;
  }

  async callServerAPI(question) {
    const datasetId = window.datasetId || 'car_sales';
    console.log('Using dataset_id:', datasetId);
    
    // Replace with your Render service URL
    const response = await fetch('https://peter-portfolio.onrender.com/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            dataset_id: datasetId,
            question: question,
            conversation_history: this.messages
        })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Server request failed');
    }

    const data = await response.json();
    return data.answer;
  }

  addMessage(role, content, isLoading = false) {
    const messagesContainer = document.getElementById('chat-messages');
    const messageId = `msg-${Date.now()}-${Math.random()}`;
    const messageDiv = document.createElement('div');
    messageDiv.id = messageId;
    messageDiv.className = `chat-message chat-message-${role}`;
    
    const avatar = role === 'user' 
      ? `<div class="chat-avatar chat-avatar-user">
           <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
             <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
             <circle cx="12" cy="7" r="4"></circle>
           </svg>
         </div>`
      : `<div class="chat-avatar chat-avatar-assistant">
           <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
             <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
             <path d="M2 17l10 5 10-5"></path>
             <path d="M2 12l10 5 10-5"></path>
           </svg>
         </div>`;
    
    if (isLoading) {
      messageDiv.innerHTML = `
        ${avatar}
        <div class="chat-message-content">
          <div class="chat-loading">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
          </div>
        </div>
      `;
    } else {
      messageDiv.innerHTML = `
        ${avatar}
        <div class="chat-message-content">
          <div class="chat-content">${this.formatMessage(content)}</div>
        </div>
      `;
    }
    
    messagesContainer.appendChild(messageDiv);
    
    // Smooth scroll to bottom
    setTimeout(() => {
      messagesContainer.scrollTo({
        top: messagesContainer.scrollHeight,
        behavior: 'smooth'
      });
    }, 100);
    
    return messageId;
  }

  removeMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) message.remove();
  }

  formatMessage(content) {
    // Convert markdown-like formatting to HTML
    let formatted = content
      // Bold text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      // Italic text
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      // Code blocks
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Bullet points
      .replace(/^[-•]\s(.+)$/gm, '<li>$1</li>')
      // Numbered lists
      .replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>')
      // Line breaks
      .replace(/\n\n/g, '</p><p>')
      .replace(/\n/g, '<br>');
    
    // Wrap list items in ul tags
    formatted = formatted.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // Wrap paragraphs
    if (!formatted.startsWith('<ul>') && !formatted.startsWith('<code>')) {
      formatted = `<p>${formatted}</p>`;
    }
    
    return formatted;
  }
}

// Initialize with hardcoded config (since /api/chat-config is removed)
document.addEventListener('DOMContentLoaded', () => {
  const config = {
    apiEndpoint: '/query',
    dashboardContext: {
      name: 'Sales Data Modelling Dashboard',
      domain: 'Retail Sales Analytics',
      businessProblem: 'Lack of centralized system to monitor and analyze sales performance across different car models, regions, colors, and body styles.',
      kpis: 'Total Sales, Cars Sold, Average Price, Year-over-Year growth',
      dataModel: 'Star schema with car_data as central fact table, Calendar dimension table',
      insights: 'High-volume sales in Austin, premium vs mainstream segments, rolling forecasts'
    }
  };
  new DashboardChat(config);
});

async function sendQuery(question) {
    const response = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            dataset_id: window.datasetId,  // Use the dataset ID set in the HTML
            question: question,
            conversation_history: []  // Add history if needed
        })
    });
    return response;
}