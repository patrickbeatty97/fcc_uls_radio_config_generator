# fcc_uls_radio_config_generator
--------------

This script downloads a local copy of the FCC ULS database dump ZIP files, extracts them, and loads them 
into an SQLite database, if the database doesn't already exist locally.
It then queries the database currenty either by City or ZIP code(s) and the Radio Service Code(s) and outputs the frequency results formatted for importing into HAM radios.
The default database downloaded is Land Mobile - Private.
Multiple databases can be specified with the -zf flag.
List supported databases with the -lz flag.

USAGE
-----
    gen_fcc_uls_radio_config.py --help

This will download and load the FCC ULS ZIP database dump files specified and return frequencies from NYC for the PW service (Public Works - Police, Fire, EMS, etc)

    gen_fcc_uls_radio_config.py --city "New York" -s PW -zf l_LMcomm.zip,l_LMpriv.zip,l_LMbcast.zip,l_coast.zip,l_micro.zip,l_paging.zip

INSTALLING
-----------------------

Some PIP modules are probaly not installed by default. Install them with PIP as needed.
To be updated...
