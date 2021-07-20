from flask import Flask, request, render_template, url_for, redirect
from flask_restful import Resource, Api
from flask_mail import Mail, Message  # used for email
# used for serializer email and error handling
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from flask_cors import CORS
import boto3, botocore
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from urllib.parse import urlparse
import urllib.request
import base64
from oauth2client import GOOGLE_REVOKE_URI, GOOGLE_TOKEN_URI, client
from io import BytesIO
from pytz import timezone
import pytz
from dateutil.relativedelta import relativedelta
import math

from werkzeug.exceptions import BadRequest, NotFound

from dateutil.relativedelta import *
from decimal import Decimal
from datetime import datetime, date, timedelta
from hashlib import sha512
from math import ceil
import string
import random
import os
import hashlib 

#regex
import re
# from env_keys import BING_API_KEY, RDS_PW

import decimal
import sys
import json
import pytz
import pymysql
import requests
import stripe
import binascii
from datetime import datetime
import datetime as dt
from datetime import timezone 
import time
from env_file import RDS_PW, S3_BUCKET, S3_KEY, S3_SECRET_ACCESS_KEY

# RDS for AWS SQL 8.0
RDS_HOST = 'io-mysqldb8.cxjnrciilyjq.us-west-1.rds.amazonaws.com'
RDS_PORT = 3306
RDS_USER = 'admin'
RDS_DB = 'manifest'
s3 = boto3.client('s3')
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg'])


app = Flask(__name__)
cors = CORS(app, resources={r'/api/*': {'origins': '*'}})
# Set this to false when deploying to live application
app.config['DEBUG'] = True
# Adding for email testing
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'ptydtesting@gmail.com'
app.config['MAIL_PASSWORD'] = 'ptydtesting06282020'
app.config['MAIL_DEFAULT_SENDER'] = 'ptydtesting@gmail.com'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
# app.config['MAIL_DEBUG'] = True
# app.config['MAIL_SUPPRESS_SEND'] = False
# app.config['TESTING'] = False
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

mail = Mail(app)
s = URLSafeTimedSerializer('thisisaverysecretkey')
# API
api = Api(app)


# convert to UTC time zone when testing in local time zone
utc = pytz.utc
def getToday(): return datetime.strftime(datetime.now(utc), "%Y-%m-%d")
def getNow(): return datetime.strftime(datetime.now(utc),"%Y-%m-%d %H:%M:%S")

# Connect to MySQL database (API v2)
def connect():
    global RDS_PW
    global RDS_HOST
    global RDS_PORT
    global RDS_USER
    global RDS_DB

    print("Trying to connect to RDS (API v2)...")
    try:
        conn = pymysql.connect(host=RDS_HOST,
                               user=RDS_USER,
                               port=RDS_PORT,
                               passwd=RDS_PW,
                               db=RDS_DB,
                               charset='utf8mb4',
                               cursorclass=pymysql.cursors.DictCursor)
        print("Successfully connected to RDS. (API v2)")
        return conn
    except:
        print("Could not connect to RDS. (API v2)")
        raise Exception("RDS Connection failed. (API v2)")


# Disconnect from MySQL database (API v2)
def disconnect(conn):
    try:
        conn.close()
        print("Successfully disconnected from MySQL database. (API v2)")
    except:
        print("Could not properly disconnect from MySQL database. (API v2)")
        raise Exception("Failure disconnecting from MySQL database. (API v2)")


# Serialize JSON
def serializeResponse(response):
    try:
        for row in response:
            for key in row:
                if type(row[key]) is Decimal:
                    row[key] = float(row[key])
                elif isinstance(row[key], bytes):
                    row[key] = row[key].decode()
                elif (type(row[key]) is date or type(row[key]) is datetime) and row[key] is not None:
                    row[key] = row[key].strftime("%Y-%m-%d")
        return response
    except:
        raise Exception("Bad query JSON")

# Execute an SQL command (API v2)
# Set cmd parameter to 'get' or 'post'
# Set conn parameter to connection object
# OPTIONAL: Set skipSerialization to True to skip default JSON response serialization
def execute(sql, cmd, conn, skipSerialization=False):
    response = {}
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            if cmd == 'get':
                result = cur.fetchall()
                response['message'] = 'Successfully executed SQL query.'
                # Return status code of 280 for successful GET request
                response['code'] = 280
                if not skipSerialization:
                    result = serializeResponse(result)
                response['result'] = result
            elif cmd == 'post':
                conn.commit()
                response['message'] = 'Successfully committed SQL command.'
                # Return status code of 281 for successful POST request
                response['code'] = 281
            else:
                response['message'] = 'Request failed. Unknown or ambiguous instruction given for MySQL command.'
                # Return status code of 480 for unknown HTTP method
                response['code'] = 480
    except:
        response['message'] = 'Request failed, could not execute MySQL command.'
        # Return status code of 490 for unsuccessful HTTP request
        response['code'] = 490
    finally:
        # response['sql'] = sql
        return response


# Function to upload image to s3
def helper_upload_img(file):
    bucket = S3_BUCKET
    # creating key for image name
    salt = os.urandom(8)
    dk = hashlib.pbkdf2_hmac('sha256',  (file.filename).encode('utf-8') , salt, 100000, dklen=64)
    key = (salt + dk).hex()
    
    if file and allowed_file(file.filename):

        # image link
        filename = 'https://s3-us-west-1.amazonaws.com/' \
                   + str(bucket) + '/' + str(key)

        # uploading image to s3 bucket
        upload_file = s3.put_object(
                            Bucket=bucket,
                            Body=file,
                            Key=key,
                            ACL='public-read',
                            ContentType='image/jpeg'
                        )
        return filename
    return None

# Function to upload icons 
def helper_icon_img(url):

    bucket = S3_BUCKET
    response = requests.get(url, stream=True)

    if response.status_code==200:
        raw_data = response.content
        url_parser = urlparse(url)
        file_name = os.path.basename(url_parser.path)
        key = 'image' + "/" + file_name

        try:
           
            with open(file_name, 'wb') as new_file:
                new_file.write(raw_data)
    
            # Open the server file as read mode and upload in AWS S3 Bucket.
            data = open(file_name, 'rb')
            upload_file = s3.put_object(
                            Bucket=bucket,
                            Body=data,
                            Key=key,
                            ACL='public-read',
                            ContentType='image/jpeg')
            data.close()

            file_url = 'https://%s/%s/%s' % ('s3-us-west-1.amazonaws.com', bucket, key)

        except Exception as e:
            print("Error in file upload %s." % (str(e)))
        
        finally:
            new_file.close()
            os.remove(file_name)
    else:
        print("Cannot parse url")
  
    return file_url

