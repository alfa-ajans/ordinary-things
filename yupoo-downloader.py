import os
import aiohttp
import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from urllib.parse import urlparse
from alive_progress import alive_bar
from pyfiglet import Figlet
from termcolor import colored

figlet = Figlet(font='slant')
print(colored(figlet.renderText('ALFA AJANS'), 'cyan'))

# Birden fazla albüm veya kategori linki alma özelliği ekleniyor
albums_input = []
print(colored("Enter album or category URLs one by one (type 'q' to finish):", 'yellow'))
while True:
    album_url = input()
    if album_url.lower() == 'q':
        break
    albums_input.append(album_url)

main_folder = "yupoo_albums"
os.makedirs(main_folder, exist_ok=True)

# Headers ekliyoruz
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Referer": "https://brandgift.x.yupoo.com",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Cookie": "ar_debug=1"
}

# requests.Session() oluşturuyoruz
session = requests.Session()

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

async def get_category_albums(category_url):
    async with aiohttp.ClientSession() as session:
        page = 1
        total_albums = 0
        print(f"Fetching albums from category: {category_url}")
        album_links = []

        while True:
            page_url = f"{category_url}?page={page}"
            async with session.get(page_url, headers=headers) as response:
                if response.status == 200:
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, 'html.parser')

                    album_tags = soup.find_all('a', class_='album__main')
                    if not album_tags:
                        break

                    subdomain = get_subdomain_from_url(category_url)  # Subdomain'i al
                    for album_tag in album_tags:
                        album_path = album_tag.get('href')  # 'href' varsa al
                        if album_path:  # Kontrol ekliyoruz
                            album_url = f"https://{subdomain}.x.yupoo.com{album_path}"
                            album_links.append(album_url)

                    total_albums += len(album_tags)
                    page += 1
                else:
                    print(colored(f"Failed to fetch category page: {page}", "red"))
                    break

        print(f"Total albums found in category: {total_albums}")
        return album_links



async def download_from_category(category_url):
    album_links = await get_category_albums(category_url)

    if album_links:
        print(f"Found {len(album_links)} albums. Starting download...")
        with alive_bar(len(album_links), title="Downloading albums from category", bar="smooth", spinner="dots", theme="smooth") as bar:
            async with aiohttp.ClientSession() as session:
                for album_url in album_links:
                    await download_single_album(album_url)
                    bar()
    else:
        print(colored("No albums found in the category.", "red"))

async def count_total_albums(session, album_input_url):
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

async def get_album_links(album_input_url):
    async with aiohttp.ClientSession() as session:
        subdomain = get_subdomain_from_url(album_input_url)

        total_albums = await count_total_albums(session, album_input_url)

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
    async with aiohttp.ClientSession() as session:
        for album_url in albums_input:
            if "/albums/" in album_url and "?uid=" in album_url:
                await download_single_album(album_url)
            elif "/albums?tab=gallery" in album_url:
                await get_album_links(album_url)
            elif "/categories/" in album_url:  # Kategori URL'si kontrolü
                await download_from_category(album_url)
            else:
                print(colored(f"Invalid URL format for {album_url}!", "red"))

asyncio.run(main())
