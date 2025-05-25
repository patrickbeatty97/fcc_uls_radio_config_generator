# fcc_uls_radio_config_generator
--------------

This script downloads a local copy of the FCC ULS database dump ZIP files, extracts them, and loads them 
into an SQLite database, if the database doesn't already exist locally.
It then queries the database currenty either by City or ZIP code(s) and the Radio Service Code(s) and outputs the frequency results formatted for importing into HAM radios.

The resulting config is output to a CSV file for the specified radio model.
Currently, only TIDRADIO TD-H8s are supported. 
The radio model can be specified with the -r / --radio argument.
List supported radio models with the -lr / --list-radios argument. 
If no radio model is specified, generically formated results are display to stdout.

The default database downloaded is Land Mobile - Private.
Multiple databases can be specified with the -zf / --zipfiles argument.
List supported databases with the -lz / --listzips argument.

NOTE:
  All of the FCC ULS database dump zip files take up between 6 and 7GB my last check.
  The first time the script runs to download and load them it can take 10 minutes are longer.
  Future runs use the local existing data unless the --cc / --clearcache option is specified.  

USAGE
-----
    gen_fcc_uls_radio_config.py --help

Download and load the FCC ULS database dump files specified and return frequencies from NYC for the PW service (Public Works - Police, Fire, EMS, etc). A resulting CSV file will be generated for a TIDRADIO TD-H8.

    gen_fcc_uls_radio_config.py --city "New York" -s PW -zf l_LMcomm.zip,l_LMpriv.zip,l_LMbcast.zip,l_coast.zip,l_micro.zip,l_paging.zip -r tdh8

INSTALLING
-----------------------

Some pip modules are probably not installed by default. Install them with pip as needed.
To be updated...
