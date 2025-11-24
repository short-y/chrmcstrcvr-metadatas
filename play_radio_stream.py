import argparse
import sys
import time
import pychromecast

# Default Stream (Radio Paradise Main Mix)
DEFAULT_STREAM_URL = "http://stream.radioparadise.com/aac-128"
DEFAULT_STREAM_TYPE = "audio/mp4" # or audio/mpeg
DEFAULT_IMAGE_URL = "https://radioparadise.com/graphics/logo_flat_shadow.png"
DEFAULT_TITLE = "Radio Paradise"
DEFAULT_SUBTITLE = "Internet Radio"

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
        cast.start_app(app_id) # Custom Receiver
    else:
        print("Launching Default Media Receiver")
        # Default Media Receiver is launched automatically by play_media if no app is running
        # But explicitly setting it helps if we want to switch apps
        # cast.start_app("CC1AD845") # Default Media Receiver ID

    mc.play_media(stream_url, stream_type, stream_type="LIVE", title=title, thumb=image_url, metadata=metadata)
    mc.block_until_active()
    print("Playback started!")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
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
    
    args = parser.parse_args()
    
    play_radio(args.device_name, args.url, DEFAULT_STREAM_TYPE, args.title, args.image, args.app_id)
