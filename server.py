import datetime
import os
import traceback
from enum import Enum

import psycopg2
from sanic import Sanic, response
from sanic.exceptions import InvalidUsage
from sanic.response import json
from sanic_openapi import swagger_blueprint,doc
from sanic_cors import CORS, cross_origin
from psycopg2.extras import RealDictCursor
class RES_STATUS(Enum):
   INITIAL = 1,
   CONFIRMED = 2,
   CANCELLED = 3
DATABASE_URL = os.environ['DATABASE_URL']
app = Sanic()
app.blueprint(swagger_blueprint)
app.config["API_SCHEMES"] = ["https","http"]
cors = CORS(app, resources={r"/api/*": {"origins": "*"}})

def rooms_per_day(reservations, start, end, num):
    ans = []
    for row in reservations:
        ans.append((row['start_date'], -1))
        ans.append((row['end_date'], 1))

    ans.sort()
    curr_active= 0
    curr_date = start
    day_dict = {}
    for i in range(0, len(ans)):
        #fill previous values
        if (curr_date < ans[i][0].date()):
            delta = ans[i][0].date() - curr_date
            for j in range(delta.days+1):
                day = curr_date + datetime.timedelta(days=j)
                day_dict[day] ={'occupied':0-curr_active,'available':num+curr_active}

        #quit loop if date passed
        if (curr_date > end):
            break
        #update date with this value
        curr_active += ans[i][1]
        curr_date = ans[i][0].date()


    delta = end - curr_date  # as timedelta
    #complete missing entries in the end
    for i in range(delta.days + 1):
        day = curr_date + datetime.timedelta(days=i)
        day_dict[day] = {'occupied': curr_active, 'available': num - curr_active}
    return day_dict


def get_inventory_inner(hotel_id,start_date, end_date, inventory_id=None,cur = None):
    if (cur == None):
        inited_con = True
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        inited_con = False
    if (inventory_id == None):
        cur.execute("SELECT id, name,num FROM inventory where hotel_id = %(hotel_id)s", {'hotel_id':hotel_id})
        states = (RES_STATUS.CONFIRMED.value)
    else: #checking specific inventory in reservqtion, consider initial reservations too for concurrency considertions
        cur.execute("SELECT id, name,num FROM inventory where hotel_id = %(hotel_id)s and id =  %(id)s",
                    {'hotel_id': hotel_id,'id':inventory_id})
        states = (RES_STATUS.CONFIRMED.value,RES_STATUS.INITIAL.value)
    inventory = cur.fetchall()

    cur.execute("SELECT id,inventory_id,  start_date,end_date FROM reservations "+
                " where hotel_id = %(hotel_id)s and status in %(states)s "+
                " and (end_date > %(start_date)s and start_date < %(end_date)s )",
                {'hotel_id': hotel_id,'start_date':start_date,'end_date':end_date,'states':states})
    reservations = cur.fetchall()
    if inited_con:
        cur.close()
        conn.close()
    inventories =[]
    for row in inventory:
        relevant_res = [x for x in reservations if x['inventory_id'] == row['id'] ]
        dict ={}
        dict['inventory_name'] = row['name']
        dict['id'] = row['id']
        dict['rooms'] = rooms_per_day(relevant_res, start_date, end_date, row['num'])

        inventories.append( dict)
    return inventories

@app.route("/reservation/<reservation_id>", methods=["GET","OPTIONS"])
@doc.summary('GET Reservation details')
@doc.produces({"id":str,"inventory_id":int,"hotel_id":int,"start_date":datetime,"end_date":datetime,
               "hotel_name":str,"room_type":str})
def get_reservation(request,reservation_id):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("SELECT r.id,r.inventory_id,r.hotel_id,r.start_date,r.end_date, h.name as hotel_name,"
                " i.name as room_type FROM reservations r, "+
                " inventory i , hotels h" +
                " where r.hotel_id = h.id and r.inventory_id = i.id " +
                " and r.id =  %(id)s",
                {'id': reservation_id})
    reservation = cur.fetchone()
    cur.close()
    conn.close()
    return response.json(reservation)

