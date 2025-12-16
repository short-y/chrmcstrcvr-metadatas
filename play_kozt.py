import random
import argparse
import sys
import time
import logging
import requests
import pychromecast
from pychromecast.controllers import BaseController
from pychromecast.discovery import CastBrowser, SimpleCastListener
import zeroconf
import threading
import struct
import json
import signal
import atexit
import os
from urllib.parse import quote

# Default Stream (KOZT) 
DEFAULT_STREAM_URL = "http://live.amperwave.net/playlist/caradio-koztfmaac-ibc3.m3u"
DEFAULT_STREAM_TYPE = "video/mp4" # Trick: Use video type to avoid persistent Audio UI
DEFAULT_IMAGE_URL = "https://radioparadise.com/graphics/logo_flat_shadow.png" # Keep generic or find a KOZT logo
DEFAULT_TITLE = "KOZT - The Coast"
DEFAULT_SUBTITLE = "Mendocino County Public Broadcasting"
DEFAULT_APP_ID = "6509B35C"

# Silent Audio for "No-Stream" Mode (keeps receiver active)
SILENT_STREAM_URL = "https://github.com/anars/blank-audio/blob/master/10-minutes-of-silence.mp3?raw=true"
SILENT_STREAM_TYPE = "audio/mp3"

NAMESPACE = 'urn:x-cast:com.example.radio'

# Global state for signal handling
current_cast = None
current_browser = None
current_mc = None
current_zconf = None
cleanup_in_progress = False

def safe_write(msg):
    """Signal-safe write to stdout."""
    try:
        os.write(sys.stdout.fileno(), f"{msg}\n".encode())
    except:
        pass

def graceful_exit(signum, frame):
    """Handle kill signals (SIGINT/SIGTERM) robustly."""
    global cleanup_in_progress

    if cleanup_in_progress:
        # Already cleaning up, force exit
        safe_write("\nForced exit.")
        os._exit(1)

    cleanup_in_progress = True
    safe_write("\nSignal received. Stopping playback...")

    try:
        # Stop media playback first
        if current_mc:
            safe_write("Stopping media controller...")
            current_mc.stop()
            time.sleep(0.5)

        # Quit the app
        if current_cast:
            safe_write("Quitting Cast app...")
            try:
                current_cast.quit_app()
                time.sleep(1)  # Wait for quit command to be sent
            except Exception as e:
                safe_write(f"Error quitting app: {e}")

        # Stop discovery
        if current_browser:
            safe_write("Stopping discovery...")
            current_browser.stop_discovery()

        # Close zeroconf
        if current_zconf:
            safe_write("Closing zeroconf...")
            current_zconf.close()

    except Exception as e:
        safe_write(f"Error during cleanup: {e}")

    safe_write("Exiting.")
    os._exit(0)

def cleanup_atexit():
    """Cleanup function registered with atexit as backup."""
    global cleanup_in_progress

    if cleanup_in_progress:
        return

    cleanup_in_progress = True

    try:
        if current_mc:
            current_mc.stop()
        if current_cast:
            current_cast.quit_app()
        if current_browser:
            current_browser.stop_discovery()
        if current_zconf:
            current_zconf.close()
    except:
        pass

def discover_all_chromecasts(timeout=5):
    """
    Discover all chromecasts on the network using CastBrowser directly,
    avoiding the deprecated discover_chromecasts function.
    """
    global current_zconf

    found_chromecasts = []

    # Reuse existing zeroconf or create new one
    if not current_zconf:
        current_zconf = zeroconf.Zeroconf()

    # SimpleCastListener expects a callback for add (and optionally remove/update)
    # We just need to start discovery and let the browser populate browser.devices
    listener = SimpleCastListener(lambda uuid, service: None)
    browser = CastBrowser(listener, current_zconf)
    browser.start_discovery()

    print(f"Scanning for devices ({timeout}s)...")
    time.sleep(timeout)

    for uuid, service in browser.devices.items():
        try:
             cc = pychromecast.get_chromecast_from_cast_info(service, current_zconf)
             found_chromecasts.append(cc)
        except Exception as e:
             logging.debug(f"Error creating Chromecast object for {uuid}: {e}")

    return found_chromecasts, browser

