# GS1 barcodes encode multiple fields in one string.
# These are used on settleplates to encode the fields GTIN, serial number, lot/batch number exipration date
# Each field is prefixed by an Application Identifier (AI) — a 2–4 digit code that
# says for example: "the data that follows is a GTIN" or "...is a lot number", etc.
# A raw GS1 string might look like: 
#	011234567890123417270415101A2B3C
#	↑↑              ↑↑      ↑↑
#	AI=01 (GTIN)    AI=17   AI=10 (Lot)
#	                 (Expiry)
# Above plate expires April 15th 2027


#	01035730265999281725052610101099846021092819
#	↑↑              ↑↑      ↑↑          ↑↑
#	AI=01 (GTIN)    AI=17   AI=10 (Lot) AI=21(Serial)
#	                (Expiry)
# Above plate expires April 26th 2025, belongs to lot 1010998460 and has serial 092819
# As from the example, some AIs are of variable length ('10', and '21'). 
# Because of this they are identified by a terminator (\X1D) or the start of the next AI
#
# Other AIs are fixed length eg ('16' and '17')



# GS1 AI definitions (extendable)
from datetime import datetime

FIXED_LENGTH_AIS = {
	"01": 14, # GTIN
	"17": 6, # DATE
}

VARIABLE_LENGTH_AIS = {
	"10": 20,   # Lot
	"21": 20,   # Serial
}

# Combine the keys from both dictionaries into one set of all valid AI codes:
# - set(dict) extracts the dictionary keys
# - "|" performs a union, merging both sets without duplicates
ALL_AIS = set(FIXED_LENGTH_AIS) | set(VARIABLE_LENGTH_AIS)


def match_ai(data, pos):
	"""
		Match 2-digit GS1 AI at position. 
		note, so far all plate AIs are only 2, change matcah_ai() when they get longer 
	"""
	ai_length = 2
	ai = data[pos:pos + ai_length]
	if ai in ALL_AIS:
		return ai, pos + ai_length
	return None, pos

def parse_gs1(datamatrix: str):
	"""
	Detects AIs in string left to right
	"""
	pos = 0
	length = len(datamatrix)
	result = {}

	# track which AIs have already been seen
	seen_ais = set()

	while pos < length:
		ai, new_pos = match_ai(datamatrix, pos)
		if not ai:
			break

		pos = new_pos
		
		seen_ais.add(ai) # mark AI as seen if we see it again, we know it's a value not an AI

		# FIXED-LENGTH
		if ai in FIXED_LENGTH_AIS:
			size = FIXED_LENGTH_AIS[ai]
			value = datamatrix[pos:pos + size]
			pos += size

		# VARIABLE-LENGTH
		elif ai in VARIABLE_LENGTH_AIS:
			max_len = VARIABLE_LENGTH_AIS[ai]
			start = pos

			while pos < length:
				# Stop at FNC1 separator
				if datamatrix[pos] == "\x1D":
					break
				
				next_two = datamatrix[pos:pos+2]

				# Only treat next AI as boundary if:
				#     1. It is a known AI
				#     2. We have consumed at least 1 character
				#     3. It has not been seen already
				if (pos > start + 1 # ensure at least 2 characters consumed
				and next_two in ALL_AIS
				and next_two not in seen_ais
				):
					break

				pos += 1

			value = datamatrix[start:pos][:max_len]

			# Skip FNC1 if present
			if pos < length and datamatrix[pos] == "\x1D":
				pos += 1
				seen_ais.add(ai)

		else:
			break

		# Store fields
		if ai == "01":
			result["gtin"] = value
		elif ai == "17":
			if len(value) == 6:  # YYMMDD format
				try:
					# extract YYMMDD and convert to datetime eg "270415" will be datetime(2027, 4, 15)
					year = int("20" + value[0:2])
					month = int(value[2:4])
					day = int(value[4:6])
					result["expire"] = datetime(year, month, day)
				except ValueError:
					pass  # Ignore invalid dates like 991332

		elif ai == "10":
			result["lot"] = value
		elif ai == "21":
			result["plate_serial"] = value

	return result