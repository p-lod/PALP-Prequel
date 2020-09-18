from __future__ import print_function
from flask import Flask, render_template, session, json, request, redirect, flash
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

#Google Translate credentials
tr_credentials = service_account.Credentials.from_service_account_file("My Project-1f2512d178cb.json")

#Google Sheets credentials
scopes = ['https://www.googleapis.com/auth/spreadsheets']
scoped_gs = tr_credentials.with_scopes(scopes)
sheets_client = build('sheets', 'v4', credentials=scoped_gs)

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

workflow_tracker_id = "1EdnoFWDpd38sznIrqMplmFwDMHlN7UATGEEIUsxpZdU"

#Roman numeral utility
def toRoman(data):
	romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
	romin = int(data) - 1
	if romin >= 0 and romin < len(romans):
		romreg = romans[romin]
	else:
		romreg = data
	return romreg

def toWorkspaceSheet():
	cur = mysql.connection.cursor()
	PPMQuery = "SELECT `ARC`, `is_art`, `is_plaster`,`other_ARC`, `notes` FROM `PPM`"
	cur.execute(PPMQuery)

	PinPQuery = "SELECT `ARC`, `is_art`, `is_plaster`, `other_ARC`, `notes` FROM `PinP`"
	cur.execute(PinPQuery)
	data = cur.fetchall()
	cur.close()

	arclist = {}
	dataNotTuple = []
	for d in data:
		if d[0] != "":
			arclist[d[0]] = {"art": "", "plaster": "", "other_notes": ""}
			dataNotTuple.append([d[0], d[1], d[2], d[3], d[4]])
	for x in dataNotTuple:
		if "art" in arclist[x[0]]:
			if arclist[x[0]]["art"] != "yes":
				arclist[x[0]]["art"] = x[1]
		else:
			arclist[x[0]]["art"] = x[1]

		if "plaster" in arclist[x[0]]:
			if arclist[x[0]]["plaster"] != "yes":
				arclist[x[0]]["plaster"] = x[2]
		else:
			arclist[x[0]]["plaster"] = x[2]
		arclist[x[0]]["other_notes"] += ", " + x[4]
	print(arclist)

	sheet = sheets_client.spreadsheets()
	ranges = "Workflow_Tracking!A1:V87077"
	gsheet = sheet.values().get(spreadsheetId=workflow_tracker_id, range="Workflow_Tracking!A1:V87077").execute()
	values = gsheet.get('values', [])
	toupdate = {}
	for gindex in range(len(values)):
		g = values[gindex]
		if g[6] in arclist:
			print(g[6])
			print(arclist[g[6]])
			print(g)
			g[11] = arclist[g[6]]["art"]
			g[12] = arclist[g[6]]["plaster"]
			g[16] = arclist[g[6]]["other_notes"]
			toupdate[gindex] = g
	for k in toupdate:
		rangenum = "Workflow_Tracking!H"+str(k) + ":V" + str(k)
		print(rangenum)
		valuerangebody = {"range": rangenum, "majorDimension": "ROWS", "values": [toupdate[k][7:]]}
		updaterequest = sheet.values().update(spreadsheetId=workflow_tracker_id, range=rangenum, body=valuerangebody, valueInputOption="RAW").execute()

@app.route("/") # Home page
def index():
	#data = toWorkspaceSheet()
	return render_template('index.html', error="")

@app.route("/login", methods=['POST']) # Login form
def login():
	error = ""
	with open('user.cfg', 'r') as user_cfg:
		user_lines = user_cfg.read().splitlines()
		username = user_lines[0]
		password = user_lines[1]
	if request.form['password'] == password and request.form['username'] == username:
		session['logged_in'] = True
	else:
		error = 'Sorry, wrong password!'
	return render_template('index.html', error=error)

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
	return redirect('/PPM')

