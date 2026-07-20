"""Lightweight ClipCheck adapter for the CoolDecide render pipeline.

This is intentionally dependency-free: the GitHub Actions runner already installs
FFmpeg, and FFprobe supplies the metadata. Reports use the shared ClipCheck JSON
shape so the dashboard and future video bots can render them consistently.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import uuid


def _finding(check_id: str, passed: bool, severity: str, message: str,
             evidence: dict) -> dict:
    return {
        "checkId": check_id,
        "passed": passed,
        "severity": severity,
        "message": message,
        "evidence": evidence,
    }


def _asset_id(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as video:
        for chunk in iter(lambda: video.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:20]


def _probe(path: str) -> dict:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams") or []
    video = next(stream for stream in streams if stream.get("codec_type") == "video")
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    duration = (payload.get("format") or {}).get("duration") or video.get("duration")
    return {
        "filename": os.path.basename(path),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "durationSeconds": round(float(duration), 3),
        "hasAudio": audio is not None,
        "videoCodec": video.get("codec_name"),
        "audioCodec": audio.get("codec_name") if audio else None,
        "bytes": os.path.getsize(path),
    }


def analyze_video(path: str, bot_id: str = "kids") -> dict:
    """Return a normalized, explainable ClipCheck report.

    Any analyzer failure becomes a block report. Observation mode decides whether
    the caller enforces that result; the analyzer never silently approves a file.
    """
    created = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    report_id = str(uuid.uuid4())

    try:
        asset_id = _asset_id(path)
        metadata = _probe(path)
    except Exception as error:  # noqa: BLE001 - failure must become a report
        return {
            "reportId": report_id,
            "botId": bot_id,
            "assetId": os.path.basename(path),
            "platform": "youtube",
            "decision": "block",
            "score": 0,
            "createdAt": created,
            "metadata": {"filename": os.path.basename(path)},
            "findings": [_finding(
                "probe-video", False, "error",
                "The rendered video could not be inspected.",
                {"error": str(error)[:240]},
            )],
        }

    width, height = metadata["width"], metadata["height"]
    ratio = width / height if height else 0
    vertical = abs(ratio - (9 / 16)) <= 0.03
    resolution = width >= 720 and height >= 1280
    duration = 1 <= metadata["durationSeconds"] <= 180
    audio = bool(metadata["hasAudio"])
    even = width % 2 == 0 and height % 2 == 0

    findings = [
        _finding(
            "vertical-aspect-ratio", vertical, "error",
            "Video uses the expected vertical aspect ratio." if vertical
            else "Video is not close enough to the configured vertical aspect ratio.",
            {"width": width, "height": height, "aspectRatio": round(ratio, 4)},
        ),
        _finding(
            "minimum-resolution", resolution, "warning",
            "Video meets the configured minimum resolution." if resolution
            else "Video is below the configured minimum resolution.",
            {"width": width, "height": height, "minimumWidth": 720, "minimumHeight": 1280},
        ),
        _finding(
            "duration", duration, "warning",
            "Video duration is inside the configured range." if duration
            else "Video duration is outside the configured range.",
            {"durationSeconds": metadata["durationSeconds"], "minimumSeconds": 1,
             "maximumSeconds": 180},
        ),
        _finding(
            "audio-stream", audio, "error",
            "An audio stream is present." if audio else "No audio stream was found.",
            {"hasAudio": audio, "audioCodec": metadata["audioCodec"]},
        ),
        _finding(
            "even-dimensions", even, "warning",
            "Video dimensions are encoder-friendly even numbers." if even
            else "One or more video dimensions are odd numbers.",
            {"width": width, "height": height},
        ),
    ]

    score = round(100 * sum(f["passed"] for f in findings) / len(findings))
    failed_error = any(not f["passed"] and f["severity"] == "error" for f in findings)
    any_failure = any(not f["passed"] for f in findings)
    decision = "block" if failed_error else "review" if any_failure else "pass"
    return {
        "reportId": report_id,
        "botId": bot_id,
        "assetId": asset_id,
        "platform": "youtube",
        "decision": decision,
        "score": score,
        "createdAt": created,
        "metadata": metadata,
        "findings": findings,
    }


def print_summary(report: dict) -> None:
    print(f"ClipCheck: {report.get('score', 0)}/100 — "
          f"{str(report.get('decision', 'block')).upper()} (observation mode)")
    for finding in report.get("findings") or []:
        marker = "PASS" if finding.get("passed") else str(finding.get("severity", "error")).upper()
        print(f"  {marker:7} {finding.get('message', '')}")

