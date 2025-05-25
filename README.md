# fcc_uls_radio_config_generator
--------------

This script downloads a local copy of the FCC ULS database dump ZIP files, extracts them, and loads them 
into an SQLite database, if the database doesn't already exist locally.
It then searches the database, currenty either by City or ZIP code(s) and the Radio Service Code(s), and outputs the frequency results formatted for importing into HAM radios and/or scanners.

I primarily use it in combination with the PWS (Public Works) service code argument, for obtaining Police/Fire/EMS frequencies for quickly importing into my radio based on a location. 

Generically formated results are displayed to stdout.

The resulting config is output to a CSV file for the specified radio model.
Currently, only TIDRADIO TD-H8s are supported. 
The radio model can be specified with the -r / --radio argument.
List supported radio models with the -lr / --list-radios argument. 

The default database downloaded is Land Mobile - Private.
Multiple databases can be specified with the -zf / --zip-files argument.
List supported databases with the -lz / --list-zips argument.

**NOTE:**
  All of the FCC ULS database dump zip files take up between 6 and 7GB my last check.
  The first time the script runs to download and load them it can take 10 minutes are longer.
  Future runs use the local existing data unless the --cc / --clear-cache option is specified.  

USAGE
-----
    gen_fcc_uls_radio_config.py --help

Download and load the FCC ULS database dump files specified and return frequencies from NYC for the PW service code (Public Works - Police, Fire, EMS, etc). A resulting CSV file will be generated for a TIDRADIO TD-H8 : 

    gen_fcc_uls_radio_config.py --city "New York" -s PW -zf l_LMcomm.zip,l_LMpriv.zip,l_LMbcast.zip,l_coast.zip,l_micro.zip,l_paging.zip -r tdh8

Example stdout generic result lines (not from the CSV file generated) :

	Freq: 487.53750000 MHz, Entity: NEW YORK CITY TRANSIT AUTHORITY, Location: NEW YORK, NY 10004, Service: PW, Eligibility: APPLICANT IS THE NEW YORK CITY TRANSIT AUTHORITY WHICH IS A GOVERNMENTAL ENTITY CHARGED WITH SPECIFIC DUTIES. RADIOS WILL BE USED FOR OFFICIAL ACTIVITIES OF THE LICENSEE., Status: A
	Freq: 487.56250000 MHz, Entity: NEW YORK CITY POLICE DEPARTMENT, Location: NEW YORK, NY 10038, Service: PW, Eligibility: POLICE DEPARTMENT PROVIDING SAFETY, PROTECTION OF LIFE AND PROPERTY, Status: A
	Freq: 487.66250000 MHz, Entity: NEW YORK CITY POLICE DEPARTMENT, Location: NEW YORK, NY 10038, Service: PW, Eligibility: POLICE DEPARTMENT PROVIDING SAFETY, PROTECTION OF LIFE AND PROPERTY, Status: A

INSTALLING
-----------------------

Some pip modules are probably not installed by default. Install them with pip as needed.
To be updated...
