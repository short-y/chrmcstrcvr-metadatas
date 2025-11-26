import argparse
import sys
import time
import logging
import requests
import pychromecast
from pychromecast.controllers import BaseController
import threading
import struct
import json
from urllib.parse import quote

# Silent MP3 URL (hosted on GitHub to ensure accessibility)
# Using a reliable source for 10 minutes of silence
SILENT_STREAM_URL = "https://github.com/anars/blank-audio/blob/master/10-minutes-of-silence.mp3?raw=true"
SILENT_STREAM_TYPE = "audio/mp3"

DEFAULT_IMAGE_URL = "https://radioparadise.com/graphics/logo_flat_shadow.png"
DEFAULT_TITLE = "Dashboard Mode"
DEFAULT_SUBTITLE = "Metadata Display Only"

NAMESPACE = 'urn:x-cast:com.example.radio'

class RadioController(BaseController):
    """
    Controller to send custom messages to the receiver.
    """
    def __init__(self):
        super(RadioController, self).__init__(NAMESPACE)
        self.received_disconnect = False
        self.pong_received = threading.Event()
        self.is_hidden = False

    def receive_message(self, message, data):
        """
        Called when a message is received from the receiver.
        """
        logging.debug(f"RadioController: Received message -> {data}")
        
        if data.get('type') == 'PONG':
            visibility = data.get('visibilityState', 'unknown')
            standby = data.get('standbyState', 'unknown')
            logging.debug(f"PONG received. Visibility: {visibility}, Standby: {standby}")
            
            if visibility == 'hidden':
                logging.warning("Receiver reports it is HIDDEN (background/screensaver).")
                self.is_hidden = True
            if standby == 'STANDBY':
                 logging.warning("Receiver reports it is in STANDBY mode.")

            self.pong_received.set()
            return True
            
        if data.get('type') == 'DISCONNECT':
             logging.warning("Receiver sent DISCONNECT signal.")
             self.received_disconnect = True
             return True # Handled
        return False

    def send_track_update(self, title, artist, image_url=None, album=None, time=None):
        """Sends a track update message to the receiver."""
        msg = {
            "title": title,
            "artist": artist,
            "image": image_url,
            "album": album,
            "time": time
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

def play_dashboard(device_name, app_id=None):
    print(f"Searching for Chromecast: {device_name}...")
    chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=[device_name])
    
    if not chromecasts:
        print(f"Device '{device_name}' not found immediately. Scanning all devices...")
        chromecasts, browser = pychromecast.get_chromecasts()
        chromecasts = [cc for cc in chromecasts if cc.name == device_name]

    if not chromecasts:
        print(f"Error: Could not find Chromecast named '{device_name}'.")
        sys.exit(1)

    cast = chromecasts[0]
    cast.wait()
    print(f"Connected to {cast.name}!")

    # Register Custom Controller
    radio_controller = RadioController()
    cast.register_handler(radio_controller)

    mc = cast.media_controller
    
    print("Launching Dashboard (Silent Audio Mode)...")
    
    # Prepare metadata for the Silent Stream
    metadata = {
        "metadataType": 3,
        "title": DEFAULT_TITLE,
        "subtitle": DEFAULT_SUBTITLE,
        "images": [{"url": DEFAULT_IMAGE_URL}]
    }

    # Launch Default Media Receiver and play
    if app_id:
        print(f"Launching Custom App ID: {app_id}")
        try:
            cast.start_app(app_id) # Custom Receiver
            time.sleep(5) # Wait longer for app to load and initialize Media Manager
        except pychromecast.error.RequestFailed:
            print(f"Error: Failed to launch App ID {app_id}.")
            sys.exit(1)
            
        # Verify App ID matches
        cast.socket_client.receiver_controller.update_status()
        if cast.status and cast.status.app_id != app_id:
            print(f"WARNING: Active App ID is {cast.status.app_id}, expected {app_id}.")
            print("The custom receiver may have failed to load, falling back to Default Receiver.")
    else:
        print("Launching Default Media Receiver")

    # Play the Silent Stream to keep the device awake
    # This is CRITICAL. Without this, Ambient Mode will kick in.
    print(f"Starting Silent Audio Loop on App ID: {cast.status.app_id if cast.status else 'Unknown'}...")
    mc.play_media(SILENT_STREAM_URL, SILENT_STREAM_TYPE, stream_type="BUFFERED", title=DEFAULT_TITLE, thumb=DEFAULT_IMAGE_URL, metadata=metadata)
    mc.block_until_active()
    print("Dashboard started (Silent Audio Playing)!")
    
    # Loop variables
    stop_event = threading.Event()
    consecutive_errors = 0
    last_song_title = None
    last_artist_name = None
    last_heartbeat_time = time.time()
    
    try:
        while True:
            # Heartbeat Log
            if time.time() - last_heartbeat_time > 30:
                logging.info(f"Heartbeat: Dashboard is alive. Current App ID: {cast.status.app_id if cast.status else 'Unknown'}")
                last_heartbeat_time = time.time()

            # 1. Keepalive / Status Check
            try:
                # Update standard status
                cast.socket_client.receiver_controller.update_status()
                
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
            
            # Check if receiver is hidden (backgrounded)
            if radio_controller.is_hidden:
                logging.warning("Receiver is hidden. Sending Launch command to foreground it...")
                cast.socket_client.receiver_controller.launch_app(app_id)
                radio_controller.is_hidden = False
                time.sleep(2)

            # 2. Check logical connection state
            if not cast.socket_client.is_connected:
                logging.warning("Chromecast connection lost (socket).")
                break
            
            if cast.status and cast.status.app_id != app_id:
                logging.warning(f"App ID changed to {cast.status.app_id} (expected {app_id}). Relaunching...")
                break
            
            # 3. App Logic (Fetch Data)
            # Only fetch KOZT data for now as requested
            song_title, artist_name, fetched_image_url, album_name, track_time = scrape_kozt_now_playing()
            
            if song_title and artist_name and (song_title != last_song_title or artist_name != last_artist_name):
                logging.debug(f"Dashboard Update: {song_title} / {artist_name}")
                last_song_title = song_title
                last_artist_name = artist_name
                
                # Use fetched image URL directly (no iTunes lookup needed)
                if fetched_image_url:
                    final_image_url = fetched_image_url
                else:
                    final_image_url = fetch_album_art(artist_name, song_title) 
                
                try:
                    radio_controller.send_track_update(song_title, artist_name, final_image_url, album_name, track_time)
                except Exception as e:
                    logging.debug(f"Dashboard Update failed: {e}")
            
            time.sleep(10) # Refresh every 10 seconds

    except KeyboardInterrupt:
        print("Stopping...")
        stop_event.set()
        if app_id:
             cast.quit_app()
        browser.stop_discovery()
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Display radio metadata on Chromecast without playing audio (Dashboard Mode).")
    parser.add_argument("device_name", help="The friendly name of the Chromecast (e.g., 'Living Room TV')")
    parser.add_argument("--app_id", default=None, help="Custom Receiver App ID (Register at cast.google.com/publish)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format='%(message)s')
    
    browser = None
    
    try:
        while True:
            try:
                play_dashboard(args.device_name, args.app_id)
            except Exception as e:
                logging.error(f"Connection lost or error occurred: {e}")
                logging.info("Attempting to reconnect in 5 seconds...")
                time.sleep(5)
    except KeyboardInterrupt:
        logging.info("Script stopped by user.")
    finally:
        if browser:
            logging.debug("Stopping Chromecast discovery.")
            browser.stop_discovery()
