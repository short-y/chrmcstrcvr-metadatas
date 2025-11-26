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

# Default Stream (Radio Paradise Main Mix)
DEFAULT_STREAM_URL = "http://stream.radioparadise.com/aac-128"
DEFAULT_STREAM_TYPE = "audio/mp4" # or audio/mpeg
DEFAULT_IMAGE_URL = "https://radioparadise.com/graphics/logo_flat_shadow.png"
DEFAULT_TITLE = "Radio Paradise"
DEFAULT_SUBTITLE = "Internet Radio"

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

def play_radio(device_name, stream_url, stream_type, title, image_url, app_id=None, is_kozt_station=False):
    print(f"Searching for Chromecast: {device_name}...")
    chromecasts, browser = pychromecast.get_listed_chromecasts(friendly_names=[device_name])
    
    if not chromecasts:
        # Try discovering all if specific one not found immediately
        print(f"Device '{device_name}' not found immediately. Scanning all devices...")
        chromecasts, browser = pychromecast.get_chromecasts()
        # Filter manually
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
    
    print(f"Playing {title} ({stream_url})...")
    
    # Prepare metadata
    metadata = {
        "metadataType": 3, # Generic
        "title": title,
        "subtitle": DEFAULT_SUBTITLE,
        "images": [{"url": image_url}] if image_url else []
    }

    # Launch Default Media Receiver and play
    if app_id:
        print(f"Launching Custom App ID: {app_id}")
        try:
            cast.start_app(app_id) # Custom Receiver
            time.sleep(2) # Wait for app to load
        except pychromecast.error.RequestFailed:
            print(f"Error: Failed to launch App ID {app_id}.")
            print("Possible causes:")
            print("1. The App ID is incorrect.")
            print("2. The Chromecast device is not registered for development (if the App is unpublished).")
            print("3. The Chromecast has not been rebooted since registering the device serial number.")
            print("4. The App ID was created very recently and hasn't propagated to the device yet.")
            sys.exit(1)
    else:
        print("Launching Default Media Receiver")
        # Default Media Receiver is launched automatically by play_media if no app is running
        # But explicitly setting it helps if we want to switch apps
        # cast.start_app("CC1AD845") # Default Media Receiver ID

    mc.play_media(stream_url, stream_type, stream_type="LIVE", title=title, thumb=image_url, metadata=metadata)
    mc.block_until_active()
    print("Playback started!")
    
    # Verify the correct app is running AFTER playback starts
    time.sleep(1) # Allow status to update
    if app_id and cast.status:
         logging.debug(f"Debug: Active App ID is {cast.status.app_id}")
         if cast.status.app_id != app_id:
             print(f"WARNING: Active App ID ({cast.status.app_id}) does not match requested ID ({app_id}).")
             print("The device may have fallen back to the Default Media Receiver.")
    elif app_id:
         logging.debug("Debug: Could not determine Active App ID (status is None)")
    
    # MONITOR LOGIC
    stop_event = threading.Event()
    browser_discovery_active = True
    
    consecutive_errors = 0

    try:
        # KOZT SPECIFIC LOGIC - Check explicit flag first
        if is_kozt_station or "kozt" in stream_url.lower():
            print("--- Detected KOZT Stream. Using Amperwave JSON API for Metadata ---")
            last_song_title = None
            last_artist_name = None
            last_heartbeat_time = time.time()
            
            while True:
                # Heartbeat Log
                if time.time() - last_heartbeat_time > 30:
                    logging.info(f"Heartbeat: Sender is alive. Current App ID: {cast.status.app_id if cast.status else 'Unknown'}")
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
                    logging.warning("Receiver is hidden. Sending Launch command to foreground it (without restarting playback)...")
                    # specific 'launch_app' simply brings the existing app to focus if running
                    cast.socket_client.receiver_controller.launch_app(app_id)
                    radio_controller.is_hidden = False
                    time.sleep(2) # Give it a moment to become active again

                # 2. Check logical connection state
                if not cast.socket_client.is_connected:
                    logging.warning("Chromecast connection lost (socket).")
                    break
                
                if cast.status and cast.status.app_id != app_id:
                    logging.warning(f"App ID changed to {cast.status.app_id} (expected {app_id}). Relaunching...")
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
                        radio_controller.send_track_update(song_title, artist_name, final_image_url, album_name, track_time)
                        consecutive_errors = 0
                    except Exception as e:
                        logging.debug(f"KOZT Monitor: Send failed: {e}")
                        # If send fails here, the next loop's keepalive will likely catch it too
                
                time.sleep(10) # Refresh every 10 seconds
        
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
                    logging.info(f"Heartbeat: Sender is alive. Current App ID: {cast.status.app_id if cast.status else 'Unknown'}")
                    last_heartbeat_time = time.time()

                try:
                    # Update status frequently
                    cast.socket_client.receiver_controller.update_status()
                    
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

                # Check if receiver is hidden (backgrounded)
                if radio_controller.is_hidden:
                    logging.warning("Receiver is hidden. Sending Launch command to foreground it (without restarting playback)...")
                    # specific 'launch_app' simply brings the existing app to focus if running
                    cast.socket_client.receiver_controller.launch_app(app_id)
                    radio_controller.is_hidden = False
                    time.sleep(2) # Give it a moment to become active again

                if not cast.socket_client.is_connected:
                    logging.warning("Chromecast connection lost.")
                    break
                
                if cast.status and cast.status.app_id != app_id:
                    logging.warning(f"App ID changed to {cast.status.app_id}. Relaunching...")
                    break

                time.sleep(1)

    except KeyboardInterrupt:
        print("Stopping...")
        stop_event.set()
        # mc.stop() # Uncomment if you want to stop playback on exit
        if app_id:
             cast.quit_app()
        browser.stop_discovery()
        raise # Re-raise to stop the outer loop

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play an internet radio stream on Chromecast.")
    parser.add_argument("device_name", help="The friendly name of the Chromecast (e.g., 'Living Room TV')")
    parser.add_argument("--url", default=DEFAULT_STREAM_URL, help="Stream URL")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Display Title")
    parser.add_argument("--image", default=DEFAULT_IMAGE_URL, help="Display Image URL")
    parser.add_argument("--app_id", default=None, help="Custom Receiver App ID (Register at cast.google.com/publish)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--kozt", action="store_true", help="Force KOZT metadata scraping, even if URL doesn't contain 'kozt'")
    
    args = parser.parse_args()
    
    # Configure logging: DEBUG if requested, otherwise INFO
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, format='%(message)s')
    
    # Resolve playlist if necessary
    final_url = resolve_playlist(args.url)
    
    browser = None # Initialize browser here to be accessible in finally
    
    try:
        while True:
            try:
                play_radio(args.device_name, final_url, DEFAULT_STREAM_TYPE, args.title, args.image, args.app_id, args.kozt)
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
