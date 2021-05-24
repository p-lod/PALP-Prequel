"""
Flask web application created to help researchers for the PALP project classify images.

[Github repository](https://github.com/p-lod/PALP-Prequel)
"""
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
import requests


# === Setup and Authentication ===

# Using [Sentry](https://sentry.io/) to log and report errors
sentry_sdk.init(
    dsn="https://467f5f32371848da8c0ef7a3481afd04@o493026.ingest.sentry.io/5561397",
    integrations=[FlaskIntegration()],
    traces_sample_rate=1.0
)

# Set up Flask
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

# [Google Sheets](https://developers.google.com/sheets/api) credentials
tr_credentials = service_account.Credentials.from_service_account_file("My Project-1f2512d178cb.json")
scopes = ['https://www.googleapis.com/auth/spreadsheets']
scoped_gs = tr_credentials.with_scopes(scopes)
sheets_client = build('sheets', 'v4', credentials=scoped_gs)
tracking_ws = "1F4nXX1QoyV1miaRUop2ctm8snDyov6GNu9aLt9t3a3M"
ranges = "Workflow_Tracking!A3:L87078"
sheet = sheets_client.spreadsheets()
gsheet = sheet.values().get(spreadsheetId=tracking_ws, range=ranges, majorDimension="COLUMNS").execute()


#[Box API](https://developer.box.com/) configurations
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

# === Helper Function ===

# Roman numeral utility. Takes in integer Arabic number to be converted 
# (must be between 1 and 9) and turns it into a string of the Roman numeral.
def toRoman(data):
    romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"]
    romin = int(data) - 1
    if romin >= 0 and romin < len(romans):
        romreg = romans[romin]
    else:
        romreg = data
    return romreg

# === Forms ===

# Log-in form. Pulls credentials from user.cfg
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

# Form submitted from home page to select location
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
    
    building = "r" + str(session['region']) + "-i"+str(session['insula']) + "-p" + session['property'] + "-space-" + session['room']
    values = gsheet.get('values', [])
    locationlist = values[1]
    arclist = values[7]

    # Find valid ARCs for data validation
    session['validARCs'] = []
    for l in range(len(locationlist)):
        if locationlist[l].startswith(building):
            session['validARCs'].append(arclist[l])
    session['invcheckedARCs'] = []
    return redirect('/PPM')

# Location search bar at top of pages
@app.route('/search', methods=['POST'])
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
    
# === User Pages ===

# Custom server error handler
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# Home page, displays either login form or location choice form
@app.route("/")
def index():
    return render_template('index.html')

# Show PPM images to be classified
@app.route('/PPM')
def showPPM():

    if session.get('logged_in') and session["logged_in"]:
        base_url = "http://umassamherst.lunaimaging.com/luna/servlet/as/search?"

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
            ppm2Query = "SELECT `is_art`, `is_plaster`, `ARC`, `other_ARC`, `notes`, `hero_image`, `need_help` FROM PPM_preq WHERE id = %s;"
            ppm2Cur.execute(ppm2Query, [d[0]])
            toin = []
            for l in d:
                toin.append(l)
            fetched = ppm2Cur.fetchall()
            if len(fetched) > 0:
                for j in fetched[0]:
                    toin.append(j)
            data.append(toin)

        ### START BOX - to be replaced
        imgs = []
        for d in data:
            itemid = "0"
            searchid = "\"" + d[2] + "\""
            box_id = box_client.search().query(query=searchid, file_extensions=['jpg'], ancestor_folder_ids="97077887697,87326350215", fields=["id", "name"], content_types=["name"])
            for item in box_id:
                if item.name == d[2]:
                    itemid = item.id
                    break
            imgs.append(itemid)
            filename = str(itemid) + ".jpg"
            # Download thumbnail from Box into temporary images folder (emptied once a week)
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
        ### END BOX
        # for d in data:
        #     toin = []
        #     params = ["q=filename=image"+str(d[0]) + ".jpg", "lc=umass~14~14"]
        #     request = requests.get(base_url+"&".join(params))
        #     result = request.json()
        #     if len(result['results']) > 0:
        #         toin.append(result['results'][0]['urlSize1'])
        #         toin.append(result['results'][0]['id'])
        #     else:
        #         toin.append("")
        #         toin.append("")
        #     d.insert(8, toin)
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

# Show PinP images to be classified
@app.route('/PinP')
def showPinP():
    if session.get('logged_in') and session["logged_in"]:

        base_url = "http://umassamherst.lunaimaging.com/luna/servlet/as/search?"
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
        pinpCur.close()

        pinp2Cur = mysql.connection.cursor()
        data = []
        indices = []
        for d in dataTuple:
            pinp2Query = "SELECT `is_art`, `is_plaster`, `ARC`, `other_ARC`, `notes`, `hero_image`, `need_help` FROM PinP_preq WHERE `archive_id` = %s;"
            pinp2Cur.execute(pinp2Query, [d[0]])
            toin = []
            for l in d:
                toin.append(l)
            fetched = pinp2Cur.fetchall()
            if len(fetched) > 0:
                for j in fetched[0]:
                    toin.append(j)
            indices.append(d[1])
            filename = str(d[1]) + ".jpg"
            params = ["q=filename=image"+str(d[0]) + ".jpg", "lc=umass~14~14"]
            request = requests.get(base_url+"&".join(params))
            result = request.json()
            if len(result['results']) > 0:
                toin.append(result['results'][0]['urlSize1'])
                toin.append(result['results'][0]['id'])
            else:
                toin.append("")
                toin.append("")
            data.append(toin)
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

