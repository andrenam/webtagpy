Web-based audio tag editor
==========

- Edit audio tags using a webinterface
- Inspired by puddletag
- Driven by python and angular.js

Requirements:
-------------

- python
	- mutagen
	- flask
	- requests
	- python-magic
	- python-Levenshtein

![screenshot](http://i.imgur.com/ZsNOPj5.png?1)

Installation:
-------------
 - Clone the repository:
 
	``git clone http://....``
	
 - Go to the cloned repository:
 
	``cd ...``
	
 - Install python requirements:
 
	``pip install -r requirements.txt``
	
 - Install angularjs components using bower:

	``bower install``

 - Edit webtagpy.cfg config file


Start:
-----------
 - Test the app using the built-in webserver:

	``./api.py``

Deployment using wsgi:
-----------

There are many ways to deploy the app. Here's a sample configuration using uwsgi behind nginx as reverse-proxy:

uwsgi config 


	[uwsgi]
	
	http = 127.0.0.1:5010
	plugins = python2
	chdir = /path/to/tageditor
	wsgi-file = /path/to/tageditor/api.py
	callable = app
	uid = username
	gid = groupname
	master = true
	processes = 2
	threads = 1

nginx config 

    location /tageditor/ {
        proxy_pass http://127.0.0.1:5010;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /tageditor;
    }

