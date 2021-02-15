from __future__ import print_function
from flask import Flask, render_template, session, json, request, redirect, flash, get_flashed_messages, jsonify, make_response
from flask_mysqldb import MySQL
from google.cloud import translate_v2 as translate
from google.oauth2 import service_account
from googleapiclient.discovery import build
import boxsdk
import json
import re
from datetime import datetime
import os
import glob
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="https://467f5f32371848da8c0ef7a3481afd04@o493026.ingest.sentry.io/5561397",
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0
)

app = Flask(__name__)
app.config["SECRET_KEY"] = "ShuJAxtrE8tO5ZT"

# MySQL configurations
with open('mysql.cfg', 'r') as mysql_cfg:
	mysql_cfg_lines = mysql_cfg.read().splitlines()
	app.config['MYSQL_USER'] = mysql_cfg_lines[0]
	app.config['MYSQL_PASSWORD'] = mysql_cfg_lines[1]
	app.config['MYSQL_DB'] = mysql_cfg_lines[2]
	app.config['MYSQL_HOST'] = mysql_cfg_lines[3]
mysql = MySQL(app)

#Google Sheets credentials
tr_credentials = service_account.Credentials.from_service_account_file("My Project-1f2512d178cb.json")
scopes = ['https://www.googleapis.com/auth/spreadsheets']
scoped_gs = tr_credentials.with_scopes(scopes)
sheets_client = build('sheets', 'v4', credentials=scoped_gs)
tracking_ws = "1F4nXX1QoyV1miaRUop2ctm8snDyov6GNu9aLt9t3a3M"
ranges = "Workflow_Tracking!A3:L87078"
sheet = sheets_client.spreadsheets()
gsheet = sheet.values().get(spreadsheetId=tracking_ws, range=ranges, majorDimension="COLUMNS").execute()


#Box API configurations
with open('box_config.json', 'r') as f:
	boxapi = json.load(f)
box_auth = boxsdk.JWTAuth(
	client_id=boxapi["boxAppSettings"]["clientID"],
    client_secret=boxapi["boxAppSettings"]["clientSecret"],
    enterprise_id=boxapi["enterpriseID"],
    jwt_key_id=boxapi["boxAppSettings"]["appAuth"]["publicKeyID"],
    rsa_private_key_data=boxapi["boxAppSettings"]["appAuth"]["privateKey"],
    rsa_private_key_passphrase=boxapi["boxAppSettings"]["appAuth"]["passphrase"],
)

box_access_token = box_auth.authenticate_instance()
box_client = boxsdk.Client(box_auth)

#Roman numeral utility
def toRoman(data):
	romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
	romin = int(data) - 1
	if romin >= 0 and romin < len(romans):
		romreg = romans[romin]
	else:
		romreg = data
	return romreg

@app.route('/debug-sentry')
def trigger_error():
    division_by_zero = 1 / 0

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

@app.route("/") # Home page
def index():
	return render_template('index.html')

@app.route("/login", methods=['POST']) # Login form
def login():
	with open('user.cfg', 'r') as user_cfg:
		user_lines = user_cfg.read().splitlines()
		username = user_lines[0]
		password = user_lines[1]
	if request.form['password'] == password and request.form['username'] == username:
		session['logged_in'] = True
	else:
		flash('Sorry, wrong password!')
	return render_template('index.html')

@app.route('/init', methods=['POST']) #Form submitted from home page
def init():
	if (request.form.get('region')):
		session['region'] = request.form['region']
	else:
		session['region'] = ""
	if (request.form.get('insula')):
		session['insula'] = request.form['insula']
	else:
		session['insula'] = ""
	if (request.form.get('property')):
		session['property'] = request.form['property']
	else:
		session['property'] = ""
	if (request.form.get('room')):
		session['room'] = request.form['room']
	else:
		session['room'] = ""

	# prop = session['property']
	# if session['property'].isalpha():
	# 	prop += "1"
	# elif len(session['property']) < 2:
	# 	prop = "0" + prop
	# ins = session['insula']
	# if len(session['insula']) < 2:
	# 	ins = "0" + ins
	# building = toRoman(session['region']) + ins + prop + session['room']
	
	building = "r" + str(session['region']) + "-i"+str(session['insula']) + "-p" + session['property'] + "-space-" + session['room']
	values = gsheet.get('values', [])
	locationlist = values[1]
	arclist = values[7]

	session['validARCs'] = []
	for l in range(len(locationlist)):
		if locationlist[l].startswith(building):
			session['validARCs'].append(arclist[l])
	session['invcheckedARCs'] = []
	return redirect('/PPM')
	

