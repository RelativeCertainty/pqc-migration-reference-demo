#!/usr/bin/env python3
"""Encode actual tab-screencast frames with auditable, text-led annotations.

No screenshots are manufactured and no application state is changed. Input is
the capture.json produced by pqc_browser_video_recorder.mjs. Each input becomes
one retained scene. An optional chapter plan groups consecutive scenes without
retiming them; scene boundaries remain explicit. Source pauses are preserved unless a cue explicitly identifies
repetition for compression. Added reading time is an explicitly labelled hold
of an already captured frame, never represented as recorded motion.
"""
from __future__ import annotations
import argparse
import html
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import textwrap

ROOT = Path(__file__).resolve().parents[1] / "artifacts/pqc-enterprise-demo"
MAX_CHAPTER_SECONDS = 90 * 60
MAX_MASTER_SECONDS = 4 * 60 * 60
MAX_PROCESS_SECONDS = 4 * 60 * 60
MAX_SCENES = 512
READING_WORDS_PER_SECOND = 2.3


def stamp(seconds: float) -> str:
    ticks = max(0, round(seconds * 100))
    return f"{ticks // 360000}:{ticks // 6000 % 60:02}:{ticks // 100 % 60:02}.{ticks % 100:02}"


def ass_text(value: str, width: int = 115) -> str:
    # Subtitle markup is authored here, never accepted from scenario content.
    safe = str(value).replace("\\", "/").replace("{", "(").replace("}", ")").replace("\r", " ")
    return r"\N".join(textwrap.wrap(safe, width=width, break_long_words=False))


def number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("finite_capture_timestamp_required")
    return float(value)


def frame_timestamp(frame: dict) -> float:
    timestamp = frame.get("metadata", {}).get("timestamp")
    if timestamp is None:
        raise ValueError("browser_frame_timestamp_required")
    # Chromium supplies seconds since epoch. Older recorder editions used pump
    # delivery time in capturedAtMs; prefer the preserved source timestamp.
    return number(timestamp) * 1000


def ffconcat_path(file: Path) -> str:
    value = file.as_posix()
    if any(character in value for character in "\r\n\x00"):
        raise ValueError("invalid_media_path")
    return "'" + value.replace("'", "'\\''") + "'"


def filter_path(file: Path) -> str:
    # libavfilter has its own escaping layer, distinct from a shell argument.
    value = file.as_posix()
    return "'" + value.replace("\\", "\\\\").replace(":", "\\:").replace("'", "'\\''") + "'"


def annotation_text(marker: dict) -> str:
    lines = ["TASK: " + str(marker["task"]), "WHY: " + str(marker["why"]), "NEXT: " + str(marker["next"]) + " | REPORT: " + str(marker["effect"])]
    if marker.get("compressed"):
        lines.append("Repeated actions/time compressed; the underlying steps were performed.")
    value = r"\N".join(ass_text(line) for line in lines)
    if len(value.split(r"\N")) > 6 or any(len(line) > 130 for line in value.split(r"\N")):
        raise ValueError("annotation_too_long_for_readable_band")
    return value


def reading_budget(marker: dict) -> float:
    """A minimum, not a reason to cut naturally longer source pauses."""
    value = annotation_text(marker)
    supplied = number(marker.get("minimumDwellSeconds", 8))
    if not 8 <= supplied <= 120:
        raise ValueError("minimum_dwell_must_be_8_to_120_seconds")
    if marker.get("emphasis") not in (None, "report"):
        raise ValueError("unsupported_cue_emphasis")
    if not isinstance(marker.get("compressed", False), bool):
        raise ValueError("compression_flag_must_be_boolean")
    budget = max(8, len(value.replace(r"\N", " ").split()) / READING_WORDS_PER_SECOND + 3,
                 supplied, 25 if marker.get("emphasis") == "report" else 0)
    budget = math.ceil(budget * 100) / 100
    if marker.get("compressed"):
        target = number(marker.get("targetDurationSeconds"))
        if not budget <= target <= MAX_CHAPTER_SECONDS:
            raise ValueError("compression_target_must_preserve_reading_budget")
    elif "targetDurationSeconds" in marker:
        raise ValueError("compression_target_requires_explicit_repetition_marker")
    return budget


