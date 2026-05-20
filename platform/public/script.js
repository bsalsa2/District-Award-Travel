const searchForm = document.getElementById('search-form');
const resultsSection = document.getElementById('results-section');

const redemptionRates = {
    'American Airlines': {
        'economy': 25000,
        'premium-economy': 40000,
        'business': 60000,
        'first': 100000
    },
    'Delta Air Lines': {
        'economy': 30000,
        'premium-economy': 50000,
        'business': 80000,
        'first': 120000
    },
    'United Airlines': {
        'economy': 20000,
        'premium-economy': 35000,
        'business': 55000,
        'first': 90000
    },
    'Alaska Airlines': {
        'economy': 25000,
        'premium-economy': 40000,
        'business': 60000,
        'first': 100000
    },
    'Southwest Airlines': {
        'economy': 20000,
        'premium-economy': 35000,
        'business': 55000,
        'first': 90000
    },
    'JetBlue Airways': {
        'economy': 25000,
        'premium-economy': 40000,
        'business': 60000,
        'first': 100000
    },
    'Spirit Airlines': {
        'economy': 20000,
        'premium-economy': 35000,
        'business': 55000,
        'first': 90000
    },
    'Frontier Airlines': {
        'economy': 25000,
        'premium-economy': 40000,
        'business': 60000,
        'first': 100000
    },
    'Hawaiian Airlines': {
        'economy': 30000,
        'premium-economy': 50000,
        'business': 80000,
        'first': 120000
    },
    'Allegiant Air': {
        'economy': 20000,
        'premium-economy': 35000,
        'business': 55000,
        'first': 90000
    },
    'Sun Country Airlines': {
        'economy': 25000,
        'premium-economy': 40000,
        'business': 60000,
        'first': 100000
    },
    'Silver Airways': {
        'economy': 20000,
        'premium-economy': 35000,
        'business': 55000,
        'first': 90000
    },
    'Cape Air': {
        'economy': 25000,
        'premium-economy': 40000,
        'business': 60000,
        'first': 100000
    },
    'Mokulele Airlines': {
        'economy': 20000,
        'premium-economy': 35000,
        'business': 55000,
        'first': 90000
    },
    'PenAir': {
        'economy': 25000,
        'premium-economy': 40000,
        'business': 60000,
        'first': 100000
    },
    'Grant Aviation': {
        'economy': 20000,
        'premium-economy': 35000,
        'business': 55000,
        'first': 90000
    },
    'Ravn Alaska': {
        'economy': 25000,
        'premium-economy': 40000,
        'business': 60000,
        'first': 100000
    },
    'Yakutat Air': {
        'economy': 20000,
        'premium-economy': 35000,
        'business': 55000,
        'first': 90000
    }
};

searchForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const originAirport = document.getElementById('origin-airport').value;
    const destinationAirport = document.getElementById('destination-airport').value;
    const cabinClass = document.getElementById('cabin-class').value;

    const results = calculateResults(originAirport, destinationAirport, cabinClass);
    displayResults(results);
});

function calculateResults(originAirport, destinationAirport, cabinClass) {
    const results = [];
    for (const airline in redemptionRates) {
        const milesRequired = redemptionRates[airline][cabinClass];
        const cashEquivalent = milesRequired * 0.02; // assuming 2 cents per mile
        const cppRating = cashEquivalent / milesRequired;
        let verdict;
        if (cppRating > 0.05) {
            verdict = 'EXCELLENT';
        } else if (cppRating > 0.03) {
            verdict = 'GOOD';
        } else if (cppRating > 0.01) {
            verdict = 'FAIR';
        } else {
            verdict = 'SKIP';
        }
        results.push({
            airline,
            milesRequired,
            cashEquivalent,
            cppRating,
            verdict
        });
    }
    return results;
}

function displayResults(results) {
    const resultsHtml = results.map((result) => {
        return `
            <div>
                <h2>${result.airline}</h2>
                <p>Miles Required: ${result.milesRequired}</p>
                <p>Cash Equivalent: $${result.cashEquivalent.toFixed(2)}</p>
                <p>CPP Rating: ${result.cppRating.toFixed(4)}</p>
                <p>Verdict: ${result.verdict}</p>
            </div>
        `;
    }).join('');
    resultsSection.innerHTML = resultsHtml;
}

NEW_TASKS:
