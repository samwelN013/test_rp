-- INCLUDES : FOREIGN KEYS, JOINS, CONSTRAINTS:
-- 1 to many table relationship
-- "personel" table, and "things" table
CREATE TABLE things(
    id serial primary key,
    inventory_number varchar(255) unique,
    thing_name varchar(255) not null,
    description varchar(255),
    price decimal(10, 2) check (price >= 0),
    -- constraint
    item_owner int,
    -- references personel(id)
    constraint fk_item_owner foreign key (item_owner) references personel(id)
);
---------------------------------------------------------------------
insert into things(inventory_number, thing_name, price, item_owner)
values ('a122', 'laptop', 900, 1),
    ('a132', 'book', 20, 1),
    ('a172', 'pen', 5, 2);
------------------------------------
SELECT *
FROM things;
--------------
SELECT *
from personel;
-------------
TRUNCATE TABLE things;
drop table things;
--------------------------------------------
-- JOIN ----
-- a) : the inner join
--SELECT * from personel, things where personel.id = things.item_owner; -- OLD way
SELECT *
FROM personel
    JOIN things on personel.id = things.item_owner;
-------------------------
SELECT *
FROM personel
    JOIN things on personel.id = things.item_owner
where price < 800;
------------
SELECT *
FROM personel
    INNER JOIN things on personel.id = things.item_owner;
--- b) : left join
SELECT *
FROM personel
    LEFT JOIN things on personel.id = things.item_owner;
--- c) : right join
SELECT *
FROM personel
    RIGHT JOIN things on personel.id = things.item_owner;
---d) : full join
SELECT *
FROM personel
    FULL JOIN things on personel.id = things.item_owner;
-------- CONSTRAINTS ---------------