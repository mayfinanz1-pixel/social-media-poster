"""
Posts a carousel/multi-image post to Facebook, Instagram and LinkedIn at once.

Looks for subfolders under posts/pending/. Each subfolder is one post and must
contain a caption.txt plus one or more images (.jpg/.jpeg/.png), named so that
alphabetical order matches the order they should appear in (01.jpg, 02.jpg, ...).

On success, a post's folder is moved to posts/done/. On failure it stays in
posts/pending/ and an error.log is written next to it so the next run doesn't
silently retry a broken post forever without a trace.
"""

import os
import sys
import shutil
import mimetypes
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
PENDING_DIR = REPO_ROOT / "posts" / "pending"
DONE_DIR = REPO_ROOT / "posts" / "done"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

FB_GRAPH_VERSION = "v21.0"


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_post(folder: Path):
    caption_file = folder / "caption.txt"
    if not caption_file.exists():
        raise RuntimeError(f"{folder.name}: no caption.txt found")
    caption = caption_file.read_text(encoding="utf-8").strip()

    images = sorted(
        p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        raise RuntimeError(f"{folder.name}: no images found")
    if len(images) > 10:
        raise RuntimeError(
            f"{folder.name}: {len(images)} images found, Instagram carousels allow max 10"
        )

    return caption, images


def upload_to_wordpress(image_path: Path, wp_url: str, wp_user: str, wp_app_password: str) -> str:
    """Uploads an image to the WordPress media library and returns its public URL.

    Needed because Instagram's Graph API requires a publicly reachable image_url
    per carousel item; it cannot accept raw binary data.
    """
    mime_type, _ = mimetypes.guess_type(image_path.name)
    mime_type = mime_type or "application/octet-stream"

    resp = requests.post(
        f"{wp_url.rstrip('/')}/wp-json/wp/v2/media",
        auth=(wp_user, wp_app_password),
        headers={
            "Content-Disposition": f'attachment; filename="{image_path.name}"',
            "Content-Type": mime_type,
        },
        data=image_path.read_bytes(),
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["source_url"]


def post_facebook(image_urls, caption, page_id, page_token):
    photo_ids = []
    for url in image_urls:
        resp = requests.post(
            f"https://graph.facebook.com/{FB_GRAPH_VERSION}/{page_id}/photos",
            data={
                "url": url,
                "published": "false",
                "access_token": page_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        photo_ids.append(resp.json()["id"])

    attached_media = [{"media_fbid": pid} for pid in photo_ids]
    resp = requests.post(
        f"https://graph.facebook.com/{FB_GRAPH_VERSION}/{page_id}/feed",
        json={
            "message": caption,
            "attached_media": attached_media,
            "access_token": page_token,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def post_instagram(image_urls, caption, ig_user_id, page_token):
    if len(image_urls) == 1:
        resp = requests.post(
            f"https://graph.facebook.com/{FB_GRAPH_VERSION}/{ig_user_id}/media",
            data={
                "image_url": image_urls[0],
                "caption": caption,
                "access_token": page_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        creation_id = resp.json()["id"]
    else:
        child_ids = []
        for url in image_urls:
            resp = requests.post(
                f"https://graph.facebook.com/{FB_GRAPH_VERSION}/{ig_user_id}/media",
                data={
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": page_token,
                },
                timeout=60,
            )
            resp.raise_for_status()
            child_ids.append(resp.json()["id"])

        resp = requests.post(
            f"https://graph.facebook.com/{FB_GRAPH_VERSION}/{ig_user_id}/media",
            data={
                "media_type": "CAROUSEL",
                "children": ",".join(child_ids),
                "caption": caption,
                "access_token": page_token,
            },
            timeout=60,
        )
        resp.raise_for_status()
        creation_id = resp.json()["id"]

    resp = requests.post(
        f"https://graph.facebook.com/{FB_GRAPH_VERSION}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": page_token},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def post_linkedin(cover_image_url, caption, person_urn, access_token):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "LinkedIn-Version": "202405",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    resp = requests.post(
        "https://api.linkedin.com/rest/images?action=initializeUpload",
        headers=headers,
        json={"initializeUploadRequest": {"owner": person_urn}},
        timeout=60,
    )
    resp.raise_for_status()
    upload_info = resp.json()["value"]
    upload_url = upload_info["uploadUrl"]
    image_urn = upload_info["image"]

    image_bytes = requests.get(cover_image_url, timeout=60)
    image_bytes.raise_for_status()

    put_resp = requests.put(
        upload_url,
        headers={"Authorization": f"Bearer {access_token}"},
        data=image_bytes.content,
        timeout=60,
    )
    put_resp.raise_for_status()

    resp = requests.post(
        "https://api.linkedin.com/rest/posts",
        headers=headers,
        json={
            "author": person_urn,
            "commentary": caption,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "content": {"media": {"id": image_urn}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.headers.get("x-restli-id", "ok")


def process_post(folder: Path, config) -> None:
    caption, image_paths = load_post(folder)

    print(f"[{folder.name}] uploading {len(image_paths)} image(s) to WordPress ...")
    image_urls = [
        upload_to_wordpress(p, config["wp_url"], config["wp_user"], config["wp_app_password"])
        for p in image_paths
    ]

    print(f"[{folder.name}] posting to Facebook ...")
    post_facebook(image_urls, caption, config["fb_page_id"], config["fb_page_token"])

    print(f"[{folder.name}] posting to Instagram ...")
    post_instagram(image_urls, caption, config["ig_user_id"], config["fb_page_token"])

    print(f"[{folder.name}] posting to LinkedIn (cover image only) ...")
    post_linkedin(image_urls[0], caption, config["linkedin_person_urn"], config["linkedin_access_token"])

    DONE_DIR.mkdir(parents=True, exist_ok=True)
    destination = DONE_DIR / folder.name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.move(str(folder), str(destination))
    print(f"[{folder.name}] done, moved to posts/done/")


def main() -> int:
    config = {
        "fb_page_id": env("FB_PAGE_ID"),
        "fb_page_token": env("FB_PAGE_ACCESS_TOKEN"),
        "ig_user_id": env("IG_USER_ID"),
        "linkedin_person_urn": env("LINKEDIN_PERSON_URN"),
        "linkedin_access_token": env("LINKEDIN_ACCESS_TOKEN"),
        "wp_url": env("WP_SITE_URL"),
        "wp_user": env("WP_USERNAME"),
        "wp_app_password": env("WP_APP_PASSWORD"),
    }

    if not PENDING_DIR.exists():
        print("No posts/pending directory found, nothing to do.")
        return 0

    post_folders = sorted(p for p in PENDING_DIR.iterdir() if p.is_dir())
    if not post_folders:
        print("No pending posts found.")
        return 0

    had_failure = False
    for folder in post_folders:
        error_log = folder / "error.log"
        try:
            process_post(folder, config)
            if error_log.exists():
                error_log.unlink()
        except Exception as exc:  # noqa: BLE001 - surface every failure, keep processing others
            had_failure = True
            print(f"[{folder.name}] FAILED: {exc}", file=sys.stderr)
            error_log.write_text(str(exc), encoding="utf-8")

    return 1 if had_failure else 0


if __name__ == "__main__":
    sys.exit(main())
