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

#Roman numeral utility
def toRoman(data):
	romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
	romin = int(data) - 1
	if romin >= 0 and romin < len(romans):
		romreg = romans[romin]
	else:
		romreg = data
	return romreg

@app.route("/") # Home page
def index():

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
	return redirect('/PinP')

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
	

# When items are marked as reviewed, update database
@app.route('/ppm-reviewed') 
def ppmReviewed():
	strargs = request.args['data'].replace("[", "").replace("]", "")
	ppmCur = mysql.connection.cursor()
	ppmQuery = "UPDATE PPM SET reviewed=1 WHERE id in (" + strargs + ") ;"
	ppmCur.execute(ppmQuery)
	mysql.connection.commit()
	ppmCur.close()

	return redirect('/PPM')

@app.route('/update-ppm', methods=['POST'])
def updatePPM():
	ppmCur = mysql.connection.cursor()
	dictargs = request.form.to_dict()
	for k in dictargs:
		krem =  dictargs[k].replace('\n', ' ').replace('\r', ' ').replace('\'', "\\'")
		ppmQuery = "UPDATE PPM SET `description` = '" + krem + "' WHERE id = " + k + ";"
		print(ppmQuery)
		ppmCur.execute(ppmQuery)
	mysql.connection.commit()
	ppmCur.close()

	return redirect('/PPM')

@app.route('/PinP') #PinP page
def showPinP():
	if session.get('logged_in') and session["logged_in"]:

		pinp = reg = ins = prop = room = ""

		pinpCur = mysql.connection.cursor()

		#Join tbl_webpage_images and tbl_box_images on id
		pinpQuery = "SELECT `archive_id`, `id_box_file`, `img_alt`, `is_art`, `is_plaster`, `ARC`, `other_ARC`, `notes` FROM `PinP` WHERE `pinp_regio` LIKE %s and `pinp_insula` LIKE %s  and `pinp_entrance` LIKE %s ORDER BY `archive_id` "
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

		return render_template('PinP.html',
			catextpinp=pinp, dbdata = data, indices = indices,
			region=reg, insula=ins, property=prop, room=room)
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

@app.route('/carryover-button') #Carryover button found on multiple pages
def carryover_button():
	if (request.args.get('catextppm')):
		strargs = request.args['catextppm'].replace("[", "").replace("]", "")
		if (session.get('carryoverPPMids')):
			session['carryoverPPMids'] += strargs.split(",")
		else:
			session['carryoverPPMids'] = strargs.split(",")
		carryCur = mysql.connection.cursor()
		carryQuery = "SELECT description, reviewed FROM PPM WHERE id in (" + strargs + ") ;"
		carryCur.execute(carryQuery)
		dataList = carryCur.fetchall()
		carryCur.close()

		dataCopy = ""
		for d in dataList:
			if d[1] == 1:
				dataCopy += translate_client.translate(d[0], target_language="en", source_language="it")['translatedText'] + "; "

		if (session.get('carryoverPPM')):
			session['carryoverPPM'] += "; " + dataCopy
		else:
			session['carryoverPPM'] = dataCopy

	if (request.args.get('catextpinp')):
		pinpCur = mysql.connection.cursor()
		pinpQuery = 'UPDATE `PinP` SET `already_used` = 1 where `id_box_file` in (' + request.args['catextpinp'] +');'
		pinpCur.execute(pinpQuery)
		mysql.connection.commit()
		pinpCur.close()
		if (session.get('carryoverPinP')):
			session['carryoverPinP'] += "; " + request.args['catextpinp']
		else:
			session['carryoverPinP'] = request.args['catextpinp']

	if (request.args.get('catextppm')):
		return redirect("/PPM")

	if (request.args.get('catextpinp')):
		return redirect("/PinP")

	return redirect("/PinP")

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