import sys
import logging
import logging.handlers

# setup logging
log_root = logging.getLogger()
log_formatter = logging.Formatter("%(asctime)s | %(name)12s | %(levelname)8s : %(message)s")
#log_filehandler = logging.handlers.TimedRotatingFileHandler('log/ColonizerHW.log', when='midnight', backupCount=7)
#log_filehandler.setFormatter(log_formatter)
#log_filehandler.setLevel('DEBUG')
log_stdhandler = logging.StreamHandler(sys.stdout)
log_stdhandler.setFormatter(log_formatter)
log_stdhandler.setLevel('DEBUG')
#log_root.addHandler(log_filehandler)
log_root.addHandler(log_stdhandler)