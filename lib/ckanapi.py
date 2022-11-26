"""
A wrapper containing high-level functions to connect to the public-facing REST API of a
CKAN site. This wrapper is only intended to be used with the GIS Hub CKAN site.
"""

import os
from enum import Enum
import requests
from requests.exceptions import Timeout, ConnectionError, ConnectTimeout, RequestException
from json import JSONDecodeError
import json
import traceback
import settings
import time


logger = settings.setup_logger('ckanapi')

project_root = os.path.realpath(os.path.dirname(__file__))
data_folder = os.path.join(project_root, 'data')

default_error = {'error': 'Server error'}

# Empty for now, API key must be supplied by user at runtime
ghub_headers = {}


class ApiAction(Enum):
    res_show = '/resource_show'
    res_create = '/resource_create'
    res_update = '/resource_update'
    res_patch = '/resource_patch'
    res_delete = '/resource_delete'
    package_update = '/package_update'
    package_patch = '/package_patch'
    package_show = '/package_show'
    package_create = '/package_create'
    package_list = '/package_list'
    all_datasets = '/package_search?include_private=True&rows=1000'
    package_search = '/package_search'
    user_show = '/user_show'
    user_update = '/user_update'
    datastore_create = '/datastore_create'
    datastore_search_sql = '/datastore_search_sql'
    tag_update = '/tag_update'
    tag_list = '/tag_list'
    user_list = '/user_list'

    # For creating vocabulary and adding tags
    vocab_create = '/vocabulary_create'
    tag_add_to_vocab = '/tag_create'


def compare_datasets(ds1, ds2):
    # Returns None if no difference, else set of key names with diffs
    # Detecting diffs: ignore fields like metadata_modified, revision_id, etc
    ignore_fields = ['resources', 'uuid', 'hash', 'revision_id', 'metadata_modified', 'species_codes', 'readme_updated']
    # Compare dataset level
    if len(ds1) != len(ds2):
        diff = ds1.keys().difference(ds2.keys())
        logger.info('Datasets have different keys: %s' % diff)
        return diff
    diffs = set()
    for key, val1 in ds1.items():
        if key in ignore_fields:
            continue
        if val1 != ds2.get(key):
            diffs.add(key)
    # Check resources
    res1 = ds1.get('resources')
    res2 = ds2.get('resources')
    if len(res1) != len(res2):
        logger.info('Datasets have different resource count')
        diffs.add('resource-count')
        return diffs
    for i in range(len(res1)):
        for key, value in res1[i].items():
            if key in ignore_fields:
                continue
            if value != res2[i].get(key):
                diffs.add(key)
    if diffs:
        return diffs
    return None


def dataset_has_changed(current_ds, ds_name):
    # Compare the current dataset (dict) with the last version stored on disk
    last_file = os.path.join(settings.meta_archives, '%s.json' % ds_name)
    if not os.path.exists(last_file):
        logger.info('No previous metadata saved')
        return True
    # Read the json file as a dict
    try:
        with open(last_file) as f:
            last_ds = json.load(f)
            # Compare datasets
            diff = compare_datasets(current_ds, last_ds)
            if diff:
                logger.warning('Datasets differ in: %s' % diff)
                return True
            else:
                return False
    except JSONDecodeError:
        logger.error('Cannot load data from file %s' % last_file)
        logger.error(traceback.format_exc())
        return True


def is_updating(ds_name):
    """
    True if a dataset update is in progress (.update file exist in meta_archives)
    :param ds_name:
    :return:
    """
    logger.info('Check update status for %s' % ds_name)
    update_file = os.path.join(settings.meta_archives, '%s.update' % ds_name)
    status = os.path.exists(update_file)
    logger.info('Updating: %s' % status)
    return status


def save_metadata_to_file(dataset):
    # Save all dataset metadata to file before refresh
    name = dataset.get('name')
    logger.info('Saving metadata for %s to file...' % name)

    if not name:
        logger.warning('Dataset has no name. Dataset ID will be used for backup filename.')
        name = dataset.get('id')
    archive_file = os.path.join(settings.meta_archives, '%s_%s.json' % (
        name, settings.safe_timestamp()))
    with open(archive_file, 'w', encoding='utf8') as f:
        json.dump(dataset, f, indent=4)
    logger.info('Dataset backup saved to %s' % archive_file)
    return archive_file


def ensure_alive():
    intervals = [0, 10, 60, 300, 600]  # seconds   #, 300, 600

    for interval in intervals:

        if interval > 0:
            logger.warning('CKAN API down. Waiting %s secs...' % interval)
        time.sleep(interval)
        is_alive = test_connect()
        if is_alive:
            return is_alive
    logger.error('CKAN API is still down!')
    return False


def test_connect():

    logger.info('Testing API connection...')
    test_url = settings.ghub_api_url_base + '/package_show?id=bops'
    # Check if we can connect to a test URL and get data
    try:
        r = requests.get(test_url, headers=ghub_headers)
        if r.status_code != 200:
            logger.error('Test URL failed, check the GISHUB_API environment var')
            return False
        data = r.json()
        if not data:
            logger.error('No json in response to test URL!')
            return False
        result = data.get('result')
        if not result:
            logger.error('Empty result in CKAN API call!')
            return False
        logger.info('Test call to CKAN API looks ok.')
        return True
    except (Timeout, ConnectionError, ConnectTimeout, RequestException):
        # Server dead for now. Try later
        logger.error('CKAN server is down!')
        return False


