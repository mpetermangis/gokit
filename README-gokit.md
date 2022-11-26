# Gokit

GoKit is a tool for syncing data files from the GIS Hub, a private CKAN site containing important data for emergency environmental response.  It is intended for first responders to use before going in the field, to ensure that they have the latest version of any data that they need. Once installed, the user only needs to run a single command to ensure they have the latest versions of key datasets listed in their input file. 

## Developer Installation

To install this tool for development, first create a new Python virtual environment (venv).  With the venv activated, run:

`pip3 install -r requirements.txt`

## Compiling

These instructions have only been tested on Windows 10 with Python 3.8.x.  The compiled file is a generic Windows executable, and the end user does not need to have Python installed on their PC.  It should work with Windows 7, but backwards compatibility is not guaranteed. 

First, find the full path to the `pyinstaller` executable in your venv. 

Windows: `where pyinstaller`

Linux/POSIX: `which pyinstaller`

This works:

`pyinstaller --onedir gokit_sync.py --noconfirm`

If for some reason, the `pyinstaller` command alone does not work, try using the full path to this executable, followed by the full path to the gokit_sync.py file. The `--onedir` flag ensures that all dependencies are packaged into a single folder.  

Example: `C:\Full\Path\to\venv\gokit\Scripts\pyinstaller.exe --onedir C:\Full\Path\to\gokit\gokit_sync.py`

You may also need to add the full path to gokit in the `pathex` variable in spec file (gokit_sync.spec). For example `pathex=['C:\Full\Path\to\venv\gokit'],`

This command will create a folder `/dist/gokit_sync` containing the executable.  

## Distribution

To distribute the executable to end users, simply zip the entire `/dist/gokit_sync` and share using your preferred channel. 

## Running the tool (for end users)

End users must create a file containing a list of dataset IDs for datasets they wish to sync.  The file simply contains a list of dataset IDs, one on each line.  The dataset ID is the last portion of the dataset's URL on the GIS Hub.  For example, to sync this dataset: https://www.gis-hub.ca/dataset/env-layers-nsbssb, add the following line to your dataset file: 

`env-layers-nsbssb`

The dataset file should be on the user's local PC, in a folder with full access rights, for example in the user's home folder.  Data will be downloaded to a folder `downloads` at the same level as the dataset file.  For example, if your dataset file is at: 

`C:\Users\abc\gokit\datasets.txt`

Data will be downloaded to:

`C:\Users\abc\gokit\downloads`

You will also need your CKAN API key. This can be found at the bottom-left of your user page: 

https://www.gis-hub.ca/user/<username>

To run the tool, open a command prompt at the location of the unzipped executable containing gokit_sync.exe.  Then run the executable, followed by the full path to your dataset file, then your API key:  

`gokit_sync.exe C:\Users\abc\gokit\datasets.txt XXX-XXX-XXX`

## Security

When accessing a resource's metadata, a user excluded from a restricted resource will see only a subset of metadata fields.  This is now handled in the CKAN backend, using a customized implementation of ckanext-restricted. There are two cases:

1. A private dataset, which is visible only to users in the creator's organization.  A user outside the creator organization who tries to access this dataset will see this error: 

`No metadata for <dataset>. Are you sure this dataset exists?`

2. A restricted resource within a dataset (typically, we want to restrict the download resource).  An unauthorized user who tries to download a restricted zip file will see this error: 

`You do not have access to the data for: <dataset>. Please contact the dataset owner.` 
