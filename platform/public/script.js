const form = document.getElementById('user-form');
const submitBtn = document.getElementById('submit-btn');
const predictionDiv = document.getElementById('prediction');

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;
    const preferences = document.getElementById('preferences').value;

    const response = await fetch('/predict', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ name, email, preferences })
    });

    const prediction = await response.json();
    predictionDiv.innerText = `Prediction: ${prediction}`;
});