@app.route('/PPM') #PPM page
def showPPM():

	if session.get('logged_in') and session["logged_in"]:

		#PPM data has individual location columns
		ppmCur = mysql.connection.cursor()
		ppmQuery = "SELECT id, description, image_path, region, insula, doorway, room, translated_text, `is_art`, `is_plaster`, `ARC`, `other_ARC`, `notes` FROM PPM WHERE region LIKE %s AND insula LIKE %s AND doorway LIKE %s AND room LIKE %s ORDER BY `description` ASC;"
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
		data = []

		indices = []
		for d in dataTuple:
			indices.append(d[0])
			toin = []
			for l in d:
				toin.append(l)
			data.append(toin)

		imgs = []
		for d in data:
			itemid = "0"
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
			data[x].append(imgs[x])
		 	
		# 	imgQuery = "UPDATE PPM SET image_id= %s WHERE id = %s ;"
		# 	ppmCur.execute(imgQuery, [imgs[x], j[0]])
		# 	mysql.connection.commit()
		
		ppmCur.close()

		ppm = ppmimg = reg = ins = prop = room = iframeurl = ""

		#each region (theoretically) has its own PDF doc
		if (session.get('region')):
			reg = session['region']
			if session['region'] == "1":
				iframeurl = ""
			if session['region'] == "2":
				iframeurl = ""
			if session['region'] == "3":
				iframeurl = ""
			if session['region'] == "4":
				iframeurl = ""
			if session['region'] == "5":
				iframeurl = ""
			if session['region'] == "6":
				iframeurl = ""
			if session['region'] == "7":
				iframeurl = ""
			if session['region'] == "8":
				iframeurl = ""
			if session['region'] == "9":
				iframeurl = ""
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
			region=reg, insula=ins, property=prop, room=room, iframeurl = iframeurl)
	else:
		error= "Sorry, this page is only accessible by logging in."
		return render_template('index.html', error=error)

@app.route('/PinP') #PinP page
def showPinP():
	if session.get('logged_in') and session["logged_in"]:

		pinp = reg = ins = prop = room = ""

		pinpCur = mysql.connection.cursor()

		#Join tbl_webpage_images and tbl_box_images on id
		pinpQuery = "SELECT DISTINCT `archive_id`, `id_box_file`, `img_alt`, `is_art`, `is_plaster`, `ARC`, `other_ARC`, `notes` FROM `PinP` WHERE `pinp_regio` LIKE %s and `pinp_insula` LIKE %s  and `pinp_entrance` LIKE %s ORDER BY `archive_id` "
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

		data = pinpCur.fetchall()
		pinpCur.close()

		indices = []
		for d in data:
			indices.append(d[1])
			filename = str(d[1]) + ".jpg"
			if not os.path.exists("static/images/"+filename):
				try:
					thumbnail = box_client.file(d[1]).get_thumbnail(extension='jpg', min_width=200)
				except boxsdk.BoxAPIException as exception:
					thumbnail = exception.message
				with open(os.path.join("static/images",filename), "wb") as f:
					f.write(thumbnail)

		if (session.get('region')):
			reg = session['region']
		if (session.get('insula')):
			ins = session['insula']
		if (session.get('property')):
			prop = session['property']
		if (session.get('room')):
			room = session['room']

		ex = ""
		if session.get('ex'):
			ex = session['ex']

		return render_template('PinP.html',
			catextpinp=pinp, dbdata = data, indices = indices,
			region=reg, insula=ins, property=prop, room=room, ex=ex)
	else:
		error= "Sorry, this page is only accessible by logging in."
		return render_template('index.html', error=error)
	
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
	if (request.form.get('savepinp')):
		pinpCur = mysql.connection.cursor()
		for k, v in request.form.items():
			if v != "":
				ksplit = k.split("-")
				if len(ksplit) > 1:
					if ksplit[1] == "art":
						pinpQuery = 'UPDATE `PinP` SET `is_art` = "'+ str(v) + '" where `id_box_file` = ' + ksplit[0] +';'
						pinpCur.execute(pinpQuery)
					elif ksplit[1] == "plaster":
						pinpQuery = 'UPDATE `PinP` SET `is_plaster` = "'+ str(v) + '" where `id_box_file` = ' + ksplit[0] +';'
						pinpCur.execute(pinpQuery)
					elif ksplit[1] == "ARC":
						pinpQuery = 'UPDATE `PinP` SET `ARC` = "'+ str(v) + '" where `id_box_file` = ' + ksplit[0] +';'
						pinpCur.execute(pinpQuery)
					elif ksplit[1] == "others":
						pinpQuery = 'UPDATE `PinP` SET `other_ARC` = "'+ str(v) + '" where `id_box_file` = ' + ksplit[0] +';'
						pinpCur.execute(pinpQuery)
					elif ksplit[1] == "notes":
						pinpQuery = 'UPDATE `PinP` SET `notes` = "'+ str(v) + '" where `id_box_file` = ' + ksplit[0] +';'
						pinpCur.execute(pinpQuery)
		mysql.connection.commit()
		pinpCur.close()
	if (request.form.get('saveppm')):
		ppmCur = mysql.connection.cursor()
		for k, v in request.form.items():
			if v != "":
				ksplit = k.split("-")
				if len(ksplit) > 1:
					if ksplit[1] == "art":
						ppmQuery = 'UPDATE `PPM` SET `is_art` = "'+ str(v) + '" where `id` = ' + ksplit[0] +';'
						ppmCur.execute(ppmQuery)
					elif ksplit[1] == "plaster":
						ppmQuery = 'UPDATE `PPM` SET `is_plaster` = "'+ str(v) + '" where `id` = ' + ksplit[0] +';'
						ppmCur.execute(ppmQuery)
					elif ksplit[1] == "ARC":
						ppmQuery = 'UPDATE `PPM` SET `ARC` = "'+ str(v) + '" where `id` = ' + ksplit[0] +';'
						ppmCur.execute(ppmQuery)
					elif ksplit[1] == "others":
						ppmQuery = 'UPDATE `PPM` SET `other_ARC` = "'+ str(v) + '" where `id` = ' + ksplit[0] +';'
						ppmCur.execute(ppmQuery)
					elif ksplit[1] == "notes":
						ppmQuery = 'UPDATE `PPM` SET `notes` = "'+ str(v) + '" where `id` = ' + ksplit[0] +';'
						ppmCur.execute(ppmQuery)
		mysql.connection.commit()
		ppmCur.close()

	return redirect(request.referrer)

