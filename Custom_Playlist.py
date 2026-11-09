import requests
import re
import os

# REVERTED TO GLOBAL LINK: Adhering strictly to your provided file source
ORIGINAL_M3U_URL = "https://iptv-org.github.io/iptv/index.m3u"
OUTPUT_FILE = "Custom_Playlist.m3u"
INPUT_TXT_FILE = "Channels.txt"

def load_channels_from_txt(file_path):
    """Reads the custom Channels.txt file and parses groups and channels structured in order."""
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
            
            # Detect group headers like [Sports Channels]
            if line.startswith("[") and line.endswith("]"):
                current_group = line[1:-1].strip()
                groups_dict[current_group] = []
            elif current_group is not None:
                groups_dict[current_group].append(line)
                
    return groups_dict

def strict_clean(name):
    """Advanced normaliser that strips all country tags, bracket info, resolutions, and special characters."""
    if not name:
        return ""
    name = name.lower()
    # Removes all content inside parentheses entirely, e.g., (720p), (india), (united states)
    name = re.sub(r'\(.*?\)', '', name)
    # Removes country domain suffixes often found in global lists like .in, .us, .tv
    name = re.sub(r'\.in|\.us|\.tv|\.ua|\.ru|\.net|\.ke|\.et|\.do', '', name)
    # Strips all resolutions, quality descriptors, spaces, and punctuations
    name = re.sub(r'hd|sd|fhd|uhd|i|p|\s+|_|-|\+|&|,', '', name)
    return name.strip()

def build_flat_lookup(groups_and_channels):
    """Builds a flat reverse-lookup map with auto-numbering based on the txt group index and order."""
    lookup_table = {}
    for g_idx, (group_name, channel_list) in enumerate(groups_and_channels.items(), start=1):
        for ch_idx, original_name in enumerate(channel_list, start=1):
            clean_key = strict_clean(original_name)
            if clean_key:
                channel_num = (g_idx * 100) + ch_idx
                lookup_table[clean_key] = (group_name, channel_num)
    return lookup_table

def fetch_and_filter_m3u():
    print(f"Loading target configurations from '{INPUT_TXT_FILE}'...")
    groups_config = load_channels_from_txt(INPUT_TXT_FILE)
    
    if not groups_config:
        print("No channels found to filter. Exiting.")
        return
        
    lookup_map = build_flat_lookup(groups_config)
    print(f"Lookup dictionary built successfully with {len(lookup_map)} lookup tokens.")
    
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
            if current_extinf:
                source_channel_name = current_extinf.split(',')[-1].strip()
                clean_source_key = strict_clean(source_channel_name)
                
                if clean_source_key in lookup_map:
                    matched_group, assigned_number = lookup_map[clean_source_key]
                    cleaned_metadata = re.sub(r'\s*group-title="[^"]+"', '', current_extinf)
                    final_metadata = re.sub(
                        r'^#EXTINF:([-0-9]*)', 
                        f'#EXTINF:\\1 group-title="{matched_group}" tvg-chno="{assigned_number}"', 
                        cleaned_metadata
                    )
                    
                    normalized_playlist.append(final_metadata)
                    normalized_playlist.extend(vlc_options_buffer)
                    normalized_playlist.append(line)
                
                current_extinf = None
                vlc_options_buffer = []

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(normalized_playlist))
    print(f"Successfully processed list! Final playlist generated as: '{OUTPUT_FILE}'")

if __name__ == "__main__":
    fetch_and_filter_m3u()
