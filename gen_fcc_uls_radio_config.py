#!/usr/bin/python3

import os
import sys
import csv
import zipfile
import sqlite3
import argparse
import requests
from tqdm import tqdm
import glob
from bs4 import BeautifulSoup
from datetime import datetime

# Constants
BASE_URL = 'https://data.fcc.gov/download/pub/uls/complete/'
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
DATA_DIR = os.getcwd() + '/uls_data'
DB_FILE = DATA_DIR + '/uls_lmpriv.db'
ZIPS_LOADED_TABLE_NAME = 'loaded_zips'
SUPPORTED_RADIOS = ['tdh8']
CSV_FILE_PREFIX = ''
CSV_FILE_SUFFIX = '_frequencies-' + datetime.today().strftime('%Y%m%d%H%M%S') + '.csv'

CSV_HEADERS_TDH8 = [
    "Location", "Name", "Frequency", "Duplex", "Offset", "Tone", "rToneFreq", "cToneFreq",
    "DtcsCode", "DtcsPolarity", "RxDtcsCode", "CrossMode", "Mode", "TStep", "Skip",
    "Power", "Comment", "URCALL", "RPT1CALL", "RPT2CALL", "DVCODE"
]
CSV_DEFAULT_ROW_TDH8 = [
    "", "", "", "", "0.00000", "", "88.5", "88.5", "023", "NN", "023", "Tone->Tone",
    "FM", "5.0", "", "8.0W", "", "", "", "", ""
]

csv.field_size_limit(sys.maxsize)

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

    if (not table_exists(conn, table)):
        create_table(cursor, table, column_count)
    else:
        if (not new_db):
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

