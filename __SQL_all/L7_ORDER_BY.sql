SELECT *
from personel;
--------------------------------
-- TO ORDER THE TABLE DATA
SELECT *
FROM personel
ORDER BY JOB DESC;
------------------------------
-- TO Order by more than one column
SELECT *
FROM personel
ORDER BY JOB ASC,
    age DESC;
--------------------------------------