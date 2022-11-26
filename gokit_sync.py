import settings
import os
import sys
import errno
import json
import requests
from urllib.parse import urlparse
from lib import ckanapi

logger = settings.setup_logger('gokit')
base_dir = os.path.dirname(os.path.realpath(__file__))

# Define metadata fields to save to output
DS_FIELDS = ['title', 'notes', 'name', 'url', 'maintainer_email', 'citation', 'start_date',
             'end_date', 'metadata_standard', 'metadata_created', 'metadata_modified', 'data_creator',
             'program_manager', 'co_creators', 'quality_control', 'topic_category', 'date_published',
             'date_completed', 'status', 'update_frequency', 'hierarchyLevel', 'keywords',
             'science_keywords', 'theme', 'methods', 'data_inputs', 'scripts_or_software_routines',
             'spatial_data_quality', 'positional_accuracy', 'attribute_accuracy', 'logical_consistency',
             'completeness', 'absence_data', 'uncertainties', 'use_restrictions', 'change_history',
             'species_codes', 'sp_code_list', 'references', 'collaboration', 'confidentiality',
             'other_information', 'type', 'organization']

RES_FIELDS = ['title', 'name', 'layer_name', 'layer_description', 'filepath', 'format', 'data_format',
              'mimetype', 'spatial_type', 'geometry_type', 'projection_code', 'projection_text',
              'projection_codespace', 'codespace_version', 'locale', 'bbox', 'map_preview_link',
              'attribute', 'url', 'restricted', 'last_modified', 'created', 'position', 'disclaimer',
              'disclaimer_url']

# Internal fields at dataset level
DS_INTERNALS = ['relationships_as_object', 'private', 'num_tags', 'license_title',
                 'isopen', 'id', 'state', 'author', 'author_email', 'version', 'creator_user_id',
                 'num_resources', 'data_charset', 'groups', 'license_id', 'relationships_as_subject',
                 'revision_id', 'character_set', 'maintainer', 'summary_french', 'temporal_coverage']

# Internal fields at resource level
RES_INTERNALS = ['cache_last_updated', 'package_id', 'datastore_active', 'state',
                     'cache_url', 'mimetype_inner', 'revision_id', 'resource_type']


def read_dataset_list(ds_file):
    ds_list = []
    # If the file contains no path, assume it's at this level
    if not os.path.isabs(ds_file):
        ds_file = os.path.join(settings.base_dir, ds_file)
    if not os.path.exists(ds_file):
        logger.error('Missing required file: %s' % ds_file)
        sys.exit(1)

    logger.info('Reading list of datasets from: %s' % ds_file)
    with open(ds_file) as f:
        # Read the list of datasets
        for line in f.readlines():
            ds = line.strip()
            if len(ds) > 0:
                ds_list.append(ds)

    logger.info('You are syncing %s datasets' % len(ds_list))
    return ds_list


def setup_downloads_folder(ds_file):
    # Downloads folder will be created adjacent to the datasets file list
    output_base_dir = os.path.dirname(ds_file)
    downloads = os.path.join(output_base_dir, 'downloads')
    # Ensure downloads folder exists
    if not os.path.exists(downloads):
        try:
            logger.info('Creating downloads folder: %s' % downloads)
            os.mkdir(downloads)
        except OSError as e:
            if e.errno == errno.EEXIST:
                logger.warning('Download folder: %s already exists' % downloads)
                pass
            elif e.errno == errno.EACCES or e.errno == errno.EROFS:
                logger.error(
                    'No write access to folder: %s.  Are you running this in your home folder?' % downloads)
                sys.exit(1)
            elif e.errno == errno.ENOSPC:
                logger.error('No space left on disk. Please delete some files and try again. ')
                sys.exit(1)

    logger.info('Datasets will be synced to: %s' % downloads)
    return downloads


def remove_internal_fields(ds_meta):
    # Removes internal CKAN metadata fields that users don't want to see.
    for field in DS_INTERNALS:
        ds_meta.pop(field, None)

    resources = ds_meta.get('resources')
    ds_meta['resources'] = []
    for res in resources:
        for field in RES_INTERNALS:
            res.pop(field, None)
        # Skip the upload placeholder resource
        if res.get('url_type') != 'upload':
            ds_meta['resources'].append(res)
    return ds_meta


def format_output(output_lines, content):
    # Check if content is a nested json
    try:
        content = json.loads(content)
        # Check type
        if type(content) is list:
            for entry in content:
                for k, v in entry.items():
                    format_output(output_lines, '%s: %s' % (k, v))
        elif type(content) is dict:
            for k, v in content.items():
                format_output(output_lines, '%s: %s' % (k, v))
        else:
            logger.warning('Unexpected type')

    except (TypeError, json.JSONDecodeError):
        # Content is text, write to output
        output_lines.append('\t%s\n' % str(content))

    return output_lines


