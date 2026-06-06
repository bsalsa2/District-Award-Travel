import { fetch } from 'node-fetch';

class AwardFlightRecommender {
    constructor() {
        this.apiUrl = '/api/recommend_flights';
    }

    async getRecommendations(userInput) {
        const response = await fetch(this.apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(userInput)
        });
        const data = await response.json();
        return data;
    }

    renderRecommendations(recommendations) {
        const recommendationsHtml = recommendations.map(recommendation => {
            return `
                <div>
                    <h2>${recommendation.flight_number}</h2>
                    <p>Departure: ${recommendation.departure}</p>
                    <p>Arrival: ${recommendation.arrival}</p>
                </div>
            `;
        }).join('');
        document.getElementById('recommendations').innerHTML = recommendationsHtml;
    }
}

const recommender = new AwardFlightRecommender();
document.getElementById('submit-button').addEventListener('click', async () => {
    const userInput = {
        departure: document.getElementById('departure').value,
        arrival: document.getElementById('arrival').value,
        travel_dates: document.getElementById('travel_dates').value
    };
    const recommendations = await recommender.getRecommendations(userInput);
    recommender.renderRecommendations(recommendations);
});
