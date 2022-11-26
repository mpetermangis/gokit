import settings
import os
import sys
import argparse
from lib import ckanapi

logger = settings.setup_logger('get_datasets')
base_dir = os.path.dirname(os.path.realpath(__file__))


def get_datasets_in_group(apikey, group_name):
    """
    Writes a text file containing the names of all datasets in a CKAN group.
    :param apikey: user's API key in CKAN
    :param group_name: name of the group
    :return: None
    """
    # Set API key in ckanapi module.
    ckanapi.ghub_headers = {'Authorization': apikey}

    # Get group information.
    spill_datasets = ckanapi.list_datasets_in_group(group_name)

    if spill_datasets:  # List is not empty
        # Get list of dataset names.
        dataset_names = [ds.get('name') for ds in spill_datasets]

        # Create datasets.txt file at same level, with group name appended
        datasets_txt = os.path.join(os.getcwd(), 'datasets-%s.txt' % group_name)

        with open(datasets_txt, 'w') as ds_file:
            for ds_name in dataset_names:
                ds_file.write("%s\n" % ds_name)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('apikey',
                        help='Your API key from the GIS Hub.')
    parser.add_argument('group_name',
                        help='Name of group from the GIS Hub to get dataset names from.')

    # Ensure arguments contains api key and group name.
    if len(sys.argv) < 3:
        parser.print_help()
        parser.exit()
    args = parser.parse_args()
    get_datasets_in_group(args.apikey, args.group_name)


if __name__ == "__main__":
    main()
