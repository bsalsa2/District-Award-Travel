// Update UTC clock every second
setInterval(() => {
    const utcClock = document.getElementById('utc-clock');
    const date = new Date();
    const hours = date.getUTCHours().toString().padStart(2, '0');
    const minutes = date.getUTCMinutes().toString().padStart(2, '0');
    const seconds = date.getUTCSeconds().toString().padStart(2, '0');
    utcClock.textContent = `${hours}:${minutes}:${seconds}`;
}, 1000);

// Mock data for booking pipeline and award search results
const bookingPipelineData = [
    { client: 'John Doe', route: 'New York - Los Angeles', cabin: 'Business', miles: 2500, status: 'Pending' },
    { client: 'Jane Doe', route: 'Chicago - New York', cabin: 'Economy', miles: 800, status: 'Confirmed' },
];

const awardSearchResultsData = [
    { route: 'New York - Los Angeles', cabin: 'Business', miles: 2500, valueRating: 8 },
    { route: 'Chicago - New York', cabin: 'Economy', miles: 800, valueRating: 6 },
];

// Update booking pipeline table
const bookingPipelineTable = document.getElementById('booking-pipeline-table');
bookingPipelineData.forEach((data) => {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>${data.client}</td>
        <td>${data.route}</td>
        <td>${data.cabin}</td>
        <td>${data.miles}</td>
        <td>${data.status}</td>
    `;
    bookingPipelineTable.appendChild(row);
});

// Update award search results table
const awardSearchResultsTable = document.getElementById('award-search-results-table');
awardSearchResultsData.forEach((data) => {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td>${data.route}</td>
        <td>${data.cabin}</td>
        <td>${data.miles}</td>
        <td>${data.valueRating}/10</td>
    `;
    awardSearchResultsTable.appendChild(row);
});
