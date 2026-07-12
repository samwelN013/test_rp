--  HAVING CLAUSE TO ADD CONDITION ON THE GROUP BY ie ---
SELECT job,
    min(age) AS lowest_age,
    max(age) AS highest_age,
    avg(age) as average_age,
    count(*) as number_of_people
from personel
GROUP BY job
HAVING COUNT(*) < 3;
---------------------------------------------