def build_timeline(times: list[float], capture_end: float, markers: list[dict]) -> tuple[list[dict], list[dict], float]:
    """Retain source-frame order, splitting only at explicit cue boundaries.

    Each recorded interval maps to exactly one input frame. Reading holds reuse
    the last frame already visible in that cue and carry a separate edit kind.
    They do not claim that an action occurred or that capture continued.
    """
    budgets = [reading_budget(marker) for marker in markers]
    grouped: list[list[dict]] = [[] for _ in markers]
    prefix: list[dict] = []
    cue = -1
    for frame_index, start in enumerate(times):
        end = times[frame_index + 1] if frame_index + 1 < len(times) else capture_end
        cursor = start
        while cursor < end:
            while cue + 1 < len(markers) and markers[cue + 1]["atMs"] <= cursor:
                cue += 1
            boundary = min(end, markers[cue + 1]["atMs"]) if cue + 1 < len(markers) else end
            segment = {"frameIndex": frame_index, "sourceStart": cursor, "sourceEnd": boundary,
                       "duration": (boundary - cursor) / 1000, "kind": "recorded", "shortened": False}
            (prefix if cue < 0 else grouped[cue]).append(segment)
            cursor = boundary
    segments, transcript = [], []
    elapsed = 0.0

    def append(segment: dict) -> None:
        nonlocal elapsed
        segments.append({**segment, "start": elapsed})
        elapsed += segment["duration"]

    for segment in prefix:
        append(segment)
    for index, marker in enumerate(markers):
        recorded = grouped[index]
        if not recorded:
            raise ValueError("annotation_requires_captured_source_interval")
        original = sum(segment["duration"] for segment in recorded)
        target = min(original, number(marker["targetDurationSeconds"])) if marker.get("compressed") else original
        ratio = target / original
        start = elapsed
        for segment in recorded:
            append({**segment, "duration": segment["duration"] * ratio,
                    "shortened": ratio < 1, "kind": "compressed_repetition" if ratio < 1 else "recorded"})
        hold = max(0, budgets[index] - target)
        if hold:
            # Freeze the last already-seen source frame; do not insert a future
            # frame, a reconstructed page or a fabricated recording interval.
            last = recorded[-1]
            append({"frameIndex": last["frameIndex"], "sourceStart": last["sourceEnd"],
                    "sourceEnd": last["sourceEnd"], "duration": hold,
                    "kind": "edited_reading_hold", "shortened": False})
        transcript.append({**marker, "compressed": ratio < 1, "compressionRequested": bool(marker.get("compressed")),
                           "start": start, "end": elapsed, "minimumReadingSeconds": budgets[index],
                           "sourceSeconds": original, "recordedPlaybackSeconds": target,
                           "editedReadingHoldSeconds": hold,
                           "editedHoldStart": elapsed - hold if hold else None})
    if elapsed > MAX_CHAPTER_SECONDS:
        raise ValueError("edited_chapter_duration_limit")
    return segments, transcript, elapsed


def timing_spans(segments: list[dict]) -> list[dict]:
    """Coalesce contiguous edit notices instead of making one per frame."""
    spans: list[dict] = []
    for segment in segments:
        if segment["kind"] == "recorded":
            continue
        end = segment["start"] + segment["duration"]
        if spans and spans[-1]["kind"] == segment["kind"] and abs(spans[-1]["end"] - segment["start"]) < .000001:
            spans[-1]["end"] = end
        else:
            spans.append({"kind": segment["kind"], "start": segment["start"], "end": end})
    return spans


def checked_path(value: Path) -> Path:
    absolute = value.absolute()
    if any(p.is_symlink() for p in (absolute, *absolute.parents)):
        raise ValueError("symlink_not_allowed")
    resolved = absolute.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError("isolated_pqc_artifacts_required")
    return resolved


