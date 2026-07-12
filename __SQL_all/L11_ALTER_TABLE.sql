-- ALTER -- used for changing the TABLE, column NAMES ; its different from UPDATE- which focuses on contents of columns or cells
-- TO ADD A COLUMN TO A TABLE
ALTER TABLE personel
add column height decimal(10, 2);
--------------------------------------
SELECT *
FROM personel;
-- TO DROP/DELETE A COLUMN
ALTER TABLE personel DROP COLUMN employed;