class RadioController(BaseController):
    """
    Controller to send custom messages to the receiver.
    """
    def __init__(self):
        super(RadioController, self).__init__(NAMESPACE)
        self.received_disconnect = False
        self.pong_received = threading.Event()

    def receive_message(self, message, data):
        """
        Called when a message is received from the receiver.
        """
        logging.debug(f"RadioController: Received message -> {data}")
        
        if data.get('type') == 'PONG':
            visibility = data.get('visibilityState', 'unknown')
            standby = data.get('standbyState', 'unknown')
            version = data.get('version', 'unknown')
            logging.debug(f"PONG received. Version: {version}, Visibility: {visibility}, Standby: {standby}")
            self.pong_received.set()
            return True
            
        if data.get('type') == 'DISCONNECT':
             logging.warning("Receiver sent DISCONNECT signal.")
             self.received_disconnect = True
             return True # Handled
        return False

    def send_track_update(self, title, artist, image_url=None, album=None, time=None, station_name=DEFAULT_TITLE):
        """Sends a track update message to the receiver."""
        msg = {
            "title": title,
            "artist": artist,
            "image": image_url,
            "album": album,
            "time": time,
            "stationName": station_name
        }
        logging.debug(f"RadioController: Sending update -> {title} / {artist}")
        if image_url:
            logging.debug(f"  Image: {image_url}")
        self.send_message(msg)

    def send_keepalive(self):
        """
        Sends a PING and waits for a PONG.
        Returns True if PONG received within timeout, False otherwise.
        """
        try:
            self.pong_received.clear()
            self.send_message({"type": "PING"})
            
            # Wait for PONG (3 seconds timeout)
            if self.pong_received.wait(timeout=3.0):
                return True
            else:
                logging.debug("Keepalive: PING sent but no PONG received (Timeout).")
                return False
                
        except Exception as e:
            logging.debug(f"Keepalive failed (Exception): {e}")
            return False


def resolve_playlist(url):
    """
    If the URL looks like a playlist (.m3u, .pls), try to fetch it 
    and extract the actual stream URL.
    Excludes .m3u8 as those are usually HLS streams handled natively by the player.
    """
    lower_url = url.lower()
    if not (lower_url.endswith('.m3u') or lower_url.endswith('.pls')):
        return url
        
    logging.debug(f"Resolving playlist URL: {url}")
    try:
        # Fake a user agent, some radios block generic python/requests
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.text
        
        # Parse line by line
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # PLS format: File1=http://...
            if lower_url.endswith('.pls') and line.lower().startswith('file'):
                if '=' in line:
                    parts = line.split('=', 1)
                    if parts[1].lower().startswith('http'):
                        logging.debug(f"Found stream URL in PLS: {parts[1]}")
                        return parts[1].strip()

            # M3U format: just the URL
            if line.lower().startswith('http'):
                 logging.debug(f"Found stream URL in M3U: {line}")
                 return line
                 
    except Exception as e:
        print(f"Warning: Failed to resolve playlist: {e}")
        print("Using original URL.")
    
    return url

def fetch_album_art(artist, title):
    """
    Fetches album art URL using the iTunes Search API.
    Returns None if not found or on error.
    """
    if not artist or not title:
        return None
        
    search_term = f"{artist} {title}"
    url = f"https://itunes.apple.com/search?term={quote(search_term)}&media=music&limit=1"
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['resultCount'] > 0:
                # Get the largest available image (artworkUrl100 is usually 100x100)
                # We can try to hack the URL to get a higher res version (e.g. 600x600)
                artwork_url = data['results'][0].get('artworkUrl100')
                if artwork_url:
                    # Replace '100x100bb' with '600x600bb' for higher quality
                    return artwork_url.replace('100x100bb', '600x600bb')
    except Exception as e:
        print(f"Error fetching album art: {e}")
    
    return None

