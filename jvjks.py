import os
import requests
from bs4 import BeautifulSoup
from discord_webhook import DiscordWebhook, DiscordEmbed
from datetime import datetime, timedelta
import time

# Configuration
WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL') # Get from environment variable
BASE_URL = 'https://javjunkies.org/main/2025/'  # Base URL with fixed year
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def generate_dynamic_base_url_for_day():
    """Generate the base URL for the previous day (e.g., https://javjunkies.org/main/2025/05-21-16/)"""
    yesterday = datetime.now() - timedelta(days=7)
    date_suffix = yesterday.strftime("%m-%d-16")
    return f"{BASE_URL}{date_suffix}/"

def scrape_vr_data():
    all_vr_results = []
    page_num = 1
    
    while True:
        current_day_base_url = generate_dynamic_base_url_for_day()
        if page_num == 1:
            dynamic_url = current_day_base_url
        else:
            dynamic_url = f"{current_day_base_url}{page_num}/"

        print(f"Scraping URL: {dynamic_url}")

        try:
            response = requests.get(dynamic_url, headers=HEADERS)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            video_entries_on_page = soup.find_all('div', class_='iH')
            
            # Check if any video entries were found on this page before processing
            if not video_entries_on_page and page_num > 1: # If no entries on a subsequent page, it's likely the end
                print(f"No video entries found on page {page_num}. Assuming end of content.")
                break

            for entry in video_entries_on_page:
                # Ensure the 'id' attribute exists and contains 'VR'
                if 'id' in entry.attrs and 'VR' in entry['id']:
                    video_code = entry['id'].replace('VR ', '').strip()
                    
                    style = entry.get('style')
                    image_url = None
                    if style and 'background-image:url(' in style:
                        start_index = style.find('background-image:url(') + len('background-image:url(')
                        end_index = style.find(')', start_index)
                        if start_index != -1 and end_index != -1:
                            image_url_relative = style[start_index:end_index].strip("'").strip('"')
                            if image_url_relative and not image_url_relative.startswith('http'):
                                image_url = f"https://javjunkies.org{image_url_relative}"
                            else:
                                image_url = image_url_relative
                    
                    # Only add to results if both code and image_url are valid
                    if video_code and image_url:
                        all_vr_results.append({
                            'code': video_code,
                            'image_url': image_url
                        })
                    else:
                        print(f"Skipping entry due to missing code or image for ID: {entry.get('id', 'N/A')}")
                # Optional: If you want to log entries that have 'id' but no 'VR'
                # elif 'id' in entry.attrs:
                #     print(f"Skipping non-VR entry: {entry['id']}")
                
                time.sleep(0.5) # Small delay to be polite

            # Pagination Logic:
            pagination_div = soup.find('strong', string='Pages:')
            if pagination_div:
                page_links = pagination_div.find_next_siblings('a')
                
                last_page_num = page_num 
                # Find the maximum page number from the links
                for link in page_links:
                    try:
                        page_number_from_link = int(link.text.strip())
                        if page_number_from_link > last_page_num:
                            last_page_num = page_number_from_link
                    except ValueError:
                        continue 
                
                if page_num < last_page_num:
                    page_num += 1
                    time.sleep(1) 
                else:
                    print(f"Reached last advertised page ({page_num}). Stopping pagination.")
                    break 
            else:
                print("No pagination links found. Assuming single page or end of pagination.")
                break 

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"Page {dynamic_url} not found (404). Assuming end of valid pages.")
                break 
            else:
                print(f"HTTP Error ({e.response.status_code}) for URL: {dynamic_url}. Breaking.")
                break
        except Exception as e:
            print(f"Error scraping data from {dynamic_url}: {str(e)}. Breaking.")
            break 

    return all_vr_results

def send_to_discord(video_data):
    # Keep track of sent items to avoid sending duplicates in case of re-runs if needed
    # For this script, we'll assume fresh run each time.
    
    print(f"Attempting to send {len(video_data)} items to Discord...")
    if not video_data:
        print("No video data provided to send to Discord.")
        return

    for item in video_data:
        # Crucial checks before sending to Discord
        if not item or not item.get('code') or not item.get('image_url'):
            print(f"Skipping Discord send for incomplete item: {item}. Missing 'code' or 'image_url'.")
            continue # Skip to the next item if this one is incomplete

        webhook = DiscordWebhook(url=WEBHOOK_URL)
        
        embed = DiscordEmbed(
            color="03b2f8"
        )
        
        # Ensure image_url is valid and set it
        if item['image_url']:
            embed.set_image(url=item['image_url'])
        else:
            print(f"Warning: No image URL found for {item['code']}. Sending embed without image.")

        try:
            webhook.add_embed(embed)
            response = webhook.execute()
            
            if response.status_code == 204: # 204 No Content is a successful Discord webhook response
                print(f"Successfully sent webhook for {item['code']}")
            else:
                print(f"Failed to send webhook for {item['code']}: Status Code {response.status_code} - Response: {response.text}")
        except Exception as e:
            print(f"An error occurred while sending webhook for {item['code']}: {str(e)}")
        
        time.sleep(1) # Prevent rate limiting

if __name__ == "__main__":
    video_data = scrape_vr_data()
    if video_data:
        send_to_discord(video_data)
        print(f"Finished sending {len(video_data)} VR items to Discord.")
    else:
        print("No VR data found to send for the previous day across all pages.")
