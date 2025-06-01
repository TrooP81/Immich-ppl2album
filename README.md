# Immich-ppl2album

This Python script synchronizes assets from an [Immich](https://immich.app/) server into a specified target album based on person names and optional filename filters. It can find photos containing all specified persons together, as well as photos containing each specified person individually.
The script is made to run recursivly to allow dynamic adding of photos into for example a shared album.

## Features

-   Connects to your Immich instance using an API key.
-   Identifies persons in Immich based on a provided list of names.
-   Fetches assets associated with these persons:
    -   Assets containing **all** specified persons together.
    -   Assets containing **each** specified person individually.
-   Optionally filters assets by filename patterns (e.g., `*.jpg`, `*.png`).
-   Checks which of these filtered assets are not already in a target album.
-   Adds any new, relevant assets to the target album.
-   Designed to run periodically to keep the album updated.

## Prerequisites

-   Python 3.7+
-   `requests` library: `pip install requests`
-   `python-dotenv` library: `pip install python-dotenv` (for managing environment variables)
-   An Immich server instance.
-   An API key for your Immich server.
-   The ID of the target album in Immich.

## Setup

1.  **Clone or Download:**
    Get the `immich_album_sync.py` script (the Python script we've been working on).

2.  **Install Dependencies:**
    Open your terminal or command prompt and run:
    ```bash
    pip install requests python-dotenv
    ```

3.  **Create a `.env` file:**
    In the same directory as the `immich_album_sync.py` script, create a file named `.env`. This file will store your Immich server details and API key securely.

    Add the following content to your `.env` file, replacing the placeholder values with your actual information:

    ```env
    # --- Immich Server Configuration ---
    IMMICH_BASE_URL="http://your-immich-server-url:port"
    IMMICH_API_KEY="your_immich_api_key_here"

    # --- Album and Person Configuration ---
    # The UUID of the album you want to sync photos into.
    # You can find this by looking at the URL when viewing an album in Immich,
    # or by using other API tools to list albums and their IDs.
    IMMICH_ALBUM_ID="your_target_album_uuid_here"

    # Comma-separated list of person names exactly as they appear in Immich.
    # Example: IMMICH_PERSONS="Alice Wonderland,Bob The Builder,Charles Xavier"
    IMMICH_PERSONS="Person One Name,Person Two Name"

    # Optional: Comma-separated list of filename patterns to include.
    # Uses standard Unix shell-style wildcards (fnmatch).
    # Example: IMMICH_NAME_FILTERS="*.jpg,*.jpeg,*.png,*.heic"
    # Leave empty if you don't want to filter by filename: IMMICH_NAME_FILTERS=
    IMMICH_NAME_FILTERS="*.jpg,*.png"

    # --- Sync Interval ---
    # How often the script should run the sync cycle, in seconds.
    # Default is 3600 seconds (1 hour).
    SYNC_INTERVAL_SECONDS="3600"
    ```

    **Important Notes for `.env`:**
    * `IMMICH_BASE_URL`: Should be the full URL to your Immich instance (e.g., `http://localhost:2283` or `https://immich.example.com`). Do **not** include `/api` at the end.
    * `IMMICH_API_KEY`: Generate this from your Immich user settings.
    * `IMMICH_ALBUM_ID`: This is the UUID of the album.
    * `IMMICH_PERSONS`: Names are case-sensitive and must match exactly how they appear in Immich.
    * `IMMICH_NAME_FILTERS`: If you want to include all file types for the selected persons, you can leave this blank (e.g., `IMMICH_NAME_FILTERS=`).

## Usage

1.  **Navigate to the script directory:**
    Open your terminal or command prompt and change to the directory where you saved `immich_album_sync.py` and the `.env` file.

2.  **Run the script:**
    ```bash
    python immich_album_sync.py
    ```

3.  **Logging:**
    The script will log its actions to the console.
    -   By default, it logs `INFO` level messages.
    -   You can change the logging level in the script (e.g., to `logging.DEBUG`) for more detailed output, which is helpful for troubleshooting.

    The script will perform an initial sync cycle and then wait for the duration specified by `SYNC_INTERVAL_SECONDS` before running the next cycle. You can stop the script by pressing `Ctrl+C`.

## How it Works

1.  **Load Configuration:** Reads settings from the `.env` file.
2.  **Get Person IDs:** Fetches all people from Immich and finds the UUIDs for the names specified in `IMMICH_PERSONS`.
3.  **Fetch Assets:**
    * It first searches for assets where **all** specified persons appear together.
    * Then, for each specified person, it searches for assets containing that **individual** person.
    * All unique assets found are collected.
4.  **Filter by Filename:** If `IMMICH_NAME_FILTERS` is set, it filters the collected assets based on these patterns.
5.  **Check Target Album:** Retrieves the list of asset IDs already present in the `TARGET_ALBUM_ID`.
6.  **Add New Assets:** Compares the set of desired assets with those already in the album. Any assets not yet in the album are added.
7.  **Repeat:** Waits for the `SYNC_INTERVAL_SECONDS` and repeats the process.

## Troubleshooting

* **"Essential environment variables ... are not set"**: Ensure your `.env` file is correctly named, in the same directory as the script, and contains all required variables (`IMMICH_BASE_URL`, `IMMICH_API_KEY`, `IMMICH_ALBUM_ID`).
* **"Person with name '...' not found"**: Double-check the spelling and case of person names in your `.env` file. They must exactly match Immich. You can enable `DEBUG` logging to see the names the script fetches from Immich.
* **"Error searching assets ... 404 Client Error"**: This usually means the API endpoint for searching assets (`/api/search/metadata`) is incorrect for your Immich version or there's a base URL issue. Verify your `IMMICH_BASE_URL`. The script is designed for versions of Immich that use `POST /api/search/metadata`.
* **No assets being added**:
    * Enable `DEBUG` logging to see detailed steps.
    * Check if the persons specified actually have photos that match the criteria.
    * Verify your `IMMICH_NAME_FILTERS` if you're using them. An overly restrictive filter might exclude everything.
    * Ensure the `TARGET_ALBUM_ID` is correct.

## Contributing

Feel free to fork this script, suggest improvements, or adapt it to your needs.


