#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import sys, os, os.path
import ConfigParser
import logging
from flask import Flask, send_file, Response, request, json, jsonify
from reverseproxy import ReverseProxied
import mutagen
import base64
import StringIO, magic
import hashlib
import requests
import Levenshtein
import shutil

app = Flask(__name__, static_folder='', static_url_path='')
app.wsgi_app = ReverseProxied(app.wsgi_app)

# try to load config
try:
	config = ConfigParser.ConfigParser()
	config.read(['webtagpy.cfg', os.path.join(os.path.dirname(os.path.abspath(__file__)) , 'webtagpy.cfg'), '/etc/webtagpy.cfg' ])
except Exception as e:
	print >>sys.stderr, "Error while parsing the configuration file(s):\n%s" % str(e)

if config:
	try:
		loggerFileName = config.get('base', 'log_file')
	except:
		loggerFileName = None
else:
	loggerFileName = None	

if loggerFileName:
	logging.basicConfig(
		format='%(asctime)s:%(name)s:%(levelname)s:%(message)s',
		filename=loggerFileName,
		level=logging.WARNING)
else:
	logging.basicConfig(
		format='%(asctime)s:%(name)s:%(levelname)s:%(message)s',
		level=logging.WARNING)
	

logger = logging.getLogger(__name__)

def encodeId(path):
	return base64.b64encode(path)

def decodeId(id):
	return base64.b64decode(id)
	
def readFolders(folder_path):
	folders = []
	try:
		root, ds, fs = next(os.walk(folder_path))
		for d in ds:
			p = os.path.join(root,d)
			subfolders = readFolders(p)
			if not d.startswith('.'):
				folders.append({'folder_id': encodeId(p),
							'folder_path': p,
							'folder_name': d,
							'folders': subfolders})
	except:
		logger.exception("Exception in readFolders():")
	
	return folders

def tagsToDict(tags):
	d = {}
	for k in tags.keys():
		v = tags[k]
		d[k] = v[0]
	
	# enforce the existance of basic tags
	forcedTags = [ 'artist', 'title', 'album', 'date', 'genre', 'tracknumber' ]
	for forcedTag in forcedTags:
		if not forcedTag in d:
			d[forcedTag] = ''
	
	return d

def readCoverArt(file_path):
	try:
		tags = mutagen.File(file_path, easy=False)
		keys = [key for key in tags.keys() if 'APIC' in key and tags[key].type == 3]
		if len(keys) == 1:
			coverart = tags[keys[0]].data
			md5sum = hashlib.md5(coverart).hexdigest()
			return {
				'embedded': True,
				'coverart': coverart,
				'md5sum': md5sum,
			}
		try:
			if tags.pictures and len(tags.pictures) > 0:
				coverart = tags.pictures[0].data
				md5sum = hashlib.md5(coverart).hexdigest()
				return {
					'embedded': True,
					'coverart': coverart,
					'md5sum': md5sum,
				}
		except:
			pass
			#logger.exception("Exception in readCoverArt():")
		
		folder_path = os.path.dirname(file_path)
		for cover_file in ['folder.jpg', 'Folder.jpg', 'folder.png', 'Folder.png', 'cover.jpg', 'Cover.jpg', 'cover.png', 'Cover.png']:
			coverart = os.path.join(folder_path, cover_file)
			if os.path.exists(coverart):
				md5 = hashlib.md5()
				with open(coverart, 'rb') as f:
					for chunk in iter(lambda: f.read(8192), b''):
						md5.update(chunk)
				md5sum = md5.hexdigest()
					
				return {
					'embedded': False,
					'coverart': coverart,
					'md5sum': md5sum,
				}
	except:
		logger.exception("Exception in readCoverArt():")
		raise
	
	return None
	
def getTags(file_path):
	tagsDict = {}
	try:
		tagsEasy = mutagen.File(file_path, easy=True)
		tagsDict = tagsToDict(tagsEasy)
		tagsDict["has_embedded_cover_art"] = False
		
		# detect embedded cover art
		tags = mutagen.File(file_path, easy=False)
		# mp3 pictures
		keys = [key for key in tags.keys() if 'APIC' in key and tags[key].type == 3]
		if len(keys) == 1:
			tagsDict["has_embedded_cover_art"] = True
		# flac pictures
		try:
			if tags.pictures and len(tags.pictures) > 0:
				tagsDict["has_embedded_cover_art"] = True
		except:
			pass
			#logger.exception("Exception in getTags():")
				
	except:
		logger.exception("Exception in getTags():")
	
	return tagsDict

