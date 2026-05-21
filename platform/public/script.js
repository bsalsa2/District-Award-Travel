const form = document.getElementById('book-award-form');
const resultDiv = document.getElementById('result');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const userId = document.getElementById('user-id').value;
    const awardId = document.getElementById('award-id').value;
    const points = document.getElementById('points').value;

    try {
        const response = await fetch('/book_award', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ user_id: userId, award_id: awardId, points: points })
        });
        const data = await response.json();
        resultDiv.innerText = data.message;
    } catch (error) {
        resultDiv.innerText = error.message;
    }
});
