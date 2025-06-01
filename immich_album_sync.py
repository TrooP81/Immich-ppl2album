import requests
import json
import re # For UUID validation
import logging # Using Python's standard logging library
import os
import time # For adding delays in recursive runs
from dotenv import load_dotenv # For loading .env file
from urllib.parse import urljoin # For robust URL construction
import fnmatch # For filename pattern matching

# --- Load Environment Variables ---
load_dotenv()

# --- Configuration (from .env file) ---
IMMICH_BASE_URL = os.getenv("IMMICH_BASE_URL")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY")
TARGET_ALBUM_ID = os.getenv("IMMICH_ALBUM_ID") # Direct Album ID
PERSON_NAMES_STR = os.getenv("IMMICH_PERSONS", "") # Comma-separated string of person names
NAME_FILTERS_STR = os.getenv("IMMICH_NAME_FILTERS", "") # Comma-separated string of filename filters
SYNC_INTERVAL_SECONDS_STR = os.getenv("SYNC_INTERVAL_SECONDS", "3600") # Default to 1 hour (3600 seconds)

# --- Setup Logging ---
# Adjust level to logging.DEBUG to see more detailed logs from the modified function
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Validate Essential Configuration ---
if not all([IMMICH_BASE_URL, IMMICH_API_KEY, TARGET_ALBUM_ID]):
    logger.error("Essential environment variables (IMMICH_BASE_URL, IMMICH_API_KEY, TARGET_ALBUM_ID) are not set. Exiting.")
    exit(1)

# Ensure base URL doesn't have trailing slash for cleaner joining
if IMMICH_BASE_URL.endswith('/'):
    IMMICH_BASE_URL = IMMICH_BASE_URL[:-1]

try:
    SYNC_INTERVAL_SECONDS = int(SYNC_INTERVAL_SECONDS_STR)
    if SYNC_INTERVAL_SECONDS <= 0:
        logger.warning("SYNC_INTERVAL_SECONDS must be a positive integer. Defaulting to 3600 seconds.")
        SYNC_INTERVAL_SECONDS = 3600
except ValueError:
    logger.warning(f"Invalid SYNC_INTERVAL_SECONDS value '{SYNC_INTERVAL_SECONDS_STR}'. Defaulting to 3600 seconds.")
    SYNC_INTERVAL_SECONDS = 3600


# --- API Headers ---
HEADERS = {
    "Accept": "application/json",
    "x-api-key": IMMICH_API_KEY,
    "Content-Type": "application/json" # Content-Type is more for PUT/POST but often sent
}

# --- Helper function for UUID validation ---
def is_valid_uuid(uuid_string):
    """Checks if a string is a valid UUID format."""
    if not uuid_string: return False
    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    return bool(uuid_pattern.match(uuid_string))

