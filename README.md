# Upserve Home Exam

Webserver for upserve code exam\
simplicity over structure.


## API
https://upserve-y.herokuapp.com/ endpoint, \
documentation in swagger \
https://upserve-y.herokuapp.com/swagger/ \
Implementation straightforward,
 available rooms algorithm based on sorting the reservations per inventory and filling info for all dates.\
Same code is used to validate redservation - 
reservation inserted to db, then verify nothing is broken (rooms available became negative) and decide whether to confirm reservation or delete it.


## DB

3 tables: 
hotels -> id(generated) + name\
inventory-> id (generated) , hotel_id (fk) , name of room category + number\
reservations -> reservation (reference to inventory )+start date, end date and status.
