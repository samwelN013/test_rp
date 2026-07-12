-- CREATING A MANY TO MANY RELATIONSHIP TABLE 
--parent table  --
SELECT *
from personel;
--then 'things_v2'
--then  'ownership'  : dealing with 3 tables
----------------------
CREATE TABLE things_v2(
    id serial primary key,
    inventory_number varchar(255) unique,
    thing_name varchar(255) not null,
    description varchar(255),
    price decimal(10, 2) check (price >= 0)
);
--------------------------
insert into things_v2(inventory_number, thing_name, price)
values ('a122', 'laptop', 900),
    ('a132', 'book', 20),
    ('a172', 'pen', 5);
----------------------------------
SELECT *
FROM things_v2;
----------------------------------
CREATE table ownership(
    item_owner int references personel (id),
    item int references things_v2(id),
    primary key (item_owner, item)
);
--------------------------------------
SELECT *
from ownership;
-------------------------------------
INSERT into ownership
values (1, 1),
    (2, 1),
    (2, 2),
    (4, 3),
    (5, 3);
-------------- TO SELECT --------------------
SELECT p.first_name,
    p.job,
    t.thing_name,
    t.price
FROM ownership
    JOIN personel p on p.id = ownership.item_owner
    JOIN things_v2 t on t.id= ownership.item; 