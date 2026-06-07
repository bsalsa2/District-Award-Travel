const search_bar = document.getElementById('search-bar');
const flight_list = document.getElementById('flight-list');

search_bar.addEventListener('input', async (e) => {
    const search_query = e.target.value;
    const response = await fetch(`/api/award-flights?search=${search_query}`);
    const data = await response.json();
    const flight_list_html = data.map((flight) => {
        return `
            <li>
                <h3>${flight.airline} ${flight.flight_number}</h3>
                <p>Departure: ${flight.departure_airport} (${flight.departure_date})</p>
                <p>Arrival: ${flight.arrival_airport} (${flight.arrival_date})</p>
                <p>Estimated Value: ${flight.estimated_value}</p>
                <a href="${flight.booking_link}">Book Now</a>
            </li>
        `;
    }).join('');
    flight_list.innerHTML = flight_list_html;
});