def search_frequencies(conn, zip_codes=None, city=None, service_codes=None, status='active', radio=None):
    cursor = conn.cursor()
    try:
        if not city and not zip_codes:
            print("Error: Must provide ZIP code(s) or city.")
            return
        
        if not service_codes:
            print("Error: Must provide service code(s).")
            return        
        
        lm_table_exists = False;

        if (table_exists(conn, 'LM')):
            lm_table_exists = True;

        base_query = '''
        SELECT
            EM.col_7 AS frequency_assigned,
            EN.col_7 AS entity_name,
            EN.col_16 AS city,
            EN.col_17 AS state,
            EN.col_18 AS zip_code,
            HD.col_6 AS service_code,'''
        
        if (lm_table_exists):
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
        
        if (lm_table_exists):
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

        debug_sql(base_query, params)

        cursor.execute(base_query, tuple(params))
        results = cursor.fetchall()
        label = f"ZIP(s) {', '.join(zip_codes)}" if zip_codes else f"City {city}"

        print(f"\nResults for {label} and Service Codes {', '.join(service_codes)} (Status: {status}):")

        for row in results:
            freq, name, city, state, zipc, service, eligibility, status = row
            print(f"Freq: {freq} MHz, Entity: {name}, Location: {city}, {state} {zipc}, Service: {service}, Eligibility: {eligibility}, Status: {status}")

        if not results:
            print("No results found.")
            return

        if radio == 'tdh8':
            csv_filename = CSV_FILE_PREFIX + radio + CSV_FILE_SUFFIX

            with open(csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(CSV_HEADERS_TDH8)

                for idx, row in enumerate(results, start=1):
                    freq = row[0]
                    name = str(int(float(freq) * 1000))[:5]  # first five digits without dot
                    formatted_row = CSV_DEFAULT_ROW_TDH8.copy()
                    formatted_row[0] = str(idx)
                    formatted_row[1] = name
                    formatted_row[2] = f"{float(freq):.5f}"
                    writer.writerow(formatted_row)

            print(f"\nCSV file written: {csv_filename}")
        else:
            for row in results:
                freq, name, city, state, zipc, service, eligibility, status = row

                print(f"Freq: {freq} MHz, Entity: {name}, Location: {city}, {state} {zipc}, Service: {service}, Eligibility: {eligibility}, Status: {status}")

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
    parser = argparse.ArgumentParser(description="FCC ULS Database Loader and Frequency Search")
    parser.add_argument('-lr', '--list-radios', action='store_true', help="List supported radio models")
    parser.add_argument('-r', '--radio', choices=SUPPORTED_RADIOS, help="Output result formatted for a specific radio (currently only: tdh8)")
    parser.add_argument('-z', '--zip', help="ZIP code(s) to search, comma-separated")
    parser.add_argument('-c', '--city', help="City to search")
    parser.add_argument('-ls', '--list-services', action='store_true', help="List available radio service code(s) to search")
    parser.add_argument('-s', '--service', help="Radio service code(s) to search, comma-separated (e.g. PW,IG)")
    parser.add_argument('--status', choices=['active', 'expired', 'any'], default='active', help="License status filter. Default : active")
    parser.add_argument('-lz', '--list-zipfiles', action='store_true', help="List available ZIP files to download from FCC")
    zf_arg_help_msg = 'Comma-separated ZIP filenames to download and load (e.g. l_LMpriv.zip,l_AM.zip). Default : ' + ", ".join(DEFAULT_ZIPFILES)
    parser.add_argument('-zf', '--zipfiles', help=zf_arg_help_msg)
    parser.add_argument('-cc', '--clear-cache', action='store_true', help="Clear cached ZIP files and SQL tables. Default is to use cached data if it exist")
    args = parser.parse_args()

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
        parser.error("You must specify a minimum of one service code with --service (e.g. PW,IG). Use -ls, --list-services to list available service codes")   

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

    if (os.path.exists(DB_FILE)):
        if (args.clear_cache):
            print(f"{DB_FILE} exists, but re-creating database because --clear-cache was specified")
            os.remove(DB_FILE)
        else:
            print(f"{DB_FILE} exists. Using existing database. Use -cc / --clear-cache to re-create database")

    conn = sqlite3.connect(DB_FILE)

    if (not table_exists(conn, 'loaded_zips')):
        init_loaded_zips_table(conn)

    for zip_filename in zip_filenames:
        zip_filename_full_path = DATA_DIR + '/' + zip_filename
        zip_url = BASE_URL + zip_filename

        if os.path.exists(zip_filename_full_path):
            if args.clear_cache:
                print(f"{zip_filename} exists, but re-downloading because --clear-cache was specified")
                download_with_progress(zip_url, DATA_DIR + '/' + zip_filename)
            else:
                print(f"{zip_filename} exists. Using existing file. Use -cc / --clear-cache to re-download ZIP files")
        else:
            print(f"{zip_filename} doesn't exist, downloading")
            download_with_progress(zip_url, zip_filename_full_path)

        extract_dir = DATA_DIR + '/' + zip_filename.replace('.zip', '')

        if not os.path.exists(extract_dir):
            os.makedirs(extract_dir, exist_ok=True)
            extract_zip(zip_filename_full_path, extract_dir)
        elif (args.clear_cache):
            print(f"{extract_dir} directory exists, but re-extracting because --clear-cache was specified")
            extract_zip(zip_filename_full_path, extract_dir)
        else:
            print(f"{extract_dir} directory exists. Skipping extraction. Use -cc / --clear-cache to re-extract ZIP files")

        new_zip_db = False

        if (not zip_already_loaded(conn, zip_filename)):
            new_zip_db = True

        dat_files = [('EN.dat', 'EN'), ('HD.dat', 'HD'), ('EM.dat', 'EM'), ('LM.dat', 'LM')]

        for fname, table in dat_files:
            fpath = find_file(extract_dir, fname)
            if fpath:
                load_dat_to_sqlite(conn, fpath, table, new_zip_db)
            else:
                print(f"{fname} not found in {extract_dir}.")

        if (new_zip_db):
          set_zip_as_loaded(conn, zip_filename)

    search_frequencies(
        conn,
        zip_codes=zip_codes,
        city=args.city,
        service_codes=service_codes,
        status=args.status,
        radio=args.radio
    )

    conn.close()

if __name__ == '__main__':
    main()
