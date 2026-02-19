from datetime import datetime
from sqlalchemy.orm import deferred
from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField, DateField, IntegerField, validators, HiddenField
from webdaemon.database import db
from webdaemon.version import __version__

from sqlalchemy import Text
import os


# ------------------------------------------------------
# Configuration
# ------------------------------------------------------
config_file = os.environ.get("SETTLEPLATE_CONFIG", "default").lower()

if config_file == "kubernetes":
	IS_K8S = True
else:
	IS_K8S = False

# ------------------------------------------------------
# Database type aliases (legacy-compatible)
# ------------------------------------------------------
if IS_K8S:
	# PostgreSQL-friendly types
	Str32 = db.String(32)
	Str64 = db.String(64)
	Str128 = db.String(128)
	ColoniesType = Text # Required for PostgreSQL to allow large text fields
	ExportedType = db.Boolean
	ExportedDefault = False
else:
	# Legacy / SQL Server-compatible types
	Str32 = db.NVARCHAR(32)
	Str64 = db.VARCHAR(64)
	Str128 = db.NVARCHAR(128)
	ColoniesType = db.VARCHAR("max")
	ExportedType = db.BINARY(1)
	ExportedDefault = b"\x00" # False in legacy - code is a Python boolean, but the actual binary value of false for SQL Server is b'\x00'


# ------------------------------------------------------
# Models
# ------------------------------------------------------
class Settleplate(db.Model):
	__tablename__ = 'SETTLEPLATE'

	ID = db.Column(db.Integer, primary_key=True)
	Username = db.Column(db.Unicode(32))
	ScanDate = db.Column(db.DateTime)
	Barcode = db.Column(db.String(128))
	Lot_no = db.Column(db.String(64))
	Expires = db.Column(db.Date)
	Counts = db.Column(db.Integer)
	Version = db.Column(db.String(32))
	Location = db.Column(db.Unicode(128))
	Batch = db.Column(db.String(128))
	Image = deferred(db.Column(db.LargeBinary)) # deferred so only loaded when accessed, not when queried
	Colonies = db.Column(db.String(8192))
	Exported = db.Column(db.Boolean, default=False)

	def __init__(self, **kwargs):
		super(Settleplate, self).__init__(**kwargs)
		# Ensure old file behavior exactly
		if 'ScanDate' not in kwargs:
			self.ScanDate = datetime.now()
		if 'Exported' not in kwargs:
			self.Exported = ExportedDefault #will be False in k8s and b'\x00' in legacy
		self.Version = f'WebApp {__version__}'

	def __repr__(self):
		return f'<Settleplate {self.ID}>'


# ------------------------------------------------------
# Forms
# ------------------------------------------------------
class SettleplateForm(FlaskForm):
	Username = StringField('Name', [validators.DataRequired("Please enter study name")])
	ScanDate = DateTimeField('Date')
	Barcode = StringField('Barcode', [validators.DataRequired("Settleplate barcode needed")])
	Lot_no = StringField('Lot number')
	Expires = DateField('Expire Date')
	Counts = IntegerField('Counts')
	Location = StringField('Location', [validators.DataRequired("Location needed")])
	Batch = StringField('Batch', [validators.DataRequired("Batch# needed")])
	Colonies = HiddenField('Colonies')
	Version = StringField('Version', render_kw={'readonly': True})