def metadata_monitor(stream_url, controller, stop_event):
    """
    Connects to the stream in a separate thread, reads interleaved metadata,
    and pushes updates to the Chromecast receiver.
    """
    logging.debug(f"Metadata Monitor: Connecting to {stream_url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; IcecastMetadataReader/1.0)',
        'Icy-MetaData': '1'
    }
    
    current_raw_title = None
    
    while not stop_event.is_set():
        try:
            with requests.get(stream_url, headers=headers, stream=True, timeout=10) as r:
                # Check for Icy-MetaInt
                metaint = int(r.headers.get('icy-metaint', -1))
                
                if metaint == -1:
                    logging.debug("Metadata Monitor: No Icy-MetaInt header found. Stream does not support interleaved metadata.")
                    return

                logging.debug(f"Metadata Monitor: Connected. Interval: {metaint} bytes.")
                
                while not stop_event.is_set():
                    # Read audio chunk (discard)
                    # Read in loop to handle stop_event responsively
                    bytes_to_read = metaint
                    while bytes_to_read > 0:
                        if stop_event.is_set(): return
                        # Read small chunks to avoid blocking forever
                        chunk_size = min(bytes_to_read, 8192) 
                        chunk = r.raw.read(chunk_size) 
                        if not chunk:
                            raise Exception("Stream ended")
                        bytes_to_read -= len(chunk)
                    
                    # Read metadata length
                    len_byte = r.raw.read(1)
                    if not len_byte:
                        raise Exception("Stream ended")
                    
                    length = struct.unpack('B', len_byte)[0] * 16
                    
                    if length > 0:
                        meta_data = r.raw.read(length)
                        meta_str = meta_data.decode('utf-8', errors='ignore')
                        
                        # Parse StreamTitle='...';
                        if "StreamTitle=" in meta_str:
                            try:
                                raw_title_part = meta_str.split("StreamTitle=")[1].split(';')[0].strip("'")
                                
                                if raw_title_part != current_raw_title:
                                    logging.debug(f"Metadata Monitor: New Track -> {raw_title_part}")
                                    current_raw_title = raw_title_part
                                    
                                    # Try to split Artist - Title
                                    artist = ""
                                    title = raw_title_part
                                    if " - " in raw_title_part:
                                        parts = raw_title_part.split(" - ", 1)
                                        artist = parts[0].strip()
                                        title = parts[1].strip()
                                    
                                    # Fetch Album Art
                                    image_url = fetch_album_art(artist, title)
                                    
                                    try:
                                        controller.send_track_update(title, artist, image_url)
                                    except Exception as e:
                                        logging.debug(f"Metadata Monitor: Send failed: {e}")
                                        
                            except IndexError:
                                pass
                    
        except Exception as e:
            # Only print error if not stopping
            if not stop_event.is_set():
                logging.debug(f"Metadata Monitor Connection Lost: {e}")
                logging.debug("Reconnecting in 5 seconds...")
                time.sleep(5)

def scrape_kozt_now_playing():
    """
    Fetches KOZT now playing data from the Amperwave JSON API.
    Returns: title, artist, image_url, album, time
    """
    try:
        # Discovered API endpoint
        url = "https://api-nowplaying.amperwave.net/api/v1/prtplus/nowplaying/10/4756/nowplaying.json"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        if "performances" in data and isinstance(data["performances"], list) and len(data["performances"]) > 0:
            current_track = data["performances"][0]
            
            song_title = current_track.get("title", "Unknown Song").strip()
            artist_name = current_track.get("artist", "Unknown Artist").strip()
            album_name = current_track.get("album", "").strip()
            track_time = current_track.get("time", "").strip()
            
            # Prefer large image, fall back to medium, then small
            image_url = current_track.get("largeimage") or \
                        current_track.get("mediumimage") or \
                        current_track.get("smallimage")
            
            return song_title, artist_name, image_url, album_name, track_time
            
        return None, None, None, None, None

    except Exception as e:
        logging.debug(f"Error fetching KOZT now playing JSON: {e}")
        return None, None, None, None, None