@app.route('/PPM') #PPM page
def showPPM():

	if session.get('logged_in') and session["logged_in"]:

		#PPM data has individual location columns
		ppmCur = mysql.connection.cursor()
		ppmQuery = "SELECT id, description, image_path, region, insula, doorway, room, translated_text FROM PPM WHERE region LIKE %s AND insula LIKE %s AND doorway LIKE %s AND room LIKE %s ORDER BY `image_path` ASC;"
		loc = []
		if (session.get('region')):
			loc.append(toRoman(session['region']))
		else:
			loc.append("%")
		if (session.get('insula')):
			ins = session['insula']
			if session['insula'][0] == "0":
				ins = session['insula'].replace("0","")
			loc.append(ins)
		else:
			loc.append("%")
		if (session.get('property')):
			prop = session['property'] 
			if session['property'][0] == "0":
				prop = session['property'].replace("0","")
			loc.append(prop)
		else:
			loc.append("%")
		if (session.get('room')):
			room = session['room'] 
			if session['room'][0] == "0":
				room = session['room'].replace("0","")
			loc.append(room)
		else:
			loc.append("%")

		ppmCur.execute(ppmQuery, loc)
		dataTuple = ppmCur.fetchall()
		ppmCur.close()

		ppm2Cur = mysql.connection.cursor()
		data = []
		indices = []
		for d in dataTuple:
			indices.append(d[0])
			ppm2Query = "SELECT `is_art`, `is_plaster`, `ARC`, `other_ARC`, `notes`, `hero_image` FROM PPM_preq WHERE id = %s;"
			ppm2Cur.execute(ppm2Query, [d[0]])
			toin = []
			for l in d:
				toin.append(l)
			fetched = ppm2Cur.fetchall()
			if len(fetched) > 0:
				for j in fetched[0]:
					toin.append(j)
			data.append(toin)

		imgs = []
		for d in data:
			itemid = "0"
			#THIS SHOULD BE COMING FROM DATABASE IF POSSIBLE
			print(d[2])
			searchid = "\"" + d[2] + "\""
			box_id = box_client.search().query(query=searchid, file_extensions=['jpg'], ancestor_folder_ids="97077887697,87326350215", fields=["id", "name"], content_types=["name"])
			for item in box_id:
				if item.name == d[2]:
					itemid = item.id
					break
			imgs.append(itemid)
			filename = str(itemid) + ".jpg"
			if not os.path.exists("static/images/"+filename):
				try:
					thumbnail = box_client.file(itemid).get_thumbnail(extension='jpg', min_width=200)
				except boxsdk.BoxAPIException as exception:
					thumbnail = bytes(exception.message, 'utf-8')
				with open(os.path.join("static/images",filename), "wb") as f:
					f.write(thumbnail)
		
		for x in range(len(data)):
			data[x].insert(8,imgs[x])
		 	
			imgQuery = "UPDATE PPM SET image_id= %s WHERE id = %s ;"
			ppm2Cur.execute(imgQuery, [imgs[x], data[x][0]])
		mysql.connection.commit()
		
		ppm2Cur.close()

		ppm = ppmimg = reg = ins = prop = room = ""

		if (session.get('region')):
			reg = session['region']
		if (session.get('insula')):
			ins = session['insula']
		if (session.get('property')):
			prop = session['property']
		if (session.get('room')):
			room = session['room']

		if (session.get('carryoverPPM')):
			ppm = session['carryoverPPM']
		if (session.get('carryoverPPMImgs')):
			ppmimg = session['carryoverPPMImgs']

		return render_template('PPM.html',
			catextppm=ppm, catextppmimg=ppmimg, dbdata = data, indices = indices,
			region=reg, insula=ins, property=prop, room=room)
	else:
		flash("Sorry, this page is only accessible by logging in.")
		return render_template('index.html')