def run(args: list[str]) -> None:
    subprocess.run(args, check=True, stdin=subprocess.DEVNULL, timeout=MAX_PROCESS_SECONDS)


def encode(capture: Path, output: Path, index: int, *, timing_test: bool = False) -> dict:
    data = json.loads(capture.read_text())
    if data.get("schemaVersion") != "pqc.browser-capture.v1" or data.get("source") != "actual_tab_screencast" or not data.get("synthetic"):
        raise ValueError("real_synthetic_tab_capture_required")
    frames = data["frames"]
    # CDP emits frames on painted changes, not at a guaranteed sampling rate.
    # One genuine frame can therefore represent a completed unchanged-page
    # dwell. Frame count cannot establish that an operator action is visible.
    if not isinstance(frames, list) or not 1 <= len(frames) <= 90000 or not data.get("endedAtMs") or data.get("failure"):
        raise ValueError("completed_source_capture_required")
    capture_start, capture_end = number(data["startedAtMs"]), number(data["endedAtMs"])
    times = [frame_timestamp(frame) for frame in frames]
    if capture_start < 0 or capture_end <= capture_start or capture_end - capture_start > 45 * 60 * 1000 or any(not capture_start <= timestamp <= capture_end for timestamp in times) or any(right <= left for left, right in zip(times, times[1:])):
        raise ValueError("invalid_capture_timeline")
    markers = data.get("markers", [])
    if not markers or len(markers) > 1024 or any(not capture_start <= number(marker["atMs"]) < capture_end for marker in markers) or any(right["atMs"] <= left["atMs"] for left, right in zip(markers, markers[1:])):
        raise ValueError("valid_ordered_annotations_required")
    segments, transcript, elapsed = build_timeline(times, capture_end, markers)
    chapter_dir = output / "chapters"
    chapter_dir.mkdir(exist_ok=True, mode=0o700)
    stem = f"{index:02d}"
    video_name = f"{stem}_Capture_Timing_Test.mp4" if timing_test else f"{stem}_PQC_Workflow.mp4"
    concat = output / f"chapter-{stem}.frames.txt"
    if any(file.exists() for file in (concat, output / f"chapter-{stem}.ass", chapter_dir / video_name)):
        raise ValueError("existing_chapter_will_not_be_overwritten")
    files, total_bytes = [], 0
    for frame in frames:
        name = frame["file"]
        if Path(name).name != name or not name.endswith(".jpg"):
            raise ValueError("invalid_capture_frame")
        file = checked_path(capture.parent / name)
        if not file.is_file():
            raise ValueError("capture_frame_missing")
        if file.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("capture_frame_size_limit")
        total_bytes += file.stat().st_size
        if total_bytes > 512 * 1024 * 1024:
            raise ValueError("capture_storage_limit")
        if not isinstance(frame.get("sha256"), str) or len(frame["sha256"]) != 64:
            raise ValueError("capture_frame_digest_required")
        if hashlib.sha256(file.read_bytes()).hexdigest() != frame["sha256"]:
            raise ValueError("capture_frame_digest_mismatch")
        if file in files:
            raise ValueError("duplicate_capture_frame_file")
        files.append(file)
    lines = []
    for segment in segments:
        lines.extend([f"file {ffconcat_path(files[segment['frameIndex']])}", "option framerate 1000", f"duration {segment['duration']:.6f}"])
    lines.extend([f"file {ffconcat_path(files[segments[-1]['frameIndex']])}", "option framerate 1000"])
    concat.write_text("\n".join(lines) + "\n")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Guide,DejaVu Sans,24,&H00F4F8FA,&H00F4F8FA,&H00132028,&H00132028,0,0,0,0,100,100,0,0,1,0,0,7,44,44,906,1
