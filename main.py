from google.cloud import datastore
from flask import Flask, request, jsonify, render_template, make_response
import json
import string
import random
import flask
import constants
import load
from json2html import *

# now can run locally
import os
from datetime import datetime
from requests_oauthlib import OAuth2Session
from google.oauth2 import id_token
from google.auth import crypt
from google.auth import jwt

from google.auth.transport import requests


os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
dclient = datastore.Client()
app = Flask(__name__)

app.register_blueprint(load.bp)

# oauth 2 info stuff
client_id = constants.clientID
client_secret = constants.clientSecret
redirect_uri = constants.redirectURL


# identify users
urls = ['https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile', 'openid']
oauth = OAuth2Session(client_id, redirect_uri = redirect_uri, scope = urls)

@app.route('/')
def index():
	# citation:
	# site: https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html
	# used to create the oauth.authorization_url
	# date: 5/16/2022

	authorization_url, state = oauth.authorization_url(
	'https://accounts.google.com/o/oauth2/auth',
	# access_type and prompt are Google specific extra
	# parameters.
	# https://accounts.google.com/o/oauth2/auth?response_type=code&client_id=499938882837-c6rurjceojlncsj010vfsph7d6aoaukq.apps.googleusercontent.com&redirect_uri=http%3A%2F%2F127.0.0.1%3A8080%2Foauth&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.email+https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fuserinfo.profile+openid&state=hjU0ToOUkBxRa3JwRmlLh2QkrLJaGt&access_type=offline&prompt=select_account
	access_type="offline", prompt="select_account")
	print(authorization_url)
	#return '<h1>Welcome</h1>\n <p>Click <a href=%s>here</a> to get your JWT.</p>' % authorization_url
	url = {
		'url' : authorization_url
	}
	return render_template('index.html', data = url)


@app.route('/oauth', methods = ['GET'])
def oauth_data():
	
	token = oauth.fetch_token('https://oauth2.googleapis.com/token', authorization_response=request.url, client_secret=client_secret)
	req = requests.Request()
	print("HIHI", token)
	id_info = id_token.verify_oauth2_token(token['id_token'], req, client_id)

	tokens = {
		'id_token' : token['id_token']
	}
	# output = jsonify({"jwt" : token['id_token']})
	# return (render_template('jwt.html', data = json.dumps(load, indent = 4)))
	return(jsonify({"jwt" : token['id_token']}), 200)
	#render_template('info.html', data = tokens)


# citation:
# site: https://developers.google.com/identity/sign-in/web/backend-auth
# used to help verify if jwt is correct in each functions below
# date: 5/16/2022

