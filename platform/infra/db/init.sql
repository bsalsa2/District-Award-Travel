CREATE TABLE metrics (
    id SERIAL PRIMARY KEY,
    booking_requests INTEGER,
    award_redemptions INTEGER,
    customer_engagement INTEGER
);

INSERT INTO metrics (booking_requests, award_redemptions, customer_engagement)
VALUES (100, 50, 200);