Style: Badge,DejaVu Sans,18,&H0058E3D2,&H0058E3D2,&H00132028,&H00132028,1,0,0,0,100,100,0,0,1,0,0,9,24,30,876,1
Style: Timing,DejaVu Sans,18,&H00CDE7FF,&H00CDE7FF,&H00132028,&H00132028,1,0,0,0,100,100,0,0,1,0,0,7,44,30,876,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    badge = "CAPTURE TIMING TEST / NOT A WORKFLOW DEMONSTRATION" if timing_test else f"SYNTHETIC TRAINING / SCENE {index:03d} / SEPARATE CAPTURE"
    events = [f"Dialogue: 1,0:00:00.00,{stamp(elapsed)},Badge,,0,0,0,,{badge}"]
    for cue in transcript:
        events.append(f"Dialogue: 0,{stamp(cue['start'])},{stamp(cue['end'])},Guide,,0,0,0,,{annotation_text(cue)}")
    notices = timing_spans(segments)
    for span in notices:
        label = "EDITED READING HOLD / NO NEW ACTIONS" if span["kind"] == "edited_reading_hold" else "REPEATED ACTIONS TIME-COMPRESSED / SOURCE ORDER PRESERVED"
        events.append(f"Dialogue: 2,{stamp(span['start'])},{stamp(span['end'])},Timing,,0,0,0,,{label}")
    subtitles = output / f"chapter-{stem}.ass"
    subtitles.write_text(header + "\n".join(events) + "\n")
    video = chapter_dir / video_name
    # Reserve a separate explanation band: annotations never cover form controls.
    # CDP can report real frame-size changes. Reinitializing the entire graph
    # resets fps/subtitle state and corrupts timing; evaluate geometry per frame
    # instead. Never drop changed frames or trust metadata dimensions over JPEGs.
    vf = f"scale=1920:864:force_original_aspect_ratio=decrease:eval=frame,pad=1920:864:(ow-iw)/2:(oh-ih)/2:color=0x071319:eval=frame,pad=1920:1080:0:0:color=0x132028,ass={filter_path(subtitles)},fps=30,format=yuv420p"
    # The final repeated file is the concat end-time sentinel. Bound output to
    # the computed edit timeline so demuxer duration inference cannot append an
    # unrecorded last-frame tail. Intended pauses and labelled holds are included.
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-threads", "1", "-filter_threads", "1", "-reinit_filter", "0", "-f", "concat", "-safe", "0", "-i", str(concat), "-vf", vf, "-t", f"{elapsed:.6f}", "-an", "-c:v", "libx264", "-threads", "1", "-preset", "veryfast", "-crf", "21", "-movflags", "+faststart", str(video)])
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "1", "-i", str(video), "-f", "null", "-"])
    duration = number(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(video)], text=True, timeout=30)))
    if abs(duration - elapsed) > .15:
        raise ValueError("encoded_capture_timing_drift")
    return {"title": data["title"], "file": str(video.relative_to(output)), "seconds": duration,
            "sceneNumber": index, "cutDisclosure": "Separate recording; gaps between captures are not presented as continuous action.",
            "sha256": file_sha256(video),
            "sourceSeconds": (capture_end - capture_start) / 1000,
            "uncapturedLeadSeconds": max(0, (times[0] - capture_start) / 1000),
            "capture": str(capture), "captureSha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
            "purpose": "capture_timing_test_not_workflow_proof" if timing_test else "annotated_synthetic_browser_chapter",
            "encoderIdentity": {
                "sourceFile": "scripts/build_pqc_walkthrough_video.py",
                "sourceSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "ffmpegVersion": subprocess.check_output(["ffmpeg", "-version"], text=True, timeout=30).splitlines()[0],
                "plannedSeconds": elapsed, "encodedSeconds": duration,
                "durationToleranceSeconds": .15, "fullDecodePassed": True
            },
            "frames": len(frames), "transcript": transcript, "segments": segments, "timingEdits": notices,
            "captureReview": {"lowMotionReviewRequired": len(frames) < 8,
                              "frameSampling": "Chrome CDP emits changed frames; unchanged dwell uses the last captured frame until capture stop.",
                              "interactionVisibility": "Not inferred from frame count. Verify each claimed action and result in source frames before delivery.",
                              "allFrameDigestsVerified": True, "sourceTimestampsStrictlyOrderedAndBounded": True},
            "readingPolicy": {"minimumSeconds": 8, "wordsPerSecond": READING_WORDS_PER_SECOND,
                              "orientationSeconds": 3, "reportEmphasisMinimumSeconds": 25,
                              "unmarkedPauses": "preserved", "holds": "explicitly_labelled_last_captured_frame"},
            "readabilityWarnings": []}


