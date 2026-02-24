from flask import Flask, request, jsonify, Response
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import os, json
import logging
import traceback
from datetime import datetime

API_KEY = "x9J2f8S2pA9W-qZvB"

app = Flask(__name__)

# ---------------- LOGGING CONFIGURATION ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

logger.info("Application initialized")
# ------------------------------------------------------- #


# Root
@app.route("/")
def home():
    logger.info("Root endpoint accessed")
    return {"status": "YouTube Transcript API Active 🚀", "auth": "required"}


# Transcript Route
@app.route("/transcript")
def get_transcript():

    request_id = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    logger.info(f"[{request_id}] Incoming /transcript request")
    logger.info(f"[{request_id}] Headers: {dict(request.headers)}")
    logger.info(f"[{request_id}] Query Params: {dict(request.args)}")

    # -------- API KEY CHECK -------- #
    client_key = request.headers.get("X-API-KEY")
    if client_key != API_KEY:
        logger.warning(f"[{request_id}] Unauthorized access attempt. Provided key: {client_key}")
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    logger.info(f"[{request_id}] API key validated successfully")

    # now supports id, v, video_id ✔
    video_id = (
        request.args.get("id")
        or request.args.get("v")
        or request.args.get("video_id")
    )

    if not video_id:
        logger.error(f"[{request_id}] Missing video_id parameter")
        return jsonify({"success": False,
                        "error": "Missing parameter. Use /transcript?id=VIDEO_ID"}), 400

    logger.info(f"[{request_id}] Processing video_id: {video_id}")

    try:
        logger.info(f"[{request_id}] Initializing YouTubeTranscriptApi")
        api = YouTubeTranscriptApi()

        logger.info(f"[{request_id}] Fetching transcript list")
        transcripts = api.list(video_id)

        logger.info(f"[{request_id}] Transcript list retrieved successfully")

        # -------- Language priority -------- #
        t = None

        # 1. Prefer Manual CC if exists
        logger.info(f"[{request_id}] Searching for manual transcripts")
        for tc in transcripts:
            logger.info(f"[{request_id}] Found transcript: lang={tc.language_code}, generated={tc.is_generated}")
            if not tc.is_generated:
                t = tc
                logger.info(f"[{request_id}] Selected manual transcript: {tc.language_code}")
                break

        # 2. Then Auto CC
        if t is None:
            logger.info(f"[{request_id}] Manual transcript not found. Searching for auto-generated transcript")
            for tc in transcripts:
                if tc.is_generated:
                    t = tc
                    logger.info(f"[{request_id}] Selected auto transcript: {tc.language_code}")
                    break

        # 3. Fallback first available
        if t is None:
            logger.info(f"[{request_id}] No manual/auto distinction found. Falling back to first available transcript")
            t = list(transcripts)[0]
            logger.info(f"[{request_id}] Fallback transcript selected: {t.language_code}")

        logger.info(f"[{request_id}] Fetching transcript content")
        data = t.fetch()
        logger.info(f"[{request_id}] Transcript fetch successful. Total segments: {len(data)}")

        # -------- Final Output Format -------- #
        subtitles = [{
            "text": x.text,
            "start": x.start,
            "duration": x.duration,
            "language": t.language_code
        } for x in data]

        logger.info(f"[{request_id}] Subtitles formatted successfully")

        response_json = {
            "success": True,
            "mode": "YTA",
            "count": len(subtitles),
            "lang": t.language_code,
            "format": "manual" if not t.is_generated else "auto",
            "subtitles": subtitles
        }

        logger.info(f"[{request_id}] Response ready. Returning success response")

        return Response(
            json.dumps(response_json, ensure_ascii=False, indent=2),
            mimetype="application/json"
        )

    except (TranscriptsDisabled, NoTranscriptFound) as e:
        logger.error(f"[{request_id}] Transcript not available for video_id={video_id}")
        logger.error(f"[{request_id}] Exception Type: {type(e).__name__}")
        logger.error(f"[{request_id}] Exception Message: {str(e)}")
        return jsonify({"success": False, "error": "Transcript not available"}), 404

    except Exception as e:
        logger.critical(f"[{request_id}] Unexpected server error occurred")
        logger.critical(f"[{request_id}] Exception Type: {type(e).__name__}")
        logger.critical(f"[{request_id}] Exception Message: {str(e)}")
        logger.critical(f"[{request_id}] Stack Trace:\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500


# -------- Railway Entry -------- #
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"🚀 Server starting on port {port}")
    app.run(host="0.0.0.0", port=port)
