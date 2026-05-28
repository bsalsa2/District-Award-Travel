fetch('/dashboard')
    .then(response => response.text())
    .then(data => {
        const recommendationsElement = document.querySelector('.recommendations');
        recommendationsElement.innerHTML = data;
    });