def file_sha256(file: Path) -> str:
    digest = hashlib.sha256()
    with file.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_chapter_plan(plan: object, scene_count: int) -> list[dict]:
    """A grouping plan cannot omit, duplicate or reorder any input scene."""
    if not isinstance(plan, dict) or set(plan) != {"schemaVersion", "chapters"} or plan["schemaVersion"] != "pqc.video-chapter-plan.v1":
        raise ValueError("unsupported_chapter_plan")
    chapters = plan["chapters"]
    if not isinstance(chapters, list) or not 1 <= len(chapters) <= 60:
        raise ValueError("chapter_group_count_limit")
    ordered = []
    for chapter in chapters:
        if not isinstance(chapter, dict) or set(chapter) != {"title", "scenes"}:
            raise ValueError("invalid_chapter_group")
        title, scenes = chapter["title"], chapter["scenes"]
        if not isinstance(title, str) or not title.strip() or len(title) > 180 or any(ord(c) < 32 for c in title):
            raise ValueError("invalid_chapter_title")
        if not isinstance(scenes, list) or not scenes or any(type(i) is not int for i in scenes):
            raise ValueError("integer_scene_numbers_required")
        ordered.extend(scenes)
    if ordered != list(range(1, scene_count + 1)):
        raise ValueError("chapter_plan_must_preserve_every_scene_once_in_order")
    return chapters


def capture_boundaries(captures: list[Path]) -> list[dict]:
    """Make off-camera gaps explicit and reject out-of-order source captures."""
    boundaries = []
    for capture in captures:
        data = json.loads(capture.read_text())
        start, end = number(data.get("startedAtMs")), number(data.get("endedAtMs"))
        previous_end = boundaries[-1]["captureEndedAtMs"] if boundaries else start
        if end <= start or start < previous_end:
            raise ValueError("capture_order_or_overlap_invalid")
        boundaries.append({"captureStartedAtMs": start, "captureEndedAtMs": end,
                           "offCameraGapBeforeSeconds": (start - previous_end) / 1000})
    return boundaries


def group_chapters(scenes: list[dict], plan: list[dict]) -> list[dict]:
    """Projection only: input scenes and their cue times are not mutated."""
    groups = []
    for index, entry in enumerate(plan, 1):
        selected = [scenes[i - 1] for i in entry["scenes"]]
        seconds = sum(number(scene["seconds"]) for scene in selected)
        if seconds > MAX_CHAPTER_SECONDS:
            raise ValueError("grouped_chapter_duration_limit")
        groups.append({"title": entry["title"], "file": f"workflow-chapters/{index:02d}_PQC_Chapter.mp4",
                       "seconds": seconds, "masterStart": selected[0]["masterStart"],
                       "sceneNumbers": entry["scenes"], "scenes": [{"sceneNumber": n, "title": s["title"],
                           "file": s["file"], "seconds": s["seconds"], "masterStart": s["masterStart"],
                           "chapterStart": s["masterStart"] - selected[0]["masterStart"],
                           "captureSha256": s.get("captureSha256"), "sha256": s.get("sha256")}
                          for n, s in zip(entry["scenes"], selected)],
                       "editPolicy": "Stream-copy consecutive retained scenes; no retiming, fades or omitted scenes. Separate-capture badges disclose cuts."})
    return groups


