# fcc_uls_radio_config_generator
--------------

This script downloads a local copy of the FCC ULS database dump ZIP files, extracts them, and loads them into an SQLite database, if the database doesn't already exist locally.\
It then searches the database, currenty either by City, State, or ZIP code(s) and the Radio Service Code(s), and outputs the frequency results formatted for importing into HAM radios and/or scanners.

I primarily use it in combination with the PW (Public Works) service code argument, for obtaining Police/Fire/EMS frequencies for quickly importing into my radio based on a location. 

A CSV file is output by default in a CHIRP and Odmaster compatible CSV format.\
This format is confirmed to work on a **TIDRADIO TD-H8**, and hopefully will work on at least a **Baofeng UV-5R** as well.
At this time only generic formatting is supported until other radio models can be tested.\
For future use, a specific radio model can be set with the **-r / --radio** argument,\
and supported radio models can be listed with the **-lr / --list-radios** argument.

Generically formated results are displayed to stdout.

The default database(s) downloaded is Land Mobile - Private.\
Multiple databases can be specified with the **-zf / --zip-files** argument.\
List supported databases with the **-lz / --list-zips** argument

List supported service codes with the **-ls / --list-services** argument

See **--help** output for channel numbering and naming options and an explanation of how channel names are generated when set to auto (default)

**NOTE:**\
  The first time the script runs, it can take about 10 minutes or longer to download the FCC ULS database dump zip files and load them into the SQLite database, depending on your internet speed, the FCC's internet speed, your computer, and how many files are requested, to name a few factors.\
  Future runs use the local existing data unless the --cc / --clear-cache option is specified.

USAGE
-----
    gen_fcc_uls_radio_config.py --help

Download the FCC ULS database dump zip files specified, load them into the database, and generate a CSV file of frequencies from NYC for the PW service code (Public Works - Police, Fire, EMS, etc) : \

    gen_fcc_uls_radio_config.py -c "New York" -s PW -zf l_LMcomm.zip,l_LMpriv.zip,l_LMbcast.zip,l_coast.zip

Example stdout generic result lines (not from the CSV file generated) :

Freq: 485.78750000 MHz, Call Sign: WQX1234, Entity: NEW YORK CITY TRANSIT AUTHORITY, City/State/ZIP/County: NEW YORK/NY/10004/BRONX, Service: PW, Eligibility: APPLICANT IS THE NEW YORK CITY TRANSIT AUTHORITY WHICH IS A GOVERNMENTAL ENTITY CHARGED WITH SPECIFIC DUTIES. RADIOS WILL BE USED FOR OFFICIAL ACTIVITIES OF THE LICENSEE., Status: A
Freq: 485.81250000 MHz, Call Sign: WQX4321, Entity: NEW YORK CITY POLICE DEPARTMENT, City/State/ZIP/County: NEW YORK/NY/10038/RICHMOND, Service: PW, Eligibility: POLICE DEPARTMENT PROVIDING SAFETY AND PROTECTION OF LIFE AND PROPERTY, Status: A
Freq: 485.83750000 MHz, Call Sign: WQXX999, Entity: NEW YORK CITY POLICE DEPARTMENT, City/State/ZIP/County: NEW YORK/NY/10038/None, Service: PW, Eligibility: POLICE DEPARTMENT PROVIDING SAFETY, PROTECTION OF LIFE AND PROPERTY., Status: A

INSTALLING
-----------------------

pip install -r requirements.txt

Debian/Ubuntu specific (use system packages) : 

sudo apt install python3-bs4 python3-requests python3-tqdm

To be updated...
