import logging
import os
from datetime import datetime


hostname = 'https://www.gis-hub.ca'
ghub_api_url_base = hostname + '/api/3/action'

# Storage locations and paths
base_dir = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.realpath(base_dir)
data_folder = os.path.join(project_root, 'data')
prod_data_folder = os.environ.get('DATA_WORKING_DIR')
if prod_data_folder:
    data_folder = prod_data_folder
meta_archives = os.path.join(base_dir, 'metadata_archive')

filesafe_timestamp = '%Y%m%d-%H%M%S'


def safe_timestamp():
    now = datetime.now()
    return now.strftime(filesafe_timestamp)


# Logging format
screen_fmt = logging.Formatter(
    '%(asctime)s:%(levelname)s:%(module)s(%(lineno)d) - %(message)s'
)

LOG_NAME = 'GeoMeta'


def setup_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    sh = logging.StreamHandler()
    sh.setFormatter(screen_fmt)
    sh.setLevel(level)
    if not logger.handlers:
        logger.addHandler(sh)

    return logger


def add_disk_log(logger, logfile, level=logging.INFO):
    fh = logging.FileHandler(logfile)
    fh.setLevel(level)
    fh.setFormatter(screen_fmt)
    logger.addHandler(fh)
    logger.info('Logging to %s' % logfile)
