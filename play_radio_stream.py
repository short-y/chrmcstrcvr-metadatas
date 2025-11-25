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

    def send_track_update(self, title, artist, image_url=None):
        """Sends a track update message to the receiver."""
        msg = {
            "title": title,
            "artist": artist,
            "image": image_url
        }
        print(f"RadioController: Sending update -> {title} / {artist}")
        self.send_message(msg)


def resolve_playlist(url):
    """
    If the URL looks like a playlist (.m3u, .pls), try to fetch it 
    and extract the actual stream URL.
    Excludes .m3u8 as those are usually HLS streams handled natively by the player.
    """
    lower_url = url.lower()
    if not (lower_url.endswith('.m3u') or lower_url.endswith('.pls')):
        return url
        
    print(f"Resolving playlist URL: {url}")
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
                        print(f"Found stream URL in PLS: {parts[1]}")
                        return parts[1].strip()

            # M3U format: just the URL
            if line.lower().startswith('http'):
                 print(f"Found stream URL in M3U: {line}")
                 return line
                 
    except Exception as e:
        print(f"Warning: Failed to resolve playlist: {e}")
        print("Using original URL.")
    
    return url

def metadata_monitor(stream_url, controller, stop_event):
    """
    Connects to the stream in a separate thread, reads interleaved metadata,
    and pushes updates to the Chromecast receiver.
    """
    print(f"Metadata Monitor: Connecting to {stream_url}")
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
                    print("Metadata Monitor: No Icy-MetaInt header found. Stream does not support interleaved metadata.")
                    return

                print(f"Metadata Monitor: Connected. Interval: {metaint} bytes.")
                
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
                                    print(f"Metadata Monitor: New Track -> {raw_title_part}")
                                    current_raw_title = raw_title_part
                                    
                                    # Try to split Artist - Title
                                    artist = ""
                                    title = raw_title_part
                                    if " - " in raw_title_part:
                                        parts = raw_title_part.split(" - ", 1)
                                        artist = parts[0].strip()
                                        title = parts[1].strip()
                                    
                                    try:
                                        controller.send_track_update(title, artist)
                                    except Exception as e:
                                        print(f"Metadata Monitor: Send failed: {e}")
                                        
                            except IndexError:
                                pass
                    
        except Exception as e:
            # Only print error if not stopping
            if not stop_event.is_set():
                print(f"Metadata Monitor Connection Lost: {e}")
                print("Reconnecting in 5 seconds...")
                time.sleep(5)

def play_radio(device_name, stream_url, stream_type, title, image_url, app_id=None):
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
            
        # Verify the correct app is running
        if cast.status and cast.status.app_id != app_id:
             print(f"WARNING: Active App ID ({cast.status.app_id}) does not match requested ID ({app_id}).")
             print("The device may have fallen back to the Default Media Receiver.")
    else:
        print("Launching Default Media Receiver")
        # Default Media Receiver is launched automatically by play_media if no app is running
        # But explicitly setting it helps if we want to switch apps
        # cast.start_app("CC1AD845") # Default Media Receiver ID

    mc.play_media(stream_url, stream_type, stream_type="LIVE", title=title, thumb=image_url, metadata=metadata)
    mc.block_until_active()
    print("Playback started!")
    
    # Start Metadata Monitor
    stop_event = threading.Event()
    monitor_thread = threading.Thread(target=metadata_monitor, args=(stream_url, radio_controller, stop_event))
    monitor_thread.daemon = True
    monitor_thread.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
        stop_event.set()
        # mc.stop() # Uncomment if you want to stop playback on exit
        if app_id:
             cast.quit_app()
        browser.stop_discovery()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Play an internet radio stream on Chromecast.")
    parser.add_argument("device_name", help="The friendly name of the Chromecast (e.g., 'Living Room TV')")
    parser.add_argument("--url", default=DEFAULT_STREAM_URL, help="Stream URL")
    parser.add_argument("--title", default=DEFAULT_TITLE, help="Display Title")
    parser.add_argument("--image", default=DEFAULT_IMAGE_URL, help="Display Image URL")
    parser.add_argument("--app_id", default=None, help="Custom Receiver App ID (Register at cast.google.com/publish)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    # Resolve playlist if necessary
    final_url = resolve_playlist(args.url)
    
    play_radio(args.device_name, final_url, DEFAULT_STREAM_TYPE, args.title, args.image, args.app_id)
