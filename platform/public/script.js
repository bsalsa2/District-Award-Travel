const awardRedemptionForm = document.getElementById('award-redemption-form');
const simulationResultsDiv = document.getElementById('simulation-results');

awardRedemptionForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const clientId = document.getElementById('client-id').value;
    const travelDates = document.getElementById('travel-dates').value;
    const destination = document.getElementById('destination').value;

    const response = await fetch('/simulate-redemption', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            client_id: clientId,
            travel_dates: [travelDates],
            destination: destination
        })
    });

    const simulationResults = await response.json();
    simulationResultsDiv.innerHTML = `
        <h3>Simulation Results</h3>
        <p>Client ID: ${simulationResults.client_id}</p>
        <p>Travel Dates: ${simulationResults.travel_dates.join(', ')}</p>
        <p>Destination: ${simulationResults.destination}</p>
        <p>Award Redemption Rate: ${simulationResults.award_redemption_rate}</p>
        <h4>Redemption Options</h4>
        <ul>
            ${simulationResults.redemption_options.map(option => `<li>${option.option} - ${option.points_required} points</li>`).join('')}
        </ul>
    `;
});