# supports mp3 and flac
def embedCoverArt(file_path, imageData):
	bname, ext = os.path.splitext(file_path)
	
	logger.debug('embedCoverArt for file %s' % file_path)
	
	if ext == '.mp3':
		tags = mutagen.File(file_path, easy=False)
		
		# delete previous cover images
		keys = [tag for tag in tags.keys() if 'APIC' in tag and tags[tag].type == 3]
		for key in keys:
			del tags[key]
		
		# save cover image to file
		mime = magic.from_buffer(imageData, mime=True)
		img = mutagen.id3.APIC(encoding=3, mime=mime, type=3, desc='', data=imageData)
		tags.tags.add(img)
		tags.save()
		logger.debug('coverArt for file %s saved' % file_path)
		
		
	elif ext == '.flac':
		tags = mutagen.File(file_path, easy=False)
		
		# delete previous cover images
		tags.clear_pictures()
		
		# save cover image to file
		mime = magic.from_buffer(imageData, mime=True)
		img = mutagen.flac.Picture()
		img.mime = mime
		img.type = 3
		img.desc = u''
		img.data = imageData
		tags.add_picture(img)
		
		# save and exit
		tags.save()
		logger.debug('coverArt for file %s saved' % file_path)
		
		
		
# supports mp3 and flac
def exportCoverArt(folder_path, imageData):
	ext = None
	mime = magic.from_buffer(imageData, mime=True)
	if mime == "image/png":
		ext = ".png"
	elif mime == "image/jpg" or mime == "image/jpeg":
		ext = ".jpg"
	
	if ext:
		for cover_file in ['folder', 'Folder', 'cover', 'Cover']:
			file_path = os.path.join(folder_path, "%s%s" % (cover_file, ext))
			if not os.path.exists(file_path):
				logger.info("Export coverArt to '%s'" % file_path)
				with open(file_path, 'wb') as f:
					f.write(imageData)
					f.close()


def send_image(imgdata):
    imgIo = StringIO.StringIO()
    imgIo.write(imgdata)
    imgIo.seek(0)
    mime = magic.from_buffer(imgIo.read(1024), mime=True)
    imgIo.seek(0)
    return send_file(imgIo, mimetype=mime, cache_timeout=0)



@app.route('/')
def root():
	return app.send_static_file('index.html')

@app.route('/api/coverart/search/<artist>/<album>')
def apiCoverArtSearch(artist, album):
	try:
		api_key = "a42ead6d2dcc2938bec2cda08a03b519"
		api_url = "http://ws.audioscrobbler.com/2.0/?method=album.search&album=%(album)s&api_key=%(api_key)s&format=json" % { 'album': album, 'api_key': api_key }
		r = requests.get(api_url)
		results = r.json()
		albumlist = results["results"]["albummatches"]["album"]
		if isinstance(albumlist, dict):
			albumlist = [ albumlist ]
		
		# exact match
		for result in albumlist:
			if artist.lower() == result["artist"].lower():
				logger.debug("Found exact artist in apiCoverArtSearch '%s'" % result["artist"].lower())
				for image in result["image"]:
					if image["size"] == "extralarge":
						return jsonify(**{ 'coverarturl': image["#text"] })
		
		# fuzzy matches using Levenshtein
		maxRatio = 0.0
		bestMatch = None
		for result in albumlist:
			ratio = Levenshtein.ratio(artist.lower(), result["artist"].lower())
			if ratio > maxRatio:
				maxRatio = ratio
				for image in result["image"]:
					if image["size"] == "extralarge":
						bestMatch = image
		if bestMatch:
			logger.debug("Found fuzzy match artist in apiCoverArtSearch")
			return jsonify(**{ 'coverarturl': image["#text"] })

	except:
		logger.exception("exception in apiCoverArtSearch('%s', '%s'):" % (artist, album))
				
	return "", 404


@app.route('/api/coverart/info/<file_id>')
def apiCoverArtInfo(file_id):
	file_path = decodeId(file_id)
	if not file_path or not os.path.exists(file_path) or not os.path.isfile(file_path):
		logger.warning("apiCoverArtInfo('%s'): file '%s' does not exist" % (file_id, file_path))
		return '', 404
	
	cover = readCoverArt(file_path)
	if cover:
		return jsonify(**{'embedded' : cover['embedded'], 'md5sum': cover['md5sum']})
	else:
		logger.warning("apiCoverArtInfo('%s'): no cover art found for file '%s'" % (file_id, file_path))
		return jsonify(**{'error': 'no cover art found'}), 404	

