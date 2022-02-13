from flask import request, jsonify, Blueprint, current_app 
from random import randint
from .models import MongoClient, RedisClient
from functools import wraps
from datetime import datetime
from PIL import Image
from bson.objectid import ObjectId
from geopy.geocoders import Nominatim


import jwt
import requests
import datetime
import pytz
import json
import base64
import io
import pymongo

_headers = {'Content-Type':'application/json', 'x-api-key':'dSVNbU8tWzcYNWDr2Q073WrMJtRMeJqaLjOxzbl6'}
phone_bp = Blueprint('phone', __name__) 

format = '%Y-%m-%d %H:%M:%S'
timezone = pytz.timezone('America/Mexico_City')

MongoObject = MongoClient()
RedisObject = RedisClient()
#clera
# CLIENT CONNECTORS
mongo_conn = MongoObject.mongo_client
redis_conn = RedisObject.redis_client

# DB INSTANCE
mongo_db = MongoObject.mongo_db

# CREATE INDEX FOR IMAGE COLLECTION
mongo_db.images.create_index('hashtag', unique=True)
list_index = mongo_db.images.list_indexes()

# INITIALIZATE NOMINATIM API
geolocator = Nominatim(user_agent='geoapiExercises')

# FUNC FOR SENT TOKEN
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers['authorization']
        print(token)
        real_token = token.replace('Bearer ', '')
        print(real_token)
        
        if not real_token:
            return jsonify({'message': 'Token has not been defined'})        
        try:
            data = jwt.decode(real_token, 'secret', algorithms=['HS256'])
            print(data)
        except:
            return jsonify({'message': 'Token is invalid'})

        return f(*args, **kwargs)

    return decorated


@phone_bp.route('/phone_number', methods=['POST'])
def phone_number():

    # REQUEST DATA
    phone_number = request.json['phone_number']

    # VALIDATING LENGTH OF NUMBER
    if len(phone_number) != 10 and phone_number.isnumeric():
        return ({'message': 'The number entered does not have 10 digits'})

    # VALIDATE THAT THERE IS AN ACTIVE SESSION
    list_keys = redis_conn.keys()
    if bytes(phone_number, 'UTF-8') in redis_conn.keys():
        msg_value = 'The number ' + phone_number + ' has an active session'
        return ({'message': msg_value})
    else:

        # GENERATE RANDOM RUMBER TO SEND SMS
        num_rang = []
        for x in range(6):
            a = randint(0,9)
            num_rang.append(str(a))

        msg = ''.join(num_rang)


        # SETTING TZ TO INSERT IN MONGODB
        now = datetime.datetime.now(timezone)
        time_in = str(now.strftime('%Y-%m-%d %H:%M:%S'))

        payload = {'nbr': phone_number, 'msg': msg}
        
        # SEND REQUEST TO API SMS
        response = requests.post(current_app.config['SMS_API'], headers=_headers, data=json.dumps(payload))
        json_response = response.json()

        # CHECK RESPONSE FOR 200 CODE
        if json_response['statusCode'] == 200:
            # SET CACHE WITH NUMBER PHONE FOR 5 MINUTES
            data_cache = {'msg': msg, 'status': 'Active'}
            redis_conn.set(phone_number, json.dumps(data_cache), 300)
            
            # INSERT REGISTER TO MONGODB
            collection = mongo_db['data']
            collection.insert_one({'nbr': phone_number, 'msg': msg})
    
        return ({'message': 'Message sent'})





@phone_bp.route('/phone_number_login', methods=['POST'])
def phone_number_login():
    
    # REQUEST DATA
    phone_number = request.json['phone_number']
    code = request.json['code']


    data = {'msg': code, 'status': 'Active'}
   #print(bytes(json.dumps(data), 'UTF-8'))
    print(redis_conn.get(phone_number) )
    print(bytes(json.dumps(data), 'UTF-8'))
    if bytes(phone_number, 'UTF-8') in redis_conn.keys() and (redis_conn.get(phone_number) == bytes(json.dumps(data), 'UTF-8')):
        
        # AUTH HEADER FROM REQUEST
        msg = redis_conn.get(phone_number).decode('UTF-8')
        token_header = jwt.encode({'phone_number': phone_number, 'msg': msg, 'exp' : datetime.datetime.utcnow() + datetime.timedelta(minutes=10)}, "secret", algorithm="HS256")
    else:
        return ({'message': 'The code or the phones was incorrect'})
    

    return ({'message': token_header})

    

