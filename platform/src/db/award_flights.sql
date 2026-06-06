-- Create the award flights table
CREATE TABLE award_flights (
    id INTEGER PRIMARY KEY,
    airline TEXT NOT NULL,
    departure TEXT NOT NULL,
    arrival TEXT NOT NULL,
    date TEXT NOT NULL,
    award_price INTEGER NOT NULL
);

-- Create an index on the airline column
CREATE INDEX idx_airline ON award_flights (airline);

-- Create an index on the departure column
CREATE INDEX idx_departure ON award_flights (departure);

-- Create an index on the arrival column
CREATE INDEX idx_arrival ON award_flights (arrival);

-- Create an index on the date column
CREATE INDEX idx_date ON award_flights (date);
