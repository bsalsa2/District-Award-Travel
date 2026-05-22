const searchForm = document.getElementById('search-form');
const searchInput = document.getElementById('search-input');
const searchButton = document.getElementById('search-button');
const searchResults = document.getElementById('search-results');

searchButton.addEventListener('click', async (e) => {
    e.preventDefault();
    const searchQuery = searchInput.value.trim();
    if (searchQuery) {
        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ query: searchQuery })
            });
            const data = await response.json();
            searchResults.innerHTML = '';
            data.forEach((result) => {
                const resultHTML = `
                    <div>
                        <h2>${result.destination}</h2>
                        <p>${result.description}</p>
                    </div>
                `;
                searchResults.insertAdjacentHTML('beforeend', resultHTML);
            });
        } catch (error) {
            console.error(error);
        }
    }
});