@phone_bp.route('/check_session', methods=['POST'])
def check_session():
    # REQUEST DATA
    phone_number = request.json['phone_number']
 
    # VALIDATE THAT THERE IS AN ACTIVE SESSION
    list_keys = redis_conn.keys()
    if bytes(phone_number, 'UTF-8') in redis_conn.keys():
        data = redis_conn.get(phone_number)
        dict_output = json.loads(data.decode('UTF-8'))

        msg_value = 'The actual status is ' + str(dict_output['status'])
        return ({'message': msg_value}) 
    else:
        return ({'message': 'The actual status is Empty'})

    
@phone_bp.route('/new_image', methods=['POST'])
@token_required
def new_image():

    # REQUEST DATA
    data_image = request.json['data_image']
    mime = request.json['mime']
    
    hashtag = request.json['hashtag']
    latitude = request.json['latitude']
    longitude = request.json['longitude']

       
    # INSERT IN MONGODB
    try:
        # OBTAIN ACTUAL TIME
        current_utc = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
        date_insert = datetime.datetime.strptime(current_utc, '%Y-%m-%dT%H:%M:%S.000Z')

        byte_data = bytes(data_image, 'UTF-8')
        
        collection = mongo_db['images']
        _id = collection.insert_one({'image': byte_data,'hashtag': hashtag, 'latitude': latitude, 'longitude': longitude, 'created_at': date_insert})

        
        # NOM FOR FILES
        prefix = 'selfity/resources/'
        name_file = prefix + hashtag + '.' + mime

        image = open(name_file, 'wb')
        
        image.write(base64.b64decode((byte_data)))
        image.close()

        # CREATE THUMBNAIL    
        name_file_thumb = hashtag
        size = 128, 128
        thumb = Image.open(name_file)
        thumb.thumbnail(size)
        thumb.save(prefix + hashtag + '.thumbnail', 'JPEG')
        thumb.close()
        


        return {'msg': 'The image has been inserted correctly', 'id': str(_id.inserted_id)} 
    except Exception as e:
        print('------> ' + str(e))
        return {'msg': 'The hashtag already exist'}
    


    

@phone_bp.route('/thumbnail_by_id', methods=['POST'])
@token_required
def thumbnail_by_id():

    # REQUEST DATA
    _id = request.json['id']

    collection = mongo_db['images']
    data_new_thumbnail = collection.find_one({'_id': ObjectId(_id)})
        
    # CREATE THUMBNAIL
    prefix = 'selfity/resources/'
    name_file_thumb = prefix + data_new_thumbnail['hashtag'] + '.jpeg'
    size = 64, 64
    thumb = Image.open(name_file_thumb)
    thumb.thumbnail(size)
    thumb.save(prefix + data_new_thumbnail['hashtag'] + '_reduced' + '.thumbnail', 'JPEG')
    thumb.close()
     
    lat = data_new_thumbnail['latitude']
    lon = data_new_thumbnail['longitude']
        
    geo_data = geolocator.reverse(lat + "," + lon).raw['address']
    city = None

    if 'city' in geo_data.keys():
        city = geo_data['city']
    else:
        city = geo_data['town']

    print(city)
    

    return {'created_at': data_new_thumbnail['created_at'], 'hashtag': data_new_thumbnail['hashtag'], 'city': city}

@phone_bp.route('/all_images', methods=['POST'])
@token_required
def all_images():
    collection = mongo_db['images']
    all_images_list = []
    for x in collection.find({}, {'hashtag': 0, 'latitude': 0, 'longitude': 0, 'created_at': 0}):
        all_images_list.append(str(x['_id']))
    

    return {'images': all_images_list}


@phone_bp.route('/all_hashtags', methods=['POST'])
@token_required
def all_hashtags():
    collection = mongo_db['images']
    all_hashtags_list = []   
    for x in collection.find({}, {'_id': 0, 'latitude': 0, 'longitude': 0}):
        all_hashtags_list.append(x['hashtag'])
        

    return {'hashtags': all_hashtags_list}