@app.route('/cleardata') #Start over, redirects to home page
def clearData():
	session['carryoverPPM'] = ""
	session['carryoverPPMImgs'] = []
	session['carryoverPinP'] = ""
	session['carryoverPPMids'] = []
	session['carryoverPPMImgsids'] = []

	session['region'] = ""
	session['insula'] = ""
	session['property'] = ""
	session['room'] = ""

	session['gdoc'] = ""

	files = glob.glob('static/images/*')
	for f in files:
		try:
			os.remove(f)
		except OSError as e:
			print("Error: %s : %s" % (f, e.strerror))

	return render_template('index.html')

@app.route('/savedata') #Copy saved data to Google Sheets
def saveData():

	if session.get('logged_in') and session["logged_in"]:

		now = datetime.now()
		timestamp = now.strftime("%m/%d/%Y, %H:%M:%S")
		queryvars = [timestamp]
		if (session.get('region')):
			queryvars.append(str(session['region']))
		else:
			queryvars.append("")
		if (session.get('insula')):
			queryvars.append(str(session['insula']))
		else:
			queryvars.append("")
		if (session.get('property')):
			queryvars.append(str(session['property']))
		else:
			queryvars.append("")
		if (session.get('room')):
			queryvars.append(str(session['room']))
		else:
			queryvars.append("")

		if (session.get('carryoverPPMids')):
			queryvars.append(",".join(session['carryoverPPMids']))
		else:
			queryvars.append("")

		if (session.get('carryoverPPM')):
			queryvars.append(str(session['carryoverPPM']))
		else:
			queryvars.append("")


		if (session.get('carryoverPPMImgs')):
			queryvars.append(",".join(session['carryoverPPMImgs']))
		else:
			queryvars.append("")
		if (session.get('carryoverPinP')):
			queryvars.append(str(session['carryoverPinP']))
		else:
			queryvars.append("")

		values = [queryvars]
		print(values)
		body = {
		    'values': values
		}

		result = sheets_client.spreadsheets().values().append(spreadsheetId="1HaKXGdS-ZS42HiK8d1KeeSdC199MdxyP42QqsUlzZBQ",range="Sheet1", valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS", body=body).execute()

		return redirect(request.referrer)
	else:
		error= "Sorry, this page is only accessible by logging in."
		return render_template('index.html', error=error)

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


if __name__ == "__main__":
	app.run()