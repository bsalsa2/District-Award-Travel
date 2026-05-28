const paymentForm = document.getElementById('payment-form');
const makePaymentButton = document.getElementById('make-payment');
const paymentStatusDiv = document.getElementById('payment-status');

makePaymentButton.addEventListener('click', async (e) => {
    e.preventDefault();

    const amount = document.getElementById('amount').value;
    const paymentMethod = document.getElementById('payment-method').value;

    try {
        const response = await fetch('/payment', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ amount, paymentMethod })
        });

        const data = await response.json();

        if (data.message === 'Payment successful') {
            paymentStatusDiv.innerHTML = 'Payment successful!';
        } else {
            paymentStatusDiv.innerHTML = data.message;
        }
    } catch (error) {
        paymentStatusDiv.innerHTML = error.message;
    }
});