@app.route('/PinP') #PinP page
def showPinP():
	if session.get('logged_in') and session["logged_in"]:

		pinp = reg = ins = prop = room = ""

		pinpCur = mysql.connection.cursor()

		pinpQuery = "SELECT DISTINCT `archive_id`, `id_box_file`, `img_alt` FROM `PinP` WHERE `pinp_regio` LIKE %s and `pinp_insula` LIKE %s  and `pinp_entrance` LIKE %s ORDER BY `img_url` "
		loc = []
		if (session.get('region')):
			loc.append(toRoman(session['region']))
		else:
			loc.append("%")
		if (session.get('insula')):
			ins = session['insula']
			if session['insula'][0] == "0":
				ins = session['insula'].replace("0","")
			loc.append(ins)
		else:
			loc.append("%")
		if (session.get('property')):
			prop = session['property'] 
			if session['property'][0] == "0":
				prop = session['property'].replace("0","")
			loc.append(prop)
		else:
			loc.append("%")

		pinpCur.execute(pinpQuery, loc)
		dataTuple = pinpCur.fetchall()
		print(dataTuple)
		pinpCur.close()

		pinp2Cur = mysql.connection.cursor()
		data = []
		indices = []
		for d in dataTuple:
			pinp2Query = "SELECT `is_art`, `is_plaster`, `ARC`, `other_ARC`, `notes`, `hero_image` FROM PinP_preq WHERE `archive_id` = %s;"
			pinp2Cur.execute(pinp2Query, [d[0]])
			toin = []
			for l in d:
				toin.append(l)
			fetched = pinp2Cur.fetchall()
			if len(fetched) > 0:
				for j in fetched[0]:
					toin.append(j)
			data.append(toin)
			indices.append(d[1])
			filename = str(d[1]) + ".jpg"
			if not os.path.exists("static/images/"+filename):
				try:
					thumbnail = box_client.file(d[1]).get_thumbnail(extension='jpg', min_width=200)
				except boxsdk.BoxAPIException as exception:
					thumbnail = exception.message
				with open(os.path.join("static/images",filename), "wb") as f:
					try:
						f.write(thumbnail)
					except TypeError:
						print(thumbnail)
		pinp2Cur.close()

		if (session.get('region')):
			reg = session['region']
		if (session.get('insula')):
			ins = session['insula']
		if (session.get('property')):
			prop = session['property']
		if (session.get('room')):
			room = session['room']

		return render_template('PinP.html',
			catextpinp=pinp, dbdata = data, indices = indices,
			region=reg, insula=ins, property=prop, room=room)
	else:
		flash("Sorry, this page is only accessible by logging in.")
		return render_template('index.html')
	
@app.route('/help') #Help page - the info here is in the HTML
def help():
	reg = ins = prop = room = ""

	if (session.get('region')):
		reg = session['region']
	if (session.get('insula')):
		ins = session['insula']
	if (session.get('property')):
		prop = session['property']
	if (session.get('room')):
		room = session['room']

	return render_template('help.html',
		region=reg, insula=ins, property=prop, room=room)

@app.route('/GIS') #Embedded GIS map
def GIS():
	reg = ins = prop = room = ""

	if (session.get('region')):
		reg = session['region']
	if (session.get('insula')):
		ins = session['insula']
	if (session.get('property')):
		prop = session['property']
	if (session.get('room')):
		room = session['room']

	return render_template('GIS.html',
		region=reg, insula=ins, property=prop, room=room)

