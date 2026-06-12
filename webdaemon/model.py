from datetime import datetime
from sqlalchemy.orm import deferred
from flask_wtf import FlaskForm
from wtforms import StringField, DateTimeField, DateField, IntegerField, validators, HiddenField
from webdaemon.database import db
from webdaemon.version import __version__

# ------------------------------------------------------
# Model — Used by create_database() in database.py to create the database table, inserts, queries, and all registration logic
# ------------------------------------------------------
class Settleplate(db.Model):
	__tablename__ = 'SETTLEPLATE'
	ID = db.Column(db.Integer, primary_key=True)
	Username = db.Column(db.Unicode(32))
	ScanDate = db.Column(db.DateTime)
	# TODO: find out if we can add a new column PlateSerial since this ORM model is used by both legacy and new deployments
	# SQLAlchemy requires that every database using this model already has the PlateSerial column.
	#Therefore:
		# - If PlateSerial is defined here, ALL legacy DBs must first be migrated to include the PlateSerial column.
		# - Once present in the DB, legacy workflows will simply leave it NULL.
	#PlateSerial = db.Column(db.String(128))
	Barcode = db.Column(db.String(128))
	Lot_no = db.Column(db.String(64))
	Expires = db.Column(db.Date)
	Counts = db.Column(db.Integer)
	Version = db.Column(db.String(32))
	Location = db.Column(db.Unicode(128))
	Batch = db.Column(db.String(128))
	Image = deferred(db.Column(db.LargeBinary)) # deferred so only loaded when accessed, not when queried
	Colonies = db.Column(db.Text) # use unlimited length since db uses  VARCHAR (MAX) and "Colonies" TEXT
	Exported = db.Column(db.Boolean, default=False)

	def __init__(self, **kwargs):
			super(Settleplate, self,).__init__(**kwargs)
			self.ScanDate = datetime.now()
			self.Exported = False
			self.Version = f"WebApp {__version__}"

	def __repr__(self):
		return '<Settleplate %r>' % self.ID

	@classmethod
	def get_registration(cls, barcode):
		return (
			cls.query
			.filter(cls.Barcode == barcode,
					cls.Counts == -1)
			.one_or_none()
		)

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
