const recommendationsList = document.getElementById('recommendations-list');
const searchForm = document.getElementById('search-form');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');

searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = searchInput.value.trim();
    if (query) {
        try {
            const response = await fetch(`http://localhost:8000/recommendations?query=${query}`);
            const data = await response.json();
            renderRecommendations(data);
        } catch (error) {
            console.error(error);
        }
    }
});

async function renderRecommendations(data) {
    const listItems = data.map((recommendation) => {
        return `<li>${recommendation.destination} - ${recommendation.airline}</li>`;
    }).join('');
    recommendationsList.innerHTML = listItems;
}

// Initialize with some default recommendations
fetch('http://localhost:8000/recommendations')
    .then((response) => response.json())
    .then((data) => renderRecommendations(data))
    .catch((error) => console.error(error));
