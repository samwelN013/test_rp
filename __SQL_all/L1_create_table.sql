--- CREATE clause : IS useful in the creation of new tables ie
----------------------------------------------------
-- to just create table
create table people (
    id serial primary key,
    first_name varchar(100),
    age int,
    job varchar(255),
    employed boolean
);
-- to continue if it doesn't exist
create table if not exists poeple (
    id int primary key,
    first_name varchar(100),
    age int,
    job varchar(255),
    employed boolean
);
------------------------------------------
-- 1. Get rid of the old mismatched table
DROP TABLE IF EXISTS aggtrades;
-- 2. Create the table with numeric types for the scientific notation fields
CREATE TABLE aggtrades (
    agg_trade_id NUMERIC,
    -- Changed to NUMERIC to accept scientific format
    price NUMERIC(16, 8),
    quantity NUMERIC(16, 8),
    first_trade_id NUMERIC,
    -- Changed to NUMERIC
    last_trade_id NUMERIC,
    -- Changed to NUMERIC
    transact_time NUMERIC,
    -- Changed to NUMERIC to catch the "1.7826E+12"
    is_buyer_maker BOOLEAN
);
----------------------------------------------------
INSERT INTO people (first_name, id, employed)
valueS ('john', 4, true);
----------------------------------------