def play_radio(device_name, stream_url, stream_type, title, image_url, app_id=None, is_kozt_station=False, no_stream=False):
    global current_cast, current_browser, current_mc, current_zconf

    print(f"Searching for Chromecast: {device_name}...")

    # Create zeroconf instance if not already created
    if not current_zconf:
        current_zconf = zeroconf.Zeroconf()

    chromecasts, browser = pychromecast.get_listed_chromecasts(
        friendly_names=[device_name],
        zeroconf_instance=current_zconf
    )
    current_browser = browser

    if not chromecasts:
        # Try discovering all if specific one not found immediately
        print(f"Device '{device_name}' not found immediately. Scanning all devices...")
        chromecasts, browser = discover_all_chromecasts()
        current_browser = browser
        # Filter manually
        chromecasts = [cc for cc in chromecasts if cc.name == device_name]

    if not chromecasts:
        print(f"Error: Could not find Chromecast named '{device_name}'.")
        sys.exit(1)

    current_cast = chromecasts[0]
    current_cast.wait()
    print(f"Connected to {current_cast.name}!")

    # Register Custom Controller
    radio_controller = RadioController()
    current_cast.register_handler(radio_controller)

    current_mc = current_cast.media_controller
    
    # If KOZT, try to get initial metadata for play_media call
    initial_title = title
    initial_image_url = image_url
    initial_album = None
    initial_time = None
    kozt_artist = "" # Initialize kozt_artist
    if is_kozt_station:
        kozt_title, kozt_artist, kozt_image, kozt_album, kozt_time = scrape_kozt_now_playing()
        if kozt_title and kozt_artist:
            initial_title = f"{kozt_artist} - {kozt_title}"
            if kozt_image:
                initial_image_url = kozt_image
            else:
                # If KOZT API has no image, try iTunes
                initial_image_url = fetch_album_art(kozt_artist, kozt_title)
            
            initial_album = kozt_album
            initial_time = kozt_time
            
            print(f"Initial KOZT metadata: {initial_title} / Image: {initial_image_url} / Album: {initial_album} / Time: {initial_time}")
        else:
            print("Warning: Failed to get initial KOZT metadata. Using provided defaults.")

    # Prepare minimal metadata to suppress Default UI
    # Trick: Use metadataType 1 (MOVIE) to force full-screen video UI on Pixel Tablet
    metadata = {
        "metadataType": 1, 
        "title": " ", 
        "subtitle": " ",
        "images": []
    }
    
    # We intentionally do NOT set albumName or trackTime here to keep Default UI clean.
    # The Custom UI will be populated by the first `send_track_update` message.

    # Launch Default Media Receiver and play
    if app_id:
        print(f"Launching Custom App ID: {app_id}")
        
        # Ensure any previous session is closed (helps with Pixel Tablet / Hubs)
        # try:
        #     logging.debug("Ensuring previous app is closed...")
        #     cast.quit_app()
        #     time.sleep(3) 
        # except Exception as e:
        #     logging.debug(f"Non-fatal error quitting app: {e}")

        # Try to launch with a retry
        launch_success = False
        for attempt in range(2):
            try:
                print(f"Starting app {app_id} (Attempt {attempt + 1})...")
                current_cast.start_app(app_id) # Custom Receiver
                launch_success = True
                time.sleep(3) # Wait for app to load
                break
            except Exception as e:
                print(f"Error launching app (Attempt {attempt + 1}): {e}")
                if attempt < 1:
                    print("Retrying in 5 seconds...")
                    time.sleep(5)
        
        if not launch_success:
            print(f"Error: Failed to launch App ID {app_id} after retries.")
            print("Possible causes:")
            print("1. The App ID is incorrect.")
            print("2. The Chromecast device is not registered for development (if the App is unpublished).")
            print("3. The Chromecast has not been rebooted since registering the device serial number.")
            print("4. The App ID was created very recently and hasn't propagated to the device yet.")
            print("5. The device (e.g., Pixel Tablet) prevented the launch due to idle/dock state.")
            sys.exit(1)
    else:
        print("Launching Default Media Receiver")
        # Default Media Receiver is launched automatically by play_media if no app is running
        # But explicitly setting it helps if we want to switch apps
        # cast.start_app("CC1AD845") # Default Media Receiver ID

    if not no_stream:
        print(f"Playing {initial_title} ({stream_url})...")
        # Use generic title/thumb to avoid Default UI clutter
        current_mc.play_media(stream_url, stream_type, stream_type="LIVE", title=" ", thumb=None, metadata=metadata)
        current_mc.block_until_active()
        print("Playback started!")
    else:
        print("Mode: No-Stream. Playing SILENT track to keep receiver active/visible.")
        # We must play *something* or the Pixel Tablet will revert to the dashboard.
        # Use the silent MP3, but declare it as BUFFERED or LIVE.
        current_mc.play_media(SILENT_STREAM_URL, SILENT_STREAM_TYPE, stream_type="BUFFERED", title=" ", thumb=None, metadata=metadata)
        current_mc.block_until_active()
        print("Silent Playback started!")
    
    # Send immediate update with REAL metadata to populate Custom UI
    time.sleep(1) # Wait for receiver to be ready
    # Use provided 'title' which defaults to "KOZT - The Coast" as station_name
    radio_controller.send_track_update(initial_title, kozt_artist, initial_image_url, initial_album, initial_time, station_name=title)
    
    # Verify the correct app is running AFTER playback starts
    time.sleep(1) # Allow status to update
    if app_id and current_cast.status:
         logging.debug(f"Debug: Active App ID is {current_cast.status.app_id}")
         if current_cast.status.app_id != app_id:
             print(f"WARNING: Active App ID ({current_cast.status.app_id}) does not match requested ID ({app_id}).")
             print("The device may have fallen back to the Default Media Receiver.")
    elif app_id:
         logging.debug("Debug: Could not determine Active App ID (status is None)")
    
    # MONITOR LOGIC
    stop_event = threading.Event()
    browser_discovery_active = True
    
    consecutive_errors = 0

    # KOZT SPECIFIC LOGIC - Check explicit flag first
    if is_kozt_station or "kozt" in stream_url.lower():
        print("--- Detected KOZT Stream. Using Amperwave JSON API for Metadata ---")
        last_song_title = None
        last_artist_name = None
        last_heartbeat_time = time.time()
        
        while True:
            # Heartbeat Log
            if time.time() - last_heartbeat_time > 30:
                logging.info(f"Heartbeat: Sender is alive. Current App ID: {current_cast.status.app_id if current_cast.status else 'Unknown'}")
                last_heartbeat_time = time.time()

            # 1. Keepalive / Status Check
            try:
                # Update standard status
                current_cast.socket_client.receiver_controller.update_status()
                
                # Send custom ping to ensure app pipe is open
                logging.debug("Sending Ping...")
                keepalive_success = radio_controller.send_keepalive()
                if not keepalive_success:
                    logging.warning("Ping Failed!")
                    raise Exception("Keepalive PING failed")
                
                consecutive_errors = 0 # Reset on success
                logging.debug("Ping Successful.")
            except Exception as e:
                consecutive_errors += 1
                logging.warning(f"Connection Check Failed ({consecutive_errors}/3): {e}")
                if consecutive_errors >= 3:
                    logging.warning("Too many connection errors. Assuming disconnected.")
                    break
            
            # Check for explicit disconnect message
            if radio_controller.received_disconnect:
                logging.warning("Explicit disconnect received from Receiver.")
                break
            
            # 2. Check logical connection state
            if not current_cast.socket_client.is_connected:
                logging.warning("Chromecast connection lost (socket).")
                break
            
            if current_cast.status and current_cast.status.app_id != app_id:
                logging.warning(f"App ID changed to {current_cast.status.app_id} (expected {app_id}). Relaunching...")
                break
            
            # 3. App Logic (Fetch Data)
            song_title, artist_name, fetched_image_url, album_name, track_time = scrape_kozt_now_playing()
            
            if song_title and artist_name and (song_title != last_song_title or artist_name != last_artist_name):
                logging.debug(f"KOZT Monitor: New Track -> {song_title} / {artist_name}")
                last_song_title = song_title
                last_artist_name = artist_name
                
                # Use fetched image URL directly (no iTunes lookup needed)
                if fetched_image_url:
                    logging.debug(f"  Album Art: {fetched_image_url}")
                    final_image_url = fetched_image_url
                else:
                    # Fallback to iTunes logic if API has data but no image (rare)
                    # For now, we try iTunes if JSON lacks image.
                    final_image_url = fetch_album_art(artist_name, song_title) 
                
                try:
                    # Use provided 'title' which defaults to "KOZT - The Coast" as station_name
                    radio_controller.send_track_update(song_title, artist_name, final_image_url, album_name, track_time, station_name=title)
                    consecutive_errors = 0
                except Exception as e:
                    logging.debug(f"KOZT Monitor: Send failed: {e}")
                    # If send fails here, the next loop's keepalive will likely catch it too
            
            # Random refresh interval for next poll
            sleep_delay = random.randint(10, 25)
            logging.info(f"KOZT Monitor: Waiting {sleep_delay} seconds until next refresh.")
            time.sleep(sleep_delay)
    
    # GENERIC ICECAST LOGIC
    else:
        print("--- Using Generic Icecast Metadata Monitor ---")
        monitor_thread = threading.Thread(target=metadata_monitor, args=(stream_url, radio_controller, stop_event))
        monitor_thread.daemon = True
        monitor_thread.start()
        
        last_ping_time = time.time()
        last_heartbeat_time = time.time()

        while True:
            # Heartbeat Log every 30s
            if time.time() - last_heartbeat_time > 30:
                logging.info(f"Heartbeat: Sender is alive. Current App ID: {current_cast.status.app_id if current_cast.status else 'Unknown'}")
                last_heartbeat_time = time.time()

            try:
                # Update status frequently
                current_cast.socket_client.receiver_controller.update_status()
                
                # Send Ping every 10 seconds
                if time.time() - last_ping_time > 10:
                     logging.debug("Sending Ping...")
                     if not radio_controller.send_keepalive():
                         logging.warning("Ping Failed!")
                         raise Exception("Keepalive PING failed")
                     
                     # Only reset consecutive errors if Ping succeeded
                     consecutive_errors = 0 
                     last_ping_time = time.time()
                     logging.debug("Ping Successful.")

            except Exception as e:
                consecutive_errors += 1
                logging.warning(f"Connection Check Failed ({consecutive_errors}/3): {e}")
                if consecutive_errors >= 3:
                     logging.warning("Too many connection errors. Assuming disconnected.")
                     break
            
            # Check for explicit disconnect message
            if radio_controller.received_disconnect:
                logging.warning("Explicit disconnect received from Receiver.")
                break

            if not current_cast.socket_client.is_connected:
                logging.warning("Chromecast connection lost.")
                break
            
            if current_cast.status and current_cast.status.app_id != app_id:
                logging.warning(f"App ID changed to {current_cast.status.app_id}. Relaunching...")
                break

            time.sleep(1)