# --- 1. Get Person IDs for specified names (MODIFIED FUNCTION from previous step) ---
def get_person_ids_by_names(person_names_list):
    """Fetches all people from Immich and returns IDs for the given names."""
    if not person_names_list:
        logger.info("No person names provided to search for.")
        return []

    logger.info(f"Searching for Person IDs for names: {', '.join(person_names_list)}")
    person_ids_found = []
    api_url = f"{IMMICH_BASE_URL}/api/people"
    try:
        response = requests.get(api_url, headers=HEADERS)
        response.raise_for_status()
        
        api_response_data = response.json()
        logger.debug(f"Raw response from /api/people: {json.dumps(api_response_data, indent=2)}")
        logger.debug(f"Type of api_response_data from /api/people: {type(api_response_data)}")

        actual_people_list = []
        if isinstance(api_response_data, dict) and 'people' in api_response_data:
            actual_people_list = api_response_data['people']
            logger.debug("Interpreted /api/people response as a dictionary with a 'people' key.")
        elif isinstance(api_response_data, list):
            actual_people_list = api_response_data
            logger.debug("Interpreted /api/people response as a direct list.")
        else:
            logger.error(f"Unexpected JSON structure from {api_url}. Got type: {type(api_response_data)}")
            content_to_log = str(api_response_data)[:500] if not isinstance(api_response_data, (bytes)) else "Binary data or too large to log"
            if isinstance(api_response_data, (dict, list)):
                 content_to_log = json.dumps(api_response_data, indent=2)
            logger.error(f"Response content snippet: {content_to_log}")
            return []

        if not actual_people_list:
            logger.info("No person entries found in the processed API response from /api/people.")
            return []

        people_name_to_id = {}
        for person in actual_people_list:
            if isinstance(person, dict) and 'name' in person and 'id' in person and person.get('name') is not None:
                person_name_val = person['name']
                if isinstance(person_name_val, str):
                    people_name_to_id[person_name_val.lower()] = person['id']
                else:
                    logger.warning(f"Person entry has a non-string name: ID {person.get('id')}, Name Type {type(person_name_val)}. Skipping this entry for name mapping.")
            else:
                logger.warning(f"Skipping person entry due to missing 'name', 'id', null name, or not being a dictionary: {str(person)[:100]}")
        
        if not people_name_to_id:
            logger.warning("Could not build a name-to-ID map from the /api/people data. This means no persons had valid names and IDs, or the list was empty.")

        for name in person_names_list:
            stripped_lowercase_name = name.strip().lower()
            person_id = people_name_to_id.get(stripped_lowercase_name)
            if person_id:
                if is_valid_uuid(person_id):
                    person_ids_found.append(person_id)
                    logger.info(f"Found Person ID for '{name}': {person_id}")
                else:
                    logger.warning(f"Found person '{name}' but their ID '{person_id}' is not a valid UUID. Skipping.")
            else:
                logger.warning(f"Person with name '{name}' (searched as '{stripped_lowercase_name}') not found in Immich's populated name list.")
        
        if not person_ids_found:
            logger.warning(f"No person IDs were resolved for any of the specified input names: {person_names_list}")
            if people_name_to_id:
                 logger.info(f"Available names extracted from Immich (lowercase): {list(people_name_to_id.keys())}")
            else:
                logger.info("No names were available from Immich to match against.")

        return list(set(person_ids_found))

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching people from {api_url}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}, content: {e.response.text[:300]}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response from {api_url}: {e}")
        response_text = response.text if 'response' in locals() and hasattr(response, 'text') else 'No response text available'
        logger.error(f"Response content causing decode error: {response_text[:500]}")
        return []
    except KeyError as e:
        logger.error(f"Encountered missing key in person data (e.g., 'name' or 'id' was expected but not found): {e}")
        logger.error("This usually means a person object in the list from Immich was malformed.")
        return []
    except Exception as e:
        logger.error(f"An unexpected error occurred in get_person_ids_by_names: {e}", exc_info=True)
        return []

