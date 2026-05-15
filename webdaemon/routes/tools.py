from flask import Blueprint, current_app, request, jsonify, session, g
from webdaemon.model import Settleplate
from webdaemon.database import db
from webdaemon.barcodeparser import Decoder
from webdaemon.status import servicemonitor
from settings import settings
from webdaemon.gs1_barcodeparser import parse_gs1

NOT_COUNTED = -1
WORKFLOW_STARTS_WITH_BATCH = settings['general'].get('workflow_starts_with_batch', True)

# DB helpers
#---------------------------------------------------------#
def query_scan_count(barcode):
	return (
		db.session.query(Settleplate.ScanDate)
		.filter(Settleplate.Barcode==barcode)
		.count()
	)

def query_positive_plate(batch_name, workflow_starts_with_batch):
	"""
	Returns:
		Legacy (batch-first):
			None if no positive plate exists (Counts > 0)
			True if a positive plate exists (Counts > 0)

		GS1 (serial-first):
			None if no plate exists
			Settleplate row if plate exists
	"""
	if workflow_starts_with_batch: # batch-first legacy mode
		row = (
			db.session.query(Settleplate.ScanDate)
			.filter(Settleplate.Batch.like(batch_name),
					Settleplate.Counts > 0)
			.first()
		)
		return True if row else None

	# GS1 mode: return the actual row, not just a bolean
	else:
		return (
			db.session.query(Settleplate)
			.filter(Settleplate.Batch.like(batch_name))
			.first()
		)

# Route
#---------------------------------------------------------#

blueprint = Blueprint("tools",__name__)

@blueprint.route('/parse', methods=['POST'])
def parse_string():
	"""
	input string is routed to the appropriate parser based on settings.
	"""
	raw_data = request.get_json()
	if WORKFLOW_STARTS_WITH_BATCH:
		return handle_legacy_input(raw_data)
	return handle_gs1_or_location_input(raw_data)

# Workflow handlers
#---------------------------------------------------------#
def handle_legacy_input(raw_data):
	"""
	Legacy parser: decodes a settleplate or location barcode using the
    legacy regex-based Decoder, enriches the result with 'used' count
    and positive‑test flags, and returns {} on unrecognized input.
	"""
	result = Decoder.parse_input(raw_data)
	if result is None:
		return jsonify({})

	if 'batch' in result:
		session['batch'] = result['batch']

	if 'serial' in result:
		result['used'] = query_scan_count(result['serial'])

	try:
		result = apply_positive_test_logic(result)
	except KeyError as e:
		return jsonify({"error": {"message": f"Server misconfiguration: missing {e}"}}), 500

	return jsonify(result)

def handle_gs1_or_location_input(raw_data):
	"""
	Attempts to interpret the raw input string from the UI as:
		1. A GS1 settleplate barcode
		2. A location code (using legacy decoder)
		3. Otherwise returns an empty JSON object

	Behavior:
		- Never raises parser errors to the client (matches legacy behavior)
		- Adds 'used' count when a plate barcode is successfully decoded
		- Applies positive‑test logic when a lot number is present
		- Logs parser errors for debugging but returns {} to the client
	"""
	gs1, gs1_err = decode_gs1_input(raw_data)
	if gs1:
		result = gs1

	else: # parse string as location 
		location, loc_err = parse_location(raw_data)
		if location is not None:
			result = {"location": location}
		
		else: #both parsers failed
			current_app.logger.info(f"error: input neither a known location or settleplate barcode")
			current_app.logger.info(f"gs1 parse error: {gs1_err}, location parse error: {loc_err}, input: {raw_data}")
			return jsonify({})

	current_app.logger.info(f"Parsed input: {result}")
	current_app.logger.info(f"Parsed input ({'GS1' if gs1 else 'fallback'}): {result}")

	if 'plate_barcode' in result:
		result['used'] = query_scan_count(result['plate_barcode'])

	try:
		result = apply_positive_test_logic(result)
	except KeyError as e:
		return jsonify({"error": {"message": f"Server misconfiguration: missing {e}"}}), 500

	return jsonify(result)

