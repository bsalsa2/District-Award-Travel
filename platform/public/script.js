const form = document.getElementById('book-travel-form');
const travelOptionsDiv = document.getElementById('travel-options');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const origin = document.getElementById('origin').value;
    const destination = document.getElementById('destination').value;
    const travelDate = document.getElementById('travel_date').value;

    const response = await fetch('/book_travel', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ origin, destination, travel_date: travelDate })
    });

    const data = await response.json();
    travelOptionsDiv.innerHTML = '';
    data.forEach(option => {
        const optionDiv = document.createElement('div');
        optionDiv.textContent = `Origin: ${option.origin}, Destination: ${option.destination}, Travel Date: ${option.travel_date}`;
        travelOptionsDiv.appendChild(optionDiv);
    });
});

fetch('/travel_options')
    .then(response => response.json())
    .then(data => {
        travelOptionsDiv.innerHTML = '';
        data.forEach(option => {
            const optionDiv = document.createElement('div');
            optionDiv.textContent = `Origin: ${option.origin}, Destination: ${option.destination}, Travel Date: ${option.travel_date}`;
            travelOptionsDiv.appendChild(optionDiv);
        });
    });
