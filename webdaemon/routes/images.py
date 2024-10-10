import os
from datetime import datetime
#from webdaemon import app
from flask import Blueprint, current_app, render_template, request, session, jsonify, redirect, make_response, g
import hwlayer.client
from webdaemon.model import Settleplate
from webdaemon.imagetools import *
from settings import settings

blueprint = Blueprint("images",__name__,url_prefix="/images")

@blueprint.route('/live', methods=['GET'])
def live():
	# get parameters
	mode = request.args.get('mode')

	capture_settings = {}
	capture_settings.update(settings['camera']['default'])

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
	if session['image_jpeg'] is None:
		return redirect("/static/settleplate.svg")
	else:
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
	sp = Settleplate.query.get(int(image_id))
	if sp is None:
		return redirect("/static/settleplate.svg")
	elif sp.Image is None:
		return redirect("/static/settleplate.svg")
	else:
		img = make_response(sp.Image)
		img.headers.set('Content-Type', 'image/jpg')
		img.headers.set('Content-Disposition', 'attachment', filename=f"{image_id}.jpg")
		return img

@blueprint.route('/save', methods=['POST'])
def save_image():
	try:
		data = request.get_json()

		params = {
			'user' : g.username,
			'timestamp' : datetime.fromisoformat(session['image_timestamp']).strftime('%Y%m%d_%H%M%S'),
			'batch_id' : data['batch']
		}
		filename = '{user}-{timestamp}-{batch_id}.jpg'.format(**params)
		filepath = os.path.join(settings['general']['savepath'], filename)
		with open(filepath,'wb') as f:
			img_out = session['image_jpeg']
			current_app.logger.info('Saving image to: %s (%d kB)'%(filename,len(img_out)/1024))
			f.write(img_out)
	except Exception as error:
		current_app.logger.error('Failed to write image: %s'%error)
		return jsonify({'saved':False, 'error':str(error)})
	else:
		return jsonify({'saved':True, 'filename':filename})

@blueprint.route('/capture', methods=['get'])
def capture():
	modes = list(settings['camera'].keys())
	modes.remove('default')
	selected = None
	for m in modes:
		if 'default' in settings['camera'][m]:
			selected = m
			break
	return render_template('camera.html', modes=modes, selected=selected)