def media_signature(file: Path) -> tuple:
    """Reject mismatched streams before stream-copy concatenation."""
    data = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_data_hash", "sha256", "-of", "json", str(file)], text=True, timeout=30))
    streams = data.get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_type") != "video":
        raise ValueError("single_video_stream_required")
    s = streams[0]
    fields = ("codec_name", "profile", "level", "width", "height", "pix_fmt", "r_frame_rate", "time_base", "extradata_hash")
    if (s.get("codec_name"), s.get("width"), s.get("height"), s.get("r_frame_rate")) != ("h264", 1920, 1080, "30/1") or s.get("pix_fmt") not in ("yuv420p", "yuvj420p") or any(s.get(k) is None for k in fields):
        raise ValueError("encoded_scene_format_required")
    return tuple(s[k] for k in fields)


def concatenate_videos(files: list[Path], destination: Path, concat: Path, expected_seconds: float,
                       *, metadata: Path | None = None, decode: bool = False) -> dict:
    """Bounded, lossless grouping of already encoded clips with timing checks."""
    if not files or destination.exists() or concat.exists():
        raise ValueError("existing_or_empty_concatenation_refused")
    signatures = [media_signature(file) for file in files]
    if any(signature != signatures[0] for signature in signatures[1:]):
        raise ValueError("incompatible_scene_streams")
    concat.write_text("".join(f"file {ffconcat_path(file)}\n" for file in files))
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-n", "-threads", "1", "-f", "concat", "-safe", "0", "-i", str(concat)]
    if metadata:
        command.extend(["-i", str(metadata), "-map_metadata", "1", "-map_chapters", "1"])
    else:
        command.extend(["-map_metadata", "-1", "-map_chapters", "-1"])
    command.extend(["-map", "0:v:0", "-an", "-c", "copy", "-movflags", "+faststart", str(destination)])
    run(command)
    actual = number(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(destination)], text=True, timeout=30)))
    if abs(actual - expected_seconds) > .15:
        raise ValueError("concatenated_timing_drift")
    if decode:
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-threads", "1", "-i", str(destination), "-f", "null", "-"])
    return {"sha256": file_sha256(destination), "plannedSeconds": expected_seconds, "encodedSeconds": actual,
            "durationToleranceSeconds": .15, "streamCopy": True, "fullDecodePassed": decode}


def web_timestamp(seconds: float) -> str:
    ms = round(seconds * 1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02}.{ms%1000:03}"