# Parsing helpers
#---------------------------------------------------------#
def decode_gs1_input(data):
	"""
	Attempts to decode the input string as a GS1 barcode. 
	On success it adds the batch and scanned barcode to the extracted fields 
	and returns the result 
	"""
	if not isinstance(data, str):
		return None, "Input is not a string"

	gs1 = parse_gs1(data)

	required_gs1_fields = ['gtin', 'plate_serial', 'expire', 'lot']
	missing = [f for f in required_gs1_fields if f not in (gs1 or {})]

	if not gs1 or missing:
		#current_app.logger.warning(f"settleplate GS1 barcode is invalid: missing={missing}, input={data}, parsed={gs1}")
		message = "Invalid settleplate barcode"
		if missing:
			message += f", missing: {', '.join(missing)}"
		return None, message

	# add the lot and full valid GS1 string to the result
	gs1['batch'] = gs1 ['lot']
	gs1['plate_barcode'] = data
	current_app.logger.info(f"settleplate parse result: {gs1}")
	return gs1, None

def apply_positive_test_logic(result):
	"""
	Enriches result with positive-test status flags.

	Legacy (batch-first): A positive test exists only if there exists a plate with batch=<prefix+lot> AND Counts >0
		- no_positive = True when no row with Counts > 0 exists.
		- no_positive = False if a completed positive plate exists (i.e., colony count has been updated)
	
	GS1 (serial-first): A positive test exists if ANY plate with Batch=<prefix+lot> is found.
		- Distinguishes between completed and pending positive plates:
			- Counts > 0  means completed positive test (i.e., colonies have been updated)
			- Counts == -1 means positive_pending = True (i.e., colonies yet to be updated)

		- no_positive = True when no positive-plate row exists at all
		- no_positive = False when a positive‑plate row exists (irrespective of completed (counts > 0) or pending (counts == -1))
		- positive_pending = True when row exists but Counts == NOT_COUNTED.
	"""
	if 'lot' not in result or not settings['general'].get('positive_test_required', False):
		return result

	try:
		batch_prefix = settings['general']['positive_test_prefix']
		positive_location = settings['general']['positive_test_location']
	except KeyError:
		current_app.logger.error("Missing configuration for positive test evaluation")
		raise

	positive_batch = batch_prefix + result['lot']
	positive_row = query_positive_plate(positive_batch, WORKFLOW_STARTS_WITH_BATCH)

	# legacy mode (batch-first)
	if WORKFLOW_STARTS_WITH_BATCH:
		if positive_row is None:
			result['no_positive'] = True
			result['no_positive_batch'] = positive_batch
			result['no_positive_location'] = positive_location
		else:
			result['no_positive'] = False
		return result
	
	# GS1 mode (serial-first)
	if positive_row is None:
		result['no_positive'] = True
		result['no_positive_batch'] = positive_batch
		result['no_positive_location'] = positive_location
	else:
		result['no_positive'] = False
		result['positive_pending'] = positive_row.Counts == NOT_COUNTED # true if Counts = -1

	return result


def parse_location(data: str):
	"""
	Parse location codes only.
	Returns location string or None.
	"""
	try:
		result = Decoder.parse_input(data)
	except ValueError as e:
		current_app.logger.debug(f"Error parsing location barcode: {e}")
		return None, "Error parsing location barcode"

	if result and 'location' in result:
		loc = result['location']
		
		# A location must contain atleast 2 non-whitespace characters
		if isinstance(loc, str) and loc.strip() and len(loc.strip()) > 1:
			return loc, None # happy path
		
		current_app.logger.warning(f"Invalid location format, location {loc} is not a string")
		return None, "Invalid location barcode" # failed above if
	
	current_app.logger.warning(f"Invalid location barcode, input={data}")

	return None, "Invalid location barcode" # parsing failed

# App hook: runs automatically each time
#---------------------------------------------------------#

@blueprint.before_app_request
def include_status():
	g.status = servicemonitor.status