#!/usr/bin/python3

import os
import re
import sys
import csv
import shutil
import zipfile
import sqlite3
import argparse
import requests
from tqdm import tqdm
import glob
from bs4 import BeautifulSoup
from datetime import datetime

verbose = 0
csv.field_size_limit(sys.maxsize)

# Constants
SELF_DESC = 'FCC ULS Database Loader, Frequency Search, and Radio Config Generator'
BASE_URL = 'https://data.fcc.gov/download/pub/uls/complete/'
#DATA_DIR_PREFIX = os.getcwd()
DATA_DIR_PREFIX = '/home/dexter/Downloads'
DATA_DIR = DATA_DIR_PREFIX + '/fcc_uls_data'
DB_FILE = DATA_DIR + '/fcc_uls.db'
DEFAULT_CHAN_NAME_SUFFIX = 'Q'
DEFAULT_CHAN_NAME_MAX_LEN = 99
#EXCLUDED_CHAN_NAME_WORDS = {
#    "IS", "THE", "WHICH", "ENTITY", "APPLICANT", "SPECIFIC", "RADIOS",
#    "WILL", "BE", "USED", "FOR", "OF", "LICENSE", "LICENSEE", "PROVIDING"
#}
EXCLUDED_CHAN_NAME_WORDS = {}
SUPPORTED_RADIOS = {
    'tdh8': {
        'chan_name_max_len': 7,
        'csv_headers': [
            "Location", "Name", "Frequency", "Duplex", "Offset", "Tone", "rToneFreq", "cToneFreq",
            "DtcsCode", "DtcsPolarity", "RxDtcsCode", "CrossMode", "Mode", "TStep", "Skip",
            "Power", "Comment", "URCALL", "RPT1CALL", "RPT2CALL", "DVCODE"
        ],
        'csv_default_row': [
            "", "", "", "", "0.00000", "", "88.5", "88.5", "023", "NN", "023", "Tone->Tone",
            "FM", "5.0", "", "8.0W", "", "", "", "", ""
        ]
    }
}
CSV_FILE_PREFIX = ''
CSV_FILE_SUFFIX = '_frequencies-' + datetime.today().strftime('%Y%m%d%H%M%S') + '.csv'
ZIPS_LOADED_TABLE_NAME = 'loaded_zips'
DEFAULT_ZIPFILES = ['l_LMpriv.zip']
SUPPORTED_ZIPFILES = {
    'l_paging.zip',
    'l_LMbcast.zip',
    'l_mdsitfs.zip',
    'l_market.zip',
    'l_coast.zip',
    'l_LMpriv.zip',
    'l_LMcomm.zip',
    'l_micro.zip'
}

def gen_radio_chan_name(entity, eligibility, seen, prefix_src='city', prefix_str=None, suffix_src='auto', suffix_str=None, max_length=999):
    # Step 1: Determine prefix
    if prefix_src.lower() == 'city':
        words = prefix_str.upper().split()

        if len(words) == 1:
            prefix_str = words[0][:2]
        elif len(words) == 2:
            prefix_str = words[0][0] + words[1][0]
        else:
            prefix_str= words[0][0] + words[1][0] + + words[2][0]

        #prefix = prefix.ljust(2, 'X')

    # Step 2: Merge and normalize source text
    src_txt = f"{entity} {eligibility}".upper()

    if verbose > 1:
        print(f"CHANNEL NAME TEXT SOURCE : {src_txt}")

    # Step 3: Determine suffix
    if suffix_src.lower() == 'auto':
        if "POLICE" in src_txt and "STATE" in src_txt:
            suffix_str = "SPD"
        elif "POLICE" in src_txt and any(k in src_txt for k in ["CAMPUS", "UNIVERSITY", "COLLEGE"]):
            suffix_str = "UNVPD"
        elif "POLICE" in src_txt:
            suffix_str = "PD"
        elif "SHERIFF" in src_txt:
            suffix_str = "SHRF"
        elif "FIRE" in src_txt or "EMERGENCY" in src_txt:
            suffix_str = "FEMS"
        elif "SWAT" in src_txt or "S.W.A.T" in src_txt:
            suffix_str = "SWAT"
        elif "TRANSIT AUTHORITY" in src_txt:
            suffix_str = "TA"
        else:
            for word in re.split(r'\W+', entity.upper()):
                if verbose > 1:
                    print(f"CHANNEL NAME AUTO SUFFIX ENTITY WORD : {word}")

            # fallback: first char of first 5 non-excluded words in entity
            suffix_str = ''.join(
                word[0] for word in re.split(r'\W+', entity.upper())
                if word and word not in EXCLUDED_CHAN_NAME_WORDS            
            )[:5]

            if not suffix_str:
                suffix_str = DEFAULT_CHAN_NAME_SUFFIX   

            # Step 4: Clean remaining text and trim to fit
            #remaining_len = max_length - len(prefix + suffix_str)

            #if remaining_len > 0:
            #    src_clean = re.sub(r'[^A-Z0-9]', '', src_txt)
            #
            #    if verbose > 1:
            #        print(f"CHANNEL NAME AUTO SUFFIX TEXT SOURCE CLEANED : {source_clean}")
            #
            #    suffix_str += src_clean[:remaining_len]

            #if verbose > 1:
            #    print(f"CHANNEL NAME AUTO SUFFIX CLEANED AND TRIMMED : {suffix_str}")

        if verbose > 1:
            print(f"CHANNEL NAME AUTO SUFFIX : {suffix_str}") 

    base = (re.sub(r'[^A-Z0-9]', '', prefix_str.upper() + suffix_str.upper()))[:max_length]

   # Step 5: Only append a number if duplicate is found
    if base not in seen:
        seen[base] = {'count': 1, 'assigned': [(base, len(seen))]}
        return base, None, None  # no retroactive update needed

    entry = seen[base]
    entry['count'] += 1
    suffix = str(entry['count'])

    # On second use, retroactively rename the first one
    original_idx = None
    new_first = None

    if entry['count'] == 2:
        original_name, original_idx = entry['assigned'][0]
        new_first = original_name[:max_length - 1] + '1'
        entry['assigned'][0] = (new_first, original_idx)
        if verbose > 0:
            print(f"CHANNEL NAME Retroactively rename first instance : {original_name} → {new_first}")

    trimmed = base[:max_length - len(suffix)]
    new_name = trimmed + suffix
    entry['assigned'].append((new_name, len(seen)))

    return new_name, original_idx, new_first

