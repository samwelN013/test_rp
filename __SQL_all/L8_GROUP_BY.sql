-- GROUP BY AND THE  grand bucketing of time series data
SELECT *
from personel;
----------------------------
-- you have to use aggregate fucntions in group by
SELECT job,
    count(*)
from personel
GROUP BY job;
--------------
SELECT job,
    avg(age)
from personel
GROUP BY job;
-------------
SELECT job,
    min(age)
from personel
GROUP BY job;
------------------
SELECT job,
    max(age)
from personel
GROUP BY job;
-------- combined aggregate functions to one table ------------
SELECT job,
    min(age),
    max(age),
    avg(age),
    count(*)
from personel
GROUP BY job;

---- YOU CAN EVEN GROUP BY MULTIPLE COLUMNS ------------

--- PASSING IN  an alias to change the customise the new column names after GROUPING
SELECT job,
    min(age) AS lowest_age,
    max(age) AS highest_age,
    avg(age) as average_age,
    count(*) as number_of_people
from personel
GROUP BY job;