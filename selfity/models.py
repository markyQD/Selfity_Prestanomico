from flask import current_app
import pymongo
import redis

# SINGLETON CONNECTION - MONGO
class MongoClient(object):
    __instance = None
    mongo_client = pymongo.MongoClient(current_app.config['DB_HOST'])
    mongo_db = mongo_client['selfity']

    def __new__(cls):
        if MongoClient.__instance is None:
            MongoClient.__instance = object.__new__(cls)
        return MongoClient.__instance

# SINGLETON CONNECTION - REDIS
class RedisClient(object):
    __instance = None
    redis_client = redis.Redis(current_app.config['REDIS_HOST'], port=6379, db=0)

    def __new__(cls):
        if RedisClient.__instance is None:
            RedisClient.__instance = object.__new__(cls)
        return RedisClient.__instance


    

