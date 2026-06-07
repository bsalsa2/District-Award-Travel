fetch('/analytics')
    .then(response => response.json())
    .then(data => {
        const bookingTrendsList = document.getElementById('booking-trends-list');
        const revenueList = document.getElementById('revenue-list');
        const customerDemographicsList = document.getElementById('customer-demographics-list');

        data.booking_trends.forEach(bookingTrend => {
            const li = document.createElement('li');
            li.textContent = bookingTrend;
            bookingTrendsList.appendChild(li);
        });

        data.revenue.forEach(revenue => {
            const li = document.createElement('li');
            li.textContent = revenue;
            revenueList.appendChild(li);
        });

        data.customer_demographics.forEach(customerDemographic => {
            const li = document.createElement('li');
            li.textContent = customerDemographic;
            customerDemographicsList.appendChild(li);
        });
    });
