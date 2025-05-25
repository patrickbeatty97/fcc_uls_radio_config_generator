# fcc_uls_radio_config_generator
--------------

This script downloads a local copy of the FCC ULS database dump ZIP files, extracts them, and loads them 
into an SQLite database, if the database doesn't already exist locally.
It then queries the database currenty either by City or ZIP code(s) and the Radio Service Code(s) and outputs the results formatted for importing into HAM radios

USAGE
-----
    gen_fcc_uls_radio_config.py --help

INSTALLING
-----------------------

Some PIP modules are probaly not installed by default. Install them with PIP as needed.
To be updated...
