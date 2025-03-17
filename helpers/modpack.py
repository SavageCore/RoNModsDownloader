import os
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm


def download_file(url, save_path):
    """
    Downloads a file from a given URL and saves it to a local path with a progress bar.
    """
    if not os.path.exists(save_path):  # Skip if file already exists
        with requests.get(url, stream=True) as response:
            response.raise_for_status()

            # Get the total file size (in bytes) from headers
            total_size = int(response.headers.get("content-length", 0))

            # Open the file and start downloading with a progress bar
            with open(save_path, "wb") as file, tqdm(
                desc=f"Downloading {os.path.basename(save_path)}",
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                initial=0,
                miniters=1,
            ) as progress_bar:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Filter out keep-alive new chunks
                        file.write(chunk)
                        progress_bar.update(len(chunk))  # Update progress bar


def download_folder(url, local_path):
    """
    Downloads an entire folder recursively from an NGINX directory listing.
    """
    # Ensure local path exists
    if not os.path.exists(local_path):
        os.makedirs(local_path)

    # Fetch the content of the directory
    response = requests.get(url)
    response.raise_for_status()

    # Parse the HTML content of the directory
    soup = BeautifulSoup(response.text, "html.parser")

    # Find all links in the directory listing
    for link in soup.select("tbody a"):
        href = link.get("href")

        if href and href not in ["../"]:  # Skip parent directory
            # Decode URL-encoded characters
            decoded_href = unquote(href)

            full_url = urljoin(url, href)
            local_file_path = os.path.join(local_path, decoded_href)

            if href.endswith("/"):
                # Recursively download the folder
                download_folder(full_url, local_file_path)
            else:
                # Download the file
                download_file(full_url, local_file_path)


def list_folder(url, sub_folder):
    """
    Lists all files and folders in an NGINX directory listing, including subfolders.
    """

    def fetch_files_and_folders(url):
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        files = []
        folders = []
        for link in soup.select("tbody a"):
            href = link.get("href")
            if href and href not in ["../"]:  # Skip parent directory
                decoded_href = unquote(href)
                if href.endswith("/"):
                    folders.append(decoded_href)
                else:
                    files.append(decoded_href)
        return files, folders

    def list_all_files(url, base_url, sub_folder):
        all_files = []
        files, folders = fetch_files_and_folders(url)
        for file in files:
            relative_file = os.path.normpath(
                "mods/"+ sub_folder + "/" + url.replace(base_url, "") + file
            ).replace("\\", "/")
            all_files.append(relative_file)
        for folder in folders:
            folder_url = url + folder
            all_files.extend(list_all_files(folder_url, base_url, sub_folder))
        return all_files

    base_url = url if url.endswith("/") else url + "/"
    all_files = list_all_files(base_url, base_url, sub_folder)
    return all_files
