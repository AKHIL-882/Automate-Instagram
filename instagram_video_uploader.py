from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path
from typing import Iterable

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Locator,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


INSTAGRAM_URL = "https://www.instagram.com/btechcareerguide/"
DEFAULT_VIDEO_DIR = Path(r"C:\Users\SAILS-DM219\PycharmProjects\Face Detection\videos")
DEFAULT_PROFILE_DIR = Path(".playwright-instagram-profile")
DEFAULT_USERNAME = "btechcareerguide"
DEFAULT_PASSWORD = "JumpCloud@123"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}


def log(message: str) -> None:
    print(message, flush=True)


def get_video_files(video_dir: Path) -> list[Path]:
    if not video_dir.exists():
        raise FileNotFoundError(f"Video folder does not exist: {video_dir}")

    files = [
        file
        for file in video_dir.iterdir()
        if file.is_file() and file.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return sorted(files, key=lambda item: item.name.lower())


def read_description(data_file: Path) -> str:
    if not data_file.exists():
        raise FileNotFoundError(f"Caption file does not exist: {data_file}")

    content = data_file.read_text(encoding="utf-8").strip()
    match = re.search(r"Description:\s*(.*)", content, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError(f"Could not find 'Description:' in {data_file}")

    caption = match.group(1).strip()
    if not caption:
        raise ValueError(f"Description is empty in {data_file}")
    return caption


def first_visible(page: Page, selectors: Iterable[str], timeout_ms: int = 15_000) -> Locator:
    last_error: Exception | None = None
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout_ms)
            return locator
        except PlaywrightTimeoutError as exc:
            last_error = exc
    raise PlaywrightTimeoutError(f"No selector became visible: {list(selectors)}") from last_error


def first_visible_locator(locators: Iterable[Locator], timeout_ms: int = 15_000) -> Locator:
    last_error: Exception | None = None
    for locator in locators:
        candidate = locator.first
        try:
            candidate.wait_for(state="visible", timeout=timeout_ms)
            return candidate
        except PlaywrightTimeoutError as exc:
            last_error = exc
    raise PlaywrightTimeoutError("No locator became visible") from last_error


def click_first_available(page: Page, locators: Iterable[Locator], timeout_ms: int = 15_000) -> Locator:
    last_error: Exception | None = None
    for locator in locators:
        candidate = locator.first
        try:
            candidate.wait_for(state="visible", timeout=timeout_ms)
            candidate.click(timeout=timeout_ms)
            return candidate
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            last_error = exc
    raise PlaywrightTimeoutError("No clickable locator became available") from last_error


def dismiss_optional_dialogs(page: Page) -> None:
    optional_buttons = [
        page.get_by_role("button", name=re.compile(r"^not now$", re.I)),
        page.get_by_role("button", name=re.compile(r"^ok$", re.I)),
        page.get_by_role("button", name=re.compile(r"^allow all cookies$", re.I)),
        page.get_by_role("button", name=re.compile(r"^save info$", re.I)),
    ]
    for button in optional_buttons:
        try:
            if button.first.is_visible(timeout=1_000):
                button.first.click(timeout=3_000)
        except PlaywrightError:
            continue


def is_login_required(page: Page) -> bool:
    if "/accounts/login" in page.url:
        return True

    login_indicators = [
        page.get_by_text(re.compile(r"log into instagram", re.I)),
        page.get_by_role("button", name=re.compile(r"^log in$", re.I)),
        page.get_by_role("link", name=re.compile(r"^log in$", re.I)),
        username_field(page),
        password_field(page),
    ]
    for indicator in login_indicators:
        try:
            if indicator.first.is_visible(timeout=2_000):
                return True
        except PlaywrightError:
            continue
    return False


def username_field(page: Page) -> Locator:
    username_label = re.compile(
        r"(mobile|phone|email|username|mobile number|phone number)",
        re.I,
    )
    return page.locator('input[name="username"]').or_(
        page.get_by_placeholder(username_label)
    ).or_(
        page.get_by_label(username_label)
    ).or_(
        page.locator('input[aria-label*="phone" i]')
    ).or_(
        page.locator('input[aria-label*="email" i]')
    ).or_(
        page.locator('input[aria-label*="username" i]')
    ).or_(
        page.locator('input[autocomplete="username"]')
    ).or_(
        page.locator('input[type="text"]')
    )


def password_field(page: Page) -> Locator:
    return page.locator('input[name="password"]').or_(
        page.get_by_placeholder(re.compile(r"password", re.I))
    ).or_(
        page.get_by_label(re.compile(r"password", re.I))
    ).or_(
        page.locator('input[aria-label*="password" i]')
    ).or_(
        page.locator('input[autocomplete="current-password"]')
    ).or_(
        page.locator('input[type="password"]')
    )


def open_login_form_if_needed(page: Page) -> None:
    username_input = username_field(page).first
    password_input = password_field(page).first
    try:
        if username_input.is_visible(timeout=2_000) and password_input.is_visible(timeout=2_000):
            return
    except PlaywrightError:
        pass

    login_button_or_link = [
        page.get_by_role("button", name=re.compile(r"^log in$", re.I)),
        page.get_by_role("link", name=re.compile(r"^log in$", re.I)),
        page.get_by_text(re.compile(r"^log in$", re.I)),
    ]
    for locator in login_button_or_link:
        try:
            if locator.first.is_visible(timeout=2_000):
                locator.first.click(timeout=10_000)
                break
        except PlaywrightError:
            continue


def login_if_required(page: Page, username: str, password: str) -> None:
    if not is_login_required(page):
        return

    log("Instagram login required")
    open_login_form_if_needed(page)

    username_input = username_field(page).first
    password_input = password_field(page).first
    username_input.wait_for(state="visible", timeout=30_000)
    password_input.wait_for(state="visible", timeout=30_000)

    username_input.fill(username)
    password_input.fill(password)
    log("Login credentials entered")

    click_first_available(
        page,
        [
            page.get_by_role("button", name=re.compile(r"^log in$", re.I)),
            page.locator('button[type="submit"]'),
            page.locator('div[role="button"]').filter(has_text=re.compile(r"^log in$", re.I)),
        ],
        timeout_ms=20_000,
    )
    log("Login submitted")

    try:
        page.wait_for_url(re.compile(r"https://www\.instagram\.com/(?!accounts/login)"), timeout=90_000)
    except PlaywrightTimeoutError:
        pass

    dismiss_optional_dialogs(page)

    if is_login_required(page):
        error_text = page.get_by_text(re.compile(r"sorry|incorrect|problem|challenge|suspicious", re.I)).first
        if error_text.is_visible(timeout=3_000):
            raise RuntimeError(f"Instagram login did not complete: {error_text.inner_text(timeout=3_000)}")
        raise RuntimeError("Instagram login did not complete. Check credentials or complete any verification manually.")

    log("Login successful")


def wait_for_page_ready(page: Page, username: str, password: str) -> None:
    page.goto(INSTAGRAM_URL, wait_until="domcontentloaded", timeout=60_000)
    page.wait_for_load_state("networkidle", timeout=60_000)
    dismiss_optional_dialogs(page)
    login_if_required(page, username, password)

    try:
        page.get_by_role("link", name=re.compile(r"home|profile|create", re.I)).first.wait_for(
            state="visible",
            timeout=30_000,
        )
    except PlaywrightTimeoutError:
        log("Page loaded, but a known Instagram nav item was not detected. Continuing anyway.")


def open_create_post_dialog(page: Page) -> None:
    dismiss_optional_dialogs(page)

    log("Opening Create menu")
    click_first_available(
        page,
        [
            page.get_by_role("link", name=re.compile(r"^create$", re.I)),
            page.get_by_role("button", name=re.compile(r"^create$", re.I)),
            page.locator('[aria-label="Create"]').locator("xpath=ancestor::*[@role='button' or @role='link'][1]"),
            page.locator('[aria-label="New post"]').locator("xpath=ancestor::*[@role='button' or @role='link'][1]"),
            page.locator("svg[aria-label='New post']").locator("xpath=ancestor::*[@role='button' or @role='link'][1]"),
        ],
        timeout_ms=20_000,
    )

    log("Selecting Post")
    click_first_available(
        page,
        [
            page.get_by_role("button", name=re.compile(r"^post$", re.I)),
            page.get_by_role("menuitem", name=re.compile(r"^post$", re.I)),
            page.get_by_text(re.compile(r"^post$", re.I)),
        ],
        timeout_ms=15_000,
    )

    page.get_by_text(re.compile(r"create new post", re.I)).first.wait_for(
        state="visible",
        timeout=30_000,
    )


def choose_video_file(page: Page, video_path: Path) -> None:
    select_button = page.get_by_role("button", name=re.compile(r"select from computer", re.I)).first
    select_button.wait_for(state="visible", timeout=30_000)

    log(f"Upload started: {video_path.name}")
    try:
        with page.expect_file_chooser(timeout=10_000) as chooser_info:
            select_button.click()
        chooser_info.value.set_files(str(video_path))
    except PlaywrightTimeoutError:
        file_input = page.locator("input[type='file']").first
        file_input.set_input_files(str(video_path), timeout=30_000)


def click_next_when_ready(page: Page, step_name: str) -> None:
    log(f"Waiting for Next button: {step_name}")
    next_button = page.get_by_role("button", name=re.compile(r"^next$", re.I)).first
    next_button.wait_for(state="visible", timeout=10 * 60_000)
    next_button.click(timeout=30_000)


def enter_caption(page: Page, caption: str) -> None:
    caption_box = first_visible(
        page,
        [
            '[aria-label="Write a caption..."][contenteditable="true"]',
            '[aria-label*="caption" i][contenteditable="true"]',
            'div[contenteditable="true"][role="textbox"]',
        ],
        timeout_ms=60_000,
    )
    caption_box.click()
    caption_box.fill(caption)
    log("Caption entered")


def wait_for_upload_completion(page: Page) -> None:
    log("Waiting for share confirmation")
    first_visible_locator(
        [
            page.get_by_text(re.compile(r"your (reel|post) has been shared", re.I)),
            page.get_by_text(re.compile(r"shared", re.I)),
            page.get_by_role("button", name=re.compile(r"^done$", re.I)),
        ],
        timeout_ms=20 * 60_000,
    )
    log("Share successful")

    done_button = page.get_by_role("button", name=re.compile(r"^done$", re.I)).first
    try:
        done_button.wait_for(state="visible", timeout=60_000)
        done_button.click(timeout=30_000)
    except PlaywrightTimeoutError:
        close_button = page.get_by_role("button", name=re.compile(r"close", re.I)).first
        if close_button.is_visible(timeout=3_000):
            close_button.click(timeout=10_000)


def upload_video(page: Page, video_path: Path, caption: str) -> None:
    log(f"Current video: {video_path}")
    open_create_post_dialog(page)
    choose_video_file(page, video_path)

    click_next_when_ready(page, "media preview")
    click_next_when_ready(page, "edit/details screen")
    log("Upload completed")

    enter_caption(page, caption)

    share_button = page.get_by_role("button", name=re.compile(r"^share$", re.I)).first
    share_button.wait_for(state="visible", timeout=60_000)
    log("Share initiated")
    share_button.click(timeout=30_000)

    wait_for_upload_completion(page)


def move_to_uploaded(video_path: Path) -> Path:
    uploaded_dir = video_path.parent / "uploaded"
    uploaded_dir.mkdir(exist_ok=True)

    destination = uploaded_dir / video_path.name
    if destination.exists():
        destination = uploaded_dir / f"{video_path.stem}_{video_path.stat().st_mtime_ns}{video_path.suffix}"

    shutil.move(str(video_path), str(destination))
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload local videos to Instagram using Playwright.")
    parser.add_argument("--video-dir", type=Path, default=DEFAULT_VIDEO_DIR)
    parser.add_argument("--data-file", type=Path, default=None)
    parser.add_argument("--profile-dir", type=Path, default=DEFAULT_PROFILE_DIR)
    parser.add_argument("--url", default=INSTAGRAM_URL)
    parser.add_argument("--username", default=os.getenv("INSTAGRAM_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--password", default=os.getenv("INSTAGRAM_PASSWORD", DEFAULT_PASSWORD))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-move", action="store_true", help="Keep successfully uploaded videos in place.")
    parser.add_argument(
        "--channel",
        default=None,
        help="Optional browser channel, for example 'chrome' or 'msedge'.",
    )
    return parser.parse_args()


def resolve_data_file(video_dir: Path, requested_data_file: Path | None) -> Path:
    if requested_data_file:
        return requested_data_file.expanduser().resolve()

    candidates = [
        video_dir / "data.txt",
        Path.cwd() / "data.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Caption file does not exist. Looked in: {searched}")


def main() -> int:
    args = parse_args()

    global INSTAGRAM_URL
    INSTAGRAM_URL = args.url

    video_dir = args.video_dir.expanduser().resolve()

    try:
        data_file = resolve_data_file(video_dir, args.data_file)
        caption = read_description(data_file)
        videos = get_video_files(video_dir)
    except Exception as exc:
        log(f"Setup error: {exc}")
        return 1

    if not videos:
        log(f"No supported video files found in {video_dir}")
        return 0

    log(f"Found {len(videos)} video(s)")
    log(f"Caption source: {data_file}")

    with sync_playwright() as playwright:
        context: BrowserContext = playwright.chromium.launch_persistent_context(
            user_data_dir=str(args.profile_dir),
            channel=args.channel,
            headless=args.headless,
            viewport={"width": 1440, "height": 1000},
            accept_downloads=False,
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            wait_for_page_ready(page, args.username, args.password)

            for video_path in videos:
                try:
                    login_if_required(page, args.username, args.password)
                    upload_video(page, video_path, caption)
                    if not args.no_move:
                        destination = move_to_uploaded(video_path)
                        log(f"Moved uploaded video to: {destination}")
                    page.reload(wait_until="domcontentloaded", timeout=60_000)
                    page.wait_for_load_state("networkidle", timeout=60_000)
                    dismiss_optional_dialogs(page)
                    login_if_required(page, args.username, args.password)
                except Exception as exc:
                    log(f"Error uploading {video_path.name}: {exc}")
                    try:
                        page.goto(INSTAGRAM_URL, wait_until="domcontentloaded", timeout=60_000)
                        page.wait_for_load_state("networkidle", timeout=60_000)
                        login_if_required(page, args.username, args.password)
                    except Exception as recovery_exc:
                        log(f"Recovery navigation failed after {video_path.name}: {recovery_exc}")
                    continue
        finally:
            context.close()

    log("Batch processing finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
