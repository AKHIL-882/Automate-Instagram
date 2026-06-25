# Automate-Instagram

Playwright automation for uploading videos from a local folder to Instagram.

## Setup

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

Put `data.txt` in the project folder or in the video folder with this format:

```text
Description: Your Instagram caption here
```

Run:

```powershell
python .\instagram_video_uploader.py
```

Defaults:

- Instagram URL: `https://www.instagram.com/btechcareerguide/`
- Instagram username: `btechcareerguide`
- Video folder: `C:\Users\SAILS-DM219\PycharmProjects\Face Detection\videos`
- Supported video extensions: `.mp4`, `.mov`, `.avi`, `.mkv`
- Successful uploads are moved to an `uploaded` subfolder.

The script uses a persistent Playwright profile at `.playwright-instagram-profile`.
If that profile is not already logged into Instagram, run the script once, log in
manually in the opened browser, then run it again.

Useful options:

```powershell
python .\instagram_video_uploader.py --no-move
python .\instagram_video_uploader.py --video-dir "C:\path\to\videos" --data-file "C:\path\to\data.txt"
python .\instagram_video_uploader.py --channel chrome --profile-dir "C:\path\to\playwright-profile"
python .\instagram_video_uploader.py --username "your_username" --password "your_password"
```

You can also set credentials with environment variables:

```powershell
$env:INSTAGRAM_USERNAME="your_username"
$env:INSTAGRAM_PASSWORD="your_password"
python .\instagram_video_uploader.py
```