@app.route('/save-button', methods=["POST", "GET"]) #Save button found on PinP and PPM pages
def save_button():
	date = datetime.now().strftime("%Y-%m-%d")
	if (request.form.get('savepinp')):
		pinpCur = mysql.connection.cursor()
		for k, v in request.form.items():
			if v != "":
				ksplit = k.split("-")
				if len(ksplit) > 1:
					vstrip = str(v).strip()
					if ksplit[1] == "art":
						pinpQuery = 'INSERT INTO `PinP_preq` (archive_id, is_art, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '","'+ date +'") ON DUPLICATE KEY UPDATE `is_art` = "'+ str(v) + '", `date_added` = "' + date +'";'
						pinpCur.execute(pinpQuery)
					elif ksplit[1] == "plaster":
						pinpQuery = 'INSERT INTO `PinP_preq` (archive_id, is_plaster, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '","'+ date +'") ON DUPLICATE KEY UPDATE `is_plaster` = "'+ str(v) + '", `date_added` = "' + date +'";'
						pinpCur.execute(pinpQuery)
					elif ksplit[1] == "ARC":
						if vstrip not in session['validARCs'] and vstrip not in session['invcheckedARCs'] and vstrip[:3] == "ARC":
							flash(str(v) + " is not in the list of ARCs for this building.")
							session['invcheckedARCs'].append(vstrip)
						pinpQuery = 'INSERT INTO `PinP_preq` (archive_id, ARC, date_added) VALUES ('+ ksplit[0] +',"'+ vstrip + '","'+ date +'") ON DUPLICATE KEY UPDATE `ARC` = "'+ vstrip + '", `date_added` = "' + date +'";'
						pinpCur.execute(pinpQuery)
					elif ksplit[1] == "others":
						pinpQuery = 'INSERT INTO `PinP_preq` (archive_id, other_ARC, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '","'+ date +'") ON DUPLICATE KEY UPDATE `other_ARC` = "'+ str(v) + '", `date_added` = "' + date +'";'
						pinpCur.execute(pinpQuery)
					elif ksplit[1] == "notes":
						pinpQuery = 'INSERT INTO `PinP_preq` (archive_id, notes, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '","'+ date +'") ON DUPLICATE KEY UPDATE `notes` = "'+ str(v) + '", `date_added` = "' + date +'";'
						try:
							pinpCur.execute(pinpQuery)
						except Exception:
							flash('Please resubmit without double quotes (")')
		mysql.connection.commit()
		pinpCur.close()
	if (request.form.get('saveppm')):
		ppmCur = mysql.connection.cursor()
		for k, v in request.form.items():
			if v != "":
				ksplit = k.split("-")
				if len(ksplit) > 1:
					vstrip = str(v).strip()
					if ksplit[1] == "art":
						ppmQuery = 'INSERT INTO `PPM_preq` (id, is_art, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '",'+ date +') ON DUPLICATE KEY UPDATE `is_art` = "'+ str(v) + '", `date_added` = "' + date +'";'
						ppmCur.execute(ppmQuery)
					elif ksplit[1] == "plaster":
						ppmQuery = 'INSERT INTO `PPM_preq` (id, is_plaster, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '",'+ date +') ON DUPLICATE KEY UPDATE `is_plaster` = "'+ str(v) + '", `date_added` = "' + date +'";'
						ppmCur.execute(ppmQuery)
					elif ksplit[1] == "ARC":
						if vstrip not in session['validARCs'] and vstrip not in session['invcheckedARCs'] and vstrip[:3] == "ARC":
							flash(str(v) + " is not in the list of ARCs for this building.")
							session['invcheckedARCs'].append(vstrip)
						ppmQuery = 'INSERT INTO `PPM_preq` (id, ARC, date_added) VALUES ('+ ksplit[0] +',"'+ vstrip + '",'+ date +') ON DUPLICATE KEY UPDATE `ARC` = "'+ vstrip + '", `date_added` = "' + date +'";'
						ppmCur.execute(ppmQuery)
					elif ksplit[1] == "others":
						ppmQuery = 'INSERT INTO `PPM_preq` (id, other_ARC, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '",'+ date +') ON DUPLICATE KEY UPDATE `other_ARC` = "'+ str(v) + '", `date_added` = "' + date +'";'
						ppmCur.execute(ppmQuery)
					elif ksplit[1] == "notes":
						ppmQuery = 'INSERT INTO `PPM_preq` (id, notes, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '",'+ date +') ON DUPLICATE KEY UPDATE `notes` = "'+ str(v) + '", `date_added` = "' + date +'";'
						try:
							ppmCur.execute(ppmQuery)
						except Exception:
							flash('Please resubmit without double quotes (")')
		mysql.connection.commit()
		ppmCur.close()
	return make_response(jsonify(get_flashed_messages()), 201)