def write_viewing_materials(chapters: list[dict], output: Path, groups: list[dict] | None = None) -> None:
    """The same edited cue times drive captions, transcript and seek controls."""
    transcript = ["# PQC video transcript", "", "Synthetic development demonstration; no enterprise acceptance.", ""]
    vtt = ["WEBVTT", ""]
    transcript_html = []
    for chapter in chapters:
        transcript.extend(["## " + chapter["title"], ""])
        transcript_html.append("<h2>" + html.escape(chapter["title"]) + "</h2>")
        for cue in chapter["transcript"]:
            description = f"Task: {cue['task']}\nWhy: {cue['why']}\nNext: {cue['next']}\nReport: {cue['effect']}"
            if cue.get("compressed"):
                description += "\nRepeated actions/time compressed; the underlying steps were performed in source order."
            start, end = chapter["masterStart"] + cue["start"], chapter["masterStart"] + cue["end"]
            hold = cue["editedReadingHoldSeconds"]
            note = f"\nEdited reading hold: final {hold:.2f} seconds repeat the last captured frame; no new actions." if hold else ""
            transcript.extend([f"{web_timestamp(start)} – {web_timestamp(end)}", description + note, ""])
            transcript_html.append(f"<section><h3><a href='PQC_Assessment_End_to_End_Demo.mp4#t={start:.3f}'>{web_timestamp(start)}</a></h3><p>" + html.escape(description + note).replace("\n", "<br>") + "</p></section>")
            if hold:
                split = chapter["masterStart"] + cue["editedHoldStart"]
                vtt.extend([f"{web_timestamp(start)} --> {web_timestamp(split)}", html.escape(description, quote=False), ""])
                vtt.extend([f"{web_timestamp(split)} --> {web_timestamp(end)}", html.escape(description + "\nEDITED READING HOLD / NO NEW ACTIONS", quote=False), ""])
            else:
                vtt.extend([f"{web_timestamp(start)} --> {web_timestamp(end)}", html.escape(description, quote=False), ""])
    (output / "Transcript.md").write_text("\n".join(transcript))
    (output / "PQC_Assessment_End_to_End_Demo.vtt").write_text("\n".join(vtt))
    style = "body{background:#071319;color:#edf4f7;font:18px/1.6 system-ui;margin:2rem auto;max-width:1200px;padding:1rem}a{color:#64e4d3}a:focus,video:focus{outline:3px solid #64e4d3;outline-offset:4px}video{width:100%}section{border-bottom:1px solid #526974;padding:1rem 0}li{margin:.65rem 0}"
    head = "<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='robots' content='noindex,nofollow,noarchive'><title>PQC operator video</title><style>" + style + "</style><body>"
    (output / "Transcript.readable.html").write_text(head + "<h1>PQC video transcript</h1><p>Synthetic development demonstration. Times match the edited master video; reading holds are explicitly distinguished from recorded actions.</p>" + "".join(transcript_html) + "</body></html>")
    links = []
    for c in groups if groups is not None else chapters:
        nested = ""
        if groups is not None:
            scene_links = "".join(f"<li><a href='PQC_Assessment_End_to_End_Demo.mp4#t={s['masterStart']:.3f}' data-seek='{s['masterStart']:.3f}'>Scene {s['sceneNumber']:03d}: {html.escape(s['title'])}</a> · <a href='{html.escape(s['file'], quote=True)}' download>Download scene</a> · chapter offset {web_timestamp(s['chapterStart'])}</li>" for s in c["scenes"])
            nested = "<details><summary>Individual recorded scenes and explicit cuts</summary><ol>" + scene_links + "</ol></details>"
        links.append(f"<li><a href='PQC_Assessment_End_to_End_Demo.mp4#t={c['masterStart']:.3f}' data-seek='{c['masterStart']:.3f}'>{web_timestamp(c['masterStart'])} — {html.escape(c['title'])}</a> · <a href='{html.escape(c['file'], quote=True)}' download>Download chapter</a> ({round(c['seconds'])} seconds)" + nested + "</li>")
    cue_links = "".join(f"<li><a href='PQC_Assessment_End_to_End_Demo.mp4#t={c['masterStart']+cue['start']:.3f}' data-seek='{c['masterStart']+cue['start']:.3f}'>{web_timestamp(c['masterStart']+cue['start'])} — {html.escape(cue['task'])}</a></li>" for c in chapters for cue in c["transcript"])
    seek_script = """<script>
const player = document.getElementById('walkthrough');
document.querySelectorAll('a[data-seek]').forEach(link => link.addEventListener('click', event => {
  event.preventDefault();
  const seek = () => {
    player.currentTime = Number(link.dataset.seek);
    player.focus({preventScroll:true});
    player.scrollIntoView({block:'center'});
    player.play().catch(() => {});
  };
  if (player.readyState >= 1) seek();
  else { player.addEventListener('loadedmetadata', seek, {once:true}); player.load(); }
}));
</script>"""
    (output / "index.html").write_text(head + "<h1>PQC assessment: response to report</h1><p>Actual synthetic browser workflow. Simulated role decisions are not enterprise or owner acceptance. Unmarked source pauses remain intact. Any time-compressed repetition or added still-frame reading hold is labelled on screen. Numbered scenes are separate recordings joined by explicit cuts; gaps between recordings are not continuous captured activity.</p><video id='walkthrough' controls preload='metadata' tabindex='0' src='PQC_Assessment_End_to_End_Demo.mp4'><track kind='captions' srclang='en' label='English explanations' src='PQC_Assessment_End_to_End_Demo.vtt'></video><p><a href='PQC_Assessment_End_to_End_Demo.mp4' download>Download the complete MP4</a> · <a href='PQC_Assessment_End_to_End_Demo.vtt' download>Download timed explanations</a></p><h2>Chapters — jump in the video</h2><ol>" + "".join(links) + "</ol><details><summary>Jump to a specific task</summary><ol>" + cue_links + "</ol></details><p><a href='Transcript.readable.html'>Read the complete transcript</a> · <a href='scenes.json'>Scene timing and source audit</a></p>" + seek_script + "</body></html>")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chapter-plan", type=Path, help="Optional pqc.video-chapter-plan.v1 JSON: chapters with title and consecutive 1-based scenes. Every input must appear once in order.")
    args = parser.parse_args()
    os.umask(0o077)
    output = checked_path(args.output)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    if (output / "PQC_Assessment_End_to_End_Demo.mp4").exists():
        raise ValueError("existing_master_will_not_be_overwritten")
    if len(args.capture) > MAX_SCENES:
        raise ValueError("scene_count_limit")
    captures = [checked_path(file) for file in args.capture]
    if len(set(captures)) != len(captures):
        raise ValueError("duplicate_scene_capture")
    plan = validate_chapter_plan(json.loads(checked_path(args.chapter_plan).read_text()), len(captures)) if args.chapter_plan else None
    boundaries = capture_boundaries(captures)
    scenes = []
    for i, file in enumerate(captures):
        scenes.append({**encode(file, output, i + 1), **boundaries[i]})
        if sum(scene["seconds"] for scene in scenes) > MAX_MASTER_SECONDS:
            raise ValueError("master_duration_limit")
    clock = 0.0
    for scene in scenes:
        scene["masterStart"] = clock
        clock += scene["seconds"]
    chapters = group_chapters(scenes, plan) if plan else scenes
    if plan:
        (output / "workflow-chapters").mkdir(mode=0o700, exist_ok=True)
        for index, chapter in enumerate(chapters, 1):
            chapter["assembly"] = concatenate_videos([output / s["file"] for s in chapter["scenes"]],
                output / chapter["file"], output / f"group-{index:02d}.concat.txt", chapter["seconds"])
    meta = [";FFMETADATA1"]
    for chapter in chapters:
        start = chapter["masterStart"]
        safe_title = chapter["title"].replace("\\", "\\\\").replace("=", "\\=").replace(";", "\\;").replace("#", "\\#").replace("\n", " ").replace("\r", " ")
        meta.extend(["[CHAPTER]", "TIMEBASE=1/1000", f"START={round(start * 1000)}", f"END={round((start + chapter['seconds']) * 1000)}", "title=" + safe_title])
    metadata = output / "chapters.ffmetadata"
    metadata.write_text("\n".join(meta) + "\n")
    master = output / "PQC_Assessment_End_to_End_Demo.mp4"
    master_assembly = concatenate_videos([output / scene["file"] for scene in scenes], master,
        output / "chapters.concat.txt", clock, metadata=metadata, decode=True)
    (output / "scenes.json").write_text(json.dumps(scenes, indent=2) + "\n")
    (output / "chapters.json").write_text(json.dumps(chapters, indent=2) + "\n")
    (output / "assembly.json").write_text(json.dumps({"master": master.name, "chapters": len(chapters),
        "scenes": len(scenes), "seconds": clock, "masterAssembly": master_assembly,
        "grouping": plan, "encoderSourceSha256": file_sha256(Path(__file__)),
        "ffmpegVersion": subprocess.check_output(["ffmpeg", "-version"], text=True, timeout=30).splitlines()[0]}, indent=2) + "\n")
    write_viewing_materials(scenes, output, chapters if plan else None)
    print(json.dumps({"master": str(master), "chapters": len(chapters), "scenes": len(scenes), "seconds": clock, "decoded": True}))


if __name__ == "__main__":
    main()