# Display images marked as needing help and further review
@app.route('/needs_help')
def needs_help():
    if session.get('logged_in') and session["logged_in"]:

        romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", ""]

        pinpCur = mysql.connection.cursor()
        pinpQuery = "SELECT `archive_id`, `notes`, `need_help` FROM PinP_preq WHERE `need_help` = 1 or LENGTH(`notes`) > 2;"
        pinpCur.execute(pinpQuery)
        dataTuple = pinpCur.fetchall()
        pinpCur.close()

        datapinp = []
        for d in dataTuple:
            pinp2Cur = mysql.connection.cursor()
            pinp2Query = "SELECT DISTINCT `pinp_regio`, `pinp_insula`, `pinp_entrance` FROM `PinP` WHERE `archive_id` = '"+ str(d[0])+"';"
            pinp2Cur.execute(pinp2Query)
            fetched = pinp2Cur.fetchall()
            toin = []
            for l in d:
                toin.append(l)
            if len(fetched) > 0:
                for f in fetched[0]:
                    toin.append(str(f))
            else:
                toin.extend(['', '', ''])
            toin.append(romans.index(toin[3])+1)
            toin.append("PinP")
            datapinp.append(toin)
            pinp2Cur.close()

        ppmCur = mysql.connection.cursor()
        ppmQuery = "SELECT `id`, `notes`, `need_help` FROM PPM_preq WHERE `need_help` = 1 or LENGTH(`notes`) > 2;"
        ppmCur.execute(ppmQuery)
        dataTuple2 = ppmCur.fetchall()
        ppmCur.close()

        for x in dataTuple2:
            ppm2Cur = mysql.connection.cursor()
            ppm2Query = "SELECT DISTINCT `region`, `insula`, `doorway` FROM `PPM` WHERE `id` = '"+ str(x[0])+"';"
            print(ppm2Query)
            ppm2Cur.execute(ppm2Query)
            fetched = ppm2Cur.fetchall()
            toin = []
            for l in x:
                toin.append(l)
            if len(fetched) > 0:
                for f in fetched[0]:
                    toin.append(str(f))
            else:
                toin.extend(['', '', ''])
            toin.append(romans.index(toin[3])+1)
            toin.append("PPM")
            datapinp.append(toin)
            ppm2Cur.close()

        sorted_list = sorted(datapinp, key=lambda x: x[5])
        sorted_list2 = sorted(sorted_list, key=lambda x: x[4])
        dbdata = sorted(sorted_list2, key=lambda x: x[6])
        dbdata = sorted(dbdata, key=lambda x: x[2], reverse=True)

        return render_template('needs_help.html', dbdata=dbdata)
    else:
        flash("Sorry, this page is only accessible by logging in.")
        return render_template('index.html')

# Help page
@app.route('/help')
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

# === Save to Database ===
@app.route('/save-button', methods=["POST", "GET"])
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
                        # Check if ARC submitted is in the list of ARCs for the building, flash error if not.
                        # Also, keep list of invalid ARCs that have already been checked so there aren't repeated messages.
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
                        # Check that notes field is clean (no double quotes)
                        try:
                            pinpCur.execute(pinpQuery)
                        except Exception:
                            flash('Please resubmit without double quotes (")')
                    elif ksplit[1] == "help":
                        pinpQuery = 'INSERT INTO `PinP_preq` (archive_id, need_help, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '","'+ date +'") ON DUPLICATE KEY UPDATE `need_help` = "'+ str(v) + '", `date_added` = "' + date +'";'
                        pinpCur.execute(pinpQuery)
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
                        # Check if ARC submitted is in the list of ARCs for the building, flash error if not.
                        # Also, keep list of invalid ARCs that have already been checked so there aren't repeated messages.
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
                        # Check that notes field is clean (no double quotes)
                        try:
                            ppmCur.execute(ppmQuery)
                        except Exception:
                            flash('Please resubmit without double quotes (")')
                    elif ksplit[1] == "help":
                        ppmQuery = 'INSERT INTO `PPM_preq` (id, need_help, date_added) VALUES ('+ ksplit[0] +',"'+ str(v) + '","'+ date +'") ON DUPLICATE KEY UPDATE `need_help` = "'+ str(v) + '", `date_added` = "' + date +'";'
                        ppmCur.execute(ppmQuery)
        mysql.connection.commit()
        ppmCur.close()
    return make_response(jsonify(get_flashed_messages()), 201)

# Run Flask app
if __name__ == "__main__":
    app.run()