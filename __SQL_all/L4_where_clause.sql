------------ WHERE CLAUSES : helps us select specific data in rows or columns we want:
----***********************************************
-- SELECTING THE WHOLE TABLE -----------------------
SELECT *
FROM personel;
-----------------------------------------------------
SELECT *
from aggtrades;
-- get people younger than 20--------------------
select first_name,
    age
from personel
WHERE age < 20;
-------------------------------
select id,
    first_name,
    age
from personel
WHERE age BETWEEN 14 and 30
ORDER BY id DESC;
--NB : columns are sensitive of the order of selection
---------------------------------------------------------
select *
from personel
WHERE job in ('programmer', 'coder');
-- for multiple selection
--where job='programmer' : for single selection
---------------------------------------------------------
-- for name starting with a letter 
-- 'S%' - means a name beginning with 's ' and everything else----------
select first_name,
    age
from personel
WHERE first_name like 'j%';
--------------------------------
select *
from personel
WHERE first_name like '%ce';
-- combining the where conditions----------------
select *
from personel
WHERE first_name like '%ce'
    and employed IS FALSE
    and age >= 15
    AND age < 30;
-- YOU CAN TRUNCATE OR CLEAR THE CONTENTS OF THE TABLE WITHOUT  deleting it ie
truncate table aggtrades;
-----------------------------------------
select *
from aggtrades;
---------------------------------------
-- TO RETURN ON entity of data regardless how many times it exists ; use  DISTINCT clause
select DISTINCT job
from personel
where age < 100;
--------------------------------------------------