# --- 2. Fetch Asset IDs for given Person IDs, applying name filters (NOW WITH AND/OR LOGIC) ---
def get_assets_for_person_ids(initial_person_ids_list, name_filters_list):
    """
    Fetches asset IDs based on person_ids.
    1. Finds assets where ALL persons in initial_person_ids_list are present together (AND logic).
    2. Finds assets for EACH person in initial_person_ids_list individually (OR logic).
    Combines unique asset IDs from all searches, applying filename filters to each search.
    """
    if not initial_person_ids_list:
        logger.info("No person IDs provided to fetch assets for (in get_assets_for_person_ids).")
        return []

    # Compile name filters once for use in the helper function
    compiled_name_filters = [pattern.strip().lower() for pattern in name_filters_list if pattern.strip()]
    if compiled_name_filters:
        logger.info(f"Filename filters will be applied during asset searches: {', '.join(name_filters_list)}")


    # --- Nested helper function to perform the actual API calls and filtering ---
    def _fetch_page_by_page(person_ids_for_api_call, log_label):
        """
        Fetches assets for a specific set of person_ids, paginating through results.
        Applies filename filters to the fetched assets.
        Returns a set of asset_ids.
        """
        logger.info(f"Starting asset search ({log_label}) for Person ID(s): {', '.join(person_ids_for_api_call)}")
        
        current_call_asset_ids = set()
        api_url = f"{IMMICH_BASE_URL}/api/search/metadata"
        page = 1
        page_size = 1000 # As per API docs for /search/metadata

        while True:
            payload = {
                "personIds": person_ids_for_api_call,
                "size": page_size,
                "page": page,
            }
            logger.debug(f"Searching assets ({log_label}) with payload to {api_url}: {json.dumps(payload)}")
            
            try:
                response = requests.post(api_url, headers=HEADERS, json=payload)
                response.raise_for_status()
                data = response.json()
                
                assets_data = data.get('assets', {})
                assets = assets_data.get('items', [])
                
                if not assets:
                    logger.debug(f"No more assets found ({log_label}) for Person ID(s) {', '.join(person_ids_for_api_call)} on page {page}.")
                    break
                
                logger.debug(f"Processing {len(assets)} assets from page {page} ({log_label}) for Person ID(s) {', '.join(person_ids_for_api_call)}.")
                for asset in assets:
                    asset_id = asset.get('id')
                    original_filename = asset.get('originalFileName')

                    if not asset_id or not is_valid_uuid(asset_id):
                        logger.warning(f"Skipping asset with invalid or missing ID ({log_label}): {asset.get('id', 'N/A')}")
                        continue

                    if compiled_name_filters: # Use pre-compiled filters from outer scope
                        if not original_filename:
                            logger.debug(f"Asset ID {asset_id} ({log_label}) has no originalFileName, cannot apply name filter. Skipping.")
                            continue
                        
                        filename_matches_filter = False
                        for pattern in compiled_name_filters:
                            if fnmatch.fnmatch(original_filename.lower(), pattern):
                                filename_matches_filter = True
                                break
                        if not filename_matches_filter:
                            logger.debug(f"Asset ID {asset_id} (filename: {original_filename}) ({log_label}) did not match name filters. Skipping.")
                            continue
                    
                    current_call_asset_ids.add(asset_id)
                    # Minimal log here to avoid too much verbosity if many assets
                    # logger.debug(f"Qualified Asset ID ({log_label}): {asset_id}") 

                if len(assets) < page_size:
                    logger.debug(f"Reached end of assets ({log_label}) for Person ID(s) {', '.join(person_ids_for_api_call)} (last page was not full).")
                    break
                page += 1

            except requests.exceptions.RequestException as e:
                logger.error(f"Error searching assets ({log_label}) from {api_url} for Person ID(s) {', '.join(person_ids_for_api_call)}: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}, content: {e.response.text[:300]}")
                break 
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON response ({log_label}) from {api_url} for Person ID(s) {', '.join(person_ids_for_api_call)}: {e}")
                logger.error(f"Response content: {response.text if 'response' in locals() else 'No response object'}")
                break
        
        logger.info(f"Found {len(current_call_asset_ids)} assets for ({log_label}) for Person ID(s) {', '.join(person_ids_for_api_call)} (after filters).")
        return current_call_asset_ids
    # --- End of nested helper function _fetch_page_by_page ---


    # --- Main logic for get_assets_for_person_ids starts here ---
    all_collected_asset_ids = set() # Final set of all unique asset IDs from all searches

    # 1. "AND" logic: Fetch assets containing ALL specified persons together.
    # This is how the API behaves when multiple personIds are in the list.
    if len(initial_person_ids_list) > 0:
        log_label_and = f"AND-logic (all {len(initial_person_ids_list)} persons together)"
        # logger.info(f"Initiating asset search for: {log_label_and}") # _fetch_page_by_page will log its start
        assets_from_and_search = _fetch_page_by_page(initial_person_ids_list, log_label_and)
        all_collected_asset_ids.update(assets_from_and_search)
        logger.info(f"After {log_label_and}, total unique assets collected: {len(all_collected_asset_ids)}")

    # 2. "OR" logic: Fetch assets for EACH specified person individually.
    # This is only meaningfully different from the "AND" logic if there's more than one person.
    if len(initial_person_ids_list) > 1:
        logger.info(f"Initiating asset searches for OR-logic (each of the {len(initial_person_ids_list)} persons individually)")
        for person_id in initial_person_ids_list:
            log_label_or = f"OR-logic (person: {person_id[:8]}...)" # Log first 8 chars of UUID for brevity
            assets_from_or_search = _fetch_page_by_page([person_id], log_label_or) # API needs a list for personIds
            
            # Log how many *new* assets were found by this specific OR search
            newly_added_count = len(assets_from_or_search - all_collected_asset_ids)
            all_collected_asset_ids.update(assets_from_or_search)
            logger.info(f"For {log_label_or}: found {len(assets_from_or_search)} assets, {newly_added_count} were new. Total unique assets: {len(all_collected_asset_ids)}")
    elif len(initial_person_ids_list) == 1:
        logger.info("Only one person specified, so the initial 'AND-logic' search already covers all assets for this person. Skipping redundant individual 'OR-logic' searches.")


    logger.info(f"Completed all asset searches. Total unique assets found: {len(all_collected_asset_ids)}.")
    return list(all_collected_asset_ids)