@app.route('/boats', methods = ['POST', "GET"])
def get_post_boats():
	if request.method == 'GET':
		isListPublic = False
		
		# find elements in database
		query = dclient.query(kind=constants.boat)

		# Get JWT from Authorization header/token
		req = requests.Request()
		jwtInfo = request.headers.get('Authorization')

		# check if jwt is valid. If not only show public boats
		print(jwtInfo)
		if jwtInfo != None:
			jwtInfo = jwtInfo.split(" ")[1]
			try:
				jwtClaim = id_token.verify_oauth2_token(jwtInfo, req, client_id)['sub']
			except:
				isListPublic = True
		else:
			isListPublic = True


		if isListPublic:
			query.add_filter("public", "=", True)
		else:
			query.add_filter("owner", "=", jwtClaim)

		
		# fetches the boats that are public
		results = list(query.fetch())

		# only have 3 boats per page
		query_limit = int(request.args.get('limit', '5'))
		query_offset = int(request.args.get('offset', '0'))
		list_iterator = query.fetch(limit = query_limit, offset = query_offset)
		pages = list_iterator.pages
		
		results = list(next(pages))

		if list_iterator.next_page_token:
			next_offset = query_offset + query_limit
			next_url = request.base_url + "?limit=" + str(query_limit) + "&offset=" + str(next_offset)
		else:
			next_url = None

		# Add entity id for each boat
		for e in results:
			e["id"] = e.key.id
			e["self"] = constants.url + 'boats/' + str(e.key.id)

		output = {"boats": results}
		if next_url:
			output["next"] = next_url
		# else:
		# 	output["next"] = jsonify({"next" : " "})
		# return (jsonify(output), 200)

		if "application/json" in request.accept_mimetypes:
			for e in results:
				e["id"] = e.key.id
				e["self"] = constants.url + 'boats/' + str(e.key.id)
				print(e["self"])

			output = {"boats": results, "next" : next_url}
			#return (jsonify(output), 200)
			return (render_template('list.html', data = json.dumps(output, indent = 4)), 200)

		elif "text/html" in request.accept_mimetypes:
			res = make_response(json2html.convert(json = json.dumps(output)))
			res.headers.set('Content-Type', 'text/html')
			res.status_code = 200
			return res

		else:
			return(jsonify({"Error" : "This type is not supported, must be JSON or HTML"}), 406)

	elif request.method == 'POST':
		# Get JWT from Authorization header/token
		req = requests.Request()
		jwtInfo = request.headers.get('Authorization')

		# check if jwtInfo is given
		if jwtInfo != None:
			jwtInfo = jwtInfo.split(" ")[1]
			print(jwtInfo)
			# print(req)
			# print(client_id)

			# if JWT is valid save the 'sub' value
			try:
				jwtClaim = id_token.verify_oauth2_token(jwtInfo, req, client_id)['sub']
			
			# if JWT is not valid return 401
			except:
				return('Could not verify JWT is valid!\n', 401)
		
		else:
			return (jsonify('No JWT was given!'), 401)


		# Grab content from request body
		content = request.get_json()
		print(len(content))
		# checking if body is valid (shouldent need to be validated)
		if len(content) != 4:
			return (jsonify({"Error": "The request object is missing at least one of the required attributes (name, type, length or public)"}), 400)

		# Create a new boat entity
		# boat name uniqueness is not enforced
		new_boat = datastore.entity.Entity(key=dclient.key(constants.boat))
		new_boat.update({"name": content["name"], "type": content["type"], "length": content["length"], "public": content["public"], "owner": jwtClaim, 'loads' : []})
		
		# put boat into datastore (dclient)
		dclient.put(new_boat)

		# Return boat
		return (jsonify({"id": new_boat.key.id, "name": content["name"], "type": content["type"], "length": content["length"], "public": content["public"], "owner": jwtClaim, 'loads' : []}), 201)

	else:
		return (jsonify({"Error" : 'Method not recogonized'}), 405)


