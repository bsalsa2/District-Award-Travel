class CollaborationManager {
    constructor() {
        this.apiBaseUrl = window.location.hostname === 'localhost' ?
            'http://localhost:8000/api' : '/api';
        this.socket = null;
        this.userId = this.generateUserId();
        this.initEventListeners();
        this.connectWebSocket();
    }

    generateUserId() {
        return 'user-' + Math.random().toString(36).substr(2, 9);
    }

    initEventListeners() {
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('share-itinerary-btn').addEventListener('click', () => {
                this.shareItinerary();
            });

            document.getElementById('add-collaborator-btn').addEventListener('click', () => {
                this.addCollaborator();
            });

            document.addEventListener('removeCollaborator', (e) => {
                const email = e.detail.email;
                this.removeCollaborator(email);
            });
        });
    }

    connectWebSocket() {
        // In production, use wss://
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.hostname;
        const port = window.location.port || (window.location.protocol === 'https:' ? 443 : 80);

        this.socket = new WebSocket(`${protocol}//${host}:${port}/ws/collaboration`);

        this.socket.onopen = () => {
            console.log('WebSocket connection established');
            this.sendMessage({
                type: 'join',
                userId: this.userId,
                userName: 'Current User'
            });
        };

        this.socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };

        this.socket.onclose = () => {
            console.log('WebSocket connection closed');
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    sendMessage(message) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(message));
        }
    }

    handleMessage(message) {
        switch (message.type) {
            case 'collaborators_update':
                this.updateCollaboratorsUI(message.collaborators);
                break;
            case 'route_update':
                this.handleRouteUpdate(message.route);
                break;
            case 'award_options_update':
                this.handleAwardOptionsUpdate(message.options);
                break;
            case 'ai_suggestions_update':
                this.handleAISuggestionsUpdate(message.suggestions);
                break;
        }
    }

    shareItinerary() {
        const email = prompt('Enter email to share itinerary with:');
        if (email) {
            this.sendMessage({
                type: 'share_itinerary',
                from: this.userId,
                to: email,
                userId: this.userId
            });
            alert('Itinerary shared! Collaborators can now join.');
        }
    }

    addCollaborator() {
        const email = document.getElementById('collaborator-email').value.trim();
        if (email) {
            this.sendMessage({
                type: 'add_collaborator',
                from: this.userId,
                to: email,
                userId: this.userId
            });
            document.getElementById('collaborator-email').value = '';
        }
    }

    removeCollaborator(email) {
        this.sendMessage({
            type: 'remove_collaborator',
            from: this.userId,
            to: email,
            userId: this.userId
        });
    }

    updateCollaboratorsUI(collaborators) {
        window.awardGlobe.updateCollaborators(collaborators);
    }

    handleRouteUpdate(route) {
        // Update the globe with new route
        window.awardGlobe.updateFlightPaths([route]);
    }

    handleAwardOptionsUpdate(options) {
        window.awardGlobe.updateAwardOptions(options);
    }

    handleAISuggestionsUpdate(suggestions) {
        window.awardGlobe.updateAISuggestions(suggestions);
    }
}

// Initialize collaboration manager
document.addEventListener('DOMContentLoaded', () => {
    window.collaborationManager = new CollaborationManager();
});