@app.route('/api/coverart/<file_id>')
def apiCoverArt(file_id):
	file_path = decodeId(file_id)
	if not file_path or not os.path.exists(file_path) or not os.path.isfile(file_path):
		logger.warning("apiCoverArt('%s'): file '%s' does not exist" % (file_id, file_path))
		return '', 404
	
	cover = readCoverArt(file_path)
	if cover:
		if cover['embedded']:
			return send_image(cover['coverart'])
		else:
			return send_file(cover['coverart'])
	else:
		logger.warning("apiCoverArt('%s'): no cover art found for file '%s'" % (file_id, file_path))
		return jsonify(**{'error': 'no cover art found'}), 404	



		
@app.route('/api/folder/', defaults={'folder_id': None})
@app.route('/api/folder/<folder_id>')
def apiFolder(folder_id):
	if folder_id:
		folder_path = decodeId(folder_id)
	else:
		folder_path = '/'
		folder_id = encodeId(folder_path)
	if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
		logger.warning("apiFolder('%s'): folder '%s' does not exist" % (folder_id, folder_path))
		return '', 404


	# get list of sub-folders and files in this directory
	files = []
	parent = os.path.abspath(os.path.dirname(folder_path))
	folders = [ {'folder_id': encodeId(parent),
				'folder_path': parent,
				'folder_name': '..',
				'folders': []} ]
	folders = folders + readFolders(folder_path)
	root, ds, fs = next(os.walk(folder_path))
	for f in fs:
		p = os.path.join(root,f)
		if f.endswith(('.mp3','.flac')):
			files.append({'file_id': encodeId(p),
						  'file_path': p,
						  'file_name': f,
			})
	
	folders = sorted(folders)
	files = sorted(files)
			
	return jsonify(**{'folder_id': folder_id,
			'folder_path': folder_path,
			'folder_name': os.path.basename(folder_path),
			'folders': folders,
			'files': files}), 200
			
			
@app.route('/api/files/<folder_id>', methods=['GET'])
def apiFiles(folder_id):
	if folder_id:
		folder_path = decodeId(folder_id)
	else:
		folder_path = None
		folder_id = None
	if not folder_path or not os.path.exists(folder_path) or not os.path.isdir(folder_path):
		logger.warning("apiFiles('%s'): folder '%s' does not exist" % (folder_id, folder_path))
		return '', 404
	

	# get list of files in this directory
	files = []
	root, ds, fs = next(os.walk(folder_path))
	for f in fs:
		p = os.path.join(root,f)
		if f.endswith(('.mp3','.flac')):
			try:
				tagsDict = getTags(p)
				cover = readCoverArt(p)
				if cover: 
					tagsDict['cover'] = {
						'embedded': cover['embedded'],
						'md5sum': cover['md5sum'],
					}
				else:
					tagsDict['cover'] = None
				files.append({'file_id': encodeId(p),
							  'file_path': p,
							  'file_name': f,
							  'tags': tagsDict,
				})
			except:
				raise
	
	#files = sorted(files)
	return Response(json.dumps(files),  mimetype='application/json')
			