def api_request(api_action, data, method='post', id=None, url_params=None):
    """
    Perform an API request on a specified CKAN API endpoint.
    :param api_action: an Enum option from ApiAction
    :param data: dict containing request parameters
    :param method: HTTP method, default POST
    :param id: ID of the dataset or CKAN object targetted by this request
    :param url_params: additional parameters for the request
    :return: JSON result
    """

    url = settings.ghub_api_url_base + api_action.value
    if id is not None:
        url += '?id=' + id
    if url_params is not None:
        url += url_params
    logger.debug('Waiting for CKAN API...')
    if method.lower() == 'post':
        try:
            r = requests.post(url, headers=ghub_headers, json=data)
        except RequestException:
            logger.error('Exception in POST request to CKAN API.')
            logger.error(traceback.format_exc())
            return default_error
    elif method.lower() == 'get':
        try:
            r = requests.get(url, headers=ghub_headers)
        except RequestException:
            logger.error('Exception in GET request to CKAN API.')
            logger.error(traceback.format_exc())
            return default_error
    else:
        logger.error('Unknown method: %s' % method)
        return default_error

    status = r.status_code
    if status in [200, 201, 202, 204, 205]:
        logger.debug('Success!')
        return r.json()
    else:
        logger.warning('Error %s' % status)
        # Better logging for status codes
        if status == 400:
            logger.warning('Bad request. %s' % url)
        if status in [401, 403]:
            logger.warning('Not authorized, are you logged in? %s' % url)
        if status == 408:
            logger.warning('Request timeout. %s' % url)
        if status == 409:
            logger.warning('Data conflict, the data sent is not allowed in that field. %s' % url)
        if status == 500:
            logger.warning('Internal server error. %s' % url)

        try:
            json_resp = r.json()
            logger.warning(r.json())
        except JSONDecodeError:
            if r.reason:
                default_error['reason'] = r.reason
                logger.error('Reason: %s' % r.reason)
            json_resp = default_error
        return json_resp


def get_result(resp):

    result = resp.get('result')
    if not result:
        logger.warning(resp)
        logger.debug('Response received, but no data for "result." Usually this is an error in data sent to API.')
        return []
    else:
        if type(result) is list:
            return result
        # API may give us 'results' nested inside result
        elif type(result) is dict:
            # Check for nested 'results'
            results = result.get('results')
            if results is None:
                # The query never had nested results, return top-level result
                return result
            else:
                if type(results) is not list:
                    # nested results exists, but is not a list
                    logger.warning('Unexpected nested results type: %s' % type(results))
                return results
        else:
            logger.warning('Unexpected result type: %s' % type(result))
            return []


# Convert list to string, with comma separator and no space.
def convert_to_str(input_seq, separator):
    # Join all the strings in list.
    final_str = separator.join(input_seq)
    return final_str


# Get a dataset
def get_dataset(id):
    resp = api_request(ApiAction.package_show, {'id': id})
    return get_result(resp)


# Get a resource
def get_resource(res_id):
    resp = api_request(ApiAction.res_show, {'id': res_id})
    return get_result(resp)


# Get a list of resources from dataset.
def get_resources_list(dataset_dict):
    logger.info('-' * 130)
    logger.info('Getting list of resources from dataset: {}'.format(dataset_dict['name']))
    logger.info('-'*130)
    res_list = dataset_dict['resources']
    for res in res_list:
        logger.info('Resource Name: {:65}Resource ID: {}'.format(res['name'], res['id']))
    return res_list


def get_resource_id_and_file(data_url):
    """ Extracts a resource ID and original filename from a CKAN resource URL """

    parts = data_url.split('/')
    if len(parts) < 2:
        logger.error('Bad data URL: %s parsed path: %s' % (data_url, parts))
        return

    try:
        resource_id_idx = parts.index('resource') + 1
        # Get the last part of the path (which is filename)
        orig_filename = parts[-1]
        resource_id = parts[resource_id_idx]
        return resource_id, orig_filename

    except ValueError:
        logger.error(
            'Bad data URL: expected pattern "resource/<resource_id>/download/<filename.zip>" (actual URL: %s)' % data_url)
        return None, None


def list_datasets():
    # Update to get all dataset+resource metadata, include private datasets
    logger.info('Listing all datasets, patience please...')
    resp = api_request(ApiAction.all_datasets, data=None, method='get')
    results = get_result(resp)
    if type(results) is not list:
        logger.error('List of datasets (results) is %s, expected a list' % type(results))
    return results


def list_datasets_in_group(group_name):
    # Update to get all dataset+resource metadata, include private datasets that belong to a group
    logger.info('Listing all datasets in group, patience please...')
    url_parameters = '?fq=groups:' + group_name + '&include_private=True' + '&rows=1000'
    resp = api_request(ApiAction.package_search, url_params=url_parameters, data=None,
                       method='get')
    results = get_result(resp)
    if type(results) is not list:
        logger.error('List of datasets (results) is %s, expected a list' % type(results))
    if len(results) == 0:
        logger.warning('No datasets for group "%s". are you sure this group exists?' % group_name)
    return results


def read_composite_field(field, field_name):
    """ Try to load field as a JSON string """
    field_data = {}
    # If field is blank, return right away
    if not field:
        logger.debug('Field %s is empty (not a composite field)' % field_name)
        return field_data
    try:
        field_data = json.loads(field)
        return field_data
    except JSONDecodeError:
        logger.error('Cannot load data from field %s: %s' % (field_name, field))
        logger.error(traceback.format_exc())
        return field_data


def main():
    test_connect()


if __name__ == "__main__":
    main()
