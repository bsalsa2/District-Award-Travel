import numpy as np

# Cabin multipliers
cabin_multipliers = {
    'Economy': 1.0,
    'Premium Economy': 1.5,
    'Business': 3.0,
    'First Class': 5.0
}

# Fuel surcharge penalty
fuel_surcharge_penalty = 0.1

# Lookup table of known good redemptions
known_good_redemptions = {
    ('United', 'Economy', 'New York to Los Angeles'): 1.5,
    ('American', 'Business', 'New York to London'): 3.5,
    ('Delta', 'First Class', 'New York to Tokyo'): 5.5
}

def calculate_cpp(program, miles_required, cabin, route, taxes_usd):
    # Calculate the cash equivalent value of the award flight
    cash_equivalent_usd = miles_required * 0.015  # Assume 1.5 cents per mile

    # Apply cabin multiplier
    cabin_multiplier = cabin_multipliers[cabin]
    cash_equivalent_usd *= cabin_multiplier

    # Apply fuel surcharge penalty
    fuel_surcharge_usd = taxes_usd * fuel_surcharge_penalty
    cash_equivalent_usd -= fuel_surcharge_usd

    # Check if the route is in the lookup table of known good redemptions
    if (program, cabin, route) in known_good_redemptions:
        known_good_redemption_cpp = known_good_redemptions[(program, cabin, route)]
        cpp = known_good_redemption_cpp
    else:
        # Calculate the cents per point (cpp) value
        cpp = (cash_equivalent_usd / miles_required) * 100

    return cpp, cash_equivalent_usd

def calculate_verdict(cpp):
    if cpp > 2.5:
        verdict = 'EXCELLENT'
    elif cpp > 1.5:
        verdict = 'GOOD'
    elif cpp > 0.5:
        verdict = 'FAIR'
    else:
        verdict = 'SKIP'

    return verdict

def calculate_explanation(verdict, cpp, cash_equivalent_usd):
    if verdict == 'EXCELLENT':
        explanation = f'This award flight is an excellent value, with a cpp of {cpp:.2f} and a cash equivalent value of ${cash_equivalent_usd:.2f}.'
    elif verdict == 'GOOD':
        explanation = f'This award flight is a good value, with a cpp of {cpp:.2f} and a cash equivalent value of ${cash_equivalent_usd:.2f}.'
    elif verdict == 'FAIR':
        explanation = f'This award flight is a fair value, with a cpp of {cpp:.2f} and a cash equivalent value of ${cash_equivalent_usd:.2f}.'
    else:
        explanation = f'This award flight is not a good value, with a cpp of {cpp:.2f} and a cash equivalent value of ${cash_equivalent_usd:.2f}.'

    return explanation

def award_valuation(program, miles_required, cabin, route, taxes_usd):
    cpp, cash_equivalent_usd = calculate_cpp(program, miles_required, cabin, route, taxes_usd)
    verdict = calculate_verdict(cpp)
    explanation = calculate_explanation(verdict, cpp, cash_equivalent_usd)

    return {
        'cpp': cpp,
        'cash_equivalent_usd': cash_equivalent_usd,
        'verdict': verdict,
        'explanation': explanation
    }

# Test cases
test_cases = [
    ('United', 25000, 'Economy', 'New York to Los Angeles', 50),
    ('American', 50000, 'Business', 'New York to London', 200),
    ('Delta', 100000, 'First Class', 'New York to Tokyo', 500),
    ('United', 20000, 'Premium Economy', 'New York to Chicago', 20),
    ('American', 30000, 'Economy', 'New York to Miami', 30),
    ('Delta', 40000, 'Business', 'New York to Los Angeles', 100),
    ('United', 15000, 'Economy', 'New York to Boston', 10),
    ('American', 25000, 'Premium Economy', 'New York to Dallas', 25),
    ('Delta', 35000, 'Business', 'New York to Seattle', 50),
    ('United', 10000, 'Economy', 'New York to Washington D.C.', 5)
]

for test_case in test_cases:
    program, miles_required, cabin, route, taxes_usd = test_case
    result = award_valuation(program, miles_required, cabin, route, taxes_usd)
    print(f'Program: {program}, Miles Required: {miles_required}, Cabin: {cabin}, Route: {route}, Taxes USD: {taxes_usd}')
    print(f'CPP: {result["cpp"]:.2f}, Cash Equivalent USD: {result["cash_equivalent_usd"]:.2f}, Verdict: {result["verdict"]}, Explanation: {result["explanation"]}')
    print('---')

NEW_TASKS:
