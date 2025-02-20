import os
from datetime import datetime, timedelta
from flask import Blueprint, current_app, session, jsonify
from webdaemon.model import Settleplate
from webdaemon.imagetools import from_buffer
from webdaemon.hivetools import detect_cfu
from settings import settings

blueprint = Blueprint("hive",__name__,url_prefix="/hive")

# do cfu detection on image before saving to DB
@blueprint.route('/', methods=['GET'])
def count_live():
	img_bytes = session.get('image_jpeg', None)

	if img_bytes is None:
		results = []
	else:
		image = from_buffer(img_bytes)
		results = detect_cfu(image)

	return jsonify(results)

# do cfu detection on image in DB
@blueprint.route('/<int:image_id>', methods=['GET'])
def count_image(image_id):
	sp = Settleplate.query.get(int(image_id))
	
	if sp is None:
		image = None
	elif sp.Image is None:
		image = None
	else:
		image = from_buffer(sp.Image)
	
	if image is None:
		results = []
	else:
		results = detect_cfu(image)
	current_app.logger.info(f'CFU-detect: {results}')
	return jsonify(results)