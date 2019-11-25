import os
import psycopg2

DATABASE_URL = os.environ['DATABASE_URL']

conn = psycopg2.connect(DATABASE_URL, sslmode='require')

curr = conn.cursor()

# create tables
curr.execute("CREATE TABLE hotels ( id serial PRIMARY KEY, name VARCHAR (250)  NOT NULL);")
curr.execute("CREATE TABLE inventory ( id serial PRIMARY KEY,   hotel_id integer not null,  "
             " name VARCHAR (250)  NOT NULL,  num integer NOT NULL, "
             " CONSTRAINT inventory_hotel_fk FOREIGN KEY (hotel_id)"
             " REFERENCES hotels (id) MATCH SIMPLE ON UPDATE CASCADE ON DELETE CASCADE);")

curr.execute(" CREATE TABLE reservations (   id serial PRIMARY KEY,   hotel_id integer not null,"
             "   inventory_id integer  NOT NULL,   start_date timestamp without time zone,  "
             " end_date timestamp without time zone,   status integer NOT NULL,   "
             " CONSTRAINT reservation_hotel_fk FOREIGN KEY (hotel_id) "
             " REFERENCES hotels (id) MATCH SIMPLE      "
             " ON UPDATE CASCADE ON DELETE CASCADE,   "
             " CONSTRAINT reservation_inventory_fk FOREIGN KEY (inventory_id)    "
             "  REFERENCES inventory (id) MATCH SIMPLE   "
             "   ON UPDATE CASCADE ON DELETE CASCADE);")
# insert data
curr.execute("INSERT INTO hotels(id,name) VALUES (1,'The Tavern Hotel')")
# insert data
curr.execute("INSERT INTO hotels(id,name) VALUES (2,'The Resort Hotel')")
# insert data
curr.execute("INSERT INTO inventory(id,hotel_id, name,num) VALUES (1,1, 'Standard room',10)")
curr.execute("INSERT INTO inventory(id,hotel_id, name,num) VALUES (2,1, 'Deluxe room',5)")
curr.execute("INSERT INTO inventory(id,hotel_id, name,num) VALUES (3,1, 'Honeymoon Suite',1)")
curr.execute("INSERT INTO inventory(id,hotel_id, name,num) VALUES (4,2, 'Deluxe room',8)")
curr.execute("INSERT INTO inventory(id,hotel_id, name,num) VALUES (5,2, 'Deluxe private pool',4)")
curr.execute("INSERT INTO inventory(id,hotel_id, name,num) VALUES (6,2, 'Presidential suite',1)")

conn.commit()
# Close communication with the database
curr.close()


