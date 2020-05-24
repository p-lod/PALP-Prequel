﻿# PALP Workspace

PALP Workspace is a Flask web application that was created to help researchers for the PALP project connect different sources of data to each other. It links  [Pompei: pitture e mosaici](https://www.worldcat.org/title/pompei-pitture-e-mosaici/oclc/28254535),  [Pitture e pavimenti di Pompei](https://www.worldcat.org/title/pitture-e-pavimenti-di-pompei/oclc/490575255),  [PompeiiinPictures](https://pompeiiinpictures.com/pompeiiinpictures/index.htm), and [an ArcGIS Map](https://arcg.is/ivHP0). The workspace is currently hosted at [https://workspace.p-lod.umasscreate.net/](https://workspace.p-lod.umasscreate.net/).

## User Workflow

Users start by entering an ARC number, which queries the various databases based on location data. Each successive tab walks them through steps like validating OCR data, copying relevant descriptions, and choosing relevant pictures. The Description and Saved Data tabs are where that all comes together for them to save this linked data and use it to populate a Google Sheet with more detailed information.

## Integrations

-   [Box API](https://developer.box.com/)
-   [Google Sheets API](https://developers.google.com/sheets/api)
-   [Google Cloud Translation](https://cloud.google.com/translate/docs)

## Installation

-   Clone or download [GitHub repository](https://github.com/alexroseb/PALP-Workspace)
-   `pip install -r requirements.txt`
-   Add relevant configuration files
-  Add empty images/ directory within static/

### Configuration Files
- mysql.cfg
	- MYSQL username, password, database, and host; each separated by newline
- user.cfg
	- site username and password, separated by newline
- My Project-1f2512d178cb.json
	- Generated by Google API - just rename file
- box_config.json
	- Generated by Box API - just rename file

## File Structure
- templates/ - HTML files that take in Flask output and display the site
- app.py - main Flask Python file
- static/css/style.css - Basic styling