def get_formatted_output(output_fields, data, output_lines):
    for field in output_fields:
        output_lines.append('%s:\n' % field)
        content = data.get(field)
        if content:
            output_lines = format_output(output_lines, content)
    return output_lines


def save_text_output(downloads_folder, dataset_name, ds_meta):
    # Save fields in relevant order to metadata text file
    metadata_file = os.path.join(downloads_folder, '%s.metadata.txt' % dataset_name)
    output_lines = []
    for level in ['ds_fields', 'res_fields']:

        if level == 'ds_fields':
            output_lines.append('------- Dataset-level Metadata ------- \n')
            output_lines = get_formatted_output(DS_FIELDS, ds_meta, output_lines)
            output_lines.append('------- End of Dataset-level Metadata ------- \n')
            output_lines.append('\n')
        elif level == 'res_fields':
            output_lines.append('------- Resource-level Metadata (for files, layers in uploaded data) ------- \n')
            for resource in ds_meta.get('resources'):
                output_lines = get_formatted_output(RES_FIELDS, resource, output_lines)
            output_lines.append('------- End of Resource-level Metadata ------- \n')
            output_lines.append('\n')

    logger.info('Writing metadata to text file: %s' % metadata_file)
    with open(metadata_file, 'w', encoding='utf8') as metatext:
        metatext.writelines(output_lines)


def save_json_output(downloads_folder, dataset_name, ds_meta):
    # Dump json file first
    metadata_file = os.path.join(downloads_folder, '%s.metadata.json' % dataset_name)
    with open(metadata_file, 'w', encoding='utf8') as f:
        json.dump(ds_meta, f, indent=2)
    logger.info('Metadata saved to %s' % metadata_file)


def download_file(url, downloads_folder, title):
    """
    Download the resource file directly from S3 URL, without using the
    Amazon S3 boto module (so we don't need to reveal API keys).
    :param url: a signed download URL to the resource on S3
    :param downloads_folder: local folder for downloaded files
    :param title: title of the resource in CKAN containing the
    downloadable zip archive for the dataset
    :return: None
    """
    url_parsed = urlparse(url)
    remote_file = os.path.basename(url_parsed.path)
    logger.info('Downloading data file %s for resource %s' % (remote_file, title))
    r = requests.get(url, stream=True, headers=ckanapi.ghub_headers)
    dl_target = os.path.join(downloads_folder, remote_file)
    logger.info('Saving download to: %s' % dl_target)
    with open(dl_target, 'wb') as f:
        for chunk in r.iter_content(chunk_size=128):
            f.write(chunk)
    logger.info('Saved')


def sync(ds_file):
    """
    Synchronize a list of input datasets from the CKAN site to the user's
    download folder.
    :param ds_file: text file containining dataset names, one per line
    :return: None
    """

    # Set the log file to same location as ds_file
    logfile = os.path.join(os.path.dirname(ds_file), 'gokit_sync.log')
    settings.add_disk_log(logger, logfile)

    logger.info('Starting GoKit sync')

    # Setup downloads folder and cache
    downloads_folder = setup_downloads_folder(ds_file)

    logger.info('Connecting to GIS Hub...')
    ds_list = read_dataset_list(ds_file)
    for dataset_name in ds_list:

        logger.info('')
        logger.info('      >>>>   Starting Sync   <<<<         ')
        logger.info('Syncing dataset: %s' % dataset_name)
        # List all the resources for this dataset with download URLs
        ds_meta = ckanapi.get_dataset(dataset_name)
        logger.debug(ds_meta)
        if not ds_meta:
            logger.warning('No metadata for %s. Are you sure this dataset exists?' % dataset_name)
            continue

        # List resources in metadata, find any with a url_type = 'upload'
        resources = ds_meta.get('resources')
        if not type(resources) is list or len(resources) == 0:
            logger.warning('Dataset %s has no resources.' % dataset_name)
            continue

        # Cleanup metadata and save to downloads folder
        ds_meta = remove_internal_fields(ds_meta)
        save_json_output(downloads_folder, dataset_name, ds_meta)
        save_text_output(downloads_folder, dataset_name, ds_meta)

        logger.info('Checking %s resources' % len(resources))
        for res in resources:
            if res.get('url_type') == 'upload':
                url = res.get('url')
                if not url:
                    logger.warning('You do not have access to the data for: %s' % dataset_name)
                    logger.warning('Please contact the dataset owner.')
                    continue
                title = res.get('title')
                download_file(url, downloads_folder, title)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('datasets',
                        help='Full path to a text file with a list of datasets to sync.')
    parser.add_argument('apikey',
                        help='Your API key from the GIS Hub.')

    # Ensure arguments contains a file (with list of datasets)
    if len(sys.argv) < 3:
        parser.print_help()
        parser.exit()
    args = parser.parse_args()
    ds_file = args.datasets

    # Set API key in ckanapi module
    ckanapi.ghub_headers = {'Authorization': args.apikey}
    sync(ds_file)


if __name__ == "__main__":
    main()
