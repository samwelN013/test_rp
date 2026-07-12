--  TO RETURN THE NUMBER OF COLUMNS YOU WANT --
-- use the LIMIT clause -----------ie
SELECT *
from aggtrades
limit 3;
--- with order by --------------
SELECT *
from aggtrades
order by transact_time DESC
limit 5;