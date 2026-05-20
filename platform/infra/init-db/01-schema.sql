-- Award Travel Database Schema
-- Flights
CREATE TABLE IF NOT EXISTS airlines (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    code VARCHAR(3) NOT NULL UNIQUE,
    alliance VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS airports (
    id SERIAL PRIMARY KEY,
    iata_code VARCHAR(3) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    timezone VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS flight_awards (
    id SERIAL PRIMARY KEY,
    airline_id INTEGER REFERENCES airlines(id),
    origin_airport_id INTEGER REFERENCES airports(id),
    destination_airport_id INTEGER REFERENCES airports(id),
    cabin_class VARCHAR(50) NOT NULL,
    miles_required INTEGER NOT NULL,
    points_required INTEGER NOT NULL,
    booking_fee DECIMAL(10, 2) DEFAULT 0.00,
    fuel_surcharge DECIMAL(10, 2) DEFAULT 0.00,
    taxes DECIMAL(10, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_date_range CHECK (valid_to > valid_from)
);

CREATE INDEX IF NOT EXISTS idx_flight_awards_origin ON flight_awards(origin_airport_id);
CREATE INDEX IF NOT EXISTS idx_flight_awards_destination ON flight_awards(destination_airport_id);
CREATE INDEX IF NOT EXISTS idx_flight_awards_cabin ON flight_awards(cabin_class);
CREATE INDEX IF NOT EXISTS idx_flight_awards_active ON flight_awards(is_active);

-- Hotels
CREATE TABLE IF NOT EXISTS hotel_chains (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    program_name VARCHAR(100) NOT NULL,
    website VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hotels (
    id SERIAL PRIMARY KEY,
    chain_id INTEGER REFERENCES hotel_chains(id),
    property_id VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    country VARCHAR(100) NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    star_rating INTEGER CHECK (star_rating BETWEEN 1 AND 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, chain_id)
);

CREATE TABLE IF NOT EXISTS hotel_awards (
    id SERIAL PRIMARY KEY,
    hotel_id INTEGER REFERENCES hotels(id),
    room_type VARCHAR(100) NOT NULL,
    nights_required INTEGER NOT NULL,
    points_required INTEGER NOT NULL,
    cash_required DECIMAL(10, 2) DEFAULT 0.00,
    resort_fee DECIMAL(10, 2) DEFAULT 0.00,
    taxes DECIMAL(10, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_date_range_hotel CHECK (valid_to > valid_from)
);

CREATE INDEX IF NOT EXISTS idx_hotel_awards_hotel ON hotel_awards(hotel_id);
CREATE INDEX IF NOT EXISTS idx_hotel_awards_active ON hotel_awards(is_active);

-- Car Rentals
CREATE TABLE IF NOT EXISTS car_rental_companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    program_name VARCHAR(100) NOT NULL,
    website VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS car_awards (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES car_rental_companies(id),
    vehicle_class VARCHAR(50) NOT NULL,
    rental_days INTEGER NOT NULL,
    points_required INTEGER NOT NULL,
    cash_required DECIMAL(10, 2) DEFAULT 0.00,
    taxes DECIMAL(10, 2) DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    valid_from DATE NOT NULL,
    valid_to DATE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_date_range_car CHECK (valid_to > valid_from)
);

CREATE INDEX IF NOT EXISTS idx_car_awards_company ON car_awards(company_id);
CREATE INDEX IF NOT EXISTS idx_car_awards_active ON car_awards(is_active);

-- Loyalty Programs
CREATE TABLE IF NOT EXISTS loyalty_programs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    program_type VARCHAR(50) NOT NULL CHECK (program_type IN ('airline', 'hotel', 'car', 'bank')),
    currency VARCHAR(3) DEFAULT 'USD',
    transfer_ratio DECIMAL(10, 6) DEFAULT 1.0,
    min_transfer_amount INTEGER DEFAULT 1000,
    max_transfer_amount INTEGER,
    partner_programs TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Program Partners
CREATE TABLE IF NOT EXISTS program_partners (
    id SERIAL PRIMARY KEY,
    program_id INTEGER REFERENCES loyalty_programs(id),
    partner_program VARCHAR(100) NOT NULL,
    transfer_ratio DECIMAL(10, 6) DEFAULT 1.0,
    min_transfer_amount INTEGER DEFAULT 1000,
    max_transfer_amount INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Sample Data
INSERT INTO airlines (name, code, alliance) VALUES
('American Airlines', 'AA', 'Oneworld'),
('Delta Air Lines', 'DL', 'SkyTeam'),
('United Airlines', 'UA', 'Star Alliance'),
('Southwest Airlines', 'WN', NULL),
('JetBlue Airways', 'B6', 'Oneworld'),
('Alaska Airlines', 'AS', 'Oneworld'),
('Emirates', 'EK', NULL),
('Qatar Airways', 'QR', 'Oneworld'),
('Lufthansa', 'LH', 'Star Alliance'),
('Air France', 'AF', 'SkyTeam');

INSERT INTO airports (iata_code, name, city, country, latitude, longitude, timezone) VALUES
('JFK', 'John F Kennedy International Airport', 'New York', 'US', 40.6413, -73.7781, 'America/New_York'),
('LAX', 'Los Angeles International Airport', 'Los Angeles', 'US', 33.9425, -118.4081, 'America/Los_Angeles'),
('LHR', 'London Heathrow Airport', 'London', 'GB', 51.4700, -0.4543, 'Europe/London'),
('CDG', 'Charles de Gaulle Airport', 'Paris', 'FR', 49.0097, 2.5479, 'Europe/Paris'),
('NRT', 'Narita International Airport', 'Tokyo', 'JP', 35.7647, 140.3860, 'Asia/Tokyo'),
('HND', 'Haneda Airport', 'Tokyo', 'JP', 35.5494, 139.7798, 'Asia/Tokyo'),
('DXB', 'Dubai International Airport', 'Dubai', 'AE', 25.2532, 55.3654, 'Asia/Dubai'),
('SIN', 'Singapore Changi Airport', 'Singapore', 'SG', 1.3592, 103.9893, 'Asia/Singapore'),
('SYD', 'Sydney Kingsford Smith Airport', 'Sydney', 'AU', -33.9399, 151.1753, 'Australia/Sydney'),
('AKL', 'Auckland Airport', 'Auckland', 'NZ', -37.0081, 174.7923, 'Pacific/Auckland');

INSERT INTO hotel_chains (name, program_name, website) VALUES
('Marriott International', 'Marriott Bonvoy', 'https://www.marriott.com'),
('Hilton Worldwide', 'Hilton Honors', 'https://www.hilton.com'),
('Hyatt Hotels Corporation', 'World of Hyatt', 'https://www.hyatt.com'),
('IHG Hotels & Resorts', 'IHG One Rewards', 'https://www.ihg.com'),
('Choice Hotels International', 'Choice Privileges', 'https://www.choicehotels.com'),
('Wyndham Hotels & Resorts', 'Wyndham Rewards', 'https://www.wyndhamhotels.com'),
('Accor', 'Accor Live Limitless', 'https://all.accor.com');

INSERT INTO car_rental_companies (name, program_name, website) VALUES
('Enterprise Holdings', 'Enterprise Plus', 'https://www.enterprise.com'),
('The Hertz Corporation', 'Hertz Gold Plus Rewards', 'https://www.hertz.com'),
('Avis Budget Group', 'Avis Preferred', 'https://www.avis.com'),
('Sixt', 'Sixt Rewards', 'https://www.sixt.com'),
('National Car Rental', 'Emerald Aisle', 'https://www.nationalcar.com');

-- Loyalty Programs
INSERT INTO loyalty_programs (name, program_type, currency, transfer_ratio) VALUES
('American Airlines AAdvantage', 'airline', 'USD', 1.0),
('Delta SkyMiles', 'airline', 'USD', 1.0),
('United MileagePlus', 'airline', 'USD', 1.0),
('Marriott Bonvoy', 'hotel', 'USD', 1.0),
('Hilton Honors', 'hotel', 'USD', 1.0),
('World of Hyatt', 'hotel', 'USD', 1.0),
('IHG One Rewards', 'hotel', 'USD', 1.0),
('Hertz Gold Plus Rewards', 'car', 'USD', 1.0),
('Avis Preferred', 'car', 'USD', 1.0),
('Chase Ultimate Rewards', 'bank', 'USD', 1.0),
('American Express Membership Rewards', 'bank', 'USD', 1.0),
('Citi ThankYou Points', 'bank', 'USD', 1.0);
