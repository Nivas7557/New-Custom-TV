import requests
import re
import os

ORIGINAL_M3U_URL = "https://iptv-org.github.io/iptv/index.m3u"
OUTPUT_FILE = "Custom_Playlist.m3u"
INPUT_TXT_FILE = "Channels.txt"

def load_channels_from_txt(file_path):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return {}
    groups_dict = {}
    current_group = None
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_group = line[1:-1].strip()
                groups_dict[current_group] = []
            elif current_group is not None:
                groups_dict[current_group].append(line)
    return groups_dict

def strict_clean(name):
    if not name:
        return ""
    name = name.lower()
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'hd|sd|fhd|uhd|i|p|\s+|_|-|\+|&|,', '', name)
    return name.strip()

def fetch_and_filter_m3u():
    print(f"Loading configurations from '{INPUT_TXT_FILE}'...")
    groups_config = load_channels_from_txt(INPUT_TXT_FILE)
    if not groups_config:
        print("No channels found to filter. Exiting.")
        return
        
    config_lookup = []
    for g_idx, (group_name, channel_list) in enumerate(groups_config.items(), start=1):
        for ch_idx, original_name in enumerate(channel_list, start=1):
            clean_key = strict_clean(original_name)
            if clean_key:
                config_lookup.append({
                    "token": clean_key,
                    "group": group_name,
                    "number": (g_idx * 100) + ch_idx
                })
                
    try:
        print(f"Fetching original M3U from: {ORIGINAL_M3U_URL}")
        response = requests.get(ORIGINAL_M3U_URL, timeout=60, stream=True)
        response.raise_for_status()
    except Exception as err:
        print(f"Critical error fetching upstream data: {err}")
        return

    normalized_playlist = ["#EXTM3U"]
    current_extinf = None
    vlc_options_buffer = []
    processed_urls = set()

    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode('utf-8').strip()

        if line.startswith("#EXTM3U"):
            continue

        if line.startswith("#EXTINF:"):
            current_extinf = line
            vlc_options_buffer = []
        elif line.startswith("#EXTVLCOPT:"):
            vlc_options_buffer.append(line)
        elif not line.startswith("#"):
            if current_extinf and line not in processed_urls:
                source_channel_name = current_extinf.split(',')[-1].strip()
                clean_source_key = strict_clean(source_channel_name)
                
                matched_item = None
                for item in config_lookup:
                    # ADVANCED FLEXIBLE SUBSTRING LOGIC
                    # If target is 'starsports', it captures 'starsports1telugu', 'starsports2telugu', etc.
                    if item["token"] in clean_source_key or clean_source_key in item["token"]:
                        matched_item = item
                        break
                
                if matched_item:
                    cleaned_metadata = re.sub(r'\s*group-title="[^"]+"', '', current_extinf)
                    final_metadata = re.sub(
                        r'^#EXTINF:([-0-9]*)', 
                        f'#EXTINF:\\1 group-title="{matched_item["group"]}" tvg-chno="{matched_item["number"]}"', 
                        cleaned_metadata
                    )
                    
                    normalized_playlist.append(final_metadata)
                    normalized_playlist.extend(vlc_options_buffer)
                    normalized_playlist.append(line)
                    processed_urls.add(line)
                
                current_extinf = None
                vlc_options_buffer = []

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(normalized_playlist))
    print(f"Successfully processed list! Final clean playlist generated as: '{OUTPUT_FILE}'")

if __name__ == "__main__":
    fetch_and_filter_m3u()