@app.route('/api/files/', methods=['PUT'])
def apiPutFile():
	data = request.get_json(silent=True)
	if not data:
		data = request.form
	
	# get list of file_ids
	file_ids = data["file_ids"] if "file_ids" in data else None
	if isinstance(file_ids, basestring):
		file_ids = json.loads(file_ids)
	
	# get tag data
	tags = data["tags"] if "tags" in data else None
	if isinstance(tags, basestring):
		tags = json.loads(tags)
		
	# not enough data
	if not file_ids or not tags:
		logger.error("apiPutFile(): no file_ids input")
		return "", 500
	
	# supported tags
	supportedTags = [ 'artist', 'title', 'album', 'date', 'genre', 'tracknumber' ]
	
	# validate inputs
	inputData = {}
	for supportedTag in supportedTags:
		inputData[supportedTag] = tags[supportedTag] if supportedTag in tags else None
	
	# validate file input
	fileUpload = None
	imageData = None
	if request.files and 'file' in request.files:
		if request.files['file']:
			fileUpload = request.files['file']
			bname, ext = os.path.splitext(fileUpload.filename)
			if not ext in ['.jpg', '.jpeg', '.png']:
				fileUpload = None
			else:
				imageData = fileUpload.read()
				logger.debug("apiPutFile(): cover art uploaded")
	
	# validate coverArtSearchResult
	coverArtSearchResult = None
	if data["coverArtSearchResult"]:
		logger.debug("apiPutFile(): going to fetch cover art via last.fm")
		r = requests.get(data["coverArtSearchResult"], stream=True)
		coverArtSearchResult = r.raw.data
		logger.debug("apiPutFile(): cover art fetched via last.fm")
	

	# save to files
	for file_id in file_ids:
		file_path = decodeId(file_id)
		if not os.path.exists(file_path):
			continue
		
		tagsEasy = mutagen.File(file_path, easy=True)
		for supportedTag in supportedTags:
			v = inputData[supportedTag]
			if v and v != "<keep>" and v != "<delete>":
				tagsEasy[supportedTag] = v
			elif v == "<delete>":
				del tagsEasy[supportedTag]
				logger.debug("apiPutFile(): deleting tag '%s' on file '%s'" % (supportedTag, file_path))
		tagsEasy.save()
		logger.debug("apiPutFile(): saving tags on file '%s'" % (file_path))
		
		# save uploaded file as cover art
		if fileUpload:
			embedCoverArt(file_path, imageData)
		
		# save cover image from url
		elif coverArtSearchResult:
			embedCoverArt(file_path, coverArtSearchResult)
	
	# export coverArt
	if "coverexport" in tags and tags["coverexport"]:
		folder_paths = list(set([ os.path.dirname(decodeId(file_id)) for file_id in file_ids ]))

		# only export when all files are in one folder
		if len(folder_paths) == 1:
			logger.debug("apiPutFile(): going to export covers to file")
			folder_path = folder_paths[0]
			
			# save uploaded file as cover art
			if fileUpload:
				exportCoverArt(folder_path, imageData)
			# save cover image from url
			elif coverArtSearchResult:
				exportCoverArt(folder_path, coverArtSearchResult)
		
		
	return jsonify(**data), 200
	#return "", 200


@app.route('/api/files/rename/', methods=['POST'])
def renameFiles():
	data = request.get_json(silent=True)
	if not data:
		data = request.form
	
	# file_ids: files to rename
	file_ids = data["file_ids"] if "file_ids" in data else []
	# renameFormat: rename format
	rename_format = data["rename_format"] if "rename_format" in data else ""
	# dry_run: actually rename files or preview actions
	dry_run = bool(data["dry_run"]) if "dry_run" in data else True
	
	logger.debug("renameFiles(): rename_format='%s'" % rename_format)
	
	# rename files
	rename_results = []
	for file_id in file_ids:
		file_path = decodeId(file_id)
		if not os.path.exists(file_path):
			continue
		
		tags = getTags(file_path)
		folder_path = os.path.dirname(file_path)
		old_file_name = os.path.basename(file_path)
		try:
			if tags["tracknumber"]:
				try:
					tags["tracknumber"] = int(tags["tracknumber"])
				except:
					pos = tags["tracknumber"].find("/")
					if pos > 0:
						tags["tracknumber"] = int(tags["tracknumber"][0:pos])
			if tags["date"]:
				try:
					tags["date"] = int(tags["date"])
				except:
					pos = tags["date"].find("-")
					if pos > 0:
						tags["date"] = int(tags["date"][0:pos])
			
			bn, ext = os.path.splitext(old_file_name)
			
			logger.debug("renameFiles(): trying to format file '%s' using format '%s'" % (file_path, rename_format))
			new_file_name = rename_format % tags
			new_file_name = "%s%s" % (new_file_name, ext)
			logger.debug("renameFiles(): old_file_name '%s' -> new_file_name '%s'" % (old_file_name, new_file_name))
			rename_results.append({ 'old_file_name': old_file_name, 'new_file_name': new_file_name })
			if new_file_name != old_file_name and not dry_run:
				new_file_path = os.path.join(folder_path, new_file_name)
				if not os.path.exists(new_file_path):
					logger.warning("renameFiles(): going to move '%s' -> '%s'" % (file_path, new_file_path))
					shutil.move(file_path, new_file_path)
				
		except:
			logger.exception("exception in renameFiles():")
			return jsonify(**{ 'error': 'invalid rename format' }), 500
	
	return jsonify(**{ 'rename_results': rename_results })

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5010, debug=True)
