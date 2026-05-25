const form = document.getElementById("flight-form");
const submitButton = document.getElementById("submit-button");
const recommendedFlightsDiv = document.getElementById("recommended-flights");

form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const origin = document.getElementById("origin").value;
    const destination = document.getElementById("destination").value;
    const departureDate = document.getElementById("departure-date").value;

    const response = await fetch("/api/recommended-flights", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            origin,
            destination,
            departureDate
        })
    });

    const recommendedFlights = await response.json();
    recommendedFlightsDiv.innerHTML = "";
    recommendedFlights.forEach(flight => {
        const flightDiv = document.createElement("div");
        flightDiv.innerHTML = `
            <h2>Flight ${flight.flight_number}</h2>
            <p>Departure: ${flight.departure}</p>
            <p>Destination: ${flight.destination}</p>
            <p>Departure Date: ${flight.departure_date}</p>
            <p>Price: ${flight.price}</p>
            <p>Availability: ${flight.availability}</p>
        `;
        recommendedFlightsDiv.appendChild(flightDiv);
    });
});
