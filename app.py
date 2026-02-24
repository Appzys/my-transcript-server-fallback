from flask import Flask, request, jsonify, Response
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import os, json
import logging
from datetime import datetime

API_KEY = "x9J2f8S2pA9W-qZvB"

app = Flask(__name__)

# -------- Minimal Logging -------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)
# --------------------------------- #


@app.route("/")
def home():
    return {"status": "YouTube Transcript API Active 🚀", "auth": "required"}


@app.route("/transcript")
def get_transcript():

    request_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")

    # API KEY CHECK
    client_key = request.headers.get("X-API-KEY")
    if client_key != API_KEY:
        logger.warning(f"[{request_id}] UNAUTHORIZED")
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    video_id = (
        request.args.get("id")
        or request.args.get("v")
        or request.args.get("video_id")
    )

    if not video_id:
        logger.warning(f"[{request_id}] MISSING_VIDEO_ID")
        return jsonify({
            "success": False,
            "error": "Missing parameter. Use /transcript?id=VIDEO_ID"
        }), 400

    try:
        api = YouTubeTranscriptApi()
        transcripts = api.list(video_id)

        t = None

        for tc in transcripts:
            if not tc.is_generated:
                t = tc
                break

        if t is None:
            for tc in transcripts:
                if tc.is_generated:
                    t = tc
                    break

        if t is None:
            t = list(transcripts)[0]

        data = t.fetch()

        subtitles = [{
            "text": x.text,
            "start": x.start,
            "duration": x.duration,
            "language": t.language_code
        } for x in data]

        return Response(
            json.dumps({
                "success": True,
                "mode": "YTA",
                "count": len(subtitles),
                "lang": t.language_code,
                "format": "manual" if not t.is_generated else "auto",
                "subtitles": subtitles
            }, ensure_ascii=False),
            mimetype="application/json"
        )

    except (TranscriptsDisabled, NoTranscriptFound):
        logger.warning(f"[{request_id}] NO_TRANSCRIPT_AVAILABLE video={video_id}")
        return jsonify({"success": False, "error": "Transcript not available"}), 404

    except Exception as e:
        error_name = type(e).__name__

        # 🔴 Important: detect YouTube IP block
        if "RequestBlocked" in error_name:
            logger.error(f"[{request_id}] LOGIN_REQUIRED_OR_IP_BLOCK video={video_id}")
        else:
            logger.error(f"[{request_id}] ERROR={error_name} video={video_id}")

        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"SERVER_STARTED port={port}")
    app.run(host="0.0.0.0", port=port)