# --- 3. Get Asset IDs currently in the target album ---
def get_asset_ids_in_album(album_id):
    """Fetches all asset IDs currently in the specified album."""
    logger.info(f"Fetching assets currently in album ID: {album_id}")
    asset_ids_in_album = set()
    api_url = f"{IMMICH_BASE_URL}/api/albums/{album_id}"
    try:
        response = requests.get(api_url, headers=HEADERS)
        response.raise_for_status()
        album_data = response.json()
        
        album_assets = album_data.get('assets', [])
        if not isinstance(album_assets, list):
            logger.warning(f"Album data for {album_id} does not contain a valid 'assets' list. Found: {type(album_assets)}")
            return set()

        for asset in album_assets:
            if isinstance(asset, dict): 
                asset_id = asset.get('id')
                if asset_id and is_valid_uuid(asset_id):
                    asset_ids_in_album.add(asset_id)
                elif asset_id: 
                    logger.warning(f"Asset in album {album_id} has an invalid UUID: {asset_id}. Skipping.")
            else:
                logger.warning(f"Unexpected item type in album assets list for album {album_id}. Expected dict, got: {type(asset)}. Item: {str(asset)[:100]}")
        
        logger.info(f"Found {len(asset_ids_in_album)} assets in album ID {album_id}.")
        return asset_ids_in_album
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching album details for {album_id}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"Response status: {e.response.status_code}, content: {e.response.text[:300]}")
        return set()
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response from {api_url} for album details: {e}")
        logger.error(f"Response content: {response.text if 'response' in locals() else 'No response object'}")
        return set()
    except KeyError as e:
        logger.error(f"Missing expected key in album data for {album_id} (e.g., 'assets'): {e}")
        return set()


