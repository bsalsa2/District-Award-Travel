CREATE TABLE data (
    id SERIAL PRIMARY KEY,
    feature1 FLOAT,
    feature2 FLOAT,
    target INTEGER
);

CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    prediction INTEGER
);
