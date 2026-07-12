-- UPDATE clause assists in changing information in column/row cells of the table 
SELECT *
from personel;
--------------------------------
update personel
set job = 'civil_engineer'
where first_name = 'kenney';
-- that changed kenney's job in the table
-------------------------------
UPDATE personel
SET job = 'accountant';
-- replaces the whole "age" column with 12 years every person and the whole "job" column with accountant
-- ## updating may rows of the column
UPDATE personel
SET age = CASE
        id
        WHEN 1 THEN 12
        WHEN 2 THEN 15
        WHEN 3 THEN 29
    END;
-- * but that writes in only give id and makes all others null; to prevent that, you add a WHERE clause `WHERE id IN (1, 2, 3);`  ie
UPDATE personel
SET age = CASE
        id
        WHEN 1 THEN 12
        WHEN 2 THEN 15
        WHEN 3 THEN 29
    END
WHERE id IN (1, 2, 3);
-- *BUt this too, disorganises the order of the table, to reorder by id, type;*