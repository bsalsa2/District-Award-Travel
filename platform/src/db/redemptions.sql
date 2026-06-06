CREATE TABLE IF NOT EXISTS redemptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    award_id INTEGER NOT NULL,
    redemption_date DATE NOT NULL,
    booking_id INTEGER,
    status TEXT NOT NULL CHECK(status IN ('pending', 'booked', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS idx_client_id ON redemptions (client_id);
CREATE INDEX IF NOT EXISTS idx_award_id ON redemptions (award_id);
CREATE INDEX IF NOT EXISTS idx_booking_id ON redemptions (booking_id);