@app.route('/search', methods=['POST']) #Search bar at top of pages
def search():
	if (request.form.get('region')):
		session['region'] = request.form['region']
	else:
		session['region'] = ""
	if (request.form.get('insula')):
		session['insula'] = request.form['insula']
	else:
		session['insula'] = ""
	if (request.form.get('property')):
		session['property'] = request.form['property']
	else:
		session['property'] = ""
	if (request.form.get('room')):
		session['room'] = request.form['room']
	else:
		session['room'] = ""
	return redirect(request.referrer)

@app.route("/PPP") # PPP page
def showPPP():

	if session.get('logged_in') and session["logged_in"]:
		inswithz = propwithz = ""

		pppCur = mysql.connection.cursor()
		rm = ""
		if session['room']:
			rm = "' and `Room` = '" +session['room']
		pppQuery = "SELECT uuid, id, location, material, description, condition_ppp, style, bibliography, photo_negative FROM PPP WHERE `Region` = '" +session['region']+ "' and `Insula` = '" +session['insula']+ "' and `Doorway` = '" +session['property']+ rm+"';"

		pppCur.execute(pppQuery)
		data = pppCur.fetchall()
		pppCur.close()

		return render_template('PPP.html', dbdata = data, 
			region=session['region'], insula=session['insula'], property=session['property'], room=session['room'])

	else:
		error= "Sorry, this page is only accessible by logging in."
		return render_template('index.html', arc="", error=error)

#When items are changed via update form, update database
@app.route('/update-ppp', methods=['POST'])
def updatePPP():
	pppCur = mysql.connection.cursor()
	dictargs = request.form.to_dict()
	date = datetime.now().strftime("%Y-%m-%d")
	sep = dictargs['uuid'].split("_")
	for k, v in dictargs.items():
		pppQuery = "INSERT INTO PPP(`uuid`) SELECT * FROM ( SELECT '" + sep[1] + "' ) AS tmp WHERE NOT EXISTS ( SELECT 1 FROM PPP WHERE `uuid` = '" + sep[1] + "' ) LIMIT 1;"
		pppCur.execute(pppQuery)
		mysql.connection.commit()
		vrep = v.replace('\n', ' ').replace('\r', ' ').replace('\'', "\\'")
		if k == "PPPID":
			pppQueryA = "UPDATE PPP SET `id` = '" + vrep + "' WHERE `uuid` = '" + sep[1] + "';"
			pppCur.execute(pppQueryA)
		if k == "location":
			pppQueryB = "UPDATE PPP SET `location` = '" + vrep + "' WHERE `uuid` = '" + sep[1] + "';"
			pppCur.execute(pppQueryB)
		if k == "material":
			pppQueryC = "UPDATE PPP SET `material` = '" + vrep + "' WHERE `uuid` = '" + sep[1] + "';"
			pppCur.execute(pppQueryC)
		if k == "description":
			pppQueryD = "UPDATE PPP SET `description` = '" + vrep + "' WHERE `uuid` = '" + sep[1] + "';"
			pppCur.execute(pppQueryD)
		if k == "condition":
			pppQueryE = "UPDATE PPP SET `condition_ppp` = '" + vrep + "' WHERE `uuid` = '" + sep[1] + "';"
			pppCur.execute(pppQueryE)
		if k == "style":
			pppQueryF = "UPDATE PPP SET `style` = '" + vrep + "' WHERE `uuid` = '" + sep[1] + "';"
			pppCur.execute(pppQueryF)
		if k == "bibliography":
			pppQueryG = "UPDATE PPP SET `bibliography` = '" + vrep + "' WHERE `uuid` = '" + sep[1] + "';"
			pppCur.execute(pppQueryG)
		if k == "negative":
			pppQueryH = "UPDATE PPP SET `photo_negative` = '" + vrep + "' WHERE `uuid` = '" + sep[1] + "';"
			pppCur.execute(pppQueryH)
	mysql.connection.commit()
	pppCur.close()

	return redirect('/PPP#editModal')



if __name__ == "__main__":
	app.run()