if __name__ == "__main__":
    # Register signal handlers for robust exit (especially for PyInstaller)
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    # Register atexit handler as backup cleanup mechanism
    atexit.register(cleanup_atexit)

    parser = argparse.ArgumentParser(description="Play KOZT on Chromecast.")
    parser.add_argument("device_name", help="The friendly name of the Chromecast (e.g., 'Living Room TV')")
    parser.add_argument("--url", default=DEFAULT_STREAM_URL, help="Stream URL")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Display Title")
    parser.add_argument("--image", default=DEFAULT_IMAGE_URL, help="Display Image URL")
    parser.add_argument("--app_id", default=DEFAULT_APP_ID, help="Custom Receiver App ID (Register at cast.google.com/publish)")
    parser.add_argument("--debug", action="store_true", help="Enable info-level logging (heartbeats, intervals)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging (all internal logs)")
    # KOZT is enabled by default now. Use --no-kozt to disable.
    parser.add_argument("--no-kozt", action="store_false", dest="kozt", help="Disable KOZT metadata scraping")
    parser.set_defaults(kozt=True)
    parser.add_argument("-ns", "--no-stream", action="store_true", help="Launch the app and show song information on your screen, but keep the audio silent.")
    
    args = parser.parse_args()
    
    # Configure logging based on flags
    if args.verbose:
        log_level = logging.DEBUG
    elif args.debug:
        log_level = logging.INFO
    else:
        log_level = logging.WARNING
        
    logging.basicConfig(level=log_level, format='%(message)s')
    
    # Resolve playlist if necessary
    final_url = resolve_playlist(args.url)
    
    browser = None # Initialize browser here to be accessible in finally
    
    while True:
        try:
            play_radio(args.device_name, final_url, DEFAULT_STREAM_TYPE, args.title, args.image, args.app_id, args.kozt, args.no_stream)
        except Exception as e:
            if cleanup_in_progress:
                break
            logging.error(f"Connection lost or error occurred: {e}")
            logging.info("Attempting to reconnect in 5 seconds...")
            time.sleep(5)