@app.route('/boats/<boat_id>', methods=['DELETE', 'GET', 'PATCH', 'PUT'])
def delete_boat(boat_id):
	if request.method == 'DELETE':
		# Get JWT from Authorization header/token
		req = requests.Request()
		jwtInfo = request.headers.get('Authorization')
		
		# checking jwtInfo
		if jwtInfo != None:
			jwtInfo = jwtInfo.split(" ")[1]
			
			# Check to see if JWT is valid
			try:
				jwtClaim = id_token.verify_oauth2_token(jwtInfo, req, client_id)['sub']
			except:
				return('Could not verify JWT!\n', 401)
		else:
			# Now JWT was given
			return (jsonify('No JWT was given!'), 401)
		
		# find boat with boat_id
		boat_key = dclient.key(constants.boat, int(boat_id))
		boat = dclient.get(key=boat_key)

		# error if no boat at id
		if boat == None:
			return (jsonify({'Error': 'No boat with this boat_id exists'}), 403)
		
		# error if the JWT ownter does not own the boat
		elif boat['owner'] != jwtClaim:
			return (jsonify({'Error': 'This boat is owned by someone else!'}), 403)

		if len(boat['loads']) > 0:
			for load in boat['loads']:
				load_obj = dclient.get(key=dclient.key("loads", load['id']))
				load_obj['carrier'] = None
				dclient.put(load_obj)

		# Delete boat from Datastore
		dclient.delete(boat_key)
		return (jsonify({'Result': 'Deleted the boat'}), 204)
	
	elif request.method == 'GET':
		boat_key = dclient.key("boats", int(boat_id))
		boat = dclient.get(key=boat_key)

		if boat == None:
			x = {
					"Error": "No boat with this boat_id exists"
				}
			a_ll = json.dumps(x)
			return (a_ll, 404)

		print(boat['loads'])
		i= boat['loads']
		
		y = request.url_root+ 'loads/' 
		# print(i)
		# print("hi", y)
		listfornum = []
		listforurl = []
		for load in boat['loads']:
			i = load['id']
			listfornum.append(i)
			print(i)
			selfurl= constants.url + 'loads/'  + str(i)
			listforurl.append(selfurl)
			boat['loads'] = {
				"id" : listfornum,
				"self" : listforurl
			}
			
		print("LISTFORNUM<   ", listfornum)
		boat["id"] = boat_id
		boat["self"] = constants.url + 'boats/' + boat_id
		print(json.dumps(boat))
		#i.update({'id' : [boat['loads']]})
		#return (jsonify(boat), 200)

		# print(type(boat['loads']))
		# x=0
		# listfornum = []
		# listforurl = []
		# listforjson = []
		# for load in boat['loads']:
		# 	print("HI")
		# 	#print(load['id'])
		# 	i = load['id']
		# 	listfornum.append(i)
		# 	print(listfornum)
		# 	selfurl= constants.url + 'loads/'  + str(i)
		# 	listforurl.append(selfurl)
		# 	print(listforurl)
		# 	#for num in load['id']:
		# 	boat['loads'] = {
		# 		"id" : listfornum,
		# 		"self" : listforurl
		# 		# "id" : i,
		# 		# "self" : selfurl
		# 	}
		# 	#boat.update({'loads' : [boat['loads']]})
		# 	#json.dumps(boat)
		# 	#listforjson.append(boats['loads'])
		# 	#print("HSON LIST", listforjson)
		
		if 'application/json' in request.accept_mimetypes:
			#return (jsonify(boat), 200)
			return (render_template('boatinfo.html', data = json.dumps(boat, indent = 4)), 200)
		elif 'text/html' in request.accept_mimetypes:
			res = make_response(json2html.convert(json = json.dumps(boat)))
			res.headers.set('Content-Type', 'text/html')
			res.status_code = 200
			return res
		else:
			return(jsonify({"Error" : "This type is not supported, must be JSON or HTML"}), 406)
	
	elif request.method == 'PATCH' or request.method == 'PUT':
		content = request.get_json()
		
		#####
		# Get JWT from Authorization header/token
		req = requests.Request()
		jwtInfo = request.headers.get('Authorization')
		
		# checking jwtInfo
		if jwtInfo != None:
			jwtInfo = jwtInfo.split(" ")[1]
			
			# Check to see if JWT is valid
			try:
				jwtClaim = id_token.verify_oauth2_token(jwtInfo, req, client_id)['sub']
			except:
				return('Could not verify JWT!\n', 401)
		else:
			# Now JWT was given
			return (jsonify('No JWT was given!'), 401)
		print("JWT  ", jwtClaim)
		

		# find boat with boat_id
		boat_key = dclient.key(constants.boat, int(boat_id))
		boat = dclient.get(key=boat_key)

		# error if no boat at id
		if boat == None:
			return (jsonify({'Error': 'No boat with this boat_id exists'}), 403)
		
		# error if the JWT ownter does not own the boat
		elif boat['owner'] != jwtClaim:
			return (jsonify({'Error': 'This boat is owned by someone else!'}), 403)
		#####


		if "name" in content and "type" in content and "length" in content:
			
			boat_key = dclient.key(constants.boat, int(boat_id))
			if boat_key != None:
				boat = dclient.get(key = boat_key)
				if boat != None:
					boat.update({"name": content["name"], "type": content["type"], "length": content["length"]})
					dclient.put(boat)
					boat["id"] = boat.key.id

					return(json.dumps(boat), 200)
				# boat is none
				else:
					x = {
						"Error" : "No boat with this boat_id exists"
					}
					a_ll = json.dumps(x)
					return (a_ll, 404)
			# boat_key is Nonoe
			else:
					x = {
						"Error" : "No boat with this boat_id exists"
					}
					a_ll = json.dumps(x)
					return (a_ll, 404)
		# There is missing a variable in content
		else:
			x = {
				"Error" : "The request object is missing at least one of the required attributes"
			}
			a_ll = json.dumps(x)
			#return (a_ll,400)
			#boat[boat_id] = content
			#res = make_response(jsonify({"Error": "No boat with this boat_id exists"}, 404))
			return (a_ll, 400)
	
	else:
		return (jsonify({"Error" : 'Method not recogonized'}), 405)



@app.route('/users/<owner_id>/boats', methods=['GET'])
def get_owner_of_boats(owner_id):
	if request.method == 'GET':
		# Search the database for all boats with the owner_id and that are public
		query = dclient.query(kind=constants.boat)

		# filters out owner by id and the boats that are public
		query.add_filter("owner", "=", owner_id)
		query.add_filter("public", "=", True)

		# return the boats that meet both requrments
		results = list(query.fetch())

		# add new id for each boat
		for e in results:
			e["id"] = e.key.id

		#return (jsonify(results), 200)
		return (render_template('user.html', data = json.dumps(results, indent = 4)), 200)

	else:
		return (jsonify({"Error" : 'Method not recogonized'}), 405)