@app.route("/reservation/<reservation_id>", methods=["DELETE"])
@doc.summary("delete reservation by id")
def delete_reservation(request,reservation_id):
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor()
    cur.execute("update reservations set status = %(status)s where id =%(id)s",
                {'id': reservation_id,'status':RES_STATUS.CANCELLED.value})
    updated_rows = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    return response.json({'deleted':updated_rows})


@app.route("/reservations/<hotel_id>/<start_date>/<end_date>", methods=["GET","OPTIONS"])
@doc.summary("get reservations in hotel_id from start_date to end_date, dateformat YYYY-mm-dd, start must be infuture")
@doc.produces({"id":{"name":str, "rooms":[{"date":{"occupied":int,"available":int}}]}})
async def get_inventory(request,hotel_id,start_date,end_date):
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
        if end <= start:
            raise InvalidUsage('start must be before end')
        inventory =get_inventory_inner(hotel_id,start,end)
        return response.json(inventory)
    except Exception as e:
        raise InvalidUsage(' error->' + ' ' + str(e) + traceback.format_exc())



@app.route("/reservation", methods=["POST","OPTIONS"])
@doc.summary("add reservations in hotel_id from start_date to end_date,dateformat YYYY-mm-dd")
@doc.consumes(doc.JsonBody({"start":str,"end":str,"hotel_id":int,"inventory_id":int}),
              content_type="application/json",location="body",required=True)
@doc.produces({"reservation_id":int})
async def add_reservation(request):

    hotel_id = request.json['hotel_id']
    start_date = datetime.datetime.strptime(request.json['start'], "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(request.json['end'], "%Y-%m-%d").date()
    # validate: start less than end
    if (end_date <= start_date or start_date <= datetime.datetime.now().date()):
        raise InvalidUsage('invalid dates for reservation')
    inventory_id = request.json['inventory_id']
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    cur = conn.cursor(cursor_factory=RealDictCursor)
    # try insert with status 'validating' -> wil lverify hotel_id and inventory id
    try:
        cur.execute("insert into reservations(hotel_id,   inventory_id,   start_date ,   end_date , "
                    "  status) Values ( " +
                    " %(hotel_id)s,%(inv_id)s, %(start)s,%(end)s ,%(status)s ) RETURNING id",
                    {'hotel_id': hotel_id,'inv_id':inventory_id, 'status': RES_STATUS.INITIAL.value,'start':start_date,'end':end_date})
        id_of_new_row = cur.fetchone()
        conn.commit()
        if (id_of_new_row['id'] >0):
            #check not reached negtive inventory
            dict =get_inventory_inner(hotel_id,start_date,end_date,inventory_id,cur)[0]
            conn.rollback()
            for day in dict['rooms']:
                if (dict['rooms'][day]['available'] < 0):
                    cur.execute('delete from reservations where id = %(id)s',{'id':id_of_new_row['id']})
                    conn.commit()
                    raise InvalidUsage('room unavailable')
            conn.commit()
            cur.execute('update reservations set status=%(status)s where id = %(id)s',
                        {'id': id_of_new_row['id'],'status':RES_STATUS.CONFIRMED.value})
            conn.commit()
            return response.json({'reservation_id': id_of_new_row['id'],'commited':1})
        else:
            cur.execute('delete from reservations where id = %(id)i', {'id': id_of_new_row['id']})
            conn.commit()
            return response.json('no valid inventory', 304)
    except Exception as e :
        conn.rollback()
    finally:
        cur.close()
        conn.close()



if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8000)),
        workers=int(os.environ.get('WEB_CONCURRENCY', 1)),
        debug=bool(os.environ.get('DEBUG', '')))