def allowed_file(filename):
    # Checks if the file is allowed to upload
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Returns all Goals and Routines
class GoalsRoutines(Resource):
    def get(self, user_id):
        response = {}
        items = {}
        try:

            conn = connect()
            
            # Get all goals and routines of the user
            query = """SELECT * FROM goals_routines WHERE user_id = \'""" +user_id+ """\';"""

            items = execute(query,'get', conn)

            goal_routine_response = items['result']

            # Get all notification details 
            for i in range(len(goal_routine_response)):
                gr_id = goal_routine_response[i]['gr_unique_id']
                res = execute("""SELECT * FROM notifications WHERE gr_at_id = \'""" +gr_id+ """\';""", 'get', conn)
                items['result'][i]['notifications'] = list(res['result'])
            
            response['message'] = 'successful'
            response['result'] = items['result']

            return response, 200
        except:
            raise BadRequest('Get Routines Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns Goals with actions/tasks and instructions/steps
class GAI(Resource):
    def get(self, user_id):
        response = {}
        items = {}
        try:

            conn = connect()
            
            # Get all goals and routines of the user
            query = """SELECT * FROM goals_routines WHERE user_id = \'""" +user_id+ """\' AND is_persistent = 'False' AND is_available = 'True' AND is_displayed_today = 'True';"""

            items = execute(query,'get', conn)

            goal_routine_response = items['result']

            if len(goal_routine_response) == 0:
                response['message'] = 'No goals'
                return response
            
            else:
                for goal in goal_routine_response:
                    time = []
                    time = goal['start_day_and_time'].split(',')
                    time[1] = time[1][1:]
                    time_goal = datetime.strptime(time[1], '%I:%M:%S %p')
                    goal['start_time'] = str(time_goal)
                
                goal_routine_response.sort(key = lambda x:x['start_time']) 

                for goal in goal_routine_response:
                    del goal['start_time']

                # Get all notification details 
                for i in range(len(goal_routine_response)):
                    gr_id = goal_routine_response[i]['gr_unique_id']
                    res_actions = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'""" +gr_id+ """\';""", 'get', conn)
                
                    items['result'][i]['actions_tasks'] = list(res_actions['result'])

                    if len(res_actions['result']) > 0:
                        action_response = res_actions['result']
                        for j in range(len(action_response)):
                            print(action_response[j]['at_unique_id'])
                            res_ins = execute("""SELECT * FROM instructions_steps WHERE at_id = \'""" +action_response[j]['at_unique_id']+ """\' ORDER BY is_sequence;""", 'get', conn)
                            print(res_ins)
                            items['result'][i]['actions_tasks'][j]['instructions_steps'] = list(res_ins['result'])

                response['message'] = 'successful'
                response['result'] = items['result']

            return response, 200
        except:
            raise BadRequest('Get Routines Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns Routines with actions/tasks and instructions/steps
class RTS(Resource):
    def get(self, user_id):
        response = {}
        items = {}
        try:

            conn = connect()
            
            # Get all goals and routines of the user
            query = """SELECT * FROM goals_routines WHERE user_id = \'""" +user_id+ """\' AND is_persistent = 'True' AND is_available = 'True' AND is_displayed_today = 'True';"""

            items = execute(query,'get', conn)

            goal_routine_response = items['result']

            if len(goal_routine_response) == 0:
                response['message'] = 'No Routines'
                return response
            
            else:
                for routine in goal_routine_response:
                    time = []
                    time = routine['start_day_and_time'].split(',')
                    time[1] = time[1][1:]
                    time_goal = datetime.strptime(time[1], '%I:%M:%S %p')
                    routine['start_time'] = str(time_goal)
                
                goal_routine_response.sort(key = lambda x:x['start_time']) 

                for routine in goal_routine_response:
                    del routine['start_time']

                for i in range(len(goal_routine_response)):
                    gr_id = goal_routine_response[i]['gr_unique_id']
                    res_actions = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'""" +gr_id+ """\';""", 'get', conn)
                
                    items['result'][i]['actions_tasks'] = list(res_actions['result'])

                    if len(res_actions['result']) > 0:
                        action_response = res_actions['result']
                        for j in range(len(action_response)):
                            print(action_response[j]['at_unique_id'])
                            res_ins = execute("""SELECT * FROM instructions_steps WHERE at_id = \'""" +action_response[j]['at_unique_id']+ """\' ORDER BY is_sequence;""", 'get', conn)
                            print(res_ins)
                            items['result'][i]['actions_tasks'][j]['instructions_steps'] = list(res_ins['result'])

                response['message'] = 'successful'
                response['result'] = items['result']

                return response, 200
        except:
            raise BadRequest('Get Routines Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns Goals with actions/tasks and instructions/steps
class ActionsInstructions(Resource):
    def get(self, gr_id):
        response = {}
        items = {}
        try:

            conn = connect()
            goals = execute("""SELECT * FROM goals_routines WHERE gr_unique_id = \'""" +gr_id+ """\';""", 'get', conn)
            res_actions = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'""" +gr_id+ """\';""", 'get', conn)
            items['result'] = goals['result']
            items['result'][0]['actions_tasks'] = list(res_actions['result'])

            if len(res_actions['result']) > 0:
                action_response = res_actions['result']
                for j in range(len(action_response)):
                    res_ins = execute("""SELECT * FROM instructions_steps WHERE at_id = \'""" +action_response[j]['at_unique_id']+ """\';""", 'get', conn)
                    items['result'][0]['actions_tasks'][j]['instructions_steps'] = list(res_ins['result'])

            response['message'] = 'successful'
            response['result'] = items['result']

            return response, 200
        except:
            raise BadRequest('Get Routines Request failed, please try again later.')
        finally:
            disconnect(conn)

# # Returns all Goals and Routines
# class ChangeSublist(Resource):
#     def post(self, user_id):
#         response = {}
#         items = {}
#         try:

#             conn = connect()
            
#             # Get all goals and routines of the user
#             query = """SELECT * FROM goals_routines where user_id = \'""" +user_id+ """\';"""

#             items = execute(query,'get', conn)

#             goal_routine_response = items['result']

#             # Get all notification details 
#             for i in range(len(goal_routine_response)):
#                 gr_id = goal_routine_response[i]['gr_unique_id']
#                 res = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'""" +gr_id+ """\';""", 'get', conn)
#                 if len(res['result']) > 0:
#                      query = """UPDATE goals_routines
#                                 SET 
#                                     is_sublist_available = \'""" + "True" + """\'   
#                             WHERE gr_unique_id = \'""" +gr_id+ """\';"""
#                 else:
#                     query = """UPDATE goals_routines
#                                 SET 
#                                     is_sublist_available = \'""" + "False" + """\'   
#                             WHERE gr_unique_id = \'""" +gr_id+ """\';"""

            
#             response['message'] = 'successful'
#             response['result'] = items['result']

#             return response, 200
#         except:
#             raise BadRequest('Get Routines Request failed, please try again later.')
#         finally:
#             disconnect(conn)

# Returns Notifications
class GetNotifications(Resource):
    def get(self):
        response = {}
        items = {}
        try:

            conn = connect()
            users = []
            ta = []
            # get all goals and routines
            query = """SELECT * FROM goals_routines where is_displayed_today = 'True'
                            and is_available = 'True'
                            and is_complete = 'False';"""

            items = execute(query,'get', conn)
            goal_routine_response = items['result']

            all_users = execute("""Select user_unique_id, time_zone from users;""", 'get', conn)
            all_ta = execute("""Select ta_unique_id from ta_people;""", 'get', conn)

            for i in range(len(all_users['result'])):
                users.append(all_users['result'][i]['user_unique_id'])

            for i in range(len(all_ta['result'])):
                ta.append(all_ta['result'][i]['ta_unique_id'])
            
            for i in range(len(goal_routine_response)):
                gr_id = goal_routine_response[i]['gr_unique_id']
                # Get all notifications of each goal and routine
                res = execute("""Select * from notifications where gr_at_id = \'""" +gr_id+ """\';""", 'get', conn)

                # Get TA info if first notification is of TA
                if len(res['result']) > 0:
                    for j in range(len(res['result'])):
                        if res['result'][j]['user_ta_id'][0] == '2' and res['result'][j]['user_ta_id'] in ta:
                            query1 = """SELECT ta_guid_device_id_notification FROM ta_people where ta_unique_id = \'""" +res['result'][j]['user_ta_id']+ """\';"""
                            items1 = execute(query1, 'get', conn)
                            print(items1)
                            if len(items1['result']) > 0:
                                guid_response = items1['result']
                                items['result'][i]['notifications'] = list(res['result'])
                                items['result'][i]['notifications'][j]['guid'] = guid_response[0]['ta_guid_device_id_notification']

                        # Get User Info if first notification is of user
                        elif res['result'][j]['user_ta_id'][0] == '1' and res['result'][j]['user_ta_id'] in users:
                            query1 = """SELECT user_unique_id, cust_guid_device_id_notification FROM users where user_unique_id = \'""" +res['result'][j]['user_ta_id']+ """\';"""
                            items1 = execute(query1, 'get', conn)
                            if len(items1['result']) > 0:
                                guid_response = items1['result']
                                items['result'][i]['notifications'] = list(res['result'])
                                items['result'][i]['notifications'][j]['guid'] = guid_response[0]['cust_guid_device_id_notification']

                                for j in range(len(all_users['result'])):
                                    if res['result'][0]['user_ta_id'] == all_users['result'][j]['user_unique_id']:
                                        items['result'][i]['time_zone'] = all_users['result'][j]['time_zone']

            
                    
            response['message'] = 'successful'
            response['result'] = items['result']

            return response, 200
        except:
            raise BadRequest('Get Routines Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns Actions and Tasks of a Particular goal/routine
class ActionsTasks(Resource):
    def get(self, goal_routine_id):
        response = {}
        items = {}

        try:

            conn = connect()
        
            query = """SELECT * FROM actions_tasks WHERE goal_routine_id = \'""" +goal_routine_id+ """\';"""
            items = execute(query,'get', conn)

            response['result'] = items['result']
            response['message'] = 'successful'

            return response, 200
        except:
            raise BadRequest('Get Actions/Tasks Request failed, please try again later.')
        finally:
            disconnect(conn)

class InstructionsAndSteps(Resource):
    def get(self, action_task_id):
        response = {}
        items = {}

        try:

            conn = connect()
        
            query = """SELECT * FROM instructions_steps WHERE at_id = \'""" +action_task_id+ """\' ORDER BY is_sequence;"""
            items = execute(query,'get', conn)

            response['result'] = items['result']
            response['message'] = 'successful'

            return response, 200
        except:
            raise BadRequest('Get Instructions?steps Request failed, please try again later.')
        finally:
            disconnect(conn)


# Returns About me information
class AboutMe(Resource):
    def get(self, user_id):
        response = {}
        items = {}

        try:
            conn = connect()

            progress = execute("""SELECT * FROM about_me_history WHERE user_id = \'""" +user_id+ """\'
                                    ORDER BY about_history_id
                                    LIMIT 1;""", 'get', conn)

            progress_list = progress['result']

            if len(progress_list) > 0:
                first_date = progress_list[0]['datetime_gmt']
            else:
                first_date = ''

            # returns important people
            query = """ SELECT ta_people_id
                                , ta_email_id
                                , CONCAT(ta_first_name, SPACE(1), ta_last_name) as people_name
                                , ta_have_pic
                                , ta_picture
                                , important
                                , user_uid
                                , relation_type
                                , ta_phone_number as ta_phone
                                , advisor
                            FROM relationship
                            JOIN ta_people
                            ON ta_people_id = ta_unique_id
                            WHERE important = 'TRUE' and user_uid = \'""" +user_id+ """\';"""

            items1 = execute(query, 'get', conn)

            # returns users information
            items = execute("""SELECT user_have_pic
                                    , message_card
                                    , message_day
                                    , user_picture
                                    , user_first_name
                                    , user_last_name
                                    , user_email_id
                                    , evening_time
                                    , morning_time
                                    , afternoon_time
                                    , night_time
                                    , day_end
                                    , day_start
                                    , time_zone
                                    , user_phone_number
                                    , user_birth_date
                                    , user_history
                                    , user_major_events
                                FROM users
                            WHERE user_unique_id = \'""" +user_id+ """\';""", 'get', conn)

            items['result'][0]['datetime'] = first_date

            # COmbining the data resulted form both queries
            if len(items1['result']) > 0:
                response['result'] = items['result'] + items1['result']
            else:
                items1['result'] = [{ "important_people" : "no important people"}]
                response['result'] = items['result'] + items1['result']
            
            response['message'] = 'successful'
            return response, 200

        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns Time information
class TimeSettings(Resource):
    def get(self, user_id):
        response = {}
        items = {}

        try:
            conn = connect()
           
            # returns users information
            items = execute("""SELECT 
                                     evening_time
                                    , morning_time
                                    , afternoon_time
                                    , night_time
                                    , day_end
                                    , day_start
                                    , time_zone
                                FROM users
                            WHERE user_unique_id = \'""" +user_id+ """\';""", 'get', conn)

           
            response = items['result']
            
            return response, 200

        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns all users of a TA
class AllUsers(Resource):
    def get(self, email_id):
        response = {}
        items = {}

        try:
            conn = connect()

            # All users of a TA
            query = """SELECT DISTINCT(user_unique_id)
                            , CONCAT(user_first_name, SPACE(1), user_last_name) as user_name
                            , user_email_id
                            , user_picture
                            , time_zone
                        FROM
                        users
                        JOIN
                        relationship
                        ON user_unique_id = user_uid
                        JOIN ta_people
                        ON ta_people_id = ta_unique_id
                        WHERE advisor = '1' and ta_email_id = \'""" + email_id + """\';"""
            
            items = execute(query, 'get', conn)

            response['message'] = 'successful'
            response['result'] = items['result']
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns all TA that doesn't belong to the user
class ListAllTA(Resource):
    def get(self, user_id):    
        response = {}
        items = {}

        try:
            conn = connect()
            
            # Get all TA of the user
            query = """ SELECT DISTINCT ta_unique_id
                                , CONCAT(ta_first_name, SPACE(1), ta_last_name) as name
                                , ta_first_name
                                , ta_last_name
                                , ta_email_id
                        FROM ta_people
                        JOIN relationship on ta_unique_id = ta_people_id
                        WHERE user_uid = \'""" +user_id+ """\'
                        and advisor = '1';"""

            # Get all TA
            query2 = """SELECT DISTINCT ta_unique_id
                                , CONCAT(ta_first_name, SPACE(1), ta_last_name) as name
                                , ta_first_name
                                , ta_last_name
                                , ta_email_id
                        FROM ta_people
                        JOIN relationship on ta_unique_id = ta_people_id
                        WHERE advisor = '1';"""

            # Get all TA People
            query3 = """SELECT ta_unique_id
                                , CONCAT(ta_first_name, SPACE(1), ta_last_name) as name
                                , ta_first_name
                                , ta_last_name
                                , ta_email_id
                         FROM ta_people;"""

            # Get all TA People who also has at least one relationship
            query4 = """SELECT DISTINCT ta_unique_id
                                , CONCAT(ta_first_name, SPACE(1), ta_last_name) as name
                                , ta_first_name
                                , ta_last_name
                                , ta_email_id

                        FROM ta_people
                        JOIN relationship on ta_unique_id = ta_people_id;"""


            idTAResponse = execute(query, 'get', conn)
            allTAResponse = execute(query2, 'get', conn)
            allTATableResponse = execute(query3, 'get', conn)
            allPeopleRepsonse = execute(query4, 'get', conn)

            list = []
            final_list = []

            for i in range(len(idTAResponse['result'])):
                list.append(idTAResponse['result'][i]['ta_unique_id'])

            for i in range(len(allTAResponse['result'])):
                if allTAResponse['result'][i]['ta_unique_id'] not in list:
                    final_list.append(allTAResponse['result'][i])

            peopleList = []
            for i in range(len(allPeopleRepsonse['result'])):
                peopleList.append(allPeopleRepsonse['result'][i]['ta_unique_id'])

            # If new TA and doesn't have a single user
            for i in range(len(allTATableResponse['result'])):
                if allTATableResponse['result'][i]['ta_unique_id'] not in peopleList:
                    final_list.append(allTATableResponse['result'][i])

            response['message'] = 'successful'
            response['result'] = final_list

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns all TA that doesn't belong to the user
class ListAllTAForCopy(Resource):
    def get(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            
            # Get all TA of the user
            query = """ SELECT DISTINCT ta_unique_id
                                , CONCAT(ta_first_name, SPACE(1), ta_last_name) as name
                                , ta_first_name
                                , ta_last_name
                                , ta_email_id
                        FROM ta_people
                        JOIN relationship on ta_unique_id = ta_people_id
                        and advisor = '1';"""

            
            idTAResponse = execute(query, 'get', conn)

            for i in range(len(idTAResponse['result'])):
                query1 = """SELECT DISTINCT(user_unique_id)
                            , CONCAT(user_first_name, SPACE(1), user_last_name) as user_name
                            , user_email_id
                            , user_picture
                            , time_zone
                        FROM
                        users
                        JOIN
                        relationship
                        ON user_unique_id = user_uid
                        JOIN ta_people
                        ON ta_people_id = ta_unique_id
                        WHERE advisor = '1' and ta_email_id = \'""" + idTAResponse['result'][i]['ta_email_id'] + """\';"""
                
                userResponse = execute(query1, 'get', conn)
                idTAResponse['result'][i]['users'] = userResponse['result']
            response['message'] = 'successful'
            response['result'] = idTAResponse['result']

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class ListAllUsersForCopy(Resource):
    def get(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            
            # Get all Users
            userResponse = execute(""" SELECT DISTINCT user_unique_id
                                , CONCAT(user_first_name, SPACE(1), user_last_name) as name
                                , user_email_id
                        FROM users;""", 'get', conn)

            for i in range(len(userResponse['result'])):
                taResponse = execute(""" SELECT DISTINCT ta_unique_id
                                , CONCAT(ta_first_name, SPACE(1), ta_last_name) as name
                                , ta_first_name
                                , ta_last_name
                                , ta_email_id
                        FROM ta_people
                        JOIN relationship on ta_unique_id = ta_people_id
                        WHERE user_uid = \'""" +userResponse['result'][i]['user_unique_id']+ """\'
                        and advisor = '1';""", 'get', conn)

                
                userResponse['result'][i]['TA'] = taResponse['result']
            response['message'] = 'successful'
            response['result'] = userResponse['result']

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Add another TA for a user
class AnotherTAAccess(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()

            data = request.get_json(force=True)
            timestamp = getNow()

            ta_id = data['ta_people_id']
            user_id = data['user_id']

            query = ["Call get_relation_id;"]
            new_relation_id_response = execute(query[0], 'get', conn)
            new_relation_id = new_relation_id_response['result'][0]['new_id']

            # Add new relationship 
            query.append("""INSERT INTO relationship
                                        (id
                                        , r_timestamp
                                        , ta_people_id
                                        , user_uid
                                        , relation_type
                                        , ta_have_pic
                                        , ta_picture
                                        , important
                                        , advisor)
                            VALUES 
                                        ( \'""" + str(new_relation_id) + """\'
                                        , \'""" + str(timestamp) + """\'
                                        , \'""" + str(ta_id) + """\'
                                        , \'""" + str(user_id) + """\'
                                        , \'""" + 'advisor' + """\'
                                        , \'""" + 'False' + """\'
                                        , \'""" + '' + """\'
                                        , \'""" + 'True' + """\'
                                        , \'""" + str(1) + """\');""")

            items = execute(query[1], 'post', conn)

            response['message'] = 'successful'
            response['result'] = items

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns ALl People of a user
class ListAllPeople(Resource):
    def get(self, user_id):
        response = {}
        items = {}

        try:
            conn = connect()
            
            query = """SELECT user_uid
                            , CONCAT(user_first_name, SPACE(1), user_last_name) as user_name
                            , ta_people_id
                            , ta_email_id as email
                            , ta_have_pic as have_pic
                            , important as important
                            , CONCAT(ta_first_name, SPACE(1), ta_last_name) as name
                            , ta_phone_number as phone_number
                            , ta_picture as pic
                            , relation_type as relationship
                        FROM relationship
                        JOIN
                        ta_people ta
                        ON ta_people_id = ta_unique_id
                        JOIN users on user_uid = user_unique_id
                        WHERE user_uid = \'""" + user_id+  """\';"""
            print(query)
            items = execute(query,'get', conn)

            response['message'] = 'successful'
            response['result'] = items

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Add new Goal/Routine for a user
class AddNewGR(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            
            # Information getting from the application
            audio = request.form.get('audio')
            datetime_completed = request.form.get('datetime_completed')
            datetime_started = request.form.get('datetime_started')
            end_day_and_time = request.form.get('end_day_and_time')
            expected_completion_time = request.form.get('expected_completion_time')
            user_id = request.form.get('user_id')
            ta_id = request.form.get('ta_people_id')
            is_available = request.form.get('is_available')
            is_complete = request.form.get('is_complete')
            is_displayed_today = request.form.get('is_displayed_today')
            is_in_progress = request.form.get('is_in_progress')
            is_persistent = request.form.get('is_persistent')
            is_sublist_available = request.form.get('is_sublist_available')
            is_timed = request.form.get('is_timed')
            photo = request.files.get('photo')
            photo_url = request.form.get('photo_url')
            repeat = request.form.get('repeat')
            repeat_ends = request.form.get('repeat_type')
            repeat_ends_on = request.form.get('repeat_ends_on')
            repeat_every = request.form.get('repeat_every')
            repeat_frequency = request.form.get('repeat_frequency')
            repeat_occurences = request.form.get('repeat_occurences')
            repeat_week_days = request.form.get('repeat_week_days')
            start_day_and_time = request.form.get('start_day_and_time')
            ta_notifications = request.form.get('ta_notifications')
            ta_notifications = json.loads(ta_notifications)
            ta_before_is_enable = ta_notifications['before']['is_enabled']
            ta_before_is_set = ta_notifications['before']['is_set']
            ta_before_message = ta_notifications['before']['message']
            ta_before_time = ta_notifications['before']['time']
            ta_during_is_enable = ta_notifications['during']['is_enabled']
            ta_during_is_set = ta_notifications['during']['is_set']
            ta_during_message = ta_notifications['during']['message']
            ta_during_time = ta_notifications['during']['time']
            ta_after_is_enable = ta_notifications['after']['is_enabled']
            ta_after_is_set = ta_notifications['after']['is_set']
            ta_after_message = ta_notifications['after']['message']
            ta_after_time = ta_notifications['after']['time']
            gr_title = request.form.get('title')
            user_notifications = request.form.get('user_notifications')
            user_notifications = json.loads(user_notifications)
            user_before_is_enable = user_notifications['before']['is_enabled']
            user_before_is_set = user_notifications['before']['is_set']
            user_before_message = user_notifications['before']['message']
            user_before_time = user_notifications['before']['time']
            user_during_is_enable = user_notifications['during']['is_enabled']
            user_during_is_set = user_notifications['during']['is_set']
            user_during_message = user_notifications['during']['message']
            user_during_time = user_notifications['during']['time']
            user_after_is_enable = user_notifications['after']['is_enabled']
            user_after_is_set = user_notifications['after']['is_set']
            user_after_message = user_notifications['after']['message']
            user_after_time = user_notifications['after']['time']
            icon_type = request.form.get('type')
            description = 'Other'
            
            for i, char in enumerate(gr_title):
                if char == "'":
                    gr_title = gr_title[:i+1] + "'" + gr_title[i+1:]


            # creating dictionary for changing format for week days
            repeat_week_days = json.loads(repeat_week_days)
            dict_week_days = {"Sunday":"False", "Monday":"False", "Tuesday":"False", "Wednesday":"False", "Thursday":"False", "Friday":"False", "Saturday":"False"}
            for key in repeat_week_days:
                if repeat_week_days[key] == "Sunday":
                    dict_week_days["Sunday"] = "True"
                if repeat_week_days[key] == "Monday":
                    dict_week_days["Monday"] = "True"
                if repeat_week_days[key] == "Tuesday":
                    dict_week_days["Tuesday"] = "True"
                if repeat_week_days[key] == "Wednesday":
                    dict_week_days["Wednesday"] = "True"
                if repeat_week_days[key] == "Thursday":
                    dict_week_days["Thursday"] = "True"
                if repeat_week_days[key] == "Friday":
                    dict_week_days["Friday"] = "True"
                if repeat_week_days[key] == "Saturday":
                    dict_week_days["saturday"] = "True"

            # New Goal/Routine ID
            query = ["CALL get_gr_id;"]
            new_gr_id_response = execute(query[0],  'get', conn)
            new_gr_id = new_gr_id_response['result'][0]['new_id']

            # If picture is a link and not a file uploaded
            if not photo:
            # Add G/R to database
                query.append("""INSERT INTO goals_routines(gr_unique_id
                                , gr_title
                                , user_id
                                , is_available
                                , is_complete
                                , is_in_progress
                                , is_displayed_today
                                , is_persistent
                                , is_sublist_available
                                , is_timed
                                , photo
                                , `repeat`
                                , repeat_type
                                , repeat_ends_on
                                , repeat_every
                                , repeat_frequency
                                , repeat_occurences
                                , start_day_and_time
                                , repeat_week_days
                                , datetime_completed
                                , datetime_started
                                , end_day_and_time
                                , expected_completion_time)
                            VALUES 
                            ( \'""" + new_gr_id + """\'
                            , \'""" + gr_title + """\'
                            , \'""" + user_id + """\'
                            , \'""" + str(is_available).title() + """\'
                            , \'""" + str(is_complete).title() + """\'
                            , \'""" + str(is_in_progress).title() + """\'
                            , \'""" + str(is_displayed_today).title() + """\'
                            , \'""" + str(is_persistent).title() + """\'
                            , \'""" + 'False' + """\'
                            , \'""" + str(is_timed).title() + """\'
                            , \'""" + photo_url + """\'
                            , \'""" + str(repeat).title() + """\'
                            , \'""" + str(repeat_ends).title() + """\'
                            , \'""" + repeat_ends_on + """\'
                            , \'""" + str(repeat_every).title() + """\'
                            , \'""" + str(repeat_frequency).title() + """\'
                            , \'""" + str(repeat_occurences) + """\'
                            , \'""" + start_day_and_time + """\'
                            , \'""" + json.dumps(dict_week_days) + """\'
                            , \'""" + datetime_completed + """\'
                            , \'""" + datetime_started + """\'
                            , \'""" + end_day_and_time + """\'
                            , \'""" + expected_completion_time + """\');""")
                print(query[1])
                execute(query[1], 'post', conn)
            
            # If a new picture is uploaded
            else:

                gr_picture = helper_upload_img(photo)

                query.append("""INSERT INTO goals_routines(gr_unique_id
                                , gr_title
                                , user_id
                                , is_available
                                , is_complete
                                , is_in_progress
                                , is_displayed_today
                                , is_persistent
                                , is_sublist_available
                                , is_timed
                                , photo
                                , `repeat`
                                , repeat_type
                                , repeat_ends_on
                                , repeat_every
                                , repeat_frequency
                                , repeat_occurences
                                , start_day_and_time
                                , repeat_week_days
                                , datetime_completed
                                , datetime_started
                                , end_day_and_time
                                , expected_completion_time)
                            VALUES 
                            ( \'""" + new_gr_id + """\'
                            , \'""" + gr_title + """\'
                            , \'""" + user_id + """\'
                            , \'""" + str(is_available).title() + """\'
                            , \'""" + str(is_complete).title() + """\'
                            , \'""" + str(is_in_progress).title() + """\'
                            , \'""" + str(is_displayed_today).title() + """\'
                            , \'""" + str(is_persistent).title() + """\'
                            , \'""" + str(is_sublist_available).title() + """\'
                            , \'""" + str(is_timed).title() + """\'
                            , \'""" + gr_picture + """\'
                            , \'""" + str(repeat).title() + """\'
                            , \'""" + str(repeat_ends).title() + """\'
                            , \'""" + repeat_ends_on + """\'
                            , \'""" + str(repeat_every).title() + """\'
                            , \'""" + repeat_frequency + """\'
                            , \'""" + str(repeat_occurences) + """\'
                            , \'""" + start_day_and_time + """\'
                            , \'""" + json.dumps(dict_week_days) + """\'
                            , \'""" + datetime_completed + """\'
                            , \'""" + datetime_started + """\'
                            , \'""" + end_day_and_time + """\'
                            , \'""" + expected_completion_time + """\');""")

                # if the type of picture uploaded is icon then add it to icon table
                if icon_type == 'icon':
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , Description
                                , url
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + description + """\'
                                    , \'""" + gr_picture + """\');""", 'post', conn)

                # if the type of picture uploaded is picture then add it to icon table with the description
                else:
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , url
                                , Description
                                , user_id
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + gr_picture + """\'
                                    , \'""" + 'Image Uploaded' + """\'
                                    , \'""" + user_id + """\');""", 'post', conn)
                execute(query[1], 'post', conn)
            
            # New Notification ID
            new_notification_id_response = execute("CALL get_notification_id;",  'get', conn)
            new_notfication_id = new_notification_id_response['result'][0]['new_id']

            # TA notfication
            query.append("""Insert into notifications
                                (notification_id
                                    , user_ta_id
                                    , gr_at_id
                                    , before_is_enable
                                    , before_is_set
                                    , before_message
                                    , before_time
                                    , during_is_enable
                                    , during_is_set
                                    , during_message
                                    , during_time
                                    , after_is_enable
                                    , after_is_set
                                    , after_message
                                    , after_time) 
                                VALUES
                                (     \'""" + new_notfication_id + """\'
                                    , \'""" + ta_id + """\'
                                    , \'""" + new_gr_id + """\'
                                    , \'""" + str(ta_before_is_enable).title() + """\'
                                    , \'""" + str(ta_before_is_set).title() + """\'
                                    , \'""" + ta_before_message + """\'
                                    , \'""" + ta_before_time + """\'
                                    , \'""" + str(ta_during_is_enable).title() + """\'
                                    , \'""" + str(ta_during_is_set).title() + """\'
                                    , \'""" + ta_during_message + """\'
                                    , \'""" + ta_during_time + """\'
                                    , \'""" + str(ta_after_is_enable).title() + """\'
                                    , \'""" + str(ta_after_is_set).title() + """\'
                                    , \'""" + ta_after_message + """\'
                                    , \'""" + ta_after_time + """\');""")
            execute(query[2], 'post', conn)

            # New notification ID
            UserNotificationIDresponse = execute("CALL get_notification_id;",  'get', conn)
            UserNotificationID = UserNotificationIDresponse['result'][0]['new_id']

            # User notfication
            query.append("""Insert into notifications
                                (notification_id
                                    , user_ta_id
                                    , gr_at_id
                                    , before_is_enable
                                    , before_is_set
                                    , before_message
                                    , before_time
                                    , during_is_enable
                                    , during_is_set
                                    , during_message
                                    , during_time
                                    , after_is_enable
                                    , after_is_set
                                    , after_message
                                    , after_time) 
                                VALUES
                                (     \'""" + UserNotificationID + """\'
                                    , \'""" + user_id + """\'
                                    , \'""" + new_gr_id + """\'
                                    , \'""" + str(user_before_is_enable).title() + """\'
                                    , \'""" + str(user_before_is_set).title() + """\'
                                    , \'""" + user_before_message + """\'
                                    , \'""" + user_before_time + """\'
                                    , \'""" + str(user_during_is_enable).title() + """\'
                                    , \'""" + str(user_during_is_set).title() + """\'
                                    , \'""" + user_during_message + """\'
                                    , \'""" + user_during_time + """\'
                                    , \'""" + str(user_after_is_enable).title() + """\'
                                    , \'""" + str(user_after_is_set).title() + """\'
                                    , \'""" + user_after_message + """\'
                                    , \'""" + user_after_time + """\');""")
            items = execute(query[3], 'post', conn)


            response['message'] = 'successful'
            response['result'] = new_gr_id

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update Goal/Routine of a user
class UpdateGR(Resource):
    def post(self): 
        response = {}
        items = {}
        try:
            conn = connect()

            audio = request.form.get('audio')
            id = request.form.get('id')
            datetime_completed = request.form.get('datetime_completed')
            datetime_started = request.form.get('datetime_started')
            end_day_and_time = request.form.get('end_day_and_time')
            expected_completion_time = request.form.get('expected_completion_time')
            user_id = request.form.get('user_id')
            ta_id = request.form.get('ta_people_id')
            is_available = request.form.get('is_available')
            is_complete = request.form.get('is_complete')
            is_displayed_today = request.form.get('is_displayed_today')
            is_in_progress = request.form.get('is_in_progress')
            is_persistent = request.form.get('is_persistent')
            is_sublist_available = request.form.get('is_sublist_available')
            is_timed = request.form.get('is_timed')
            photo = request.files.get('photo')
            photo_url = request.form.get('photo_url')
            repeat = request.form.get('repeat')
            repeat_ends = request.form.get('repeat_type')
            repeat_ends_on = request.form.get('repeat_ends_on')
            repeat_every = request.form.get('repeat_every')
            repeat_frequency = request.form.get('repeat_frequency')
            repeat_occurences = request.form.get('repeat_occurences')
            repeat_week_days = request.form.get('repeat_week_days')
            start_day_and_time = request.form.get('start_day_and_time')
            ta_notifications = request.form.get('ta_notifications')
            ta_notifications = json.loads(ta_notifications)
            ta_before_is_enabled = ta_notifications['before']['is_enabled']
            ta_before_is_set = ta_notifications['before']['is_set']
            ta_before_message = ta_notifications['before']['message']
            ta_before_time = ta_notifications['before']['time']
            ta_during_is_enabled = ta_notifications['during']['is_enabled']
            ta_during_is_set = ta_notifications['during']['is_set']
            ta_during_message = ta_notifications['during']['message']
            ta_during_time = ta_notifications['during']['time']
            ta_after_is_enabled = ta_notifications['after']['is_enabled']
            ta_after_is_set = ta_notifications['after']['is_set']
            ta_after_message = ta_notifications['after']['message']
            ta_after_time = ta_notifications['after']['time']
            gr_title = request.form.get('title')
            user_notifications = request.form.get('user_notifications')
            user_notifications = json.loads(user_notifications)
            user_before_is_enabled = user_notifications['before']['is_enabled']
            user_before_is_set = user_notifications['before']['is_set']
            user_before_message = user_notifications['before']['message']
            user_before_time = user_notifications['before']['time']
            user_during_is_enabled = user_notifications['during']['is_enabled']
            user_during_is_set = user_notifications['during']['is_set']
            user_during_message = user_notifications['during']['message']
            user_during_time = user_notifications['during']['time']
            user_after_is_enabled = user_notifications['after']['is_enabled']
            user_after_is_set = user_notifications['after']['is_set']
            user_after_message = user_notifications['after']['message']
            user_after_time = user_notifications['after']['time']
            icon_type = request.form.get('type')
            description = 'Other'

            for i, char in enumerate(gr_title):
                if char == "'":
                    gr_title = gr_title[:i+1] + "'" + gr_title[i+1:]

            repeat_week_days = json.loads(repeat_week_days)
            dict_week_days = {"Sunday":"False", "Monday":"False", "Tuesday":"False", "Wednesday":"False", "Thursday":"False", "Friday":"False", "Saturday":"False"}
            for key in repeat_week_days:
                if repeat_week_days[key] == "Sunday":
                    dict_week_days["Sunday"] = "True"
                if repeat_week_days[key] == "Monday":
                    dict_week_days["Monday"] = "True"
                if repeat_week_days[key] == "Tuesday":
                    dict_week_days["Tuesday"] = "True"
                if repeat_week_days[key] == "Wednesday":
                    dict_week_days["Wednesday"] = "True"
                if repeat_week_days[key] == "Thursday":
                    dict_week_days["Thursday"] = "True"
                if repeat_week_days[key] == "Friday":
                    dict_week_days["Friday"] = "True"
                if repeat_week_days[key] == "Saturday":
                    dict_week_days["Saturday"] = "True"   

            if not photo:

                query = """UPDATE goals_routines
                                SET gr_title = \'""" + gr_title + """\'
                                    , is_available = \'""" + str(is_available).title() + """\'
                                    ,is_complete = \'""" + str(is_complete).title() + """\'
                                    ,is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                    ,is_displayed_today = \'""" + str(is_displayed_today).title() + """\'
                                    ,is_persistent = \'""" + str(is_persistent).title() + """\'
                                    ,is_timed = \'""" + str(is_timed).title() + """\'
                                    ,start_day_and_time = \'""" + start_day_and_time + """\'
                                    ,end_day_and_time = \'""" + end_day_and_time + """\'
                                    ,datetime_started = \'""" + datetime_started + """\'
                                    ,datetime_completed = \'""" + datetime_completed + """\'
                                    ,`repeat` = \'""" + str(repeat).title() + """\'
                                    ,repeat_type = \'""" + repeat_ends + """\'
                                    ,repeat_ends_on = \'""" + repeat_ends_on + """\'
                                    ,repeat_every = \'""" + str(repeat_every) + """\'
                                    ,repeat_week_days = \'""" + json.dumps(dict_week_days) + """\'
                                    ,repeat_frequency = \'""" + repeat_frequency + """\'
                                    ,repeat_occurences = \'""" + str(repeat_occurences) + """\'
                                    ,expected_completion_time = \'""" + expected_completion_time + """\'
                                    ,photo = \'""" + photo_url + """\'
                            WHERE gr_unique_id = \'""" +id+ """\';"""
               
            else:
                
                gr_picture = helper_upload_img(photo)
               
                # Update G/R to database
                query = """UPDATE goals_routines
                                SET gr_title = \'""" + gr_title + """\'
                                    , is_available = \'""" + str(is_available).title() + """\'
                                    ,is_complete = \'""" + str(is_complete).title() + """\'
                                    ,is_sublist_available = \'""" + str(is_sublist_available).title() + """\'
                                    ,is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                    ,is_displayed_today = \'""" + str(is_displayed_today).title() + """\'
                                    ,is_persistent = \'""" + str(is_persistent).title() + """\'
                                    ,is_timed = \'""" + str(is_timed).title() + """\'
                                    ,start_day_and_time = \'""" + start_day_and_time + """\'
                                    ,end_day_and_time = \'""" + end_day_and_time + """\'
                                    ,datetime_started = \'""" + datetime_started + """\'
                                    ,datetime_completed = \'""" + datetime_completed + """\'
                                    ,`repeat` = \'""" + str(repeat).title() + """\'
                                    ,repeat_type = \'""" + repeat_ends + """\'
                                    ,repeat_ends_on = \'""" + repeat_ends_on + """\'
                                    ,repeat_week_days = \'""" + json.dumps(dict_week_days) + """\'
                                    ,repeat_every = \'""" + str(repeat_every) + """\'
                                    ,repeat_frequency = \'""" + repeat_frequency + """\'
                                    ,repeat_occurences = \'""" + str(repeat_occurences) + """\'
                                    ,expected_completion_time = \'""" + expected_completion_time + """\'
                                    ,photo = \'""" + gr_picture + """\'
                            WHERE gr_unique_id = \'""" +id+ """\';"""

                if icon_type == 'icon':
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , Description
                                , url
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + description + """\'
                                    , \'""" + gr_picture + """\');""", 'post', conn)
                
                else:
                     
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , url
                                , Description
                                , user_id
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + gr_picture + """\'
                                    , \'""" + 'Image Uploaded' + """\'
                                    , \'""" + user_id + """\');""", 'post', conn)
            
            items = execute(query, 'post', conn)
                
            # USER notfication
            query1 = """UPDATE notifications
                             SET   before_is_enable = \'""" + str(user_before_is_enabled).title() + """\'
                                    , before_is_set  = \'""" + str(user_before_is_set).title() + """\'
                                    , before_message = \'""" + user_before_message + """\'
                                    , before_time = \'""" + user_before_time + """\'
                                    , during_is_enable = \'""" + str(user_during_is_enabled).title() + """\'
                                    , during_is_set = \'""" + str(user_during_is_set).title() + """\'
                                    , during_message = \'""" + user_during_message + """\'
                                    , during_time = \'""" + user_during_time + """\'
                                    , after_is_enable = \'""" + str(user_after_is_enabled).title() + """\'
                                    , after_is_set = \'""" + str(user_after_is_set).title() + """\'
                                    , after_message = \'""" + user_after_message + """\'
                                    , after_time  = \'""" + user_after_time + """\'
                                WHERE gr_at_id = \'""" +id+ """\' and user_ta_id = \'""" +user_id+ """\';"""
            execute(query1, 'post', conn)
            
            noti_res = execute("""SELECT * FROM notifications WHERE gr_at_id = \'""" +id+ """\' and user_ta_id  = \'""" +ta_id+ """\';""", 'get', conn)
            print(noti_res)

            if len(noti_res['result']) == 0:
               
                execute("""UPDATE notifications
                             SET   
                                    before_time = \'""" + ta_before_time + """\'
                                    , during_time = \'""" + ta_during_time + """\'
                                    , after_time  = \'""" + ta_after_time + """\'
                                WHERE gr_at_id = \'""" +id+ """\' and user_ta_id  != \'""" +user_id+ """\';""", 'get', conn)
                 # New notification ID
                UserNotificationIDresponse = execute("CALL get_notification_id;",  'get', conn)
                UserNotificationID = UserNotificationIDresponse['result'][0]['new_id']

              
                # User notfication
                execute("""Insert into notifications
                                (notification_id
                                    , user_ta_id
                                    , gr_at_id
                                    , before_is_enable
                                    , before_is_set
                                    , before_message
                                    , before_time
                                    , during_is_enable
                                    , during_is_set
                                    , during_message
                                    , during_time
                                    , after_is_enable
                                    , after_is_set
                                    , after_message
                                    , after_time) 
                                VALUES
                                (     \'""" + UserNotificationID + """\'
                                    , \'""" + ta_id + """\'
                                    , \'""" + id + """\'
                                    , \'""" + str(ta_before_is_enabled).title() + """\'
                                    , \'""" + str(ta_before_is_set).title() + """\'
                                    , \'""" + ta_before_message + """\'
                                    , \'""" + ta_before_time + """\'
                                    , \'""" + str(ta_during_is_enabled).title() + """\'
                                    , \'""" + str(ta_during_is_set).title() + """\'
                                    , \'""" + ta_during_message + """\'
                                    , \'""" + ta_during_time + """\'
                                    , \'""" + str(ta_after_is_enabled).title() + """\'
                                    , \'""" + str(ta_after_is_set).title() + """\'
                                    , \'""" + ta_after_message + """\'
                                    , \'""" + ta_after_time + """\');""", 'post', conn)
            else:
            # TA notfication
                execute("""UPDATE notifications
                             SET   
                                    before_time = \'""" + ta_before_time + """\'
                                    , during_time = \'""" + ta_during_time + """\'
                                    , after_time  = \'""" + ta_after_time + """\'
                                WHERE gr_at_id = \'""" +id+ """\' and user_ta_id  != \'""" +user_id+ """\';""", 'get', conn)
                query2 = """UPDATE notifications
                                SET   before_is_enable = \'""" + str(ta_before_is_enabled).title() + """\'
                                        , before_is_set  = \'""" + str(ta_before_is_set).title() + """\'
                                        , before_message = \'""" + ta_before_message + """\'
                                        , before_time = \'""" + ta_before_time + """\'
                                        , during_is_enable = \'""" + str(ta_during_is_enabled).title() + """\'
                                        , during_is_set = \'""" + str(ta_during_is_set).title() + """\'
                                        , during_message = \'""" + ta_during_message + """\'
                                        , during_time = \'""" + ta_during_time + """\'
                                        , after_is_enable = \'""" + str(ta_after_is_enabled).title() + """\'
                                        , after_is_set = \'""" + str(ta_after_is_set).title() + """\'
                                        , after_message = \'""" + ta_after_message + """\'
                                        , after_time  = \'""" + ta_after_time + """\'
                                    WHERE gr_at_id = \'""" +id+ """\' and user_ta_id  = \'""" +ta_id+ """\';"""
                execute(query2, 'post', conn)
            response['message'] = 'Update to Goal and Routine was Successful'
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)


class AddNewAT(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()

            audio = request.form.get('audio')
            datetime_completed = request.form.get('datetime_completed')
            datetime_started = request.form.get('datetime_started')
            expected_completion_time = request.form.get('expected_completion_time')
            gr_id = request.form.get('gr_id')
            is_timed = request.form.get('is_timed')
            is_available = request.form.get('is_available')
            is_complete = request.form.get('is_complete')
            is_in_progress = request.form.get('is_in_progress')
            is_must_do = request.form.get('is_must_do')
            is_sublist_available = request.form.get('is_sublist_available')
            photo = request.files.get('photo')
            photo_url = request.form.get('photo_url')
            at_title = request.form.get('title')
            available_end_time = request.form.get('available_end_time')
            available_start_time = request.form.get('available_start_time')
            icon_type = request.form.get('type')

            for i, char in enumerate(at_title):
                if char == "'":
                    at_title = at_title[:i+1] + "'" + at_title[i+1:]

            query = ["CALL get_at_id;"]
            NewATIDresponse = execute(query[0],  'get', conn)
            NewATID = NewATIDresponse['result'][0]['new_id']
            
            if not photo:
                
                query.append("""INSERT INTO actions_tasks(at_unique_id
                                , at_title
                                , goal_routine_id
                                , at_sequence
                                , is_available
                                , is_complete
                                , is_in_progress
                                , is_sublist_available
                                , is_must_do
                                , photo
                                , is_timed
                                , datetime_completed
                                , datetime_started
                                , expected_completion_time
                                , available_start_time
                                , available_end_time)
                            VALUES 
                            ( \'""" + NewATID + """\'
                            , \'""" + at_title + """\'
                            , \'""" + gr_id + """\'
                            , \'""" + '1' + """\'
                            , \'""" + str(is_available).title() + """\'
                            , \'""" + str(is_complete).title() + """\'
                            , \'""" + str(is_in_progress).title() + """\'
                            , \'""" + 'False'+ """\'
                            , \'""" + str(is_must_do).title() + """\'
                            , \'""" + photo_url + """\'
                            , \'""" + str(is_timed).title() + """\'
                            , \'""" + datetime_completed + """\'
                            , \'""" + datetime_started + """\'
                            , \'""" + expected_completion_time + """\'
                            , \'""" + available_start_time + """\'
                            , \'""" + available_end_time + """\' );""")
            
            else:
                
                at_picture = helper_upload_img(photo)
                print(at_picture)
                query.append("""INSERT INTO actions_tasks(at_unique_id
                                , at_title
                                , goal_routine_id
                                , at_sequence
                                , is_available
                                , is_complete
                                , is_in_progress
                                , is_sublist_available
                                , is_must_do
                                , photo
                                , is_timed
                                , datetime_completed
                                , datetime_started
                                , expected_completion_time
                                , available_start_time
                                , available_end_time)
                            VALUES 
                            ( \'""" + NewATID + """\'
                            , \'""" + at_title + """\'
                            , \'""" + gr_id + """\'
                            , \'""" + '1' + """\'
                            , \'""" + str(is_available).title() + """\'
                            , \'""" + str(is_complete).title() + """\'
                            , \'""" + str(is_in_progress).title() + """\'
                            , \'""" + str(is_sublist_available).title() + """\'
                            , \'""" + str(is_must_do).title() + """\'
                            , \'""" + at_picture + """\'
                            , \'""" + str(is_timed).title() + """\'
                            , \'""" + datetime_completed + """\'
                            , \'""" + datetime_started + """\'
                            , \'""" + expected_completion_time + """\'
                            , \'""" + available_start_time + """\'
                            , \'""" + available_end_time + """\' );""")

                if icon_type == 'icon':
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , Description
                                , url
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + description + """\'
                                    , \'""" + at_picture + """\');""", 'post', conn)
                
                else:
                     
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , url
                                , Description
                                , user_id
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + at_picture + """\'
                                    , \'""" + 'Image Uploaded' + """\'
                                    , \'""" + user_id + """\');""", 'post', conn)

            items = execute(query[1], 'post', conn)

            execute("""UPDATE goals_routines
                                SET 
                                    is_sublist_available = \'""" + "True" + """\'   
                            WHERE gr_unique_id = \'""" +gr_id+ """\';""", 'post', conn)

            response['message'] = 'successful'
            response['result'] = NewATID

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class AddNewIS(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()

            at_id = request.form.get('at_id')
            is_timed = request.form.get('is_timed')
            is_sequence = request.form.get('is_sequence')
            is_available = request.form.get('is_available')
            is_complete = request.form.get('is_complete')
            is_in_progress = request.form.get('is_in_progress')
            photo = request.files.get('photo')
            photo_url = request.form.get('photo_url')
            title = request.form.get('title')
            expected_completion_time = request.form.get('expected_completion_time')
            icon_type = request.form.get('type')

            for i, char in enumerate(title):
                if char == "'":
                    title = title[:i+1] + "'" + title[i+1:]
            
            query = ["CALL get_is_id;"]
            NewISIDresponse = execute(query[0],  'get', conn)
            NewISID = NewISIDresponse['result'][0]['new_id']
                
            if not photo:

                query.append("""INSERT INTO instructions_steps(unique_id
                                , title
                                , at_id
                                , is_sequence
                                , is_available
                                , is_complete
                                , is_in_progress
                                , photo
                                , is_timed
                                , expected_completion_time)
                            VALUES 
                            ( \'""" + NewISID + """\'
                            , \'""" + title + """\'
                            , \'""" + at_id + """\'
                            , \'""" + is_sequence + """\'
                            , \'""" + str(is_available).title() + """\'
                            , \'""" + str(is_complete).title() + """\'
                            , \'""" + str(is_in_progress).title() + """\'
                            , \'""" + photo_url + """\'
                            , \'""" + str(is_timed).title() + """\'
                            , \'""" + str(expected_completion_time) + """\');""")
            
            else:
                is_picture = helper_upload_img(photo)
                query.append("""INSERT INTO instructions_steps(unique_id
                                , title
                                , at_id
                                , is_sequence
                                , is_available
                                , is_complete
                                , is_in_progress
                                , photo
                                , is_timed
                                , expected_completion_time)
                            VALUES 
                            ( \'""" + NewISID + """\'
                            , \'""" + title + """\'
                            , \'""" + at_id + """\'
                            , \'""" + is_sequence + """\'
                            , \'""" + str(is_available).title() + """\'
                            , \'""" + str(is_complete).title() + """\'
                            , \'""" + str(is_in_progress).title() + """\'
                            , \'""" + is_picture + """\'
                            , \'""" + str(is_timed).title() + """\'
                            , \'""" + str(expected_completion_time) + """\');""")
                
                if icon_type == 'icon':
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , Description
                                , url
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + description + """\'
                                    , \'""" + is_picture + """\');""", 'post', conn)
                
                else:
                     
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , url
                                , Description
                                , user_id
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + is_picture + """\'
                                    , \'""" + 'Image Uploaded' + """\'
                                    , \'""" + user_id + """\');""", 'post', conn)

            items = execute(query[1], 'post', conn)

            execute("""UPDATE actions_tasks
                                SET 
                                    is_sublist_available = \'""" + "True" + """\'   
                            WHERE at_unique_id = \'""" +at_id+ """\';""", 'post', conn)
            res = {}
            items = execute("""Select * from actions_tasks WHERE at_unique_id = \'""" + at_id + """\';""", 'get', conn)
            
            res['at_id']  = at_id
            res['is_sublist_available'] = items['result'][0]['is_sublist_available']
            res['id'] = NewISID
            response['message'] = 'successful'
            response['result'] = res

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class UpdateIS(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()

            is_id = request.form.get('unique_id')
            is_timed = request.form.get('is_timed')
            is_sequence = request.form.get('is_sequence')
            is_available = request.form.get('is_available')
            is_complete = request.form.get('is_complete')
            is_in_progress = request.form.get('is_in_progress')
            photo = request.files.get('photo')
            photo_url = request.form.get('photo_url')
            title = request.form.get('title')
            expected_completion_time = request.form.get('expected_completion_time')
            icon_type = request.form.get('type')


            for i, char in enumerate(title):
                if char == "'":
                    title = title[:i+1] + "'" + title[i+1:]

            if not photo:
                items = execute("""UPDATE instructions_steps
                                SET title =  \'""" + title + """\'
                                , is_available = \'""" + str(is_available).title() + """\'
                                , is_complete = \'""" + str(is_complete).title() + """\'
                                , is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                , is_sequence = \'""" + str(is_sequence) + """\'
                                , photo = \'""" + photo_url + """\'
                                , is_timed = \'""" + str(is_timed).title() + """\'
                                , expected_completion_time = \'""" + str(expected_completion_time) + """\'
                                WHERE unique_id = \'""" + is_id + """\';""", 'post', conn)

            else:
                is_picture = helper_upload_img(photo)

                items = execute("""UPDATE instructions_steps
                                SET title =  \'""" + title + """\'
                                , is_available = \'""" + str(is_available).title() + """\'
                                , is_complete = \'""" + str(is_complete).title() + """\'
                                , is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                , is_sequence = \'""" + str(is_sequence) + """\'
                                , photo = \'""" + is_picture + """\'
                                , is_timed = \'""" + str(is_timed).title() + """\'
                                , expected_completion_time = \'""" + str(expected_completion_time) + """\'
                                WHERE unique_id = \'""" + is_id + """\';""", 'post', conn)
                if icon_type == 'icon':
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , Description
                                , url
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + description + """\'
                                    , \'""" + is_picture + """\');""", 'post', conn)
                    
                else:
                    NewIDresponse = execute("CALL get_image_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO image_upload(
                                uid
                                , url
                                , user_id
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + is_picture + """\'
                                    , \'""" + user_id + """\');""", 'post', conn)
            response['message'] = 'successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)


class UpdateAT(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()

            audio = request.form.get('audio')
            datetime_completed = request.form.get('datetime_completed')
            datetime_started = request.form.get('datetime_started')
            expected_completion_time = request.form.get('expected_completion_time')
            id = request.form.get('id')
            is_available = request.form.get('is_available')
            is_complete = request.form.get('is_complete')
            is_in_progress = request.form.get('is_in_progress')
            is_timed = request.form.get('is_timed')
            is_must_do = request.form.get('is_must_do')
            is_sublist_available = request.form.get('is_sublist_available')
            photo = request.files.get('photo')
            photo_url = request.form.get('photo_url')
            at_title = request.form.get('title')
            available_end_time = request.form.get('available_end_time')
            available_start_time = request.form.get('available_start_time')
            icon_type = request.form.get('type')

            for i, char in enumerate(at_title):
                if char == "'":
                    at_title = at_title[:i+1] + "'" + at_title[i+1:]

            if not photo:

                query = """UPDATE actions_tasks
                            SET  at_title = \'""" + at_title + """\'
                                , at_sequence = \'""" + '1' + """\'
                                , is_available = \'""" + str(is_available).title() + """\'
                                , is_complete = \'""" + str(is_complete).title() + """\'
                                , is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                , is_sublist_available = \'""" + str(is_sublist_available).title() + """\'
                                , is_must_do = \'""" + str(is_must_do).title() + """\'
                                , photo = \'""" + photo_url + """\'
                                , is_timed = \'""" + str(is_timed).title() + """\'
                                , datetime_completed =  \'""" + datetime_completed + """\'
                                , datetime_started = \'""" + datetime_started + """\'
                                , expected_completion_time = \'""" + expected_completion_time + """\'
                                , available_start_time = \'""" + available_start_time + """\'
                                , available_end_time = \'""" + available_end_time + """\'
                                WHERE at_unique_id = \'""" +id+ """\';"""

            else:
                gr_id_response = execute("""SELECT goal_routine_id from actions_tasks where at_unique_id = \'""" +id+ """\'""", 'get', conn)
                gr_id = gr_id_response['result'][0]['goal_routine_id']

                at_picture = helper_upload_img(photo)

                query = """UPDATE actions_tasks
                            SET  at_title = \'""" + at_title + """\'
                                , at_sequence = \'""" + '1' + """\'
                                , is_available = \'""" + str(is_available).title() + """\'
                                , is_complete = \'""" + str(is_complete).title() + """\'
                                , is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                , is_sublist_available = \'""" + str(is_sublist_available).title() + """\'
                                , is_must_do = \'""" + str(is_must_do).title() + """\'
                                , photo = \'""" + at_picture + """\'
                                , is_timed = \'""" + str(is_timed).title() + """\'
                                , datetime_completed =  \'""" + datetime_completed + """\'
                                , datetime_started = \'""" + datetime_started + """\'
                                , expected_completion_time = \'""" + expected_completion_time + """\'
                                , available_start_time = \'""" + available_start_time + """\'
                                , available_end_time = \'""" + available_end_time + """\'
                                WHERE at_unique_id = \'""" +id+ """\';"""
                    
                if icon_type == 'icon':
                    NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO icons(
                                uid
                                , Description
                                , url
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + description + """\'
                                    , \'""" + at_picture + """\');""", 'post', conn)
                    
                else:
                    NewIDresponse = execute("CALL get_image_id;",  'get', conn)
                    NewID = NewIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO image_upload(
                                uid
                                , url
                                , user_id
                                )VALUES(
                                    \'""" + NewID + """\'
                                    , \'""" + at_picture + """\'
                                    , \'""" + user_id + """\');""", 'post', conn)

            items = execute(query, 'post', conn)
            response['message'] = 'successful'
            response['result'] = "Update Successful"

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Delete Goal/Routine
class DeleteGR(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            goal_routine_id = data['goal_routine_id']

            query = ["""DELETE FROM goals_routines WHERE gr_unique_id = \'""" + goal_routine_id + """\';"""]
            
            execute(query[0], 'post', conn)
            
            execute("""DELETE FROM notifications 
                        WHERE gr_at_id = \'""" + goal_routine_id + """\';""", 'post', conn)

            query.append("""SELECT at_unique_id FROM actions_tasks 
                            WHERE goal_routine_id = \'""" + goal_routine_id + """\';""")

            atResponse = execute(query[1], 'get', conn)

            for i in range(len(atResponse['result'])):
                at_id = atResponse['result'][i]['at_unique_id']
                execute("""DELETE FROM actions_tasks WHERE at_unique_id = \'""" + at_id + """\';""", 'post', conn)
                execute("""DELETE FROM notifications 
                            WHERE gr_at_id = \'""" + at_id + """\';""", 'post', conn)

            response['message'] = 'successful'
            response['result'] = items

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Delete Action/Task
class DeleteAT(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            at_id = data['at_id']
            gr_id_response = execute("""Select goal_routine_id from actions_tasks WHERE at_unique_id = \'""" + at_id + """\';""", 'get', conn)
            gr_id = gr_id_response['result'][0]['goal_routine_id']
            query = ["""DELETE FROM actions_tasks WHERE at_unique_id = \'""" + at_id + """\';"""]
            execute(query[0], 'post', conn)

            gr_id_response_new = execute("""Select * from actions_tasks WHERE goal_routine_id = \'""" + gr_id + """\';""", 'get', conn)
            if len(gr_id_response_new['result']) == 0:
                execute("""UPDATE goals_routines
                                SET 
                                    is_sublist_available = \'""" + "False" + """\'   
                            WHERE gr_unique_id = \'""" +gr_id+ """\';""", 'post', conn)



            # execute("""DELETE FROM notifications 
            #                 WHERE gr_at_id = \'""" + at_id + """\';""", 'post', conn)

            response['message'] = 'successful'
            response['result'] = items

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class DeleteIS(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)
            res={}
            is_id = data['is_id']
            at_id_response = execute("""Select at_id from instructions_steps WHERE unique_id = \'""" + is_id + """\';""", 'get', conn)
            at_id = at_id_response['result'][0]['at_id']
            query = ["""DELETE FROM instructions_steps WHERE unique_id = \'""" + is_id + """\';"""]
            execute(query[0], 'post', conn)
            at_id_response_new = execute("""Select * from instructions_steps WHERE at_id = \'""" + at_id + """\';""", 'get', conn)
            
            if len(at_id_response_new['result']) == 0:
                execute("""UPDATE actions_tasks
                                SET 
                                    is_sublist_available = \'""" + "False" + """\'   
                            WHERE at_unique_id = \'""" +at_id+ """\';""", 'post', conn)

            # execute("""DELETE FROM notifications 
            #                 WHERE gr_at_id = \'""" + at_id + """\';""", 'post', conn)
            items = execute("""Select * from actions_tasks WHERE at_unique_id = \'""" + at_id + """\';""", 'get', conn)
            res['at_id']  = at_id
            res['is_sublist_available'] = items['result'][0]['is_sublist_available']
            response['message'] = 'successful'
            response['result'] = res

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class TodayGR(Resource):
    def get(self):
        items = {}
        response = {}
        try:
            conn = connect()
            theday = dt.date.today()
        
            cur_date = theday
            cur_week = cur_date.isocalendar()[1]
            cur_month = cur_date.month
            cur_year = cur_date.year
            listGR = []

            # For never and day frequency
            query = ["""SELECT gr_title
                            , user_id
                            , gr_unique_id
                            , start_day_and_time
                            , repeat_frequency
                            , repeat_every
                            , `repeat`
                            , repeat_type
                            , repeat_occurences
                            , repeat_ends_on
                             from goals_routines;"""]
            
            grResponse = execute(query[0], 'get', conn)

            for i in range(len(grResponse['result'])):
                if (grResponse['result'][i]['repeat']).lower() == 'true':
                    if (grResponse['result'][i]['repeat_type']).lower() == 'never':
                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'day':
                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            new_date = datetime_object
                            while(new_date <= cur_date):
                                if(new_date == cur_date):
                                    listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + timedelta(days=grResponse['result'][i]['repeat_every'])
                        # For never and week frequency
                
                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'week':
                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            start_week = datetime_object.isocalendar()[1]
                            new_week = start_week
                            new_date = datetime_object
                            while(new_date <= cur_date):
                                if (new_week - start_week) == int(grResponse['result'][i]['repeat_every']):
                                    start_week = new_week
                                    if (new_week == cur_week):
                                        listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + timedelta(weeks=grResponse['result'][i]['repeat_every'])
                                new_week = new_date.isocalendar()[1]

                        # For never and month frequency
                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'month':
                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            start_month = datetime_object.month
                            new_month = start_month
                            new_date = datetime_object
                            while(new_date <= cur_date):
                                if (new_month - start_month) == int(grResponse['result'][i]['repeat_every']):
                                    start_month = new_month
                                    if new_date == cur_date:
                                        listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + relativedelta(months=int(grResponse['result'][i]['repeat_every']))
                                new_month = new_date.month
                            
                        # For never and year frequency
                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'year':
                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            start_year = datetime_object.year
                            new_year = start_year
                            new_date = datetime_object
                            while(new_date <= cur_date):
                                if (new_year - start_year) == int(grResponse['result'][i]['repeat_every']):
                                    start_year = new_year
                                    if cur_date == new_date:
                                        listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + relativedelta(years=grResponse['result'][i]['repeat_every'])
                                new_year = new_date.year
                            print(listGR)

                    # For after and day frequency
                    if (grResponse['result'][i]['repeat_type']).lower() == 'after':

                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'day':
                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            new_date = datetime_object
                            occurence = 1
                            while new_date <= cur_date and occurence <= int(grResponse['result'][i]['repeat_occurences']):
                                if(new_date == cur_date):
                                    listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + timedelta(days=grResponse['result'][i]['repeat_every'])
                                occurence += 1

                        # # For after and week frequency
                        # if (grResponse['result'][i]['repeat_frequency']).lower() == 'week':

                        #     datetime_str = grResponse['result'][i]['start_day_and_time']
                        #     datetime_str = datetime_str.replace(",", "")
                        #     datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                        #     start_week = datetime_object.isocalendar()[1]
                        #     new_week = start_week
                        #     new_date = datetime_object
                        #     occurence = 1
                        #     while new_date <= cur_date and occurence <= int(grResponse['result'][i]['repeat_occurences']):
                        #         if (new_week - start_week) == int(grResponse5['result'][i]['repeat_every']):
                        #             start_week = new_week
                        #             occurence += 1
                        #             if (new_week == cur_week):
                        #                 listGR.append(grResponse['result'][i]['gr_unique_id'])
                        #         new_date = new_date + timedelta(weeks=grResponse['result'][i]['repeat_every'])
                        #         new_week = new_date.isocalendar()[1]

                        # For after and month frequency
                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'month':
                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            start_month = datetime_object.month
                            new_month = start_week
                            new_date = datetime_object
                            occurence = 1
                            while new_date <= cur_date and occurence <= int(grResponse['result'][i]['repeat_occurences']):
                                if (new_month - start_month) == int(grResponse['result'][i]['repeat_every']):
                                    start_month = new_month
                                    occurence += 1
                                    if new_date == cur_date:
                                        listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + relativedelta(months=grResponse['result'][i]['repeat_every'])
                                new_month = new_date.month

                        # For after and year frequency
                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'year':

                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            start_year = datetime_object.year
                            new_year = start_year
                            new_date = datetime_object
                            occurence = 1
                            while(new_date <= cur_date) and occurence <= int(grResponse['result'][i]['repeat_occurences']):
                                if (new_year - start_year) == int(grResponse['result'][i]['repeat_every']):
                                    start_year = new_year
                                    occurence += 1
                                    if new_date == cur_date:
                                        listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + relativedelta(years=grResponse['result'][i]['repeat_every'])
                                new_year = new_date.year
                            
                    if (grResponse['result'][i]['repeat_type']).lower() == 'on':
                        # For on and day frequency
                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'day':                
                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            end_datetime = grResponse['result'][i]['repeat_ends_on']
                            end_datetime = end_datetime.replace(" GMT-0700 (Pacific Daylight Time)", "")
                            end_datetime_object = datetime.strptime(end_datetime, "%a %b %d %Y %H:%M:%S").date()
                            new_date = datetime_object
                        
                            while(new_date <= cur_date and cur_date <= end_datetime_object):
                                if(new_date == cur_date):
                                    listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + timedelta(days=grResponse['result'][i]['repeat_every'])

                        # For on and week frequency
                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'week':

                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            end_datetime = grResponse['result'][i]['repeat_ends_on']
                            end_datetime = end_datetime.replace(" GMT-0700 (Pacific Daylight Time)", "")
                            end_datetime_object = datetime.strptime(end_datetime, "%a %b %d %Y %H:%M:%S").date()
                            start_week = datetime_object.isocalendar()[1]
                            new_week = start_week
                            new_date = datetime_object
                            occurence = 1
                            while(new_date <= cur_date and cur_date <= end_datetime_object):
                                if (new_week - start_week) == int(grResponse['result'][i]['repeat_every']):
                                    start_week = new_week
                                    occurence += 1
                                    if (new_week == cur_week):
                                        listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + timedelta(weeks=grResponse['result'][i]['repeat_every'])
                                new_week = new_date.isocalendar()[1]

                        # For on and month frequency

                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'month':

                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            end_datetime = grResponse['result'][i]['repeat_ends_on']
                            end_datetime = end_datetime.replace(" GMT-0700 (Pacific Daylight Time)", "")
                            end_datetime_object = datetime.strptime(end_datetime, "%a %b %d %Y %H:%M:%S").date()
                            start_month = datetime_object.month
                            new_month = start_week
                            new_date = datetime_object
                            while(new_date <= cur_date and cur_date <= end_datetime):
                                if (new_month - start_month) == int(grResponse['result'][i]['repeat_every']):
                                    start_month = new_month
                                    if new_date == cur_date:
                                        listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + relativedelta(months=grResponse['result'][i]['repeat_every'])
                                new_month = new_date.month

                        # For on and year frequency

                        if (grResponse['result'][i]['repeat_frequency']).lower() == 'year':

                            datetime_str = grResponse['result'][i]['start_day_and_time']
                            datetime_str = datetime_str.replace(",", "")
                            datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                            end_datetime = grResponse['result'][i]['repeat_ends_on']
                            end_datetime = end_datetime.replace(" GMT-0700 (Pacific Daylight Time)", "")
                            end_datetime_object = datetime.strptime(end_datetime, "%a %b %d %Y %H:%M:%S").date()
                            start_year = datetime_object.year
                            new_year = start_year
                            new_date = datetime_object
                            while(new_date <= cur_date and cur_date <= end_datetime_object):
                                if (new_year - start_year) == int(grResponse['result'][i]['repeat_every']):
                                    start_year = new_year
                                    if cur_date == new_date:
                                        listGR.append(grResponse['result'][i]['gr_unique_id'])
                                new_date = new_date + relativedelta(years=grResponse['result'][i]['repeat_every'])
                                new_year = new_date.year

                else:
                    datetime_str = grResponse['result'][i]['start_day_and_time']
                    print(grResponse['result'][i])
                    datetime_str = datetime_str.replace(",", "")
                    datetime_object = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                    print(datetime_object)
                    if(datetime_object == cur_date):
                            listGR.append(grResponse['result'][i]['gr_unique_id'])

            i  = len(query) - 1
            
            for id_gr in listGR:
                
                query.append("""SELECT * FROM goals_routines WHERE gr_unique_id = \'""" + id_gr + """\';""")
                i += 1
                new_item = (execute(query[i], 'get', conn))['result']
                    
                items.update({id_gr:new_item})
                    
            response['result'] = items
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)


# Add new people
class CreateNewPeople(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            ts  = getNow()

            user_id = request.form.get('user_id')
            email_id = request.form.get('email_id')
            name = request.form.get('name')
            relation_type = request.form.get('relationship')
            phone_number = request.form.get('phone_number')
            picture = request.files.get('picture')
            important = 'False'

            email_list = []
            
            if not picture:
                have_pic = 'FALSE'
            else:
                have_pic = 'TRUE'

            list = name.split()
            first_name = list[0]
            if len(list) == 1:
                last_name = ''
            else:
                last_name = list[1]

            query = ["Call get_relation_id;"]
            NewRelationIDresponse = execute(query[0], 'get', conn)
            NewRelationID = NewRelationIDresponse['result'][0]['new_id']

            query.append("""SELECT ta_email_id FROM ta_people;""")
            peopleResponse = execute(query[1], 'get', conn)
            email_list = []

            for i in range(len(peopleResponse['result'])):
                email_id_existing = peopleResponse['result'][i]['ta_email_id']
                email_list.append(email_id_existing)
            

            if email_id in email_list:
                
                typeResponse = execute("""SELECT ta_unique_id from ta_people WHERE ta_email_id = \'""" + email_id + """\';""", 'get', conn)
               
                relationResponse = execute("""SELECT id from relationship 
                                            WHERE ta_people_id = \'""" + typeResponse['result'][0]['ta_unique_id'] + """\'
                                            AND user_uid = \'""" + user_id + """\';""", 'get', conn)

                if len(relationResponse['result']) > 0:
                    if picture:
                        people_picture_url = helper_upload_img(picture)
                    else:
                        people_picture_url = ''

                    execute("""UPDATE relationship
                                SET r_timestamp = \'""" + str(ts) + """\'
                                , relation_type = \'""" + relation_type + """\'
                                , ta_have_pic = \'""" + str(have_pic).title() + """\'
                                , ta_picture = \'""" + people_picture_url + """\'
                                , important = \'""" + str(important).title() + """\'
                                WHERE user_uid = \'""" + user_id + """\' AND 
                                ta_people_id = \'""" + typeResponse['result'][0]['ta_unique_id'] + """\'""", 'post', conn)

                else:
                    if picture:
                        people_picture_url = helper_upload_img(picture, str(user_id) + '-' + str(NewRelationID))
                    else:
                        people_picture_url = ''

                    execute("""INSERT INTO relationship(
                        id
                        , r_timestamp
                        , ta_people_id
                        , user_uid
                        , relation_type
                        , ta_have_pic
                        , ta_picture
                        , important
                        , advisor)
                        VALUES ( 
                            \'""" + NewRelationID + """\'
                            , \'""" + str(ts) + """\'
                            , \'""" + typeResponse['result'][0]['ta_unique_id'] + """\'
                            , \'""" + user_id + """\'
                            , \'""" + relation_type + """\'
                            , \'""" + str(have_pic).title() + """\'
                            , \'""" + people_picture_url + """\'
                            , \'""" + str(important).title() + """\'
                            , \'""" + str(0) + """\')""", 'post', conn)

            else:
                NewPeopleIDresponse = execute("CALL get_ta_people_id;", 'get', conn)
                NewPeopleID = NewPeopleIDresponse['result'][0]['new_id']

                if picture:
                    people_picture_url = helper_upload_img(picture)
                else:
                    people_picture_url = ''

                execute("""INSERT INTO ta_people(
                                        ta_unique_id
                                        , ta_timestamp
                                        , ta_email_id
                                        , ta_first_name
                                        , ta_last_name
                                        , employer
                                        , password_hashed
                                        , ta_phone_number)
                                        VALUES ( 
                                            \'""" + NewPeopleID + """\'
                                            , \'""" + ts + """\'
                                            , \'""" + email_id + """\'
                                            , \'""" + first_name + """\'
                                            , \'""" + last_name + """\'
                                            , \'""" + '' + """\'
                                            , \'""" + '' + """\'
                                            , \'""" + phone_number + """\')""", 'post', conn)

                execute("""INSERT INTO relationship(
                                        id
                                        , r_timestamp
                                        , ta_people_id
                                        , user_uid
                                        , relation_type
                                        , ta_have_pic
                                        , ta_picture
                                        , important
                                        , advisor)
                                        VALUES ( 
                                            \'""" + NewRelationID + """\'
                                            , \'""" + str(ts) + """\'
                                            , \'""" + NewPeopleID + """\'
                                            , \'""" + user_id + """\'
                                            , \'""" + relation_type + """\'
                                            , \'""" + str(have_pic).title() + """\'
                                            , \'""" + people_picture_url + """\'
                                            , \'""" + str(important).title() + """\'
                                            , \'""" + str(0) + """\')""", 'post', conn)

                
            response['message'] = 'successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Delete Important people
class DeletePeople(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)
            user_id = data['user_id']
            ta_people_id = data['ta_people_id']
            
            
            execute("""DELETE FROM relationship
                        WHERE user_uid = \'""" + user_id + """\' AND
                        ta_people_id = \'""" + ta_people_id + """\' ;""", 'post', conn)
        
            response['message'] = 'successful'
            response['result'] = items

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update time and time zone
class UpdateTime(Resource):
    def post(self, user_id):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)
            time_zone = data['time_zone']
            morning_time = data['morning_time']
            afternoon_time = data['afternoon_time']
            evening_time = data['evening_time']
            night_time = data['night_time']
            day_start = data['day_start']
            day_end = data['day_end']
            
            
            execute(""" UPDATE users
                        SET 
                        time_zone = \'""" + time_zone + """\'
                        , morning_time = \'""" + morning_time + """\'
                        , afternoon_time = \'""" + afternoon_time + """\'
                        , evening_time = \'""" + evening_time + """\'
                        , night_time = \'""" + night_time + """\'
                        , day_start = \'""" + day_start + """\'
                        , day_end = \'""" + day_end + """\'
                        WHERE user_unique_id = \'""" + user_id + """\';""", 'post', conn)
        
            response['message'] = 'successful'
            response['result'] = items

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update time and time zone
# class CurrentStatus(Resource):
#     def get(self, user_id):    
#         response = {}
#         items = {}

#         try:
#             conn = connect()
           
            
#             goal_response = execute("""SELECT gr_unique_id, gr_title, is_in_progress, is_complete FROM goals_routines 
#                         WHERE user_id = \'""" + user_id + """\';""", 'get', conn)

#             if len(goal_response['result']) > 0
#                 for i in range(len(goal_response['result'])):
#                     at_response = execute("""SELECT at_unique_id, at_title, is_in_progress, is_complete FROM actions_tasks 
#                                     WHERE goal_routine_id =  \'""" + goal_response['result'][i]['gr_unique_id'] + """\';""", 'get', conn)

#                     if len(at_response['result']) > 0:
                    
#                         goal_response['result'][i]['actions_tasks'] = at_response['result']
                 

#             response['message'] = 'successful'
#             response['result'] = goal_response

#             return response, 200
#         except:
#             raise BadRequest('Request failed, please try again later.')
#         finally:
#             disconnect(conn)


# Update time and time zone
# class Reset(Resource):
#     def post(self, gr_unique_id):    
#         response = {}
#         items = {}

#         try:
#             conn = connect()
#             data = request.get_json(force=True)
           
            
#             execute(""" UPDATE goals_routines
#                         SET 
#                         is_in_progress = \'""" + 'False' + """\'
#                         , is_complete = \'""" + 'False' + """\'
#                         WHERE gr_unique_id = \'""" + gr_unique_id + """\';""", 'post', conn)

#             execute(""" UPDATE actions_actions
#                         SET 
#                         is_in_progress = \'""" + 'False' + """\'
#                         , is_complete = \'""" + 'False' + """\'
#                         WHERE goal_routine_id = \'""" + gr_unique_id + """\';""", 'post', conn)


#             response['message'] = 'successful'
#             response['result'] = items

#             return response, 200
#         except:
#             raise BadRequest('Request failed, please try again later.')
#         finally:
#             disconnect(conn)

# Update time and time zone
class ResetGR(Resource):
    def post(self, gr_id):    
        response = {}
        items = {}

        try:
            conn = connect()
           
            execute(""" UPDATE goals_routines
                        SET 
                        is_in_progress = \'""" + 'False' + """\'
                        , is_complete = \'""" + 'False' + """\'
                        WHERE gr_unique_id = \'""" + gr_id + """\';""", 'post', conn)

            actions = execute("""SELECT at_unique_id FROM actions_tasks WHERE goal_routine_id = \'""" + gr_id + """\';""", 'get', conn)

            execute(""" UPDATE actions_tasks
                        SET 
                        is_in_progress = \'""" + 'False' + """\'
                        , is_complete = \'""" + 'False' + """\'
                        WHERE goal_routine_id = \'""" + gr_id + """\';""", 'post', conn)

            if len(actions['result']) > 0:
                for i in range(len(actions['result'])):
                    execute(""" UPDATE instructions_steps
                            SET 
                            is_in_progress = \'""" + 'False' + """\'
                            , is_complete = \'""" + 'False' + """\'
                            WHERE at_id = \'""" + actions['result'][i]['at_unique_id'] + """\';""", 'post', conn)

            response['message'] = 'successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# New TA signup
class NewTA(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            ts = getNow()

            email_id = data['email_id']
            password = data['password']
            first_name = data['first_name']
            last_name = data['last_name']
            phone_number = data['phone_number']
            employer = data['employer']


            ta_id_response = execute("""SELECT ta_unique_id, password_hashed FROM ta_people
                                            WHERE ta_email_id = \'""" +email_id+ """\';""", 'get', conn)

            if len(ta_id_response['result']) > 0:
                response['message'] = "Email ID already exists."
            
            else:
            
                salt = os.urandom(32)
            
                dk = hashlib.pbkdf2_hmac('sha256',  password.encode('utf-8') , salt, 100000, dklen=128)
                key = (salt + dk).hex()

                new_ta_id_response = execute("CALL get_ta_people_id;", 'get', conn)
                new_ta_id = new_ta_id_response['result'][0]['new_id']

                user_info_query = execute("""SELECT * FROM users WHERE user_email_id = \'""" +email_id+ """\';""", 'get', conn)
                print(user_info_query)
                user_info = user_info_query['result']
                print(user_info)
                guid = 'null'

                if user_info:
                    guid = user_info[0]['cust_guid_device_id_notification']

                execute("""INSERT INTO ta_people(
                                            ta_unique_id
                                            , ta_timestamp
                                            , ta_email_id
                                            , ta_first_name
                                            , ta_last_name
                                            , employer
                                            , password_hashed
                                            , ta_phone_number
                                            , ta_guid_device_id_notification)                                        
                                            VALUES ( 
                                                \'""" + new_ta_id + """\'
                                                , \'""" + ts + """\'
                                                , \'""" + email_id + """\'
                                                , \'""" + first_name + """\'
                                                , \'""" + last_name + """\'
                                                , \'""" + employer + """\'
                                                , \'""" + key + """\'
                                                , \'""" + phone_number + """\'
                                                , \'""" + guid + """\')""", 'post', conn)
                response['message'] = 'successful'
                response['result'] = new_ta_id

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# TA social sign up
class TASocialSignUP(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            ts = getNow()

            email_id = data['email_id']
            first_name = data['first_name']
            last_name = data['last_name']
            phone_number = data['phone_number']
            employer = data['employer']

            ta_id_response = execute("""SELECT ta_unique_id, password_hashed FROM ta_people
                                            WHERE ta_email_id = \'""" +email_id+ """\';""", 'get', conn)
            
            if len(ta_id_response['result']) > 0:
                response['message'] = "Email ID already exists."
           
            else: 
                new_ta_id_response = execute("CALL get_ta_people_id;", 'get', conn)
                new_ta_id = new_ta_id_response['result'][0]['new_id']

                execute("""INSERT INTO ta_people(
                                                ta_unique_id
                                                , ta_timestamp
                                                , ta_email_id
                                                , ta_first_name
                                                , ta_last_name
                                                , employer
                                                , ta_phone_number)
                                            VALUES ( 
                                                \'""" + new_ta_id + """\'
                                                , \'""" + ts + """\'
                                                , \'""" + email_id + """\'
                                                , \'""" + first_name + """\'
                                                , \'""" + last_name + """\'
                                                , \'""" + employer + """\'
                                                , \'""" + phone_number + """\')""", 'post', conn)
                response['message'] = 'successful'
                response['result'] = new_ta_id

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Existing TA login
class TALogin(Resource):
    def get(self, email_id, password):    
        response = {}
        items = {}

        try:
            conn = connect()
            # data = request.get_json(force=True)
            # email_id = data['email_id']
            # password = data['password']
            temp = False
            emails = execute("""SELECT ta_email_id from ta_people;""", 'get', conn)
            for i in range(len(emails['result'])):
                email = emails['result'][i]['ta_email_id']
                if email == email_id:
                    temp = True
            if temp == True:
                emailIDResponse = execute("""SELECT ta_unique_id, password_hashed from ta_people where ta_email_id = \'""" + email_id + """\'""", 'get', conn)
                password_storage = emailIDResponse['result'][0]['password_hashed']

                original = bytes.fromhex(password_storage)
                salt_from_storage = original[:32] 
                key_from_storage = original[32:]

                new_dk = hashlib.pbkdf2_hmac('sha256',  password.encode('utf-8') , salt_from_storage, 100000, dklen=128)
                
                if key_from_storage == new_dk:
                    response['result'] = emailIDResponse['result'][0]['ta_unique_id']
                    response['message'] = 'Correct Email and Password'
                else:
                    response['result'] = False  
                    response['message'] = 'Wrong Password'
  

            if temp == False:
                response['result'] = False 
                response['message'] = 'Email ID doesnt exist'
           
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# TA social login
class TASocialLogin(Resource):
    def get(self, email_id):    
        response = {}
        items = {}

        try:
            conn = connect()
            # data = request.get_json(force=True)
            # email_id = data['email_id']
            # password = data['password']
            temp = False
            emails = execute("""SELECT ta_unique_id, ta_email_id from ta_people;""", 'get', conn)
            for i in range(len(emails['result'])):
                email = emails['result'][i]['ta_email_id']
                if email == email_id:
                    temp = True
                    ta_unique_id = emails['result'][i]['ta_unique_id']
            if temp == True:
                
                response['result'] = ta_unique_id
                response['message'] = 'Correct Email'
    
            if temp == False:
                response['result'] = False 
                response['message'] = 'Email ID doesnt exist'
           
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Creating new user
class CreateNewUser(Resource):
    def post(self):    
        response = {}
        items = {}
        timestamp = getNow()
        try:
            conn = connect()
            data = request.get_json(force=True)

           
            email_id = data['email_id']
            google_auth_token = data['google_auth_token']
            google_refresh_token = data['google_refresh_token']

            user_id_response = execute("""SELECT user_unique_id FROM users
                                            WHERE user_email_id = \'""" +email_id+ """\';""", 'get', conn)
            
            if len(user_id_response['result']) > 0:
                response['message'] = 'User already exists'

            else:
                user_id_response = execute("CAll get_user_id;", 'get', conn)
                new_user_id = user_id_response['result'][0]['new_id']


                execute("""INSERT INTO users(
                                user_unique_id
                                , user_timestamp
                                , user_email_id
                                , google_auth_token
                                , google_refresh_token
                                , user_have_pic
                                , user_picture
                                , user_social_media
                                , new_account
                                , cust_guid_device_id_notification)
                            VALUES ( 
                                \'""" + new_user_id + """\'
                                , \'""" + timestamp + """\'
                                , \'""" + email_id + """\'
                                , \'""" + google_auth_token + """\'
                                , \'""" + google_refresh_token + """\'
                                , \'""" + 'False' + """\'
                                , \'""" + '' + """\'
                                , \'""" + 'GOOGLE' + """\'
                                , \'""" + 'True' + """\'
                                , \'""" + 'null' + """\')""", 'post', conn)
                

                response['message'] = 'successful'
                response['result'] = new_user_id

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Creating new user
class ExistingUser(Resource):
    def post(self):    
        response = {}
        items = {}
        timestamp = getNow()
        try:
            conn = connect()
            data = request.get_json(force=True)

            timestamp = getNow()           
            email_id = data['email_id']
            ta_people_id = data['ta_people_id']

            user_id_response = execute("""SELECT user_unique_id, new_account FROM users
                                            WHERE user_email_id = \'""" +email_id+ """\';""", 'get', conn)
            
            print(user_id_response['result'])
            if len(user_id_response['result']) > 0:
                RelationshipResponse = execute("""SELECT * FROM relationship where ta_people_id = \'"""+ta_people_id+"""\' and user_uid = \'"""+user_id_response['result'][0]['user_unique_id']+"""\';""", 'get', conn)
                print(RelationshipResponse)
                if len(RelationshipResponse['result']) == 0:
                    print(user_id_response['result'][0])
                    if user_id_response['result'][0]['new_account'] == 'False':
                        NewRelationIDresponse = execute("Call get_relation_id;", 'get', conn)
                        NewRelationID = NewRelationIDresponse['result'][0]['new_id']
                        execute("""INSERT INTO relationship
                                                (id
                                                , ta_people_id
                                                , user_uid
                                                , r_timestamp
                                                , relation_type
                                                , ta_have_pic
                                                , ta_picture
                                                , important
                                                , advisor)
                                                VALUES 
                                                ( \'""" + NewRelationID + """\'
                                                , \'""" + ta_people_id + """\'
                                                , \'""" +user_id_response['result'][0]['user_unique_id']+ """\'
                                                , \'""" + timestamp + """\'
                                                , \'""" + 'advisor' + """\'
                                                , \'""" + 'False' + """\'
                                                , \'""" + '' + """\'
                                                , \'""" + 'True' + """\'
                                                , \'""" + str(1) + """\');""", 'post', conn)
                        print("Added")
                response['message'] = user_id_response['result'][0]['new_account']

            else:
                response['message'] = 'true'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update new user
class UpdateAboutMe(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()

            timestamp = getNow()

            people_id = []
            people_have_pic = []
            people_name = []
            people_pic = []
            people_relationship = []
            people_important = []
            people_user_id = []
            people_phone_number = []
            relation_type = []

            user_id = request.form.get('user_id')
            phone_number = request.form.get('phone_number')
            history = request.form.get('history')
            major_events = request.form.get('major_events')
            birth_date = request.form.get('birth_date')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            have_pic = request.form.get('have_pic')
            message_card =  request.form.get('message_card')
            message_day = request.form.get('message_day')
            picture = request.files.get('picture')
            people = request.form.get('people')
            time_settings = request.form.get("timeSettings")
            photo_url = request.form.get("photo_url")            
            time_settings = json.loads(time_settings)
            afternoon_time = time_settings["afternoon"]
            day_end = time_settings["dayEnd"]
            day_start = time_settings["dayStart"]
            evening_time = time_settings["evening"]
            morning_time = time_settings["morning"]
            night_time = time_settings["night"]
            time_zone = time_settings["timeZone"]
            print(time_settings)
          
            # birth_date = birth_date[0:len(birth_date)-1]
            if not picture:
                execute("""UPDATE  users
                                SET 
                                    user_first_name = \'""" + first_name + """\'
                                    , user_timestamp = \'""" + timestamp + """\'
                                    , user_have_pic = \'""" + str(have_pic).title() + """\'
                                    , user_picture = \'""" + photo_url + """\'
                                    , message_card = \'""" + str(message_card) + """\'
                                    , message_day = \'""" + str(message_day) + """\'
                                    , user_last_name =  \'""" + last_name + """\'
                                    , time_zone = \'""" + str(time_zone) + """\'
                                    , morning_time = \'""" + str(morning_time) + """\'
                                    , afternoon_time = \'""" + str(afternoon_time) + """\'
                                    , evening_time = \'""" + str(evening_time) + """\'
                                    , night_time = \'""" + str(night_time) + """\'
                                    , day_start = \'""" + str(day_start) + """\'
                                    , day_end = \'""" + str(day_end) + """\'
                                    , user_birth_date = \'""" + str(birth_date) + """\'
                                    , user_phone_number = \'""" + phone_number + """\'
                                    , user_history = \'""" + history + """\'
                                    , user_major_events = \'""" + major_events + """\'
                                WHERE user_unique_id = \'""" + user_id + """\' ;""", 'post', conn)
            else:
                user_photo_url = helper_upload_img(picture)
                execute("""UPDATE  users
                                SET 
                                    user_first_name = \'""" + first_name + """\'
                                    , user_timestamp = \'""" + timestamp + """\'
                                    , user_have_pic = \'""" + str(have_pic).title() + """\'
                                    , user_picture = \'""" + str(user_photo_url) + """\'
                                    , message_card = \'""" + str(message_card) + """\'
                                    , message_day = \'""" + str(message_day) + """\'
                                    , user_last_name =  \'""" + last_name + """\'
                                    , time_zone = \'""" + str(time_zone) + """\'
                                    , morning_time = \'""" + str(morning_time) + """\'
                                    , afternoon_time = \'""" + str(afternoon_time) + """\'
                                    , evening_time = \'""" + str(evening_time) + """\'
                                    , night_time = \'""" + str(night_time) + """\'
                                    , day_start = \'""" + str(day_start) + """\'
                                    , day_end = \'""" + str(day_end) + """\'
                                    , user_birth_date = \'""" + birth_date + """\'
                                    , user_phone_number = \'""" + phone_number + """\'
                                    , user_history = \'""" + history + """\'
                                    , user_major_events = \'""" + major_events + """\'
                                WHERE user_unique_id = \'""" + user_id + """\' ;""", 'post', conn)
            
            
            response['message'] = 'successful'
            response['result'] = 'Update to about me successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update new user
class UpdateAboutMe2(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()

            timestamp = getNow()

            people_id = []
            people_have_pic = []
            people_name = []
            people_pic = []
            people_relationship = []
            people_important = []
            people_user_id = []
            people_phone_number = []
            relation_type = []

            user_id = request.form.get('user_id')
            phone_number = request.form.get('phone_number')
            birth_date = request.form.get('birth_date')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            have_pic = request.form.get('have_pic')
            message_card =  request.form.get('message_card')
            message_day = request.form.get('message_day')
            picture = request.files.get('picture')
            people = request.form.get('people')
            time_settings = request.form.get("timeSettings")
            photo_url = request.form.get("photo_url")            
            time_settings = json.loads(time_settings)
            afternoon_time = time_settings["afternoon"]
            day_end = time_settings["dayEnd"]
            day_start = time_settings["dayStart"]
            evening_time = time_settings["evening"]
            morning_time = time_settings["morning"]
            night_time = time_settings["night"]
            time_zone = time_settings["timeZone"]
            print(time_settings)
          
            # birth_date = birth_date[0:len(birth_date)-1]
            if not picture:
                execute("""UPDATE  users
                                SET 
                                    user_first_name = \'""" + first_name + """\'
                                    , user_timestamp = \'""" + timestamp + """\'
                                    , user_have_pic = \'""" + str(have_pic).title() + """\'
                                    , user_picture = \'""" + photo_url + """\'
                                    , message_card = \'""" + str(message_card) + """\'
                                    , message_day = \'""" + str(message_day) + """\'
                                    , user_last_name =  \'""" + last_name + """\'
                                    , time_zone = \'""" + str(time_zone) + """\'
                                    , morning_time = \'""" + str(morning_time) + """\'
                                    , afternoon_time = \'""" + str(afternoon_time) + """\'
                                    , evening_time = \'""" + str(evening_time) + """\'
                                    , night_time = \'""" + str(night_time) + """\'
                                    , day_start = \'""" + str(day_start) + """\'
                                    , day_end = \'""" + str(day_end) + """\'
                                    , user_birth_date = \'""" + str(birth_date) + """\'
                                    , user_phone_number = \'""" + phone_number + """\'
                                WHERE user_unique_id = \'""" + user_id + """\' ;""", 'post', conn)
            else:
                user_photo_url = helper_upload_img(picture)
                execute("""UPDATE  users
                                SET 
                                    user_first_name = \'""" + first_name + """\'
                                    , user_timestamp = \'""" + timestamp + """\'
                                    , user_have_pic = \'""" + str(have_pic).title() + """\'
                                    , user_picture = \'""" + str(user_photo_url) + """\'
                                    , message_card = \'""" + str(message_card) + """\'
                                    , message_day = \'""" + str(message_day) + """\'
                                    , user_last_name =  \'""" + last_name + """\'
                                    , time_zone = \'""" + str(time_zone) + """\'
                                    , morning_time = \'""" + str(morning_time) + """\'
                                    , afternoon_time = \'""" + str(afternoon_time) + """\'
                                    , evening_time = \'""" + str(evening_time) + """\'
                                    , night_time = \'""" + str(night_time) + """\'
                                    , day_start = \'""" + str(day_start) + """\'
                                    , day_end = \'""" + str(day_end) + """\'
                                    , user_birth_date = \'""" + birth_date + """\'
                                    , user_phone_number = \'""" + phone_number + """\'
                                WHERE user_unique_id = \'""" + user_id + """\' ;""", 'post', conn)
            
            
            response['message'] = 'successful'
            response['result'] = 'Update to about me successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update new user
class UpdatePeople(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()

            timestamp = getNow()

            user_id = request.form.get('user_id')
            ta_id = request.form.get('ta_id')
            people_id = request.form.get('ta_people_id')
            people_name = request.form.get('name')
            people_relationship = request.form.get('relationship')
            people_phone_number = request.form.get('phone_number')
            people_important = request.form.get('important')
            people_have_pic = request.form.get('have_pic')
            people_pic = request.files.get('pic')
            photo_url = request.form.get("photo_url")

            list = people_name.split(" ", 1)
            first_name = list[0]
            if len(list) == 1:
                last_name = ''
            else:
                last_name = list[1]

            execute("""UPDATE  ta_people
                        SET 
                            ta_first_name = \'""" + first_name + """\'
                            , ta_timestamp = \'""" + timestamp + """\'
                            , ta_last_name = \'""" + last_name + """\'
                            , ta_phone_number =  \'""" + people_phone_number + """\'
                        WHERE ta_unique_id = \'""" + people_id + """\' ;""", 'post', conn)

            relationResponse = execute("""SELECT id FROM relationship 
                            WHERE ta_people_id = \'""" + people_id + """\' 
                            and user_uid = \'""" + user_id + """\';""", 'get', conn)

            people_picture_url = ""

            if not people_pic:
                         
                if len(relationResponse['result']) > 0:
            
                    items = execute("""UPDATE  relationship
                                    SET 
                                        r_timestamp = \'""" + timestamp + """\'
                                        , relation_type = \'""" + people_relationship + """\'
                                        , ta_have_pic =  \'""" + str(people_have_pic).title() + """\'
                                        , ta_picture = \'""" + photo_url + """\'
                                        , important = \'""" + str(people_important).title() + """\'
                                    WHERE ta_people_id = \'""" + people_id + """\' 
                                    and user_uid = \'""" + user_id + """\' ;""", 'post', conn)

                if len(relationResponse['result']) == 0:
                    NewRelationIDresponse = execute("Call get_relation_id;", 'get', conn)
                    NewRelationID = NewRelationIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO relationship
                                        (id
                                        , ta_people_id
                                        , user_uid
                                        , r_timestamp
                                        , relation_type
                                        , ta_have_pic
                                        , ta_picture
                                        , important
                                        , advisor)
                                        VALUES 
                                        ( \'""" + NewRelationID + """\'
                                        , \'""" + people_id + """\'
                                        , \'""" + user_id + """\'
                                        , \'""" + timestamp + """\'
                                        , \'""" + people_relationship + """\'
                                        , \'""" + str(people_have_pic).title() + """\'
                                        , \'""" + photo_url + """\'
                                        , \'""" + str(people_important).title() + """\'
                                        , \'""" + str(0) + """\');""", 'post', conn)
            

            else:
                people_picture_url = helper_upload_img(people_pic)

                if len(relationResponse['result']) > 0:
                
                    items = execute("""UPDATE  relationship
                                    SET 
                                        r_timestamp = \'""" + timestamp + """\'
                                        , relation_type = \'""" + people_relationship + """\'
                                        , ta_have_pic =  \'""" + str(people_have_pic).title() + """\'
                                        , ta_picture = \'""" + people_picture_url + """\'
                                        , important = \'""" + str(people_important).title() + """\'
                                    WHERE ta_people_id = \'""" + people_id + """\' 
                                    and user_uid = \'""" + user_id + """\' ;""", 'post', conn)

                if len(relationResponse['result']) == 0:
                    NewRelationIDresponse = execute("Call get_relation_id;", 'get', conn)
                    NewRelationID = NewRelationIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO relationship
                                        (id
                                        , ta_people_id
                                        , user_uid
                                        , r_timestamp
                                        , relation_type
                                        , ta_have_pic
                                        , ta_picture
                                        , important
                                        , advisor)
                                        VALUES 
                                        ( \'""" + NewRelationID + """\'
                                        , \'""" + people_id + """\'
                                        , \'""" + user_id + """\'
                                        , \'""" + timestamp + """\'
                                        , \'""" + people_relationship + """\'
                                        , \'""" + str(people_have_pic).title() + """\'
                                        , \'""" + people_picture_url + """\'
                                        , \'""" + str(people_important).title() + """\'
                                        , \'""" + str(0) + """\');""", 'post', conn)

                NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
                NewID = NewIDresponse['result'][0]['new_id']
                
                execute("""INSERT INTO icons(
                            uid
                            , url
                            , Description
                            , user_id
                            , ta_id
                            )VALUES(
                                \'""" + NewID + """\'
                                , \'""" + people_picture_url + """\'
                                , \'""" + 'People Picture' + """\'
                                , \'""" + user_id + """\'
                                , \'""" + ta_id + """\');""", 'post', conn)
            
            response['message'] = 'successful'
            response['result'] = 'Update to People successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update new user
class UpdateNameTimeZone(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            timestamp = getNow()
            conn = connect()
            data = request.get_json(force=True)
            # with open('/data.txt', 'w+') as outfile:
            #     json.dump(data, outfile)
            # ta_email = data['ta_email']


            ta_people_id = data['ta_people_id']
            user_unique_id = data['user_unique_id']
            first_name = data['first_name']
            last_name = data['last_name']
            time_zone = data["timeZone"]

            items = execute("""UPDATE  users
                            SET 
                                user_first_name = \'""" + first_name + """\'
                                , user_last_name =  \'""" + last_name + """\'
                                , time_zone = \'""" + time_zone + """\'
                                , user_timestamp = \'""" + timestamp + """\'
                                , morning_time = \'""" + '06:00' + """\'
                                , afternoon_time = \'""" + '11:00' + """\'
                                , evening_time = \'""" + '16:00' + """\'
                                , night_time = \'""" + '21:00' + """\'
                                , day_start = \'""" + '00:00' + """\'
                                , day_end = \'""" + '23:59' + """\'
                                , new_account = \'""" + 'False' + """\'
                                , message_card = \'""" + '' + """\'
                                , message_day = \'""" + '' + """\'
                            WHERE user_unique_id = \'""" + user_unique_id + """\' ;""", 'post', conn)

            NewRelationIDresponse = execute("Call get_relation_id;", 'get', conn)
            NewRelationID = NewRelationIDresponse['result'][0]['new_id']

            execute("""INSERT INTO relationship
                        (id
                        , r_timestamp
                        , ta_people_id
                        , user_uid
                        , relation_type
                        , ta_have_pic
                        , ta_picture
                        , important
                        , advisor)
                        VALUES 
                        ( \'""" + NewRelationID + """\'
                        , \'""" + timestamp + """\'
                        , \'""" + ta_people_id + """\'
                        , \'""" + user_unique_id + """\'
                        , \'""" + 'advisor' + """\'
                        , \'""" + 'False' + """\'
                        , \'""" + '' + """\'
                        , \'""" + 'True' + """\'
                        , \'""" + str(1) + """\');""", 'post', conn)

            response['message'] = 'successful'
            response['result'] = items

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

#User login
class UserLogin(Resource):
    def get(self, email_id):    
        response = {}
        items = {}

        try:
            conn = connect()
            
            temp = False
            emails = execute("""SELECT user_unique_id, user_email_id from users;""", 'get', conn)
            for i in range(len(emails['result'])):
                email = emails['result'][i]['user_email_id']
                if email == email_id:
                    temp = True
                    user_unique_id = emails['result'][i]['user_unique_id']
            if temp == True:
                
                response['result'] = user_unique_id
    
            if temp == False:
                response['result'] = False 
                response['message'] = 'Email ID doesnt exist'
           
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

#User login
class GetEmailId(Resource):
    def get(self, user_id):    
        response = {}
        items = {}

        try:
            conn = connect()
            
            temp = False
            emails = execute("""SELECT user_email_id from users where user_unique_id = \'""" +user_id+ """\';""", 'get', conn)
            if len(emails['result']) > 0:
                response['message'] = emails['result'][0]['user_email_id']
            else:
                response['message'] = 'User ID doesnt exist'
           
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# returns users token
class Usertoken(Resource):
    def get(self, user_id = None):
        response = {}
        items = {}

        try:
            conn = connect()
            query = None
                    
            query = """SELECT user_unique_id
                                , user_email_id
                                , google_auth_token
                                , google_refresh_token
                        FROM
                        users WHERE user_unique_id = \'""" + user_id + """\';"""
            
            items = execute(query, 'get', conn)
            print(items)
            response['message'] = 'successful'
            response['email_id'] = items['result'][0]['user_email_id']
            response['google_auth_token'] = items['result'][0]['google_auth_token']
            response['google_refresh_token'] = items['result'][0]['google_refresh_token']

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# # Creating new user
# class CreateNewUsers(Resource):
#     def post(self):    
#         response = {}
#         items = {}
#         timestamp = getNow()
#         try:
#             conn = connect()
#             data = request.get_json(force=True)

#             ta_people_id = data["ta_people_id"]
#             email_id = data['email_id']
#             google_auth_token = data['google_auth_token']
#             google_refresh_token = data['google_refresh_token']
#             first_name = data['first_name']
#             last_name = data['last_name']
#             time_zone = data["timeZone"]

#             UserIDResponse = execute("CAll get_user_id;", 'get', conn)
#             NewUserID = UserIDResponse['result'][0]['new_id']
            
#             execute("""INSERT INTO users(
#                             user_unique_id
#                             , user_timestamp
#                             , user_email_id
#                             , user_first_name
#                             , user_last_name
#                             , google_auth_token
#                             , google_refresh_token)
#                         VALUES ( 
#                             \'""" + NewUserID + """\'
#                             , \'""" + timestamp + """\'
#                             , \'""" + email_id + """\'
#                             , \'""" + first_name + """\'
#                             , \'""" + last_name + """\'
#                             , \'""" + google_auth_token + """\'
#                             , \'""" + google_refresh_token + """\')""", 'post', conn)

#             NewRelationIDresponse = execute("Call get_relation_id;", 'get', conn)
#             NewRelationID = NewRelationIDresponse['result'][0]['new_id']

#             print(NewRelationID)
#             execute("""INSERT INTO relationship
#                         (id
#                         , r_timestamp
#                         , ta_people_id
#                         , user_uid
#                         , relation_type
#                         , ta_have_pic
#                         , ta_picture
#                         , important)
#                         VALUES 
#                         ( \'""" + NewRelationID + """\'
#                         , \'""" + timestamp + """\'
#                         , \'""" + ta_people_id + """\'
#                         , \'""" + NewUserID + """\'
#                         , \'""" + 'advisor' + """\'
#                         , \'""" + 'FALSE' + """\'
#                         , \'""" + '' + """\'
#                         , \'""" + 'FALSE' + """\');""", 'post', conn)
#             response['message'] = 'successful'
#             return response, 200
#         except:
#             raise BadRequest('Request failed, please try again later.')
#         finally:
#             disconnect(conn)

# Add coordinates
class AddCoordinates(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)
            x = data['x']
            y = data['y']
            z = data['z']
            timestamp = data['timestamp']
            
            execute(""" INSERT INTO coordinates
                        (     x
                            , y
                            , z
                            , timestamp)
                            VALUES (
                                \'""" +str(x)+ """\'
                                ,\'""" +str(y)+ """\'
                                , \'""" +str(z)+ """\'
                                , \'""" +str(timestamp)+ """\'
                            );""", 'post', conn)
        
            response['message'] = 'successful'
            response['result'] = "Added in database"

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Add new Goal/Routine of a user
class UpdateGRWatchMobile(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            datetime_completed = data['datetime_completed']
            datetime_started = data['datetime_started']
            id = data['id']
            print(id)
            is_complete = data['is_complete']
            is_in_progress = data['is_in_progress']


            if datetime_started == "":
                query = """UPDATE goals_routines
                            SET 
                                is_complete = \'""" + str(is_complete).title() + """\'
                                ,is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                ,datetime_completed = \'""" + datetime_completed + """\'
                        WHERE gr_unique_id = \'""" +id+ """\';"""
                execute(query, 'post', conn)

            elif datetime_completed == "":
                query = """UPDATE goals_routines
                            SET 
                                is_complete = \'""" + str(is_complete).title() + """\'
                                ,is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                ,datetime_started = \'""" + datetime_started + """\'
                        WHERE gr_unique_id = \'""" +id+ """\';"""
                execute(query, 'post', conn)

            else:
                # Update G/R to database
                query = """UPDATE goals_routines
                                SET 
                                    is_complete = \'""" + str(is_complete).title() + """\'
                                    ,is_in_progress = \'""" + str(is_in_progress).title() + """\'
                                    ,datetime_started = \'""" + datetime_started + """\'
                                    ,datetime_completed = \'""" + datetime_completed + """\'
                            WHERE gr_unique_id = \'""" +id+ """\';"""
                execute(query, 'post', conn)

            response['message'] = 'Update to Goal and Routine was Successful'
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class UpdateATWatchMobile(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            datetime_completed = data['datetime_completed']
            datetime_started = data['datetime_started']
            id = data['id']
            is_complete = data['is_complete']
            is_in_progress = data['is_in_progress']

            if datetime_started == "":
                query = """UPDATE actions_tasks
                            SET  
                                is_complete = \'""" + str(is_complete).title() + """\'
                                , is_in_progress =  \'""" + str(is_in_progress).title() + """\'
                                , datetime_completed =  \'""" + datetime_completed + """\'
                                WHERE at_unique_id = \'""" +id+ """\';"""
                execute(query, 'post', conn)

            elif datetime_completed == "":
                query = """UPDATE actions_tasks
                            SET  
                                is_complete = \'""" + str(is_complete).title() + """\'
                                , is_in_progress =  \'""" + str(is_in_progress).title() + """\'
                                , datetime_started = \'""" + datetime_started + """\'
                                WHERE at_unique_id = \'""" +id+ """\';"""
                execute(query, 'post', conn)

            else:

                query = """UPDATE actions_tasks
                            SET  
                                is_complete = \'""" + str(is_complete).title() + """\'
                                , is_in_progress =  \'""" + str(is_in_progress).title() + """\'
                                , datetime_completed =  \'""" + datetime_completed + """\'
                                , datetime_started = \'""" + datetime_started + """\'
                                WHERE at_unique_id = \'""" +id+ """\';"""
                execute(query, 'post', conn)

            response['message'] = 'Update action and task successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class UpdateISWatchMobile(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            id = data['id']
            is_complete = data['is_complete']
            is_in_progress = data['is_in_progress']

            query = """UPDATE instructions_steps
                        SET  
                            is_complete = \'""" + str(is_complete).title() + """\'
                            , is_in_progress =  \'""" + str(is_in_progress).title() + """\'
                            WHERE unique_id = \'""" +id+ """\';"""

            execute(query, 'post', conn)

            response['message'] = 'Update instructions/steps successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# # Creating new user
# class UpdateTokens(Resource):
#     def post(self):    
#         response = {}
#         items = {}
#         timestamp = getNow()
#         try:
#             conn = connect()
#             data = request.get_json(force=True)

           
#             email_id = data['email_id']
#             google_auth_token = data['google_auth_token']
#             google_refresh_token = data['google_refresh_token']

#             user_id_response = execute("""SELECT user_unique_id FROM users
#                                             WHERE user_email_id = \'""" +email_id+ """\';""", 'get', conn)
            
#             if len(user_id_response['result']) > 0:
#                 response['message'] = 'User already exists'

#             else:
#                 user_id_response = execute("CAll get_user_id;", 'get', conn)
#                 new_user_id = user_id_response['result'][0]['new_id']


#                 execute("""INSERT INTO users(
#                                 user_unique_id
#                                 , user_timestamp
#                                 , user_email_id
#                                 , google_auth_token
#                                 , google_refresh_token
#                                 , user_have_pic
#                                 , user_picture)
#                             VALUES ( 
#                                 \'""" + new_user_id + """\'
#                                 , \'""" + timestamp + """\'
#                                 , \'""" + email_id + """\'
#                                 , \'""" + google_auth_token + """\'
#                                 , \'""" + google_refresh_token + """\'
#                                 , \'""" + 'False' + """\'
#                                 , \'""" + '' + """\')""", 'post', conn)

#                 response['message'] = 'successful'
#                 response['result'] = new_user_id

#             return response, 200
#         except:
#             raise BadRequest('Request failed, please try again later.')
#         finally:
#             disconnect(conn)

class Login(Resource):
    def post(self):
        response = {}
        try:
            conn = connect()
            data = request.get_json(force=True)

            email = data['email']
            social_id = data['social_id']
            # password = data.get('password')
            refresh_token = data.get('mobile_refresh_token')
            access_token = data.get('mobile_access_token')
            signup_platform = data.get('signup_platform')

            if email == "":

                query = """
                        SELECT user_unique_id,
                            user_last_name,
                            user_first_name,
                            user_email_id,
                            user_social_media,
                            google_auth_token,
                            google_refresh_token
                        FROM users
                        WHERE social_id = \'""" + social_id + """\';
                        """
              
                items = execute(query, 'get', conn)
               

            else: 
                query = """
                        SELECT user_unique_id,
                            user_last_name,
                            user_first_name,
                            user_email_id,
                            user_social_media,
                            google_auth_token,
                            google_refresh_token
                        FROM users
                        WHERE user_email_id = \'""" + email + """\';
                        """

              
                items = execute(query, 'get', conn)

            # print('Password', password)
            print(items)

            if items['code'] != 280:
                response['message'] = "Internal Server Error."
                response['code'] = 500
                return response
            elif not items['result']:
                items['message'] = 'User Not Found. Please signup'
                items['result'] = ''
                items['code'] = 404
                return items
            else:
                print(items['result'])
                print('sc: ', items['result'][0]['user_social_media'])
                
                if email == "":
                    execute("""UPDATE users SET mobile_refresh_token = \'""" +refresh_token+ """\'
                                            , mobile_auth_token =  \'""" +access_token+ """\'
                            WHERE social_id =  \'""" +social_id+ """\'""", 'post', conn)
                    query = "SELECT * from users WHERE social_id = \'" + social_id + "\';"
                    items = execute(query, 'get', conn)
                else:
                    print(email)
                    execute("""UPDATE users SET mobile_refresh_token = \'""" +refresh_token+ """\'
                                            , mobile_auth_token =  \'""" +access_token+ """\'
                                            , social_id =  \'""" +social_id+ """\'
                                            , user_social_media =  \'""" +signup_platform+ """\'


                            WHERE user_email_id =  \'""" +email+ """\'""", 'post', conn)

                    query = "SELECT * from users WHERE user_email_id = \'" + email + "\';"
                    items = execute(query, 'get', conn)
                items['message'] = "Authenticated successfully."
                items['code'] = 200
                return items
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class AccessRefresh(Resource):
    def post(self):
        response = {}
        items = {}
        try:
            conn = connect()
            data = request.get_json(force=True)

            user_id = data['user_unique_id']
            refresh_token = data.get('mobile_refresh_token')
            access_token = data.get('mobile_access_token')
            print(user_id)
            execute("""UPDATE users SET mobile_refresh_token = \'""" +refresh_token+ """\'
                                    , mobile_auth_token =  \'""" +access_token+ """\'
                    WHERE user_unique_id =  \'""" +user_id+ """\'""", 'post', conn)

                    
            items['message'] = "Updated successfully."
            items['code'] = 200
            return items
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GoogleCalenderEvents(Resource):
    def post(self):

        try:
            conn = connect()
            data = request.get_json(force=True)

            timestamp = getNow()
            user_unique_id = data["id"]
            start = data["start"]
            end = data["end"]

            items = execute("""SELECT user_email_id, google_refresh_token, google_auth_token, access_issue_time, access_expires_in FROM users WHERE user_unique_id = \'""" +user_unique_id+ """\'""", 'get', conn )
            
            if len(items['result']) == 0:
                return "No such user exists"
            print(items)
            if items['result'][0]['access_expires_in'] == None or items['result'][0]['access_issue_time'] == None:
                f = open('credentials.json',)
                data = json.load(f)
                client_id = data['web']['client_id']
                client_secret = data['web']['client_secret']
                refresh_token = items['result'][0]['google_refresh_token']
        
                params = {
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": items['result'][0]['google_refresh_token'],
                }
            
                authorization_url = "https://www.googleapis.com/oauth2/v4/token"
                r = requests.post(authorization_url, data=params)
                auth_token = ""
                if r.ok:
                        auth_token = r.json()['access_token']
                expires_in = r.json()['expires_in']
            
                execute("""UPDATE users SET 
                                google_auth_token = \'""" +str(auth_token)+ """\'
                                , access_issue_time = \'""" +str(timestamp)+ """\'
                                , access_expires_in = \'""" +str(expires_in)+ """\'
                                WHERE user_unique_id = \'""" +user_unique_id+ """\';""", 'post', conn)
                items = execute("""SELECT user_email_id, google_refresh_token, google_auth_token, access_issue_time, access_expires_in FROM users WHERE user_unique_id = \'""" +user_unique_id+ """\'""", 'get', conn )
                print(items)
                baseUri = "https://www.googleapis.com/calendar/v3/calendars/primary/events?orderBy=startTime&singleEvents=true&"            
                timeMaxMin = "timeMax="+end+"&timeMin="+start
                url = baseUri + timeMaxMin
                bearerString = "Bearer " + items['result'][0]['google_auth_token']
                headers = {"Authorization": bearerString, "Accept": "application/json"} 
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                calendars = response.json().get('items')
                return calendars

            else:
                access_issue_min = int(items['result'][0]['access_expires_in'])/60
                access_issue_time = datetime.strptime(items['result'][0]['access_issue_time'],"%Y-%m-%d %H:%M:%S")
                timestamp = datetime.strptime(timestamp,"%Y-%m-%d %H:%M:%S")
                diff = (timestamp - access_issue_time).total_seconds() / 60
                print(diff)
                if int(diff) > int(access_issue_min):
                    f = open('credentials.json',)
                    data = json.load(f)
                    client_id = data['web']['client_id']
                    client_secret = data['web']['client_secret']
                    refresh_token = items['result'][0]['google_refresh_token']
            
                    params = {
                        "grant_type": "refresh_token",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": items['result'][0]['google_refresh_token'],
                    }
                
                    authorization_url = "https://www.googleapis.com/oauth2/v4/token"
                    r = requests.post(authorization_url, data=params)
                    auth_token = ""
                    if r.ok:
                            auth_token = r.json()['access_token']
                    expires_in = r.json()['expires_in']
                
                    execute("""UPDATE users SET 
                                    google_auth_token = \'""" +str(auth_token)+ """\'
                                    , access_issue_time = \'""" +str(timestamp)+ """\'
                                    , access_expires_in = \'""" +str(expires_in)+ """\'
                                    WHERE user_unique_id = \'""" +user_unique_id+ """\';""", 'post', conn)
                    
                items = execute("""SELECT user_email_id, google_refresh_token, google_auth_token, access_issue_time, access_expires_in FROM users WHERE user_unique_id = \'""" +user_unique_id+ """\'""", 'get', conn )
                print(items)
                baseUri = "https://www.googleapis.com/calendar/v3/calendars/primary/events?orderBy=startTime&singleEvents=true&"            
                timeMaxMin = "timeMax="+end+"&timeMin="+start
                url = baseUri + timeMaxMin
                bearerString = "Bearer " + items['result'][0]['google_auth_token']
                headers = {"Authorization": bearerString, "Accept": "application/json"} 
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                calendars = response.json().get('items')
                return calendars
          
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetIconsHygiene(Resource):
    def get(self):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT url FROM icons where Description <> 'People Picture' and Description <> 'Image Uploaded' and Description = 'Hygiene';""", 'get', conn)
            print(items)
            response['message'] = 'successful'
            response['result'] = items['result']
            print(response)
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetIconsClothing(Resource):
    def get(self):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT url FROM icons where Description <> 'People Picture' and Description <> 'Image Uploaded' and Description = 'CLothing';""", 'get', conn)
            print(items)
            response['message'] = 'successful'
            response['result'] = items['result']
            print(response)
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetIconsFood(Resource):
    def get(self):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT url FROM icons where Description <> 'People Picture' and Description <> 'Image Uploaded' and Description = 'Food';""", 'get', conn)
            print(items)
            response['message'] = 'successful'
            response['result'] = items['result']
            print(response)
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetIconsActivities(Resource):
    def get(self):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT url FROM icons where Description <> 'People Picture' and Description <> 'Image Uploaded' and Description = 'Activities';""", 'get', conn)
            print(items)
            response['message'] = 'successful'
            response['result'] = items['result']
            print(response)
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetIconsOther(Resource):
    def get(self):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT url FROM icons where Description <> 'People Picture' and Description <> 'Image Uploaded' and Description = 'Other';""", 'get', conn)
            print(items)
            response['message'] = 'successful'
            response['result'] = items['result']
            print(response)
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetImages(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT url FROM icons where Description = 'Image Uploaded' and user_id = \'""" +user_id+ """\';""", 'get', conn)
            print(items)
            response['message'] = 'successful'
            response['result'] = items['result']
            print(response)
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetPeopleImages(Resource):
    def get(self, ta_id):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT url FROM icons where Description = 'People Picture' and ta_id = \'""" +ta_id+ """\';""", 'get', conn)
            print(items)
            response['message'] = 'successful'
            response['result'] = items['result']
            print(response)
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class UploadIcons(Resource):
    def post(self):
        response = {}
        try:
            conn = connect()
            data = request.get_json(force=True)
            photo_url = data['url']
            description = data['description']
            NewIDresponse = execute("CALL get_icon_id;",  'get', conn)
            NewID = NewIDresponse['result'][0]['new_id']

            new_icon_url = helper_icon_img(photo_url)
            print(new_icon_url)
            execute("""INSERT INTO icons(
                        uid
                        , Description
                        , url
                        )VALUES(
                            \'""" + NewID + """\'
                            , \'""" + description + """\'
                            , \'""" + new_icon_url + """\');""", 'post', conn)
            response['message'] = "Uploaded"
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetHistory(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT * FROM history where user_id = \'""" +user_id+ """\';""", 'get', conn)
           
            response['message'] = 'successful'
            response['result'] = items['result']
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GoalRoutineHistory(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()
            
            start_date = request.headers['start_date']
            end_date = request.headers['end_date']

            items = execute("""SELECT * FROM history where user_id = \'""" +user_id+ """\';""", 'get', conn)

            details_json = {}
            res = {}

            for i in range(len(items['result'])):
                if items['result'][i]['date_affected'] >= start_date and items['result'][i]['date_affected'] <= end_date:
                    goal = {}

                    if items['result'][i]['details'][0] == '[':
                        details_json = json.loads(items['result'][i]['details'])

                        for k in range(len(details_json)):
                            if len(details_json[k]) > 0:
                                if 'status' in details_json[k]:
                                    goal[details_json[k]['title']] = details_json[k]['status']
                                
                    else:
                        details_json = json.loads(items['result'][i]['details'])
                        for currKey, value in list(details_json.items()):
                   
                            if currKey[0] == '3':

                                if value['is_in_progress'].lower() == 'true':
                                    goal[value['title']] = 'in_progress'
                                
                                elif value['is_complete'].lower() == 'true':
                                    goal[value['title']] = 'completed'
                                
                                else:
                                    goal[value['title']] = 'not started'

                    if len(goal) > 0:
                        res[items['result'][i]['date_affected']] = goal
            
            today_date = getToday()

            goals = execute("""SELECT gr_unique_id, gr_title, is_in_progress, is_complete FROM goals_routines where user_id = \'""" +user_id+ """\' and is_displayed_today = 'True';""", 'get', conn)

            if len(goals['result']) > 0:
                goal = {}
                for i in range(len(goals['result'])):
                
                    if goals['result'][i]['is_in_progress'].lower() == 'true':
                        goal[goals['result'][i]['gr_title']] = 'in_progress'
                    elif goals['result'][i]['is_complete'].lower() == 'true':
                        goal[goals['result'][i]['gr_title']] = 'completed'
                    else:
                        goal[goals['result'][i]['gr_title']] = 'not started'

                res[today_date] = goal

            response['message'] = 'successful'
            response['result'] = res
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class ParticularGoalHistory(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()
            
            start_date = request.headers['start_date']
            print(start_date)
            end_date = request.headers['end_date']
            gr_id = request.headers['goal_routine_id']

            print(gr_id)

            items = execute("""SELECT * FROM history where user_id = \'""" +user_id+ """\';""", 'get', conn)

            details_json = {}
            res = {}

            for i in range(len(items['result'])):
                if items['result'][i]['date_affected'] >= start_date and items['result'][i]['date_affected'] <= end_date:
                    goal = [{}]
                    res_p = 0
                    if items['result'][i]['details'][0] == '[':
                        details_json = json.loads(items['result'][i]['details'])
                        for k in range(len(details_json)):
                            if len(details_json[k]) > 0:
                                if 'goal' in details_json[k] and 'status' in details_json[k] and gr_id == details_json[k]['goal']:

                                    goal[res_p][details_json[k]['title']] = details_json[k]['status']
                                    if 'actions' in details_json[k]:
                                        action = {}
                                        for j in range(len(details_json[k]['actions'])):
                                            action[details_json[k]['actions'][j]['title']] = details_json[k]['actions'][j]['status'] 
                                        goal[res_p]['actions'] = action

                                    res_p += 1

                    if len(goal[0]) > 1:
                        res[items['result'][i]['date_affected']] = dict(goal[0])

            today_date = getToday()

            goals = execute("""SELECT gr_unique_id, gr_title, is_in_progress, is_complete FROM goals_routines where user_id = \'""" +user_id+ """\' and is_displayed_today = 'True' and is_persistent = 'False';""", 'get', conn)

            if len(goals['result']) > 0:
                goal = {}
                for i in range(len(goals['result'])):
                    if gr_id == goals['result'][i]['gr_unique_id']:
                        if goals['result'][i]['is_in_progress'].lower() == 'true':
                            goal[goals['result'][i]['gr_title']] = 'in_progress'
                        elif goals['result'][i]['is_complete'].lower() == 'true':
                            goal[goals['result'][i]['gr_title']] = 'completed'
                        else:
                            goal[goals['result'][i]['gr_title']] = 'not started'
                        actions = execute("""SELECT at_unique_id, at_title, is_in_progress, is_complete FROM actions_tasks where goal_routine_id = \'""" +goals['result'][i]['gr_unique_id']+ """\';""", 'get', conn)
                        if len(actions['result']) > 0:
                            action = {}
                            for j in range(len(actions['result'])):
                                if actions['result'][j]['is_in_progress'].lower() == 'true':
                                    action[actions['result'][j]['at_title']] = 'in_progress'
                                elif actions['result'][j]['is_complete'].lower() == 'true':
                                    action[actions['result'][j]['at_title']] = 'completed'
                                else:
                                    action[actions['result'][j]['at_title']] = 'not started'
                            goal['actions'] = action
                res[today_date] = goal

            response['message'] = 'successful'
            response['result'] = res
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GoalHistory(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()
            
            start_date = request.headers['start_date']
            end_date = request.headers['end_date']

            items = execute("""SELECT * FROM history where user_id = \'""" +user_id+ """\';""", 'get', conn)

            details_json = {}
            res = {}

            for i in range(len(items['result'])):
                if items['result'][i]['date_affected'] >= start_date and items['result'][i]['date_affected'] <= end_date:
                    goal = {}

                    if items['result'][i]['details'][0] == '[':
                        details_json = json.loads(items['result'][i]['details'])

                        for k in range(len(details_json)):
                            if len(details_json[k]) > 0:
                                if 'goal' in details_json[k]:
                                    if 'status' in details_json[k]:
                                        goal[details_json[k]['title']] = details_json[k]['status']
                                
                    else:
                        details_json = json.loads(items['result'][i]['details'])
                        for currKey, value in list(details_json.items()):
                   
                            if currKey[0] == '3':

                                if value['is_in_progress'].lower() == 'true':
                                    goal[value['title']] = 'in_progress'
                                
                                elif value['is_complete'].lower() == 'true':
                                    goal[value['title']] = 'completed'
                                
                                else:
                                    goal[value['title']] = 'not started'

                    if len(goal) > 0:
                        res[items['result'][i]['date_affected']] = goal

            today_date = getToday()

            goals = execute("""SELECT gr_unique_id, gr_title, is_in_progress, is_complete FROM goals_routines where user_id = \'""" +user_id+ """\' and is_displayed_today = 'True' and is_persistent = 'False';""", 'get', conn)

            if len(goals['result']) > 0:
                goal = {}
                for i in range(len(goals['result'])):
                
                    if goals['result'][i]['is_in_progress'].lower() == 'true':
                        goal[goals['result'][i]['gr_title']] = 'in_progress'
                    elif goals['result'][i]['is_complete'].lower() == 'true':
                        goal[goals['result'][i]['gr_title']] = 'completed'
                    else:
                        goal[goals['result'][i]['gr_title']] = 'not started'

                res[today_date] = goal

            response['message'] = 'successful'
            response['result'] = res
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class RoutineHistory(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()
            
            start_date = request.headers['start_date']
            end_date = request.headers['end_date']

            items = execute("""SELECT * FROM history where user_id = \'""" +user_id+ """\';""", 'get', conn)

            details_json = {}
            res = {}

            for i in range(len(items['result'])):
                if items['result'][i]['date_affected'] >= start_date and items['result'][i]['date_affected'] <= end_date:
                    routine = {}

                    if items['result'][i]['details'][0] == '[':
                        details_json = json.loads(items['result'][i]['details'])

                        for k in range(len(details_json)):
                            if len(details_json[k]) > 0:
                                if 'routine' in details_json[k]:
                                    if 'status' in details_json[k]:
                                        routine[details_json[k]['title']] = details_json[k]['status']
                    # else:
                    #     details_json = json.loads(items['result'][i]['details'])
                    #     for currKey, value in list(details_json.items()):
                   
                    #         if currKey[0] == '3':

                    #             if value['is_in_progress'].lower() == 'true':
                    #                 routine[value['title']] = 'in_progress'
                                
                    #             elif value['is_complete'].lower() == 'true':
                    #                 routine[value['title']] = 'completed'
                                
                    #             else:
                    #                 routine[value['title']] = 'not started'
                    if len(routine) > 0:
                        res[items['result'][i]['date_affected']] = routine
            
            routines = execute("""SELECT gr_unique_id, gr_title, is_in_progress, is_complete FROM goals_routines where user_id = \'""" +user_id+ """\' and is_displayed_today = 'True' and is_persistent = 'True';""", 'get', conn)
            today_date = getToday()

            if len(routines['result']) > 0:
                routine = {}
                for i in range(len(routines['result'])):
                
                    if routines['result'][i]['is_in_progress'].lower() == 'true':
                        routine[routines['result'][i]['gr_title']] = 'in_progress'
                    elif routines['result'][i]['is_complete'].lower() == 'true':
                        routine[routines['result'][i]['gr_title']] = 'completed'
                    else:
                        routine[routines['result'][i]['gr_title']] = 'not started'

                res[today_date] = routine
            response['message'] = 'successful'
            response['result'] = res
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class Progress(Resource):
    def get(self, user_id):
        response = {}
        res = {}
        try:
            conn = connect()

            start_date = request.headers['start_date']
            end_date = request.headers['end_date']

            start_date = start_date + " 00:00:00"
            end_date = end_date + " 23:59:59"

            feelings_dict = {}
            happy_dict = {}
            motivation_dict = {}
            important_dict = {}

            timezone_query = execute("""SELECT time_zone FROM users where user_unique_id = \'""" +user_id+ """\';""", 'get', conn)
            timezone = timezone_query['result'][0]['time_zone']

            local = pytz.timezone(timezone)
            naive = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            local_dt = local.localize(naive, is_dst=None)
            start_utc = local_dt.astimezone(pytz.utc)
            start_utc = start_utc.strftime("%Y-%m-%d %H:%M:%S")

            naive = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            local_dt = local.localize(naive, is_dst=None)
            end_utc = local_dt.astimezone(pytz.utc)
            end_utc = end_utc.strftime("%Y-%m-%d %H:%M:%S")

            items = execute("""SELECT * FROM about_me_history where user_id = \'""" +user_id+ """\';""", 'get', conn)

            for i in range(len(items['result'])):
                if items['result'][i]['datetime_gmt'] >= start_utc and items['result'][i]['datetime_gmt'] <= end_utc:
                    if items['result'][i]['category'].lower() == 'feelings':
                        if items['result'][i]['name'] in feelings_dict:
                            feelings_dict[items['result'][i]['name']] += 1
                        else:
                            feelings_dict[items['result'][i]['name']] = 1

                    if items['result'][i]['category'].lower() == 'motivation':
                        if items['result'][i]['name'] in motivation_dict:
                            motivation_dict[items['result'][i]['name']] += 1
                        else:
                            motivation_dict[items['result'][i]['name']] = 1

                    if items['result'][i]['category'].lower() == 'happy':
                        if items['result'][i]['name'] in happy_dict:
                            happy_dict[items['result'][i]['name']] += 1
                        else:
                            happy_dict[items['result'][i]['name']] = 1

                    if items['result'][i]['category'].lower() == 'important':
                        if items['result'][i]['name'] in important_dict:
                            important_dict[items['result'][i]['name']] += 1
                        else:
                            important_dict[items['result'][i]['name']] = 1

            print(motivation_dict, feelings_dict, important_dict, happy_dict)
            res['motivation'] = motivation_dict
            res['feelings'] = feelings_dict
            res['happy'] = happy_dict
            res['important'] = important_dict

            response['message'] = 'successful'
            response['result'] = res
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class CurrentStatus(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()

            goals = execute("""SELECT gr_unique_id, gr_title, is_in_progress, is_complete FROM goals_routines where user_id = \'""" +user_id+ """\';""", 'get', conn)
            user_history = {}

            if len(goals['result']) > 0:
                for i in range(len(goals['result'])):
                    curr_key = goals['result'][i]['gr_unique_id']
                    user_history[curr_key] = {'title':goals['result'][i]['gr_title'], 'is_complete': goals['result'][i]['is_complete'], 'is_in_progress': goals['result'][i]['is_in_progress']}
                        
                    actions = execute("""SELECT at_unique_id, at_title, is_complete, is_in_progress FROM actions_tasks 
                                        WHERE goal_routine_id = \'""" +curr_key+ """\';""", 'get', conn)

                    if len(actions['result']) > 0:
                        for i in range(len(actions['result'])):
                            print(actions['result'][i])
                            user_history[curr_key][actions['result'][i]['at_unique_id']] = {'title': actions['result'][i]['at_title'],  'is_complete': actions['result'][i]['is_complete'], 'is_in_progress': actions['result'][i]['is_in_progress']}

            response['message'] = 'successful'
            response['result'] = user_history
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class GetUserAndTime(Resource):
    def get(self):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT user_unique_id, day_end, time_zone FROM users WHERE day_end <> 'null';""", 'get', conn)

            response['message'] = 'successful'
            response['result'] = items['result']
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class Motivation(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT motivation FROM users WHERE user_unique_id = \'""" +user_id+ """\';""", 'get', conn)

            if len(items['result']) > 0:
                items['result'][0]['options'] = items['result'][0]['motivation']
                del items['result'][0]['motivation']
            
            response['message'] = 'successful'
            response['result'] = items['result']
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class Happy(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT happy FROM users WHERE user_unique_id = \'""" +user_id+ """\';""", 'get', conn)
            
            if len(items['result']) > 0:
                items['result'][0]['options'] = items['result'][0]['happy']
                del items['result'][0]['happy']
            response['message'] = 'successful'
            response['result'] = items['result']
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class Feelings(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT feelings FROM users WHERE user_unique_id = \'""" +user_id+ """\';""", 'get', conn)
            print(type(items['result']))
            response['message'] = 'successful'
            response['result'] = items['result']
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class Important(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT what_is_important FROM users WHERE user_unique_id = \'""" +user_id+ """\';""", 'get', conn)
            
            if len(items['result']) > 0:
                items['result'][0]['options'] = items['result'][0]['what_is_important']
                del items['result'][0]['what_is_important']
            response['message'] = 'successful'
            response['result'] = items['result']
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update Motivation
class UpdateMotivation(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)
            user_id = data['user_id']
            motivation = data['motivation']
           
            while '' in motivation:
                motivation.remove('')
           
            if len(motivation) == 0:
                items = execute("""UPDATE  users
                        SET 
                            motivation = \'""" + 'null' + """\'
                        WHERE user_unique_id = \'""" + user_id + """\';""", 'post', conn)
            
            else:
                items = execute("""UPDATE  users
                            SET 
                                motivation = \'""" + json.dumps(motivation) + """\'
                            WHERE user_unique_id = \'""" + user_id + """\';""", 'post', conn)

            print(items)
            response['message'] = 'successful'
            response['result'] = 'Update to Motivation successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update Happy
class UpdateHappy(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)
            user_id = data['user_id']
            happy = data['happy']

            while '' in happy:
                happy.remove('')
           
            if len(happy) == 0:
                items = execute("""UPDATE  users
                        SET 
                            happy = \'""" + 'null' + """\'
                        WHERE user_unique_id = \'""" + user_id + """\';""", 'post', conn)
            
            else:
                items = execute("""UPDATE  users
                            SET 
                                happy = \'""" + json.dumps(happy) + """\'
                            WHERE user_unique_id = \'""" + user_id + """\';""", 'post', conn)

            print(items)
            response['message'] = 'successful'
            response['result'] = 'Update to Motivation successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update Important
class UpdateImportant(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)
            user_id = data['user_id']
            important = data['important']

            while '' in important:
                important.remove('')
           
            if len(important) == 0:
                items = execute("""UPDATE  users
                        SET 
                            what_is_important = \'""" + 'null' + """\'
                        WHERE user_unique_id = \'""" + user_id + """\';""", 'post', conn)

            else:
                items = execute("""UPDATE  users
                            SET 
                                what_is_important = \'""" + json.dumps(important) + """\'
                            WHERE user_unique_id = \'""" + user_id + """\';""", 'post', conn)

            print(items)
            response['message'] = 'successful'
            response['result'] = 'Update to Motivation successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Update Important
class UpdateFeelings(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)
            user_id = data['user_id']
            feelings = data['feelings']
           
            items = execute("""UPDATE  users
                        SET 
                            feelings = \'""" + json.dumps(feelings) + """\'
                        WHERE user_unique_id = \'""" + user_id + """\';""", 'post', conn)

            print(items)
            response['message'] = 'successful'
            response['result'] = 'Update to Motivation successful'

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)


class AboutHistory(Resource):
    def post(self):
        response = {}
        try:
            conn = connect()

            timestamp = getNow()
            data = request.get_json(force=True)

            category = data['category']
            name = data['name']
            user_id = data['user_id']

            NewIDresponse = execute("CALL get_about_id;",  'get', conn)
            new_id = NewIDresponse['result'][0]['new_id']
            
            items = execute("""INSERT into about_me_history
                                (   about_history_id
                                    , category
                                    , name
                                    , datetime_gmt
                                    , user_id
                                )
                                VALUES
                                (
                                    \'""" +new_id+ """\'
                                    , \'""" +category+ """\'
                                    , \'""" +name+ """\'
                                    , \'""" +timestamp+ """\'
                                    , \'""" +user_id+ """\'
                                );""", 'post', conn)

            response['message'] = 'successful'
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class UserTADetails(Resource):
    def get(self):
        response = {}

        try:
            conn = connect()
        
            email_list = ((request.headers['Email'][1:-1]).replace('"', "")).split(',')
            print(email_list)
            items = []
            ta_list = {}
            user_list = []
            res = []
            ta_response = execute("""SELECT ta_unique_id, ta_email_id, ta_first_name, ta_last_name, ta_phone_number FROM ta_people;""", 'get', conn)
            user_response = execute("""SELECT user_email_id, user_first_name, user_last_name, user_picture FROM users;""", 'get', conn)

            for i in range(len(ta_response['result'])):
                ta_list[ta_response['result'][i]['ta_email_id']] = ta_response['result'][i]['ta_unique_id']

            for i in range(len(user_response['result'])):
                user_list.append(user_response['result'][i]['user_email_id'])

            for email in email_list:
                if email[0] == " ":
                    email = email[1:]
                res = {}
                if email in ta_list:
                    relation_response = execute("""SELECT * FROM relationship WHERE ta_people_id = \'""" +ta_list[email]+ """\';""", 'get', conn)
                    if len(relation_response['result']) == 0:
                        for i in range(len(ta_response['result'])):
                                if ta_response['result'][i]['ta_email_id'] == email:
                                    res['email_id'] = email
                                    res['first_name'] = ta_response['result'][i]['ta_first_name']
                                    res['last_name'] = ta_response['result'][i]['ta_last_name']
                                    res['phone_number'] = ta_response['result'][i]['ta_phone_number']
                                    res['picture'] = ''
                                    res['role'] = 'no role'
                                    items.append(res)
                            
                    for k in range(len(relation_response['result'])):
                        if relation_response['result'][k]['advisor'] == 1:
                            for i in range(len(ta_response['result'])):
                                if ta_response['result'][i]['ta_email_id'] == email:
                                    res['email_id'] = email
                                    res['first_name'] = ta_response['result'][i]['ta_first_name']
                                    res['last_name'] = ta_response['result'][i]['ta_last_name']
                                    res['phone_number'] = ta_response['result'][i]['ta_phone_number']
                                    res['picture'] = relation_response['result'][k]['ta_picture']
                                    res['role'] = 'advisor'
                                    items.append(res)
                            break
                    
                elif email in user_list and email not in ta_list:
                    for i in range(len(user_response['result'])):
                        if user_response['result'][i]['user_email_id'] == email:
                            res['email_id'] = email
                            res['first_name'] = user_response['result'][i]['user_first_name']
                            res['last_name'] = user_response['result'][i]['user_last_name']
                            res['picture'] = user_response['result'][k]['user_picture']
                            res['role'] = 'user'
                            items.append(res)
                            

                elif email not in ta_list and email not in user_list:
                    res['email_id'] = email
                    res['message'] = "Email ID doesn't exists"
                    items.append(res)

            response['message'] = 'successful'
            response['result'] = items
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)


class Notifications(Resource):
    def get(self):
        response = {}
        try:
            conn = connect()

            items = execute("""SELECT * FROM notifications;""", 'get', conn)

            response['message'] = 'successful'
            response['result'] = items['result']
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class ChangeHistory(Resource):
    def post(self, user_id):
        
        from datetime import datetime
        from pytz import timezone
        import pytz
        
        response = {}
        try:
            conn = connect()

            NewIDresponse = execute("CALL get_history_id;",  'get', conn)
            NewID = NewIDresponse['result'][0]['new_id']
            date_format='%m/%d/%Y %H:%M:%S'
            current = datetime.now(tz=pytz.utc)
            current = current.astimezone(timezone('US/Pacific'))
            date = current.strftime(date_format)
            current_time = current.strftime("%H:%M:%S")
            current_time = datetime.strptime(current_time, "%H:%M:%S").time()
            start = dt.time(0, 0, 0)
            end = dt.time(0, 59, 59)
            
            if current_time>start and current_time > end:
                date_affected = current.date()
            else:
                date_affected = current + timedelta(days=-1)
                date_affected = date_affected.date()

            currentDate = (dt.datetime.now().date())
            current_week_day = currentDate.strftime('%A').lower()
            goals = execute("""SELECT * FROM goals_routines WHERE user_id = \'""" +user_id+ """\';""", 'get', conn)

            user_history =  [{} for sub in range(len(goals['result']))]

            if len(goals['result']) > 0:
                for i in range(len(goals['result'])):
                    if goals['result'][i]['is_displayed_today'].lower() == 'true':
                        if goals['result'][i]['is_persistent'].lower() == 'false':
                            user_history[i]['goal'] = goals['result'][i]['gr_unique_id']
                            user_history[i]['photo'] = goals['result'][i]['photo']
                            user_history[i]['is_sublist_available'] = goals['result'][i]['is_sublist_available']
                            user_history[i]['start_day_and_time'] = goals['result'][i]['start_day_and_time']
                            user_history[i]['end_day_and_time'] = goals['result'][i]['end_day_and_time']
                        else:
                            user_history[i]['routine'] = goals['result'][i]['gr_unique_id']
                            user_history[i]['photo'] = goals['result'][i]['photo']
                            user_history[i]['is_sublist_available'] = goals['result'][i]['is_sublist_available']
                            user_history[i]['start_day_and_time'] = goals['result'][i]['start_day_and_time']
                            user_history[i]['end_day_and_time'] = goals['result'][i]['end_day_and_time']
                        title  = goals['result'][i]['gr_title']
                        if "'" in title:
                            for v, char in enumerate(title):
                                if char == "'":
                                    title = title[:v+1] + "'" + title[v+1:]

                        user_history[i]['title'] = title
                        if goals['result'][i]['is_in_progress'].lower() == 'true':
                            user_history[i]['status'] = 'in_progress'
                        elif goals['result'][i]['is_complete'].lower() == 'true':
                            user_history[i]['status'] = 'completed'
                        else:
                            user_history[i]['status'] = 'not started'

                        actions = execute("""SELECT at_unique_id, at_title, is_complete, is_in_progress FROM actions_tasks 
                                            WHERE goal_routine_id = \'""" +goals['result'][i]['gr_unique_id']+ """\';""", 'get', conn)

                        if len(actions['result']) > 0:
                            action_history = [{} for sub in range(len(actions['result']))]

                            for j in range(len(actions['result'])):
                                action_history[j]['action'] = actions['result'][j]['at_unique_id']

                                title  = actions['result'][j]['at_title']
                                if "'" in title:
                                    for v, char in enumerate(title):
                                        if char == "'":
                                            title = title[:v+1] + "'" + title[v+1:]

                                action_history[j]['title'] = title

                                if actions['result'][j]['is_in_progress'].lower() == 'true':
                                    action_history[j]['status'] = 'in_progress'
                                elif actions['result'][j]['is_complete'].lower() == 'true':
                                    action_history[j]['status'] = 'complete'
                                else:
                                    action_history[j]['status'] = 'not started'

                                instructions = execute("""SELECT * FROM instructions_steps 
                                            WHERE at_id = \'""" +actions['result'][j]['at_unique_id']+ """\';""", 'get', conn)

                                if len(instructions['result']) > 0:
                                    instruction_history = [{} for sub in range(len(instructions['result']))]
                                    for k in range(len(instructions['result'])):
                                        instruction_history[k]['instruction'] = instructions['result'][k]['unique_id']

                                        title  = instructions['result'][k]['title']
                                        if "'" in title:
                                            for v, char in enumerate(title):
                                                if char == "'":
                                                    title = title[:v+1] + "'" + title[v+1:]
                                        instruction_history[k]['title'] = title
                                        if instructions['result'][k]['is_in_progress'].lower() == 'true':
                                            instruction_history[k]['status'] = 'in_progress'
                                        elif instructions['result'][k]['is_complete'].lower() == 'true':
                                            instruction_history[k]['status'] = 'complete'
                                        else:
                                            instruction_history[k]['status'] = 'not started'

                                    action_history[j]['instructions'] = instruction_history
                            
                            user_history[i]['actions'] = action_history

                    execute("""UPDATE notifications
                        SET before_is_set = \'""" +'False'+"""\'
                        , during_is_set = \'""" +'False'+"""\'
                        , after_is_set = \'""" +'False'+"""\' 
                        WHERE gr_at_id = \'""" +goals['result'][i]['gr_unique_id']+"""\'""", 'post', conn)
            
            print("""INSERT INTO history                        
                        (id
                        , user_id
                        , date
                        , details
                        , date_affected)
                        VALUES
                        (
                         \'""" +NewID+ """\'
                        ,\'""" +user_id+ """\'
                        ,\'""" +date+ """\'
                        ,\'""" +str(json.dumps(user_history))+ """\'
                        ,\'""" +str(date_affected)+ """\');
                        """)
            execute("""INSERT INTO history                        
                        (id
                        , user_id
                        , date
                        , details
                        , date_affected)
                        VALUES
                        (
                         \'""" +NewID+ """\'
                        ,\'""" +user_id+ """\'
                        ,\'""" +date+ """\'
                        ,\'""" +str(json.dumps(user_history))+ """\'
                        ,\'""" +str(date_affected)+ """\');
                        """, 'post', conn)

            for goal in goals['result']:
                is_displayed_today = 'False'
                datetime_str = goal['start_day_and_time']
                datetime_str = datetime_str.replace(",", "")
                start_date = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                repeat_week_days = json.loads(goal['repeat_week_days'])
                repeat_ends_on = (datetime.min).date()
               
                week_days_unsorted = []
                occurence_dates = []

                for key in repeat_week_days.keys():
                    if repeat_week_days[key].lower() == 'true':
                        if key.lower() == "monday":
                            week_days_unsorted.append(1)
                        if key.lower() == "tuesday":
                            week_days_unsorted.append(2)
                        if key.lower() == "wednesday":
                            week_days_unsorted.append(3)
                        if key.lower() == "thursday":
                            week_days_unsorted.append(4)
                        if key.lower() == "friday":
                            week_days_unsorted.append(5)
                        if key.lower() == "saturday":
                            week_days_unsorted.append(6)
                        if key.lower() == "sunday":
                            week_days_unsorted.append(7)
                week_days = sorted(week_days_unsorted)

                if current_week_day == "monday":
                    current_week_day = 1
                if current_week_day == "tuesday":
                    current_week_day = 2
                if current_week_day == "wednesday":
                    current_week_day = 3
                if current_week_day == "thursday":
                    current_week_day = 4
                if current_week_day == "friday":
                    current_week_day = 5
                if current_week_day == "saturday":
                    current_week_day = 6
                if current_week_day == "sunday":
                    current_week_day = 7

                if goal['repeat'].lower() == 'false':
                    epoch = dt.datetime.utcfromtimestamp(0).date()
                    current_time = (currentDate - epoch).total_seconds() * 1000.0
                    start_time = (start_date - epoch).total_seconds() * 1000.0
                    is_displayed_today = (current_time - start_time) == 0
                    print(goal['gr_title'],is_displayed_today)
                    # execute("""UPDATE goals_routines
                    #             SET is_in_progress = \'""" +'False'+"""\'
                    #             , is_complete = \'""" +'False'+"""\'
                    #             , is_displayed_today = \'""" +str(is_displayed_today).title()+"""\'
                    #             WHERE gr_unique_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                    # execute("""UPDATE actions_tasks
                    #             SET is_in_progress = \'""" +'False'+"""\'
                    #             , is_complete = \'""" +'False'+"""\'
                    #             WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                    # actions_task_response = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'get', conn)
                    # if len(actions_task_response['result']) > 0:
                    #     for i in rangelen(actions_task_response['result']):
                    #         execute("""UPDATE instructions_steps
                    #                     SET is_in_progress = \'""" +'False'+"""\'
                    #                     , is_complete = \'""" +'False'+"""\'
                    #                     WHERE at_id = \'"""+actions_task_response['result'][i]['at_unique_id']+"""\';""", 'post', conn)
                else:
                    if currentDate >= start_date:

                        if goal['repeat_type'].lower() == 'after':
                            if goal['repeat_frequency'].lower() == 'day':
                                print("day")
                                repeat_occurences = goal['repeat_occurences'] -1
                                repeat_every = goal['repeat_every']
                                number_days = int(repeat_occurences) * int(repeat_every)
                                repeat_ends_on = start_date + timedelta(days=number_days)
                                print(repeat_ends_on)
                                
                                
                            elif goal['repeat_frequency'].lower() == 'week':
                                numberOfWeek = 0

                                init_date = start_date
                                start_day = init_date.isoweekday()
                                print("Weekly")
                                result = []
                                for x in week_days:
                                    if x < start_day:
                                        result.append(x)
                                new_week = []
                                if len(result) > 0:
                                    new_week = week_days[len(result):]
                                    for day in result:
                                        new_week.append(day)
                                    week_days = new_week

                                for i in range(goal['repeat_occurences']) : 
                                    if i < len(week_days):
                                        dow = week_days[i]
                                    if i >= len(week_days):
                                        numberOfWeek = math.floor(i / len(week_days))
                                        dow = week_days[i % len(week_days)]

                                    new_date = init_date
                                    today  = new_date.isoweekday()
                                    day_i_need = dow
                                    if today <= day_i_need:
                                        days = day_i_need - today
                                        nextDayOfTheWeek = new_date + timedelta(days=days)
                                    else:
                                        new_date = new_date + relativedelta(weeks=1)
                                        days = day_i_need - today
                                        nextDayOfTheWeek = new_date + timedelta(days=-days)
                                    add_weeks = numberOfWeek * int(goal['repeat_every'])
                                    date = nextDayOfTheWeek + relativedelta(weeks=add_weeks)
                                    occurence_dates.append(date)
                                print("current", currentDate)
                                print(occurence_dates)    
                                if currentDate in occurence_dates:
                                    is_displayed_today = True
                                print(goal['gr_title'], is_displayed_today)
                                print("P")
                                # execute("""UPDATE goals_routines
                                # SET is_in_progress = \'""" +'False'+"""\'
                                # , is_complete = \'""" +'False'+"""\'
                                # , is_displayed_today = \'""" +str(is_displayed_today).title()+"""\'
                                # WHERE gr_unique_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                                # execute("""UPDATE actions_tasks
                                # SET is_in_progress = \'""" +'False'+"""\'
                                # , is_complete = \'""" +'False'+"""\'
                                # WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)
                                
                                # actions_task_response = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'get', conn)
                                # if len(actions_task_response['result']) > 0:
                                #     for i in rangelen(actions_task_response['result']):
                                #         execute("""UPDATE instructions_steps
                                #                     SET is_in_progress = \'""" +'False'+"""\'
                                #                     , is_complete = \'""" +'False'+"""\'
                                #                     WHERE at_id = \'"""+actions_task_response['result'][i]['at_unique_id']+"""\';""", 'post', conn)
                            
                            elif goal['repeat_frequency'].lower() == 'month':
                                print("month")
                                repeat_occurences = goal['repeat_occurences'] - 1
                                repeat_every = goal['repeat_every']
                                end_month = int(repeat_occurences) * int(repeat_every)
                                repeat_ends_on = start_date + relativedelta(months=end_month)
                                print(repeat_ends_on)

                            elif goal['repeat_frequency'].lower() == 'year':
                                print("year")
                                repeat_occurences = goal['repeat_occurences']
                                repeat_every = goal['repeat_every']
                                end_year = int(repeat_occurences) * int(repeat_every)
                                repeat_ends_on = start_date + relativedelta(years=end_year)
                                print(repeat_ends_on)

                        elif goal['repeat_type'].lower() == 'never':
                            print("never")
                            repeat_ends_on = currentDate
                            print(goal['gr_title'], repeat_ends_on)
                        
                        elif goal['repeat_type'].lower() == 'on':
                            repeat_ends = goal['repeat_ends_on']
                            repeat_ends_on = repeat_ends[:24]
                            repeat_ends_on = datetime.strptime(repeat_ends_on, "%a %b %d %Y %H:%M:%S").date()

                    if currentDate <= repeat_ends_on:
                        repeat_every = int(goal['repeat_every'])

                        if goal['repeat_frequency'].lower() == 'day':
                            epoch = dt.datetime.utcfromtimestamp(0).date()
                            current_time = (currentDate - epoch).total_seconds() * 1000.0
                            start_time = (start_date - epoch).total_seconds() * 1000.0
                            is_displayed_today = (math.floor((current_time - start_time)/(24*3600*1000)) % repeat_every) == 0

                            # execute("""UPDATE goals_routines
                            #     SET is_in_progress = \'""" +'False'+"""\'
                            #     , is_complete = \'""" +'False'+"""\'
                            #     , is_displayed_today = \'""" +str(is_displayed_today).title()+"""\'
                            #     WHERE gr_unique_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)
                            
                            # execute("""UPDATE actions_tasks
                            #     SET is_in_progress = \'""" +'False'+"""\'
                            #     , is_complete = \'""" +'False'+"""\'
                            #     WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                            # actions_task_response = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'get', conn)
                            # if len(actions_task_response['result']) > 0:
                            #     for i in rangelen(actions_task_response['result']):
                            #         execute("""UPDATE instructions_steps
                            #                     SET is_in_progress = \'""" +'False'+"""\'
                            #                     , is_complete = \'""" +'False'+"""\'
                            #                     WHERE at_id = \'"""+actions_task_response['result'][i]['at_unique_id']+"""\';""", 'post', conn)

                            print(goal['gr_title'], is_displayed_today)

                        if goal['repeat_frequency'].lower() == 'week':
                            if current_week_day in week_days:
                                epoch = dt.datetime.utcfromtimestamp(0).date()
                                current_time = (currentDate - epoch).total_seconds() * 1000.0
                                start_time = (start_date - epoch).total_seconds() * 1000.0
                                is_displayed_today = (math.floor((current_time - start_time)/(7*24*3600*1000)) % repeat_every) == 0
                            # execute("""UPDATE goals_routines
                            #             SET is_in_progress = \'""" +'False'+"""\'
                            #             , is_complete = \'""" +'False'+"""\'
                            #             , is_displayed_today = \'""" +str(is_displayed_today).title()+"""\'
                            #             WHERE gr_unique_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                            # execute("""UPDATE actions_tasks
                            #     SET is_in_progress = \'""" +'False'+"""\'
                            #     , is_complete = \'""" +'False'+"""\'
                            #     WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)
                            # print(goal['gr_title'] , is_displayed_today)
                            # actions_task_response = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'get', conn)
                            # if len(actions_task_response['result']) > 0:
                            #     for i in rangelen(actions_task_response['result']):
                            #         execute("""UPDATE instructions_steps
                            #                     SET is_in_progress = \'""" +'False'+"""\'
                            #                     , is_complete = \'""" +'False'+"""\'
                            #                     WHERE at_id = \'"""+actions_task_response['result'][i]['at_unique_id']+"""\';""", 'post', conn)
                        
                        if goal['repeat_frequency'].lower() == 'month':
                            is_displayed_today= currentDate.day == start_date.day and ((currentDate.year - start_date.year) * 12 + currentDate.month - start_date.month) % repeat_every == 0
                            # execute("""UPDATE goals_routines
                            #     SET is_in_progress = \'""" +'False'+"""\'
                            #     , is_complete = \'""" +'False'+"""\'
                            #     , is_displayed_today = \'""" +str(is_displayed_today).title()+"""\'
                            #     WHERE gr_unique_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                            # execute("""UPDATE actions_tasks
                            #     SET is_in_progress = \'""" +'False'+"""\'
                            #     , is_complete = \'""" +'False'+"""\'
                            #     WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)
                            print(goal['gr_title'], is_displayed_today)

                        if goal['repeat_frequency'].lower() == 'year':
                            is_displayed_today= currentDate.day == start_date.day and currentDate.month == start_date.month and (currentDate.year - start_date.year) % repeat_every == 0
                            # execute("""UPDATE goals_routines
                            #     SET is_in_progress = \'""" +'False'+"""\'
                            #     , is_complete = \'""" +'False'+"""\'
                            #     , is_displayed_today = \'""" +str(is_displayed_today).title()+"""\'
                            #     WHERE gr_unique_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                            # execute("""UPDATE actions_tasks
                            #     SET is_in_progress = \'""" +'False'+"""\'
                            #     , is_complete = \'""" +'False'+"""\'
                            #     WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)
                            print(goal['gr_title'], is_displayed_today)

                    # if currentDate > repeat_ends_on:
                    #     execute("""UPDATE goals_routines
                    #             SET is_in_progress = \'""" +'False'+"""\'
                    #             , is_complete = \'""" +'False'+"""\'
                    #             , is_displayed_today = \'""" +'False'+"""\'
                    #             WHERE gr_unique_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)
                    #     execute("""UPDATE actions_tasks
                    #             SET is_in_progress = \'""" +'False'+"""\'
                    #             , is_complete = \'""" +'False'+"""\'
                    #             WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)
                print("Pragya")
                execute("""UPDATE goals_routines
                                SET is_in_progress = \'""" +'False'+"""\'
                                , is_complete = \'""" +'False'+"""\'
                                , is_displayed_today = \'""" +str(is_displayed_today).title()+"""\'
                                WHERE gr_unique_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                execute("""UPDATE actions_tasks
                            SET is_in_progress = \'""" +'False'+"""\'
                            , is_complete = \'""" +'False'+"""\'
                            WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'post', conn)

                actions_task_response = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'"""+goal['gr_unique_id']+"""\';""", 'get', conn)
                if len(actions_task_response['result']) > 0:
                    for i in range(len(actions_task_response['result'])):
                        execute("""UPDATE instructions_steps
                                    SET is_in_progress = \'""" +'False'+"""\'
                                    , is_complete = \'""" +'False'+"""\'
                                    WHERE at_id = \'"""+actions_task_response['result'][i]['at_unique_id']+"""\';""", 'post', conn)
            
            # user_history = {}
            
            # if len(goals['result']) > 0:
            #     for i in range(len(goals['result'])):
            #         user_history[goals['result'][i]['gr_unique_id']] = {'title': goals['result'][i]['gr_title'], 'is_complete': goals['result'][i]['is_complete'], 'is_in_progress': goals['result'][i]['is_in_progress']}
                    
            #         actions = execute("""SELECT at_unique_id, at_title, is_complete, is_in_progress FROM actions_tasks 
            #                             WHERE goal_routine_id = \'""" +goals['result'][i]['gr_unique_id']+ """\';""", 'get', conn)
                    
            #         if len(actions['result']) > 0:
            #             for i in range(len(actions['result'])):
            #                 user_history[actions['result'][i]['at_unique_id']] = {'title': actions['result'][i]['at_title'],'is_complete': actions['result'][i]['is_complete'], 'is_in_progress': actions['result'][i]['is_in_progress']}

            # execute("""INSERT INTO history                        
            #             (id
            #             , user_id
            #             , date
            #             , details
            #             , date_affected)
            #             VALUES
            #             (
            #              \'""" +NewID+ """\'
            #             ,\'""" +user_id+ """\'
            #             ,\'""" +date+ """\'
            #             ,\'""" +str(json.dumps(user_history))+ """\'
            #             ,\'""" +str(date_affected)+ """\');
            #             """, 'post', conn)

            # # if len(goals['result']) > 0:
            # #     for i in range(len(goals['result'])):
            # #         execute("""UPDATE goals_routines
            # #                     SET is_in_progress = \'""" +'False'+"""\'
            # #                     , is_complete = \'""" +'False'+"""\'
            # #                     WHERE gr_unique_id = \'"""+goals['result'][i]['gr_unique_id']+"""\';""", 'post', conn)

            response['message'] = 'successful'
            
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class Calender(Resource):
    def get(self, user_id):
        response = {}
        try:
            conn = connect()

            currentDate = (dt.datetime.now().date())
            current_week_day = currentDate.strftime('%A').lower()

            goals = execute("""SELECT * FROM goals_routines WHERE user_id = \'""" +user_id+ """\';""", 'get', conn)

            for goal in goals['result']:
                is_displayed_today = 'False'
                datetime_str = goal['start_day_and_time']
                datetime_str = datetime_str.replace(",", "")
                start_date = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p').date()
                repeat_week_days = json.loads(goal['repeat_week_days'])
                repeat_ends_on = (datetime.min).date()
               
                week_days_unsorted = []
                occurence_dates = []

                for key in repeat_week_days.keys():
                    if repeat_week_days[key].lower() == 'true':
                        if key.lower() == "monday":
                            week_days_unsorted.append(1)
                        if key.lower() == "tuesday":
                            week_days_unsorted.append(2)
                        if key.lower() == "wednesday":
                            week_days_unsorted.append(3)
                        if key.lower() == "thursday":
                            week_days_unsorted.append(4)
                        if key.lower() == "friday":
                            week_days_unsorted.append(5)
                        if key.lower() == "saturday":
                            week_days_unsorted.append(6)
                        if key.lower() == "sunday":
                            week_days_unsorted.append(7)
                week_days = sorted(week_days_unsorted)

                if current_week_day == "monday":
                    current_week_day = 1
                if current_week_day == "tuesday":
                    current_week_day = 2
                if current_week_day == "wednesday":
                    current_week_day = 3
                if current_week_day == "thursday":
                    current_week_day = 4
                if current_week_day == "friday":
                    current_week_day = 5
                if current_week_day == "saturday":
                    current_week_day = 6
                if current_week_day == "sunday":
                    current_week_day = 7
                if goal['repeat'].lower() == 'false':
                    epoch = dt.datetime.utcfromtimestamp(0).date()
                    current_time = (currentDate - epoch).total_seconds() * 1000.0
                    start_time = (start_date - epoch).total_seconds() * 1000.0
                    is_displayed_today = (current_time - start_time) == 0
                    print(goal['gr_title'],is_displayed_today)

                else:
                    if currentDate >= start_date:
                        if goal['repeat_type'].lower() == 'after':
                            if goal['repeat_frequency'].lower() == 'day':
                                repeat_occurences = goal['repeat_occurences'] -1
                                repeat_every = goal['repeat_every']
                                number_days = int(repeat_occurences) * int(repeat_every)
                                repeat_ends_on = start_date + timedelta(days=number_days)
                                print(goal['gr_title'], is_displayed_today)
                                
                            elif goal['repeat_frequency'].lower() == 'week':
                                numberOfWeek = 0

                                init_date = start_date
                                start_day = init_date.isoweekday()
                                result = []
                                for x in week_days:
                                    if x < start_day:
                                        result.append(x)
                                new_week = []
                                if len(result) > 0:
                                    new_week = week_days[len(result):]
                                    for day in result:
                                        new_week.append(day)
                                    week_days = new_week

                                for i in range(goal['repeat_occurences']) : 
                                    if i < len(week_days):
                                        dow = week_days[i]
                                    if i >= len(week_days):
                                        numberOfWeek = math.floor(i / len(week_days))
                                        dow = week_days[i % len(week_days)]

                                    new_date = init_date
                                    today  = new_date.isoweekday()
                                    day_i_need = dow
                                    if today <= day_i_need:
                                        days = day_i_need - today
                                        nextDayOfTheWeek = new_date + timedelta(days=days)
                                    else:
                                        new_date = new_date + relativedelta(weeks=1)
                                        days = day_i_need - today
                                        nextDayOfTheWeek = new_date + timedelta(days=-days)
                                    add_weeks = numberOfWeek * int(goal['repeat_every'])
                                    date = nextDayOfTheWeek + relativedelta(weeks=add_weeks)
                                    occurence_dates.append(date)
                                
                                if currentDate in occurence_dates:
                                    is_displayed_today = True
                                print(goal['gr_title'], is_displayed_today)

                            elif goal['repeat_frequency'].lower() == 'month':
                                print("month")
                                repeat_occurences = goal['repeat_occurences'] - 1
                                repeat_every = goal['repeat_every']
                                end_month = int(repeat_occurences) * int(repeat_every)
                                repeat_ends_on = start_date + relativedelta(months=end_month)

                            elif goal['repeat_frequency'].lower() == 'year':
                                print("year")
                                repeat_occurences = goal['repeat_occurences']
                                repeat_every = goal['repeat_every']
                                end_year = int(repeat_occurences) * int(repeat_every)
                                repeat_ends_on = start_date + relativedelta(years=end_year)

                        elif goal['repeat_type'].lower() == 'never':
                            print("never")
                            repeat_ends_on = currentDate
                        
                        elif goal['repeat_type'].lower() == 'on':
                            repeat_ends = goal['repeat_ends_on']
                            repeat_ends_on = repeat_ends[:24]
                            repeat_ends_on = datetime.strptime(repeat_ends_on, "%a %b %d %Y %H:%M:%S").date()

                    if currentDate <= repeat_ends_on:
                        repeat_every = int(goal['repeat_every'])

                        if goal['repeat_frequency'].lower() == 'day':
                           
                            epoch = dt.datetime.utcfromtimestamp(0).date()
                            print(epoch)
                            current_time = (currentDate - epoch).total_seconds() * 1000.0
                            print(current_time)
                            start_time = (start_date - epoch).total_seconds() * 1000.0
                            print(start_time)
                            is_displayed_today = (math.floor((current_time - start_time)/(24*3600*1000)) % repeat_every) == 0
                            print(goal['gr_title'], is_displayed_today)

                        if goal['repeat_frequency'].lower() == 'week':
                            print(current_week_day)
                            if current_week_day in week_days:
                                print(current_week_day)
                                epoch = dt.datetime.utcfromtimestamp(0).date()
                                current_time = (currentDate - epoch).total_seconds() * 1000.0
                                start_time = (start_date - epoch).total_seconds() * 1000.0
                                is_displayed_today = (math.floor((current_time - start_time)/(7*24*3600*1000)) % repeat_every) == 0
                    
                            print(goal['gr_title'] , is_displayed_today)

                        if goal['repeat_frequency'].lower() == 'month':
                            is_displayed_today= currentDate.day == start_date.day and ((currentDate.year - start_date.year) * 12 + currentDate.month - start_date.month) % repeat_every == 0
                            print(goal['gr_title'], is_displayed_today)

                        if goal['repeat_frequency'].lower() == 'year':
                            is_displayed_today= currentDate.day == start_date.day and currentDate.month == start_date.month and (currentDate.year - start_date.year) % repeat_every == 0
                            print(goal['gr_title'], is_displayed_today)


            response['message'] = 'successful'
            
            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

class update_guid_notification(Resource):

    def post(self, action):
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            uid = data['user_unique_id']
            guid = data['guid']
            notification = data['notification']

            if action == 'add':

                query = """
                        SELECT *
                        FROM users
                        WHERE user_unique_id = \'""" + uid + """\'
                        """
                items = execute(query, 'get', conn)

                ta_query = """SELECT * FROM ta_people
                                WHERE ta_email_id = \'""" +items['result'][0]['user_email_id'] + """\'"""
                
                ta_people_query = execute(ta_query, 'get', conn)

                del data['user_unique_id']
                
                flag = 0

                json_guid = json.loads(items['result'][0]['cust_guid_device_id_notification'])
                
                test = str(data).replace("'", "\"")
                data = "'" + test + "'"

                if ta_people_query['result']:
                    query = " " \
                            "UPDATE ta_people " \
                            "SET ta_guid_device_id_notification  = (SELECT JSON_MERGE_PRESERVE(ta_guid_device_id_notification," + data + ")) " \
                            "WHERE ta_unique_id = '" + ta_people_query['result'][0]['ta_unique_id'] + "';" \
                            ""
                    res = execute(query, 'post', conn)

                if items['result']:
                    query1 = " " \
                            "UPDATE users " \
                            "SET cust_guid_device_id_notification  = (SELECT JSON_MERGE_PRESERVE(cust_guid_device_id_notification," + data + ")) " \
                            "WHERE user_unique_id = '" + uid + "';" \
                            ""
                    items = execute(query1, 'post', conn)
               

                    if items['code'] == 281:
                        items['code'] = 200
                        items['message'] = 'Device_id notification and GUID updated'
                    else:
                        items['message'] = 'check sql query'

                else:
                    items['message'] = 'UID does not exists'

                return items

            elif action == 'update':

                query = """
                    SELECT cust_guid_device_id_notification
                    FROM users
                    WHERE user_unique_id = \'""" + uid + """\';
                    """
                items = execute(query, 'get', conn)
                
                json_guid = json.loads(items['result'][0]['cust_guid_device_id_notification'])
                for i, vals in enumerate(json_guid):
                    if vals == None or vals == 'null':
                        continue
                    if vals['guid'] == data['guid']:
                        json_guid[i]['notification'] = data['notification']
                        break
                
                if json_guid[0] == None:
                    json_guid[0] = 'null'

                guid = str(json_guid)
                guid = guid.replace("'", '"')

                query = """
                        UPDATE  users  
                        SET
                        cust_guid_device_id_notification = \'""" + guid + """\'
                        WHERE ( user_unique_id  = '""" + uid + """' );
                        """
                items = execute(query, 'post', conn)
                if items['code'] != 281:
                    items['message'] = 'guid not updated check sql query and data'

                else:
                    items['message'] = 'guid updated'
                return items

            else:
                return 'choose correct option'

        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)


# Delete User
class DeleteUser(Resource):
    def post(self):    
        response = {}
        items = {}

        try:
            conn = connect()
            data = request.get_json(force=True)

            user_unique_id = data['user_id']

            execute("""DELETE FROM users WHERE user_unique_id = \'""" + user_unique_id + """\';""", 'post', conn)
            execute("""DELETE FROM relationship WHERE user_uid = \'""" + user_unique_id + """\';""", 'post', conn)
            gr_response = execute("""SELECT * FROM goals_routines where user_id = \'""" + user_unique_id + """\';""", 'get', conn)
            
            execute("""DELETE FROM goals_routines WHERE user_id = \'""" + user_unique_id + """\';""", 'post', conn)
            
            if len(gr_response['result']) > 0:
                for j in range(len(gr_response['result'])):
                   
                    execute("""DELETE FROM notifications 
                        WHERE gr_at_id = \'""" + gr_response['result'][j]['gr_unique_id'] + """\';""", 'post', conn)
                   
                    at_response = execute("""SELECT at_unique_id FROM actions_tasks 
                            WHERE goal_routine_id = \'""" + gr_response['result'][j]['gr_unique_id'] + """\';""", 'get', conn)

                    if len(at_response['result']) > 0:
                        for k in range(len(at_response['result'])):
                            at_id = at_response['result'][k]['at_unique_id']
                            execute("""DELETE FROM actions_tasks WHERE at_unique_id = \'""" + at_id + """\';""", 'post', conn)
                            execute("""DELETE FROM notifications 
                                        WHERE gr_at_id = \'""" + at_id + """\';""", 'post', conn)
                            execute("""DELETE FROM instructions_steps WHERE at_id = \'""" + at_id + """\';""", 'post', conn)

            response['message'] = 'successful'
            

            return response, 200
        except:
            raise BadRequest('Request failed, please try again later.')
        finally:
            disconnect(conn)

# Returns Mobile app version number
class GetVersionNumber(Resource):
    def get(self):
        response = {}
        items = {}
        try:

            conn = connect()
            
            # Get all goals and routines of the user
            query = """SELECT * FROM mobile_version_number;"""

            items = execute(query,'get', conn)

            response['message'] = 'successful'
            response['result'] = items['result']

            return response, 200
        except:
            raise BadRequest('Get Routines Request failed, please try again later.')
        finally:
            disconnect(conn)

# Updates Mobile app version number
class UpdateVersionNumber(Resource):
    def post(self):
        response = {}
        items = {}
        try:

            conn = connect()
            data = request.get_json(force=True)

            version_number = data['version_number']
            # Get all goals and routines of the user
            query = """UPDATE mobile_version_number
                        SET version_number = \'""" +version_number+ """\'
                        WHERE num = 1;"""
            print(query)
            items = execute(query,'post', conn)

            response['message'] = 'successful'

            return response, 200
        except:
            raise BadRequest('Unsuccessfull.')
        finally:
            disconnect(conn)

class CopyGR(Resource):
    def post(self):
        response = {}
        items = {}

        try:

            conn = connect()
            data = request.get_json(force=True)

            user_id = data['user_id']
            goal_routine_id = data['gr_id']
            ta_id = data['ta_id']

            timezone_query = execute("""SELECT time_zone FROM users where user_unique_id = \'""" +user_id+ """\';""", 'get', conn)
            timezone = timezone_query['result'][0]['time_zone']
        
            items = execute("""SELECT * FROM goals_routines WHERE gr_unique_id = \'""" +goal_routine_id+ """\';""", 'get', conn)

            notification = execute("""SELECT * FROM notifications WHERE gr_at_id = \'""" +goal_routine_id+ """\';""", 'get', conn)

            goal_routine_response = items['result']
            
            time =  goal_routine_response[0]['start_day_and_time'].split(',')
            time[1] = time[1][1:]
            time1 =  goal_routine_response[0]['end_day_and_time'].split(',')
            time1[1] = time1[1][1:]
            datetime_str = goal_routine_response[0]['start_day_and_time']
            datetime_str = datetime_str.replace(",", "")
            datetime_object1 = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p')
            datetime_str = goal_routine_response[0]['end_day_and_time']
            datetime_str = datetime_str.replace(",", "")
            datetime_object2 = datetime.strptime(datetime_str, '%m/%d/%Y %I:%M:%S %p')
            diff = datetime_object2 - datetime_object1

            now_timestamp = datetime.now(pytz.timezone(timezone)) 
           
            start_day_and_time = now_timestamp
            start_date_time = str(start_day_and_time.strftime("%-m/%-d/%Y")) + ", " + str(time[1])#while running locally on windows use '#' instead of '-' in the format string
            end_day_and_time = start_day_and_time + diff
            end_date_time = str(end_day_and_time.strftime("%-m/%-d/%Y")) + ", " + str(time1[1]) #while running locally on windows use '#' instead of '-' in the format string
           
            # New Goal/Routine ID
            query = ["CALL get_gr_id;"]
            new_gr_id_response = execute(query[0],  'get', conn)
            new_gr_id = new_gr_id_response['result'][0]['new_id']

            execute("""INSERT INTO goals_routines(gr_unique_id
                                , gr_title
                                , user_id
                                , is_available
                                , is_complete
                                , is_in_progress
                                , is_displayed_today
                                , is_persistent
                                , is_sublist_available
                                , is_timed
                                , photo
                                , `repeat`
                                , repeat_type
                                , repeat_ends_on
                                , repeat_every
                                , repeat_frequency
                                , repeat_occurences
                                , start_day_and_time
                                , repeat_week_days
                                , datetime_completed
                                , datetime_started
                                , end_day_and_time
                                , expected_completion_time)
                            VALUES 
                            ( \'""" + new_gr_id + """\'
                            , \'""" + goal_routine_response[0]['gr_title'] + """\'
                            , \'""" + user_id + """\'
                            , \'""" + goal_routine_response[0]['is_available'] + """\'
                            , \'""" + 'False' + """\'
                            , \'""" + 'False' + """\'
                            , \'""" + goal_routine_response[0]['is_displayed_today'] + """\'
                            , \'""" + goal_routine_response[0]['is_persistent'] + """\'
                            , \'""" + goal_routine_response[0]['is_sublist_available'] + """\'
                            , \'""" + 'False' + """\'
                            , \'""" + goal_routine_response[0]['photo'] + """\'
                            , \'""" + goal_routine_response[0]['repeat'] + """\'
                            , \'""" + goal_routine_response[0]['repeat_type'] + """\'
                            , \'""" + goal_routine_response[0]['repeat_ends_on'] + """\'
                            , \'""" + str(goal_routine_response[0]['repeat_every']) + """\'
                            , \'""" + str(goal_routine_response[0]['repeat_frequency']) + """\'
                            , \'""" + str(goal_routine_response[0]['repeat_occurences']) + """\'
                            , \'""" + str(start_date_time) + """\'
                            , \'""" + goal_routine_response[0]['repeat_week_days'] + """\'
                            , \'""" + goal_routine_response[0]['datetime_completed'] + """\'
                            , \'""" + goal_routine_response[0]['datetime_started'] + """\'
                            , \'""" + str(end_date_time) + """\'
                            , \'""" + goal_routine_response[0]['expected_completion_time'] + """\');""", 'post', conn)
           
            # New Notification ID
            new_notification_id_response = execute("CALL get_notification_id;",  'get', conn)
            new_notfication_id = new_notification_id_response['result'][0]['new_id']

            notifications = notification['result']
            person_id = ""
            if notifications[0]['user_ta_id'][0] == '1':
                person_id = user_id
            else:
                person_id = ta_id

            execute("""Insert into notifications
                                (notification_id
                                    , user_ta_id
                                    , gr_at_id
                                    , before_is_enable
                                    , before_is_set
                                    , before_message
                                    , before_time
                                    , during_is_enable
                                    , during_is_set
                                    , during_message
                                    , during_time
                                    , after_is_enable
                                    , after_is_set
                                    , after_message
                                    , after_time) 
                                VALUES
                                (     \'""" + new_notfication_id + """\'
                                    , \'""" + person_id + """\'
                                    , \'""" + new_gr_id + """\'
                                    , \'""" + notifications[0]['before_is_enable'] + """\'
                                    , \'""" + notifications[0]['before_is_set'] + """\'
                                    , \'""" + notifications[0]['before_message'] + """\'
                                    , \'""" + notifications[0]['before_time'] + """\'
                                    , \'""" + notifications[0]['during_is_enable'] + """\'
                                    , \'""" + notifications[0]['during_is_set'] + """\'
                                    , \'""" + notifications[0]['during_message'] + """\'
                                    , \'""" + notifications[0]['during_time'] + """\'
                                    , \'""" + notifications[0]['after_is_enable'] + """\'
                                    , \'""" + notifications[0]['after_is_set'] + """\'
                                    , \'""" + notifications[0]['after_message'] + """\'
                                    , \'""" + notifications[0]['after_time'] + """\');""", 'post', conn)
            
             # New Notification ID
            new_notification_id_response = execute("CALL get_notification_id;",  'get', conn)
            new_notfication_id = new_notification_id_response['result'][0]['new_id']

            if notifications[1]['user_ta_id'][0] == '1':
                person_id = user_id
            else:
                person_id = ta_id

            execute("""Insert into notifications
                                (notification_id
                                    , user_ta_id
                                    , gr_at_id
                                    , before_is_enable
                                    , before_is_set
                                    , before_message
                                    , before_time
                                    , during_is_enable
                                    , during_is_set
                                    , during_message
                                    , during_time
                                    , after_is_enable
                                    , after_is_set
                                    , after_message
                                    , after_time) 
                                VALUES
                                (     \'""" + new_notfication_id + """\'
                                    , \'""" + person_id + """\'
                                    , \'""" + new_gr_id + """\'
                                    , \'""" + notifications[0]['before_is_enable'] + """\'
                                    , \'""" + notifications[0]['before_is_set'] + """\'
                                    , \'""" + notifications[0]['before_message'] + """\'
                                    , \'""" + notifications[0]['before_time'] + """\'
                                    , \'""" + notifications[0]['during_is_enable'] + """\'
                                    , \'""" + notifications[0]['during_is_set'] + """\'
                                    , \'""" + notifications[0]['during_message'] + """\'
                                    , \'""" + notifications[0]['during_time'] + """\'
                                    , \'""" + notifications[0]['after_is_enable'] + """\'
                                    , \'""" + notifications[0]['after_is_set'] + """\'
                                    , \'""" + notifications[0]['after_message'] + """\'
                                    , \'""" + notifications[0]['after_time'] + """\');""", 'post', conn)
            

            res_actions = execute("""SELECT * FROM actions_tasks WHERE goal_routine_id = \'""" +goal_routine_id+ """\';""", 'get', conn)
            
            if len(res_actions['result']) > 0:
                action_response = res_actions['result']
                for j in range(len(action_response)):

                    query = ["CALL get_at_id;"]
                    NewATIDresponse = execute(query[0],  'get', conn)
                    NewATID = NewATIDresponse['result'][0]['new_id']

                    execute("""INSERT INTO actions_tasks(at_unique_id
                            , at_title
                            , goal_routine_id
                            , at_sequence
                            , is_available
                            , is_complete
                            , is_in_progress
                            , is_sublist_available
                            , is_must_do
                            , photo
                            , is_timed
                            , datetime_completed
                            , datetime_started
                            , expected_completion_time
                            , available_start_time
                            , available_end_time)
                        VALUES 
                        ( \'""" + NewATID + """\'
                        , \'""" + action_response[j]['at_title'] + """\'
                        , \'""" + new_gr_id + """\'
                        , \'""" + str(action_response[j]['at_sequence']) + """\'
                        , \'""" + action_response[j]['is_available'] + """\'
                        , \'""" + 'False' + """\'
                        , \'""" + 'False' + """\'
                        , \'""" + action_response[j]['is_sublist_available'] + """\'
                        , \'""" + action_response[j]['is_must_do'] + """\'
                        , \'""" + action_response[j]['photo'] + """\'
                        , \'""" + action_response[j]['is_timed'] + """\'
                        , \'""" + action_response[j]['datetime_completed'] + """\'
                        , \'""" + action_response[j]['datetime_started'] + """\'
                        , \'""" + action_response[j]['expected_completion_time'] + """\'
                        , \'""" + action_response[j]['available_start_time'] + """\'
                        , \'""" + action_response[j]['available_end_time'] + """\' );""", 'post', conn)

                    res_ins = execute("""SELECT * FROM instructions_steps WHERE at_id = \'""" +action_response[j]['at_unique_id']+ """\';""", 'get', conn)

                    if len(res_ins['result']) > 0:

                        instructions = res_ins['result']

                        for k in range(len(instructions)):

                            query = ["CALL get_is_id;"]
                            NewISIDresponse = execute(query[0],  'get', conn)
                            NewISID = NewISIDresponse['result'][0]['new_id']

                            execute("""INSERT INTO instructions_steps(unique_id
                                            , title
                                            , at_id
                                            , is_sequence
                                            , is_available
                                            , is_complete
                                            , is_in_progress
                                            , photo
                                            , is_timed
                                            , expected_completion_time)
                                        VALUES 
                                        ( \'""" + NewISID + """\'
                                        , \'""" + instructions[k]['title'] + """\'
                                        , \'""" + NewATID + """\'
                                        , \'""" + str(instructions[k]['is_sequence']) + """\'
                                        , \'""" + instructions[k]['is_available'] + """\'
                                        , \'""" + instructions[k]['is_complete'] + """\'
                                        , \'""" + instructions[k]['is_in_progress'] + """\'
                                        , \'""" + instructions[k]['photo'] + """\'
                                        , \'""" + instructions[k]['is_timed'] + """\'
                                        , \'""" + instructions[k]['expected_completion_time'] + """\');""", 'post', conn)
                            

            response['message'] = 'successful'

            return response, 200
        except:
            raise BadRequest('Get Instructions?steps Request failed, please try again later.')
        finally:
            disconnect(conn)


# New APIs, uses connect() and disconnect()
# Create new api template URL
# api.add_resource(TemplateApi, '/api/v2/templateapi')

# Run on below IP address and port
# Make sure port number is unused (i.e. don't use numbers 0-1023)

# GET requests
api.add_resource(GoalsRoutines, '/api/v2/getgoalsandroutines/<string:user_id>') # working
api.add_resource(RTS, '/api/v2/rts/<string:user_id>') # working
api.add_resource(GAI, '/api/v2/gai/<string:user_id>') # working
api.add_resource(ActionsInstructions, '/api/v2/actionsInstructions/<string:gr_id>') # working
api.add_resource(AboutMe,'/api/v2/aboutme/<string:user_id>') #working
api.add_resource(TimeSettings,'/api/v2/timeSettings/<string:user_id>') #working

api.add_resource(ListAllTA, '/api/v2/listAllTA/<string:user_id>') #working
api.add_resource(ListAllTAForCopy, '/api/v2/listAllTAForCopy') #working
api.add_resource(ListAllUsersForCopy, '/api/v2/listAllUsersForCopy') #working

api.add_resource(ListAllPeople, '/api/v2/listPeople/<string:user_id>') #working
api.add_resource(ActionsTasks, '/api/v2/actionsTasks/<string:goal_routine_id>') #working
api.add_resource(InstructionsAndSteps, '/api/v2/instructionsSteps/<string:action_task_id>') #working

api.add_resource(AllUsers, '/api/v2/usersOfTA/<string:email_id>') #working
api.add_resource(TALogin, '/api/v2/loginTA/<string:email_id>/<string:password>') #working
api.add_resource(TASocialLogin, '/api/v2/loginSocialTA/<string:email_id>') #working
api.add_resource(Usertoken, '/api/v2/usersToken/<string:user_id>') #working
api.add_resource(UserLogin, '/api/v2/userLogin/<string:email_id>') #working
api.add_resource(GetEmailId, '/api/v2/getEmailId/<string:user_id>') #working
api.add_resource(CurrentStatus, '/api/v2/currentStatus/<string:user_id>') #working
api.add_resource(GoogleCalenderEvents, '/api/v2/calenderEvents')
api.add_resource(GetIconsHygiene, '/api/v2/getIconsHygiene')
api.add_resource(GetIconsClothing, '/api/v2/getIconsClothing')
api.add_resource(GetIconsFood, '/api/v2/getIconsFood')
api.add_resource(GetIconsActivities, '/api/v2/getIconsActivities')
api.add_resource(GetIconsOther, '/api/v2/getIconsOther')
api.add_resource(GetImages, '/api/v2/getImages/<string:user_id>')
api.add_resource(GetPeopleImages, '/api/v2/getPeopleImages/<string:ta_id>')
api.add_resource(GetHistory, '/api/v2/getHistory/<string:user_id>')
api.add_resource(GoalHistory, '/api/v2/goalHistory/<string:user_id>')
api.add_resource(ParticularGoalHistory, '/api/v2/particularGoalHistory/<string:user_id>')
api.add_resource(RoutineHistory, '/api/v2/routineHistory/<string:user_id>')
api.add_resource(GoalRoutineHistory, '/api/v2/goalRoutineHistory/<string:user_id>')
api.add_resource(GetUserAndTime, '/api/v2/getUserAndTime')
api.add_resource(Notifications, '/api/v2/notifications')
api.add_resource(TodayGR, '/api/v2/todayGR')
api.add_resource(GetNotifications, '/api/v2/getNotifications') # working
api.add_resource(Calender, '/api/v2/calender/<string:user_id>') # working
api.add_resource(Motivation, '/api/v2/motivation/<string:user_id>') # working
api.add_resource(Happy, '/api/v2/happy/<string:user_id>') # working
api.add_resource(Important, '/api/v2/important/<string:user_id>') # working
api.add_resource(Feelings, '/api/v2/feelings/<string:user_id>') # working
api.add_resource(UserTADetails, '/api/v2/userTADetails') # working
api.add_resource(Progress, '/api/v2/progress/<string:user_id>') # working
api.add_resource(GetVersionNumber, '/api/v2/getVersionNumber') # working

# POST requests
api.add_resource(AnotherTAAccess, '/api/v2/anotherTAAccess') #working
api.add_resource(AddNewAT, '/api/v2/addAT')
api.add_resource(AddNewIS, '/api/v2/addIS')
api.add_resource(AddNewGR, '/api/v2/addGR')
api.add_resource(UpdateGR, '/api/v2/updateGR')
api.add_resource(UpdateAT, '/api/v2/updateAT')
api.add_resource(UpdateIS, '/api/v2/updateIS')

api.add_resource(DeleteAT, '/api/v2/deleteAT')
api.add_resource(DeleteIS, '/api/v2/deleteIS')

api.add_resource(DeleteGR, '/api/v2/deleteGR')
api.add_resource(CreateNewPeople, '/api/v2/addPeople') #working
api.add_resource(DeletePeople, '/api/v2/deletePeople')
api.add_resource(UpdateTime, '/api/v2/updateTime/<user_id>')
api.add_resource(NewTA, '/api/v2/addNewTA') #working
api.add_resource(TASocialSignUP, '/api/v2/addNewSocialTA') #working
api.add_resource(CreateNewUser, '/api/v2/addNewUser') #working
api.add_resource(UpdateAboutMe, '/api/v2/updateAboutMe')
api.add_resource(UpdateNameTimeZone, '/api/v2/updateNewUser')
api.add_resource(AddCoordinates, '/api/v2/addCoordinates')
api.add_resource(UpdateGRWatchMobile, '/api/v2/udpateGRWatchMobile')
api.add_resource(UpdateATWatchMobile, '/api/v2/updateATWatchMobile')
api.add_resource(UpdateISWatchMobile, '/api/v2/updateISWatchMobile')

api.add_resource(Login, '/api/v2/login')
api.add_resource(AccessRefresh, '/api/v2/updateAccessRefresh')
api.add_resource(UpdateAboutMe2, '/api/v2/update')
api.add_resource(UploadIcons, '/api/v2/uploadIcons')
api.add_resource(UpdatePeople, '/api/v2/updatePeople')
api.add_resource(ChangeHistory, '/api/v2/changeHistory/<string:user_id>')
api.add_resource(ExistingUser, '/api/v2/existingUser')
api.add_resource(ResetGR, '/api/v2/resetGR/<string:gr_id>')
api.add_resource(update_guid_notification, '/api/v2/updateGuid/<string:action>')
api.add_resource(AboutHistory, '/api/v2/changeAboutMeHistory')
api.add_resource(UpdateMotivation, '/api/v2/updateMotivation')
api.add_resource(UpdateFeelings, '/api/v2/updateFeelings')
api.add_resource(UpdateHappy, '/api/v2/updateHappy')
api.add_resource(UpdateImportant, '/api/v2/updateImportant')
api.add_resource(DeleteUser, '/api/v2/deleteUser')
api.add_resource(UpdateVersionNumber, '/api/v2/updateVersionNumber')
api.add_resource(CopyGR, '/api/v2/copyGR')

# api.add_resource(ChangeSublist, '/api/v2/changeSub/<string:user_id>')



# api.add_resource(access_refresh_update, '/api/v2/accessRefreshUpdate')


# api.add_resource(CreateNewUsers, '/api/v2/createNewUser')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=4000)
