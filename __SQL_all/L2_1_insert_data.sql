------ TO INSERT DATA INTO THE TABLE -----------------------------
select *
from people;
--------
SELECT *
FROM personel;
-------------------------------------------------------------------
-- To insert data into table columns, in a row
INSERT into people
values (1, 'mike', 30, 'programmer', true);
--a cell in the primary key column 'cannot be null'
-- multiple rows
insert INTO people (first_name, age, job, employed)
values ('sam', 31, 'business_admin', false),
    ('mich', 23, 'accountant', true),
    ('apolo', 14, 'foreman', true);
--  OTHERS -- on modified table -------
------------------------------------------------------------------------
-- to insert data into specific column rather than all
-- a
INSERT into people
values (3, 'grace', null, null, null);
--you nullify all other column where you are not putting a value and which 'can be null'
-- b
--------------------------------------------------------------------------
INSERT INTO people (id, first_name, employed) value (4, 'john', true);
--other cells of the row , automatically become 'null'
-- you can reorder columns for data entery ie
INSERT INTO people (first_name, id, employed) value ('john', 4, true);
--------------------------------------------------------------------------
-- checking table column info
SELECT column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'people';
-------- TO TRUNCATE TABLE ------------------
TRUNCATE TABLE people;