@app.route('/users', methods=['GET'])
def get_users_here():
	if request.method == "GET":
		query = dclient.query(kind=constants.boat)
		results = list(query.fetch())
		final_result_array = []
		print(results)
		for e in results:
			print("EEEE", e["owner"])
			final_result = {"owner":""}
			users = json.dumps(e)
			users = json.loads(users)
			final_result["owner"] = users["owner"]
			final_result_array.append(final_result)
		#return json.dumps(final_result_array)
		return (render_template('user.html', data = json.dumps(final_result_array, indent = 4)))


# /boat/<boat_id>/loads/<load_id>
@app.route('/boats/<boat_id>/loads/<load_id>', methods=['PUT','DELETE'])
def add_delete_reservation(boat_id, load_id):
	if request.method == 'PUT':
		boat_key = dclient.key("boats", int(boat_id))
		boat = dclient.get(key=boat_key)
		load_key = dclient.key("loads", int(load_id))
		load = dclient.get(key=load_key)


		if boat == None or load == None:
			#THIhe specified boat and/or load does not exist"
			return (jsonify({"Error": "The specified boat and/or load does not exist"}), 404)
		# if load['carrier'] != None:
		# 	return (jsonify({"Error": "The load is already loaded on another boat"}), 403)
		if 'loads' in boat.keys():
			for loads in boat['loads']:
				if loads['id'] == load.key.id:
					return(jsonify({"Error": "Load already assigned to boat"}), 403)
			boat['loads'].append({"id": load.key.id})
			load['carrier'] = {"id": boat.key.id, "name": boat["name"]}
		else:
			boat['loads'] = {"id": load.key.id}
			load['carrier'] = {"id": boat.key.id, "name": boat["name"]}
		dclient.put(boat)
		dclient.put(load)
		return(jsonify(''), 204)
	
	elif request.method == 'DELETE':
		boat_key = dclient.key("boats", int(boat_id))
		boat = dclient.get(key=boat_key)
		load_key = dclient.key("loads", int(load_id))
		load = dclient.get(key=load_key)
		if boat == None or load == None:
			return (jsonify({"Error": "No boat with this boat_id is loaded with the load with this load_id"}), 404)
		if load['carrier'] == None or load['carrier']['id'] != boat.key.id:
			return (jsonify({"Error": "No boat with this boat_id is loaded with the load with this load_id"}), 404)
		if 'loads' in boat.keys():
			boat['loads'].remove({"id": load.key.id})
			load['carrier'] = None
			dclient.put(boat)
			dclient.put(load)
		return(jsonify(''),204)

	else:
		return (jsonify({"Error" : 'Method not recogonized'}), 405)


# /boat/<boat_id>/loads
@app.route('/boats/<boat_id>/loads', methods=['GET'])
def boats_get_loads(boat_id):
	if request.method == 'GET': 
		boat_key = dclient.key("boats", int(boat_id))
		boat = dclient.get(key=boat_key)
		if boat == None:
			print("hi1")
			x = {
				"Error": "No boat with this boat_id exists"
			}
			a_ll = json.dumps(x)
			return (a_ll,404)
		print(boat['loads'])
		load_num = boat['loads']
		print("load_num, ", load_num)
		#print(type(load_num))
		#i = load_num[0]
		#print("i, ", i)
		
		if len(load_num) != 0:
			idholder = []
			urlholder = []
			loadholder = []
			for x in load_num:
				# print(x)
				i = x['id']
				idholder.append(i)
				selfurl = constants.url + "loads/" + str(i)
				urlholder.append(selfurl)
				print("HIHI,   ", i)
				load_key =  dclient.key(constants.loads, int(i))
				load = dclient.get(key = load_key)
				loadholder.append(load)
				print("LOAD KEY", load)
				if load == None:
					x = {
						"Error": "No load with this load_id exists"
					}
					a_ll = json.dumps(x)
					return (a_ll, 404)
				#if load["carrier"]:
				#    load["carrier"]["self"] = request.url_root + "boats/" + load["carrier"]["id"]
			print(loadholder)
			load["id"] = idholder
			load["self"] = urlholder
			load["current"] = constants.url + "boats/" + boat_id + "/loads"
			# print(load)
			# print(load["id"])
			#return (jsonify(load), 200)
			return (render_template('boatinfo.html', data = json.dumps(load, indent = 4)), 200)
		else:
			#return (jsonify([]), 200)
			return (render_template('boatinfo.html', data = json.dumps([], indent = 4)), 200)

	else:
		return (jsonify({"Error" : 'Method not recogonized'}), 405)


if __name__ == '__main__':
	app.run(host='127.0.0.1', port=8080, debug=True)