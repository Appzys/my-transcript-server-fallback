from flask import Flask, request, jsonify, Response
import os, json
import logging
import requests
import re
import xml.etree.ElementTree as ET
from datetime import datetime

API_KEY = "x9J2f8S2pA9W-qZvB"
SCRAPE_TOKEN = "abbaa62bf3f54f5f9145d89d3f11fd3f6660572495a"

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


# -------- PROXY HELPERS -------- #

def scrape_get(url):
    proxy_url = f"http://api.scrape.do/?token={SCRAPE_TOKEN}&url={url}"
    return requests.get(proxy_url, timeout=25)


def scrape_post(url, payload):
    proxy_url = f"http://api.scrape.do/?token={SCRAPE_TOKEN}&url={url}"
    headers = {"Content-Type": "application/json"}
    return requests.post(proxy_url, data=json.dumps(payload), headers=headers, timeout=25)

# -------------------------------- #


@app.route("/")
def home():
    return {"status": "YouTube Transcript API Active 🚀", "auth": "required"}


@app.route("/transcript")
def get_transcript():

    request_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")

    client_key = request.headers.get("X-API-KEY")
    if client_key != API_KEY:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    video_id = (
        request.args.get("id")
        or request.args.get("v")
        or request.args.get("video_id")
    )

    if not video_id:
        return jsonify({
            "success": False,
            "error": "Missing parameter. Use /transcript?id=VIDEO_ID"
        }), 400

    try:
        logger.info(f"[{request_id}] START video={video_id}")

        # ---- WATCH PAGE ---- #
        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        watch_resp = scrape_get(watch_url)

        if watch_resp.status_code != 200:
            raise Exception("WATCH_FETCH_FAILED")

        html = watch_resp.text

        key_match = re.search(r'"INNERTUBE_API_KEY":"(.*?)"', html)
        if not key_match:
            raise Exception("INNERTUBE_KEY_NOT_FOUND")

        innertube_key = key_match.group(1)

        # ---- PLAYER API ---- #
        player_url = f"https://youtubei.googleapis.com/youtubei/v1/player?key={innertube_key}"

        payload = {
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "19.08.35",
                    "androidSdkVersion": 33
                }
            },
            "videoId": video_id
        }

        player_resp = scrape_post(player_url, payload)

        if player_resp.status_code != 200:
            raise Exception("PLAYER_FETCH_FAILED")

        player_json = player_resp.json()

        playability = player_json.get("playabilityStatus", {})
        if playability.get("status") == "LOGIN_REQUIRED":
            return jsonify({"success": False, "error": "LOGIN_REQUIRED"}), 500

        if "captions" not in player_json:
            return jsonify({"success": False, "error": "Transcript not available"}), 404

        tracks = player_json["captions"]["playerCaptionsTracklistRenderer"]["captionTracks"]

        selected = None
        for t in tracks:
            if not t.get("kind"):
                selected = t
                break

        if selected is None:
            selected = tracks[0]

        caption_url = selected["baseUrl"]
        lang = selected.get("languageCode", "unknown")

        # ---- CAPTION XML ---- #
        xml_resp = scrape_get(caption_url)

        if xml_resp.status_code != 200:
            raise Exception("CAPTION_FETCH_FAILED")

        root = ET.fromstring(xml_resp.text)

        subtitles = []
        format_used = "text"

        # -------- NORMAL FORMAT -------- #
        for node in root.iter("text"):
            subtitles.append({
                "text": (node.text or "").replace("\n", " ").strip(),
                "start": float(node.attrib.get("start", 0)),
                "duration": float(node.attrib.get("dur", 0)),
                "language": lang
            })

        # -------- SRV3 FALLBACK -------- #
        if len(subtitles) == 0:
            format_used = "srv3"

            for node in root.iter("p"):
                chunks = []
                for s in node.iter("s"):
                    if s.text:
                        chunks.append(s.text.strip())

                text_value = " ".join(chunks) if chunks else (node.text or "").strip()

                subtitles.append({
                    "text": text_value,
                    "start": float(node.attrib.get("t", 0)) / 1000,
                    "duration": float(node.attrib.get("d", 0)) / 1000,
                    "language": lang
                })

        logger.info(f"[{request_id}] SUCCESS count={len(subtitles)} format={format_used}")

        return Response(
            json.dumps({
                "success": True,
                "mode": "SCRAPE_PROXY",
                "count": len(subtitles),
                "lang": lang,
                "format": format_used,
                "subtitles": subtitles
            }, ensure_ascii=False),
            mimetype="application/json"
        )

    except Exception as e:
        logger.error(f"[{request_id}] ERROR={type(e).__name__} video={video_id}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"SERVER_STARTED port={port}")
    app.run(host="0.0.0.0", port=port)
