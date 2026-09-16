import re
from datetime import datetime
#from webdaemon import app
from flask import Blueprint, current_app, render_template, request, session, jsonify, redirect, make_response, g
import hwlayer.client
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.imagetools import *
from settings import settings
import uuid

def _safe_filename_part(value: str, max_len: int = 64) -> str:
	"""
	Strip anything that isn't alphanumeric, dash, or underscore.
	Prevents path characters (../, /, \\) from reaching the filename 
	that will be sent to the Pi for saving.
	"""
	value = str(value)
	value = re.sub(r'[^A-Za-z0-9_-]', '_', value)
	return value[:max_len] or 'unknown_batch'

blueprint = Blueprint("images",__name__,url_prefix="/images")

@blueprint.route('/live', methods=['GET'])
def live():
	# get parameters
	mode = request.args.get('mode')

	capture_settings = {}
	capture_settings.update(settings['camera']['_default'])

	if mode in settings['camera'].keys():
		capture_settings.update(settings['camera'][mode])

	# request image
	success, image = hwlayer.client.capture_image(capture_settings)

	if success:
		# process image
		image = rotate_image(image, capture_settings)
		if capture_settings['crop_mask']:
			image = mask_image(image, capture_settings)
		if capture_settings['crop_auto'] == 'ring':
			image = autocrop_ring(image, capture_settings)
		elif capture_settings['crop_auto'] == 'rect':
			image = autocrop_rect(image, capture_settings)
		if capture_settings['histogram']:
			image = draw_histogram(image)

		#session['image'] = image
		session['image_jpeg'] = to_jpg(image)
		session['image_timestamp'] = datetime.now().isoformat()
	else:
		#session['image'] = None
		session['image_jpeg'] = None
		session['image_timestamp'] = None

	# check for valid image_jpeg
	# if no image was captured, return 404 to trigger the error handler in the browser
	if session['image_jpeg'] is None:
		current_app.logger.warning("Camera offline: no image_jpeg in session")
		return make_response("No image captured - check if camera is available", 404)

	#normal case
	resp = make_response(session['image_jpeg'])
	resp.headers.set('Content-Type', 'image/jpeg')
	#resp.headers.set('Content-Disposition', 'inline', capture='.jpg')
	resp.cache_control.no_cache = True
	resp.cache_control.must_revalidate = True
	resp.cache_control.max_age = 5
	resp.last_modified = datetime.fromisoformat(session['image_timestamp'])
	return resp
 
@blueprint.route('/<int:image_id>', methods=['GET'])
def get_image(image_id):
	""" image_id is the primary key (ID) value (Settleplate.ID) in the DB for a comitted scan"""
	sp = db.session.get(Settleplate,image_id) #old version (sp = Settleplate.query.get(int(image_id))) was deprecated in SQLAlchemy 2.x
	if sp is None:
		return redirect("/static/settleplate.svg")
	elif sp.Image is None:
		return redirect("/static/settleplate.svg")
	else:
		img = make_response(sp.Image)
		img.headers.set('Content-Type', 'image/jpeg')
		img.headers.set('Content-Disposition', 'attachment', filename=f"{image_id}.jpg")
		return img

@blueprint.route('/save', methods=['POST'])
def save_image():
	try:
		data = request.get_json()

		# now filename doesnot depend on batch or timestamp for uniqueness
		batch_raw = data.get('batch') if data else None

		# only include a batch segment in filename if one was provided
		batch_part = f"-{_safe_filename_part(batch_raw)}" if batch_raw else ""

		# make suffix unique regardless of repeated saves that use the same session timestamp
		unique_suffix = uuid.uuid4().hex[:8]

		params = {
			'user' : _safe_filename_part(g.username),
			'timestamp' : datetime.fromisoformat(session['image_timestamp']).strftime('%Y%m%d_%H%M%S'),
			'suffix' : unique_suffix,
		}

		filename = '{user}-{timestamp}-{suffix}{batch_part}.jpg'.format(
			batch_part=batch_part, **params
		)

		# ask the Pi via RPC to save the image to its local storage
		success, response = hwlayer.client.send({
			'CMD': 'save',
			'filename': filename,
			'jpeg_bytes': session['image_jpeg']
		})

		if not success or response.get('msg') != 'ok':
			raise Exception(response.get('error', 'Pi failed to save image'))

	except Exception as error:
		current_app.logger.error('Failed to write image to Pi local storage: %s'%error)

		# User-friendly message
		user_error = "No image available — camera may be offline."
		return jsonify({'saved': False, 'error': user_error})
	else:
		return jsonify({'saved':True, 'filename':filename})

@blueprint.route('/capture', methods=['get'])
def capture():
	modes = list(settings['camera'].keys())
	# remove debug settings if not admin
	if not g.isAdmin:
		modes = [m for m in modes if not m.startswith('_')]

	# use this as default setting
	selected = None
	for m in modes:
		if 'default' in settings['camera'][m]:
			selected = m
			break
	return render_template('camera.html', modes=modes, selected=selected)
