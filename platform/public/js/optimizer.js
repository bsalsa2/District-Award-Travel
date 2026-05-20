class RouteOptimizer {
    constructor() {
        this.apiBaseUrl = window.location.hostname === 'localhost' ?
            'http://localhost:8000/api' : '/api';
        this.initEventListeners();
    }

    initEventListeners() {
        document.addEventListener('citySelected', (e) => {
            const city = e.detail.city;
            const input = document.getElementById('departure');
            if (!input.value) {
                input.value = city;
            } else {
                document.getElementById('destination').value = city;
            }
        });

        document.addEventListener('awardOptionSelected', (e) => {
            const index = e.detail.index;
            this.handleAwardOptionSelected(index);
        });

        document.getElementById('optimize-btn').addEventListener('click', () => {
            this.optimizeRoute();
        });
    }

    async optimizeRoute() {
        const departure = document.getElementById('departure').value.trim();
        const destination = document.getElementById('destination').value.trim();
        const departureDate = document.getElementById('departure-date').value;
        const returnDate = document.getElementById('return-date').value;

        if (!departure || !destination) {
            alert('Please enter both departure and destination');
            return;
        }

        try {
            // Show loading state
            const button = document.getElementById('optimize-btn');
            const originalText = button.textContent;
            button.textContent = 'Optimizing...';
            button.disabled = true;

            // Call backend API
            const response = await fetch(`${this.apiBaseUrl}/optimize-route`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    departure,
                    destination,
                    departure_date: departureDate,
                    return_date: returnDate
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // Update UI
            window.awardGlobe.updateFlightPaths(data.routes);
            window.awardGlobe.updateAwardOptions(data.award_options);
            window.awardGlobe.updateAISuggestions(data.ai_suggestions);

            // Update collaboration panel if needed
            if (data.collaborators && data.collaborators.length > 0) {
                this.updateCollaboratorsUI(data.collaborators);
            }

        } catch (error) {
            console.error('Error optimizing route:', error);
            alert('Failed to optimize route. Please try again.');
        } finally {
            button.textContent = originalText;
            button.disabled = false;
        }
    }

    async handleAwardOptionSelected(index) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/get-award-details`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ index })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            this.showAwardDetails(data);
        } catch (error) {
            console.error('Error fetching award details:', error);
        }
    }

    showAwardDetails(details) {
        alert(`Award Details:\n\n` +
              `Airline: ${details.airline}\n` +
              `Flight: ${details.flight_number}\n` +
              `Departure: ${details.departure.city} at ${details.departure.time}\n` +
              `Arrival: ${details.destination.city} at ${details.destination.time}\n` +
              `Points: ${details.points}\n` +
              `Cabin: ${details.cabin}\n` +
              `Duration: ${details.duration}\n` +
              `Fare Class: ${details.fare_class}`);
    }

    async updateCollaboratorsUI(collaborators) {
        const panel = document.getElementById('collaboration-panel');
        panel.style.display = 'block';

        window.awardGlobe.updateCollaborators(collaborators);
    }
}

// Initialize optimizer
document.addEventListener('DOMContentLoaded', () => {
    window.routeOptimizer = new RouteOptimizer();
});
