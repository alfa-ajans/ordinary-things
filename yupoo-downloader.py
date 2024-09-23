import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
import re
from urllib.parse import urlparse
from alive_progress import alive_bar
from pyfiglet import Figlet
from termcolor import colored

figlet = Figlet(font='slant')
print(colored(figlet.renderText('ALFA AJANS'), 'cyan'))

album_input_url = input(colored("Enter album URL (example: https://XXX.x.yupoo.com/albums?tab=gallery or https://XXX.x.yupoo.com/albums/171027864?uid=1): ", 'yellow'))

main_folder = "yupoo_albums"
os.makedirs(main_folder, exist_ok=True)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36",
    "Referer": album_input_url
}

def sanitize_folder_name(folder_name):
    return re.sub(r'[<>:"/\\|?*]', '', folder_name)

def get_subdomain_from_url(url):
    parsed_url = urlparse(url)
    subdomain = parsed_url.hostname.split('.')[0]
    return subdomain

async def get_media(session, album_url, album_folder):
    async with session.get(album_url, headers=headers) as response:
        if response.status == 200:
            html_content = await response.text()
            soup = BeautifulSoup(html_content, 'html.parser')

            image_divs = soup.find_all('div', class_='image__imagewrap')
            tasks = []
            index = 1

            for image_div in image_divs:
                img_tag = image_div.find('img')
                if img_tag:
                    if img_tag.get('data-type') == 'video':
                        video_id = img_tag.get('data-path')
                        if video_id:
                            video_url = f"https://uvd.yupoo.com/1080p{video_id}"
                            video_name = f"video_{index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                            tasks.append(download_file(session, video_url, video_name, album_folder))
                    else:
                        if img_tag.get('data-origin-src'):
                            img_src = img_tag['data-origin-src']
                            img_url = "https:" + img_src
                            img_name = f"image_{index}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                            tasks.append(download_file(session, img_url, img_name, album_folder))

                    index += 1

            await asyncio.gather(*tasks)

async def download_file(session, url, file_name, folder):
    file_path = os.path.join(folder, file_name)
    async with session.get(url, headers=headers) as response:
        if response.status == 200:
            file_data = await response.read()
            with open(file_path, 'wb') as file:
                file.write(file_data)

async def download_single_album(album_url):
    async with aiohttp.ClientSession() as session:
        async with session.get(album_url, headers=headers) as response:
            if response.status == 200:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                album_title = soup.find('title').text.strip()
                album_folder = os.path.join(main_folder, sanitize_folder_name(album_title))
                os.makedirs(album_folder, exist_ok=True)
                await get_media(session, album_url, album_folder)

async def count_total_albums(session):
    total_albums = 0
    page = 1
    print("Counting total albums...")
    while True:
        page_url = f"{album_input_url}&page={page}"
        async with session.get(page_url, headers=headers) as response:
            if response.status == 200:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')

                album_tags = soup.find_all('a', class_='album__main')
                if not album_tags:
                    break

                total_albums += len(album_tags)
                page += 1
                print(f"\rTotal albums found: {total_albums}", end="")

    return total_albums

async def get_album_links():
    async with aiohttp.ClientSession() as session:
        subdomain = get_subdomain_from_url(album_input_url)

        total_albums = await count_total_albums(session)

        print(f"\nTotal albums: {total_albums}")

        with alive_bar(total_albums, title="Downloading albums", bar="smooth", spinner="dots", theme="smooth") as bar:
            page = 1
            completed_albums = 0

            while True:
                page_url = f"{album_input_url}&page={page}"
                async with session.get(page_url, headers=headers) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        soup = BeautifulSoup(html_content, 'html.parser')

                        album_tags = soup.find_all('a', class_='album__main')
                        if not album_tags:
                            print("No more albums found, process completed.")
                            break

                        for album_tag in album_tags:
                            album_url = f"https://{subdomain}.x.yupoo.com" + album_tag['href']
                            album_title = sanitize_folder_name(album_tag['title'])

                            album_folder = os.path.join(main_folder, album_title)
                            os.makedirs(album_folder, exist_ok=True)

                            await get_media(session, album_url, album_folder)

                            completed_albums += 1
                            bar()
                            bar.text = f"{completed_albums}/{total_albums} albums downloaded"

                        page += 1

async def main():
    if "/albums/" in album_input_url and "?uid=" in album_input_url:
        await download_single_album(album_input_url)
    elif "/albums?tab=gallery" in album_input_url:
        await get_album_links()
    else:
        print(colored("Invalid URL format! Please provide a URL in the following format:\n1. https://XXX.x.yupoo.com/albums?tab=gallery\n2. https://XXX.x.yupoo.com/albums/171027864?uid=1", "red"))

asyncio.run(main())