# --- 4. Add Assets to the Album ---
def add_assets_to_album(album_id, asset_ids_to_add):
    """Adds the given asset IDs to the specified album."""
    if not asset_ids_to_add:
        logger.info("No new assets to add to the album.")
        return True

    logger.info(f"Attempting to add {len(asset_ids_to_add)} assets to album ID: {album_id}")
    payload = {"ids": list(asset_ids_to_add)} 
    api_url = f"{IMMICH_BASE_URL}/api/albums/{album_id}/assets"
    
    logger.debug(f"Payload for adding assets: {json.dumps(payload)}")

    try:
        response = requests.put(api_url, headers=HEADERS, json=payload)
        response.raise_for_status()
        try:
            response_data = response.json()
            logger.debug(f"Response from adding assets: {json.dumps(response_data, indent=2)}")
        except json.JSONDecodeError:
            logger.info(f"Successfully submitted request to add {len(asset_ids_to_add)} assets to album ID {album_id}. Response was not JSON or empty.")
        
        logger.info(f"Request to add {len(asset_ids_to_add)} assets to album {album_id} completed. Status: {response.status_code}")
        return True
    except requests.exceptions.HTTPError as e:
        error_message = f"HTTP Error: PUT {e.request.url} -> {e.response.status_code if e.response else 'N/A'}" # Corrected to use e.request.url and e.response
        if e.response is not None and e.response.text:
            error_message += f": {e.response.text[:500]}" 
        logger.error(error_message)
        logger.error(f"Failed to add assets to album ID {album_id}: {e}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Error adding assets to album ID {album_id}: {e}")
        return False

# --- Main Sync Logic ---
def run_sync_cycle():
    """Performs one cycle of the synchronization logic."""
    logger.info("Starting new sync cycle.")

    if not TARGET_ALBUM_ID or not is_valid_uuid(TARGET_ALBUM_ID):
        logger.error(f"Target Album ID '{TARGET_ALBUM_ID}' is missing or invalid. Skipping cycle.")
        return

    target_person_names = [name.strip() for name in PERSON_NAMES_STR.split(',') if name.strip()]
    filename_filters = [filt.strip() for filt in NAME_FILTERS_STR.split(',') if filt.strip()]

    if not target_person_names:
        logger.info("No persons specified in IMMICH_PERSONS. Nothing to do for this cycle.")
        return

    person_ids = get_person_ids_by_names(target_person_names)
    if not person_ids: 
        logger.warning("No valid Person IDs found for the specified names after attempting to fetch them. Ending this cycle.")
        return

    assets_of_persons = get_assets_for_person_ids(person_ids, filename_filters)
    if not assets_of_persons: 
        logger.info("No assets found matching the specified persons and filename filters for this cycle.")
        return
    
    logger.info(f"Total assets found for specified persons (after filters): {len(assets_of_persons)}")

    assets_already_in_album = get_asset_ids_in_album(TARGET_ALBUM_ID)
    
    assets_of_persons_set = set(assets_of_persons)
    
    assets_to_add_final = list(assets_of_persons_set - assets_already_in_album)

    if not assets_to_add_final:
        logger.info("All identified assets for the specified persons are already in the target album for this cycle.")
    else:
        logger.info(f"Found {len(assets_to_add_final)} new assets from specified persons to add to album {TARGET_ALBUM_ID}.")
        add_assets_to_album(TARGET_ALBUM_ID, assets_to_add_final)

    logger.info("Sync cycle finished.")

# --- Main Script Execution ---
if __name__ == "__main__":
    logger.info(f"Starting Immich person-specific album sync script. Sync interval: {SYNC_INTERVAL_SECONDS} seconds.")
    logger.info(f"Target Album ID: {TARGET_ALBUM_ID}")
    logger.info(f"Person Names to sync: {PERSON_NAMES_STR if PERSON_NAMES_STR else 'None'}")
    logger.info(f"Filename Filters: {NAME_FILTERS_STR if NAME_FILTERS_STR else 'None'}")
    
    while True:
        try:
            run_sync_cycle()
        except Exception as e:
            logger.error(f"An unexpected critical error occurred during the sync cycle: {e}", exc_info=True)
        
        logger.info(f"Waiting for {SYNC_INTERVAL_SECONDS} seconds before next sync cycle...")
        try:
            time.sleep(SYNC_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info("Script interrupted by user. Exiting.")
            break
        except Exception as e_sleep: 
            logger.error(f"Error during sleep interval: {e_sleep}. Exiting.")
            break
