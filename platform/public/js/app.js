class AwardTravelAssistant {
    constructor() {
        this.clientId = this.generateClientId();
        this.websocket = null;
        this.isConnected = false;
        this.userPreferences = {};
        this.emotionState = { score: 0.5, emotion: 'neutral' };

        this.initElements();
        this.setupEventListeners();
        this.connectWebSocket();
    }

    generateClientId() {
        return 'client_' + Math.random().toString(36).substr(2, 9);
    }

    initElements() {
        this.userInput = document.getElementById('user-input');
        this.sendButton = document.getElementById('send-button');
        this.chatMessages = document.getElementById('chat-messages');
        this.preferencesList = document.getElementById('preferences-list');
        this.recommendationsList = document.getElementById('recommendations-list');
        this.sentimentBar = document.getElementById('sentiment-bar');
        this.sentimentValue = document.getElementById('sentiment-value');
        this.emotionIndicator = document.getElementById('emotion-indicator');
        this.emotionText = document.getElementById('emotion-text');
        this.userIdElement = document.getElementById('user-id');
    }

    setupEventListeners() {
        // Send message on button click
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // Send message on Enter key
        this.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        this.userInput.addEventListener('input', () => {
            this.userInput.style.height = 'auto';
            this.userInput.style.height = (this.userInput.scrollHeight) + 'px';
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = window.location.port || (window.location.protocol === 'https:' ? 443 : 8000);

        this.websocket = new WebSocket(`${protocol}//${host}:${port}/ws/${this.clientId}`);

        this.websocket.onopen = () => {
            this.isConnected = true;
            this.userIdElement.textContent = `Guest (${this.clientId.substring(0, 8)})`;
            this.addSystemMessage('Connected to Award Travel Assistant ✅');
            console.log('WebSocket connection established');
        };

        this.websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleAssistantResponse(data);
        };

        this.websocket.onclose = () => {
            this.isConnected = false;
            this.addSystemMessage('Connection lost. Attempting to reconnect... ⚠️');
            console.log('WebSocket connection closed');
            this.reconnect();
        };

        this.websocket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    reconnect() {
        setTimeout(() => {
            this.connectWebSocket();
        }, 3000);
    }

    sendMessage() {
        const message = this.userInput.value.trim();
        if (!message || !this.isConnected) return;

        // Add user message to chat
        this.addUserMessage(message);

        // Clear input
        this.userInput.value = '';
        this.userInput.style.height = '50px';

        // Send to server
        this.websocket.send(JSON.stringify({
            message: message,
            timestamp: new Date().toISOString()
        }));
    }

    addUserMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message-bubble user';
        messageElement.innerHTML = `
            <p>${message}</p>
            <span class="message-time">${this.formatTime(new Date())}</span>
        `;
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    addAssistantMessage(message, recommendations = [], sentiment = null) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message-bubble assistant';

        let html = `<p>${message}</p>`;
        html += `<span class="message-time">${this.formatTime(new Date())}</span>`;

        if (recommendations.length > 0) {
            html += '<div class="recommendations-preview">';
            html += '<h4>Recommendations:</h4>';
            html += '<ul>';
            recommendations.slice(0, 3).forEach(rec => {
                html += `<li>${rec}</li>`;
            });
            if (recommendations.length > 3) {
                html += `<li>+${recommendations.length - 3} more</li>`;
            }
            html += '</ul>';
            html += '</div>';
        }

        messageElement.innerHTML = html;
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();

        // Update UI with sentiment
        if (sentiment) {
            this.updateSentiment(sentiment);
        }
    }

    addSystemMessage(message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'message-bubble assistant system-message';
        messageElement.innerHTML = `
            <p><strong>System:</strong> ${message}</p>
            <span class="message-time">${this.formatTime(new Date())}</span>
        `;
        this.chatMessages.appendChild(messageElement);
        this.scrollToBottom();
    }

    handleAssistantResponse(data) {
        const { response, recommendations, sentiment, preferences } = data;

        // Update preferences
        if (preferences && Object.keys(preferences).length > 0) {
            this.updatePreferences(preferences);
        }

        // Update sentiment
        if (sentiment) {
            this.updateSentiment(sentiment);
        }

        // Add assistant response
        this.addAssistantMessage(response, recommendations);

        // Update recommendations list
        if (recommendations && recommendations.length > 0) {
            this.updateRecommendations(recommendations);
        }
    }

    updatePreferences(preferences) {
        this.userPreferences = { ...this.userPreferences, ...preferences };
        this.renderPreferences();
    }

    renderPreferences() {
        if (Object.keys(this.userPreferences).length === 0) {
            this.preferencesList.innerHTML = '<p>No preferences detected yet.</p>';
            return;
        }

        this.preferencesList.innerHTML = '';
        for (const [key, value] of Object.entries(this.userPreferences)) {
            const item = document.createElement('div');
            item.className = 'preferences-item';
            item.innerHTML = `
                <span><strong>${key}:</strong> ${value}</span>
            `;
            this.preferencesList.appendChild(item);
        }
    }

    updateRecommendations(recommendations) {
        if (!recommendations || recommendations.length === 0) {
            this.recommendationsList.innerHTML = '<p>No recommendations yet. Start a conversation!</p>';
            return;
        }

        this.recommendationsList.innerHTML = '';
        recommendations.slice(0, 5).forEach((rec, index) => {
            const item = document.createElement('div');
            item.className = 'recommendation-item';
            item.innerHTML = `
                <span>${index + 1}. ${rec}</span>
            `;
            this.recommendationsList.appendChild(item);
        });
    }

    updateSentiment(sentiment) {
        this.emotionState = sentiment;

        // Update sentiment bar
        const barWidth = Math.round(sentiment.score * 100);
        this.sentimentBar.style.width = `${barWidth}%`;

        // Update sentiment value
        this.sentimentValue.textContent = `${barWidth}%`;

        // Update emotion indicator
        this.updateEmotionIndicator(sentiment.emotion);
    }

    updateEmotionIndicator(emotion) {
        this.emotionText.textContent = this.capitalize(emotion);

        // Remove all emotion classes
        this.emotionIndicator.className = 'emotion-indicator';

        // Add specific emotion class
        this.emotionIndicator.classList.add(`emotion-${emotion}`);

        // Set icon based on emotion
        const icon = this.emotionIndicator.querySelector('i');
        switch(emotion) {
            case 'happy':
                icon.className = 'fas fa-smile';
                icon.style.color = '#27ae60';
                break;
            case 'neutral':
                icon.className = 'fas fa-meh';
                icon.style.color = '#f39c12';
                break;
            case 'sad':
                icon.className = 'fas fa-frown';
                icon.style.color = '#e74c3c';
                break;
            default:
                icon.className = 'fas fa-smile';
                icon.style.color = '#3498db';
        }
    }

    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }

    formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new AwardTravelAssistant();
});