def gen_radio_conf(radio, results, chan_offset=1, chan_name_prefix_src='city', chan_name_suffix_src='auto'):
    if radio not in SUPPORTED_RADIOS:
        raise ValueError(f"Unsupported radio model: {radio}. Supported models: {', '.join(SUPPORTED_RADIOS)}")

    radio_conf_vars = SUPPORTED_RADIOS[radio]

    csv_filename = CSV_FILE_PREFIX + radio + CSV_FILE_SUFFIX        

    if radio == 'tdh8':
        with open(csv_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(radio_conf_vars.get('csv_headers'))

            chan_name_prefix_str = ''

            if chan_name_prefix_src not in ['city', 'callsign']:
                chan_name_prefix_str = chan_name_prefix_src
                chan_name_prefix_src = 'custom'            

            chan_name_suffix_str = ''

            if chan_name_suffix_src not in ['auto', 'freq']:                
                chan_name_suffix_str = chan_name_suffix_src
                chan_name_suffix_src = 'custom'

            seen_names = {}       
            formatted_rows = []

            for idx, row in enumerate(results, start=chan_offset):
                freq, call_sign, entity, city, state, zipc, service, eligibility, status = row

                if chan_name_prefix_src == 'city':
                    chan_name_prefix_str = city
                elif chan_name_prefix_src == 'callsign':
                    chan_name_prefix_str = call_sign

                if chan_name_suffix_src == 'freq':
                    chan_name_suffix_str = freq

                # Generate name and capture potential retroactive rename
                name, retro_idx, retro_name = gen_radio_chan_name(
                    entity, eligibility, seen_names,
                    chan_name_prefix_src, chan_name_prefix_str,
                    chan_name_suffix_src, chan_name_suffix_str,
                    radio_conf_vars.get('chan_name_max_len', DEFAULT_CHAN_NAME_MAX_LEN)
                )

                formatted_row = radio_conf_vars.get('csv_default_row').copy()
                formatted_row[0] = str(idx)
                formatted_row[1] = name
                formatted_row[2] = f"{float(freq):.5f}"

                formatted_rows.append(formatted_row)

                # Retroactively rename earlier assigned name in list
                if retro_idx is not None:
                    formatted_rows[retro_idx][1] = retro_name

            for row in formatted_rows:
                writer.writerow(row)

        print(f"\nCSV file written: {csv_filename}")              

def download_with_progress(url, filename):
    print(f"Downloading: {url}")

    resp = requests.get(url, stream=True)
    total = int(resp.headers.get('content-length', 0))

    with open(filename, 'wb') as f, tqdm(total=total, unit='B', unit_scale=True, desc=filename) as pbar:
        for chunk in resp.iter_content(1024):
            if chunk:
                f.write(chunk)
                pbar.update(len(chunk))

def extract_zip(zip_path, target_dir):
    print(f"Extracting {zip_path}")

    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(target_dir)

def find_file(directory, filename):
    for path in glob.glob(os.path.join(directory, '**', filename), recursive=True):
        return path
    return None

def detect_column_count(filepath, sample_lines=100):
    with open(filepath, encoding='latin1', errors='ignore') as f:
        reader = csv.reader(f, delimiter='|')

        return max(len(row) for _, row in zip(range(sample_lines), reader))
    
def debug_sql(query, params):
    try:
        printable_query = query

        for p in params:
            val = f"'{p}'" if isinstance(p, str) else str(p)
            printable_query = printable_query.replace('?', val, 1)

        print("Executed SQL Query:")
        print(printable_query)
    except Exception as e:
        print(f"Error generating debug SQL: {e}")

def table_exists(conn, table_name):
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def create_table(cursor, table_name, column_count):
    cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    cols = [f'"col_{i}" TEXT' for i in range(column_count)]
    cursor.execute(f'CREATE TABLE "{table_name}" ({", ".join(cols)})')

def init_loaded_zips_table(conn): 
    conn.execute(f'DROP TABLE IF EXISTS "{ZIPS_LOADED_TABLE_NAME}"')
    conn.execute(f'''
        CREATE TABLE "{ZIPS_LOADED_TABLE_NAME}" (
            zip_filename TEXT PRIMARY KEY,
            date TEXT
        )
    ''')
    conn.commit()

def zip_already_loaded(conn, zip_filename):
    cursor = conn.execute('SELECT date FROM loaded_zips WHERE zip_filename = ?', (zip_filename,))
    return cursor.fetchone() is not None

def set_zip_as_loaded(conn, zip_filename):
    timestamp = datetime.utcnow().isoformat()

    conn.execute('''
        INSERT OR REPLACE INTO loaded_zips (zip_filename, date)
        VALUES (?, ?)
    ''', (zip_filename, timestamp))
    conn.commit()

def load_dat_to_sqlite(conn, filepath, table, new_db=False):
    cursor = conn.cursor()
    column_count = detect_column_count(filepath)

    if not table_exists(conn, table):
        create_table(cursor, table, column_count)
    else:
        if not new_db:
            print(f"Table {table} exists. Using existing table and row rata. Use -cc / --clear-cache to clear SQL tables")    
            return
        
        print(f"Table {table} exists. Using existing table and appending row data. Use -cc or --clear-cache to clear SQL tables")
            
    print(f"Loading {table} from {filepath}")

    with open(filepath, encoding='latin1', errors='ignore') as f:
        reader = csv.reader(f, delimiter='|')
        rows = []

        for row in reader:
            if len(row) < column_count:
                row += [''] * (column_count - len(row))
            elif len(row) > column_count:
                row = row[:column_count]
            rows.append(row)

        placeholders = ','.join(['?'] * column_count)
        cursor.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
    conn.commit()

    print(f"Inserted {len(rows)} rows into {table}")

def search_freqs(conn, zip_codes=None, city=None, service_codes=None, status='active'):
    cursor = conn.cursor()

    try:
        if not city and not zip_codes:
            print("Error: Must provide ZIP code(s) or city.")
            return
        
        if not service_codes:
            print("Error: Must provide service code(s).")
            return        
        
        lm_table_exists = False;

        if table_exists(conn, 'LM'):
            lm_table_exists = True;

        base_query = '''
        SELECT
            EM.col_7 AS frequency_assigned,
            EM.col_4 as call_sign,
            EN.col_7 AS entity_name,
            EN.col_16 AS city,
            EN.col_17 AS state,
            EN.col_18 AS zip_code,
            HD.col_6 AS service_code,'''
        
        if lm_table_exists:
            base_query += '\n            LM.col_6 AS eligibility,'
        
        # base_query += '''
        #     HD.col_5 as status
        # FROM HD
        # JOIN EM ON HD.col_1 = EM.col_1
        # JOIN EN ON HD.col_1 = EN.col_1'''

        base_query += '''
            HD.col_5 as status       
        FROM EM
        JOIN HD ON EM.col_1 = HD.col_1
        JOIN EN ON HD.col_1 = EN.col_1'''
        
        if lm_table_exists:
            base_query += '\n        LEFT JOIN LM ON HD.col_1 = LM.col_1'

        base_query += '''
        WHERE HD.col_6 IN ({})
        '''.format(','.join(['?'] * len(service_codes)))

        params = service_codes

        if zip_codes:
            placeholders = ','.join('?' for _ in zip_codes)
            base_query += f' AND EN.col_18 IN ({placeholders})'
            params.extend(zip_codes)
        if city:
            base_query += ' AND EN.col_16 = ?'
            params.append(city.upper())

        if status.lower() == 'active':
            base_query += " AND HD.col_5 = 'A'"
        elif status.lower() == 'expired':
            base_query += " AND HD.col_5 = 'E'"

        #This causes various expected frequencies to be missing from the results
        #base_query += ' GROUP BY EM.col_1'

        #Not sure of the ramifications of what results this causes to be missing
        #The intent is to filter duplicate frequencies
        base_query += ' GROUP BY frequency_assigned'

        base_query += ' ORDER BY frequency_assigned ASC'

        if verbose:
            debug_sql(base_query, params)

        cursor.execute(base_query, tuple(params))
        results = cursor.fetchall()

        if not results:
            print("No results found.")
            return
        
        return results

    except sqlite3.OperationalError as e:
        print(f"Query error: {e}")

def list_available_zip_files():
    print("Fetching list of ZIP files...")

    resp = requests.get(BASE_URL)

    if resp.status_code != 200:
        print("Failed to fetch the ZIP file list.")
        return

    soup = BeautifulSoup(resp.text, 'html.parser')
    links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].startswith('l_') and a['href'].endswith('.zip')]

    for link in links:
        print(link)

