from flask import Blueprint, request, jsonify, render_template
from google.cloud import datastore
import json
import constants

client = datastore.Client()

bp = Blueprint('load', __name__, url_prefix='/loads')

# /loads
@bp.route('', methods=['POST','GET'])
def loads_get_post():
	# POST loads
	if request.method == 'POST':
		content = request.get_json()
		if len(content) != 3:
			return (jsonify({"Error": "The request object is missing at least one of the required attributes"}), 400)
		new_load = datastore.entity.Entity(key=client.key("loads"))
		new_load.update({"volume": content["volume"], 'carrier': None, 'item': content['item'], 'creation_date': content['creation_date']})
		client.put(new_load)
		new_load['id'] = new_load.key.id
		new_load['self'] = request.url + '/' + str(new_load.key.id)
		return (jsonify(new_load), 201)
	
	# GET all loads
	elif request.method == 'GET':
		query = client.query(kind="loads")
		q_limit = int(request.args.get('limit', '5'))
		q_offset = int(request.args.get('offset', '0'))
		g_iterator = query.fetch(limit= q_limit, offset=q_offset)
		pages = g_iterator.pages
		results = list(next(pages))
		if g_iterator.next_page_token:
			next_offset = q_offset + q_limit
			next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
		else:
			next_url = None
		for e in results:
			e["id"] = e.key.id
			e["self"] = request.url_root + "loads/" + str(e.key.id)
			if e["carrier"] != None:
				e['carrier']['self'] = request.url_root + "boats/" + str(e['carrier']['id'])
		output = {"loads": results}
		if next_url:
			output["next"] = next_url
		# return (jsonify(output), 200)
		return (render_template('load.html', data = json.dumps(output, indent = 4)), 200)

# /loads/<load_id>
@bp.route('/<load_id>', methods=['DELETE','GET', 'PATCH', 'PUT'])
def tloads_get_delete(load_id):
	# DELETE the load at load_id
	if request.method == 'DELETE':
		key = client.key("loads", int(load_id))
		load = client.get(key=key)
		if load == None:
			return (jsonify({"Error": "No load with this load_id exists"}), 404)
		if load['carrier'] != None:
			boat = client.get(key=client.key("boats", load['carrier']['id']))
			boat["loads"].remove({'id': load.key.id})
			client.put(boat)
		client.delete(key)
		return (jsonify(''),204)
	
	# GET load_id json information
	elif request.method == 'GET':
		print("IN get")
		load_key =  client.key(constants.loads, int(load_id))
		load = client.get(key = load_key)
		if load == None:
			x = {
				"Error": "No load with this load_id exists"
			}
			a_ll = json.dumps(x)
			return (a_ll, 404)
		
		# create carrier information
		if load['carrier'] != None:
			x = load['carrier']
			for l in load['carrier']:
				# took me forever to figure out to make url!!
				selfurl= str(request.url_root) + 'boats/'  + str(x["id"])
				load['carrier'] = {
					"name" : x["name"],
					"id" : x["id"],
					"self" : selfurl
				}
				print("load",load['carrier'])

		load["id"] = load_id
		load["self"] = request.url
		# return (jsonify(load), 200)
		return (render_template('loadinfo.html', data = json.dumps(load, indent = 4)), 200)


	elif request.method == 'PATCH' or request.method == 'PUT':
		# time to test
		# print("hi")
		content = request.get_json()
		print("CONTENT ", content)

		if "volume" in content and "item" in content and "creation_date" in content:
			load_key = client.key(constants.loads, int(load_id))
			
			if load_id != None:
				load = client.get(key = load_key)
				if load != None:
					load.update({"volume" : content["volume"], "item" : content["item"], "creation_date" : content["creation_date"]})
					client.put(load)
					load["id"] = load.key

					#return(json.dumps(load), 200)
					#print("LOAD< ", load)
					#print("JSON, ", jsonify(load))
					return (jsonify({"Message" : "Success"}), 200)
				else:
					x = {
						"Error" : "No load with this load_id exists"
					}
					a_ll = json.dumps(x)
					return (a_ll, 404)
			# load_key is None
			else:
					x = {
						"Error" : "No load with this load_id exists"
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
		print("Not in get or delete")
		return ('No load with this load_id exists', 404)