def main():
    parser = argparse.ArgumentParser(description=SELF_DESC)
    parser.add_argument('-lr', '--list-radios', action='store_true', help="List supported radio models")
    parser.add_argument('-r', '--radio', choices=SUPPORTED_RADIOS.keys(), help="Output result formatted for a specific radio (currently only: tdh8)")
    parser.add_argument('-co', '--channel-offset', type=int, default=1, help="Starting number for channel field in CSV output. Default: 1")
    parser.add_argument('-cp', '--channel-prefix', default='city', help="Method used to generate channel name prefixes : city (Default. The first two characters of the city name if its one word, or the first character of each word in the city name e.g, NY), callsign, or a custom string. The channel name will be automatically trimmed to the max length for the model radio specified")
    parser.add_argument('-cs', '--channel-suffix', default='auto', help="Method used to generate channel name suffixes : auto (Default. The suffix is obtained dynamically based on keywords in the entity and eligibility fields, or the first character from the first 5 words in the entity field), freq, or a custom string. The channel name will be automatically trimmed to the max length for the model radio specified")
    parser.add_argument('-z', '--zip', help="ZIP code(s) to search, comma-separated")
    parser.add_argument('-c', '--city', help="City to search")
    parser.add_argument('-ls', '--list-services', action='store_true', help="List available radio service code(s) to search")
    parser.add_argument('-s', '--service', help="Radio service code(s) to search, comma-separated (e.g., PW,IG)")
    parser.add_argument('--status', choices=['active', 'expired', 'any'], default='active', help="License status filter. Default : active")
    parser.add_argument('-lz', '--list-zipfiles', action='store_true', help="List available ZIP files to download from FCC")

    zf_arg_help_msg = 'Comma-separated ZIP filenames to download and load into database (e.g., l_LMpriv.zip,l_AM.zip). Default : ' + ", ".join(DEFAULT_ZIPFILES)

    parser.add_argument('-zf', '--zipfiles', help=zf_arg_help_msg)

    #parser.add_argument('-cc', '--clear-cache', action='store_true', help="Clear cached ZIP files and SQL tables. Default is to use cached data if it exist")
    parser.add_argument('-cc', '--clear-cache', action='store_true', help="Clear database, re-download ZIP files, and load into into new database. Default is to use cached data if it exist")
    parser.add_argument('-v', '--verbose', action='count', default=0,  help="Increase output verbosity (e.g., -v, -vv, -vvv)")
 
    args = parser.parse_args()

    if args.verbose:
        global verbose
        verbose = args.verbose

    if args.list_radios:
        print("Supported radio models:")
        print(", ".join(SUPPORTED_RADIOS))
        sys.exit(0)

    if args.list_services:
        cursor = sqlite3.connect(DB_FILE).cursor()
        cursor.execute("SELECT DISTINCT col_6 FROM HD ORDER BY col_6")
        available_services = [row[0] for row in cursor.fetchall()]
        print("Available service codes in the database:")
        print(', '.join(available_services))
        sys.exit(0)

    if args.list_zipfiles:
        #list_available_zip_files()
        print("Supported ZIP files are:")
        print(", ".join(sorted(SUPPORTED_ZIPFILES)))        
        sys.exit(0)

    if not args.zip and not args.city:
        parser.error("You must specify either --zip or --city.")

    zip_codes = [z.strip() for z in args.zip.split(',')] if args.zip else None

    if not args.service:
        parser.error("You must specify a minimum of one service code with --service (e.g., PW,IG). Use -ls, --list-services to list available service codes")   

    service_codes = [s.strip().upper() for s in args.service.split(',')] if args.service else None

    zip_filenames = [z.strip() for z in args.zipfiles.split(',')] if args.zipfiles else DEFAULT_ZIPFILES

    invalid = [z for z in zip_filenames if z not in SUPPORTED_ZIPFILES]

    if invalid:
        print("Error: One or more specified ZIP files are not supported:")
        print(", ".join(invalid))
        print("Supported ZIP files are:")
        print(", ".join(sorted(SUPPORTED_ZIPFILES)))
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(DB_FILE):
        if args.clear_cache:
            print(f"{DB_FILE} exists, but re-creating database because --clear-cache was specified")
            os.remove(DB_FILE)
        else:
            print(f"{DB_FILE} exists. Using existing database. Use -cc / --clear-cache to re-create database")

    conn = sqlite3.connect(DB_FILE)

    if not table_exists(conn, 'loaded_zips'):
        init_loaded_zips_table(conn)

    for zip_filename in zip_filenames:
        new_zip_db = False

        if not zip_already_loaded(conn, zip_filename):
            new_zip_db = True

        zip_filename_full_path = DATA_DIR + '/' + zip_filename
        zip_url = BASE_URL + zip_filename

        #if not os.path.exists(zip_filename_full_path):
        if new_zip_db:
            #print(f"{zip_filename} doesn't exist, downloading")
            download_with_progress(zip_url, zip_filename_full_path)
        elif args.clear_cache:
            #print(f"{zip_filename} exists, but re-downloading because --clear-cache was specified")
            print(f"{zip_filename} previously downloaded, but re-downloading because --clear-cache was specified")
            download_with_progress(zip_url, DATA_DIR + '/' + zip_filename)
        else:
            #print(f"{zip_filename} exists. Using existing file. Use -cc / --clear-cache to re-download ZIP files")
            print(f"{zip_filename} previously downloaded. Using existing data. Use -cc / --clear-cache to re-download ZIP files")

        extract_dir = DATA_DIR + '/' + zip_filename.replace('.zip', '')

        #if not os.path.exists(extract_dir):
        if new_zip_db or args.clear_cache:
            os.makedirs(extract_dir, exist_ok=True)
            extract_zip(zip_filename_full_path, extract_dir)
        #elif args.clear_cache:
            #print(f"{extract_dir} directory exists, but re-extracting because --clear-cache was specified")
            #extract_zip(zip_filename_full_path, extract_dir)
        #else:
            #print(f"{extract_dir} directory exists. Skipping extraction. Use -cc / --clear-cache to re-extract ZIP files")

            dat_files = [('EN.dat', 'EN'), ('HD.dat', 'HD'), ('EM.dat', 'EM'), ('LM.dat', 'LM')]

            for fname, table in dat_files:
                fpath = find_file(extract_dir, fname)
                if fpath:
                    load_dat_to_sqlite(conn, fpath, table, new_zip_db)
                else:
                    print(f"{fname} not found in {extract_dir}.")

            print(f"Setting {zip_filename} as loaded in database")
            set_zip_as_loaded(conn, zip_filename)

            #Delete ZIP file downloaded and extracted contents
            if os.path.exists(zip_filename_full_path):
                print(f"Removing {zip_filename_full_path}") 
                os.remove(zip_filename_full_path)

            #Delete extracted ZIP file contents
            if os.path.exists(extract_dir):
                print(f"Removing {extract_dir} and contents")
                shutil.rmtree(extract_dir)

    search_results = search_freqs(
        conn,
        zip_codes=zip_codes,
        city=args.city,
        service_codes=service_codes,
        status=args.status
    )

    conn.close()

    if search_results:
        label = f"ZIP(s) {', '.join(zip_codes)}" if zip_codes else f"City {args.city}"

        print(f"\nResults for {label} and Service Codes {', '.join(service_codes)} (Status: {args.status}):")

        for row in search_results:
            freq, call_sign, name, city, state, zipc, service, eligibility, status = row
            print(f"Freq: {freq} MHz, Call Sign: {call_sign}, Entity: {name}, Location: {city}, {state} {zipc}, Service: {service}, Eligibility: {eligibility}, Status: {status}")

        if args.radio:
            try:
                gen_radio_conf(args.radio, search_results, args.channel_offset, args.channel_prefix, args.channel_suffix)
            except ValueError as e:
                print(f"Error: {e}")

if __name__ == '__main__':
    main()
