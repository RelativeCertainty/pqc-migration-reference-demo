"""Pure assembly checks; mocked frame files never become demonstration footage."""
import importlib.util
import hashlib
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("pqc_video", Path(__file__).parents[1] / "scripts/build_pqc_walkthrough_video.py")
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


def capture_fixture(tmp_path, monkeypatch, *, failure=None):
    monkeypatch.setattr(video, "ROOT", tmp_path)
    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    start = 1_800_000_000_000
    frames = []
    for index in range(8):
        name = f"{index:06}.jpg"
        (capture_dir / name).write_bytes(b"mock JPEG bytes, never encoded")
        frames.append({"file": name, "capturedAtMs": start + 99999, "metadata": {"timestamp": (start + index * 1000) / 1000}, "sha256": hashlib.sha256((capture_dir / name).read_bytes()).hexdigest()})
    data = {"schemaVersion": "pqc.browser-capture.v1", "source": "actual_tab_screencast", "synthetic": True, "title": "Test-only capture", "startedAtMs": start, "endedAtMs": start + 8000, "frames": frames, "failure": failure, "markers": [{"atMs": start, "task": "Read record.", "why": "Context.", "next": "Reviewer.", "effect": "Pending."}]}
    capture = capture_dir / "capture.json"
    capture.write_text(json.dumps(data))
    output = tmp_path / "output"
    output.mkdir()
    commands = []
    monkeypatch.setattr(video, "run", lambda args: commands.append(args))
    monkeypatch.setattr(video.subprocess, "check_output", lambda *args, **kwargs: "8.000")
    monkeypatch.setattr(video, "file_sha256", lambda file: "mock-encoded-video-not-real-footage")
    return capture, output, data, commands


def test_uses_browser_timestamps_not_pump_delivery_and_does_not_add_fake_tail(tmp_path, monkeypatch):
    capture, output, _, commands = capture_fixture(tmp_path, monkeypatch)
    result = video.encode(capture, output, 1)
    assert result["sourceSeconds"] == result["seconds"] == 8
    assert result["transcript"][0]["start"] == 0
    assert result["transcript"][0]["end"] == 8
    assert all(segment["duration"] == 1 for segment in result["segments"])
    assert "option framerate 1000" in (output / "chapter-01.frames.txt").read_text()
    vf = commands[0][commands[0].index("-vf") + 1]
    assert "pad=1920:864" in vf and "pad=1920:1080" in vf
    assert "force_original_aspect_ratio=decrease:eval=frame" in vf
    assert "color=0x071319:eval=frame" in vf
    assert commands[0][commands[0].index("-reinit_filter") + 1] == "0"
    assert commands[0][commands[0].index("-t") + 1] == "8.000000"
    assert result["encoderIdentity"]["plannedSeconds"] == 8
    assert len(result["encoderIdentity"]["sourceSha256"]) == 64
    subtitles = (output / "chapter-01.ass").read_text()
    assert ",876,1" in subtitles  # All badges are below the application viewport.
    assert "SCENE 001 / SEPARATE CAPTURE" in subtitles


@pytest.mark.parametrize("failure", ["capture_events_truncated", "capture_storage_limit"])
def test_failed_capture_cannot_be_presented_as_complete(tmp_path, monkeypatch, failure):
    capture, output, _, _ = capture_fixture(tmp_path, monkeypatch, failure=failure)
    with pytest.raises(ValueError, match="completed_source_capture_required"):
        video.encode(capture, output, 1)


def test_one_genuine_unchanged_frame_retains_recorded_dwell_and_requires_visual_review(tmp_path, monkeypatch):
    capture, output, data, _ = capture_fixture(tmp_path, monkeypatch)
    data["frames"] = data["frames"][:1]
    data["endedAtMs"] = data["startedAtMs"] + 30000
    capture.write_text(json.dumps(data))
    monkeypatch.setattr(video.subprocess, "check_output", lambda *args, **kwargs: "30.000")
    result = video.encode(capture, output, 1)
    assert result["seconds"] == result["sourceSeconds"] == 30
    assert result["segments"] == [{"frameIndex": 0, "sourceStart": data["startedAtMs"], "sourceEnd": data["endedAtMs"], "duration": 30, "kind": "recorded", "shortened": False, "start": 0}]
    assert result["timingEdits"] == []
    assert result["captureReview"]["lowMotionReviewRequired"] is True
    assert "Not inferred from frame count" in result["captureReview"]["interactionVisibility"]


def test_empty_capture_still_cannot_be_encoded(tmp_path, monkeypatch):
    capture, output, data, commands = capture_fixture(tmp_path, monkeypatch)
    data["frames"] = []
    capture.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="completed_source_capture_required"):
        video.encode(capture, output, 1)
    assert not commands


@pytest.mark.parametrize("problem", ["before_start", "after_end", "duplicate_timestamp", "negative_start", "missing_source_timestamp", "missing_digest", "duplicate_file"])
def test_source_validity_is_not_replaced_by_a_low_frame_count_exemption(tmp_path, monkeypatch, problem):
    capture, output, data, commands = capture_fixture(tmp_path, monkeypatch)
    if problem == "before_start": data["frames"][0]["metadata"]["timestamp"] = (data["startedAtMs"] - 1) / 1000
    if problem == "after_end": data["frames"][-1]["metadata"]["timestamp"] = (data["endedAtMs"] + 1) / 1000
    if problem == "duplicate_timestamp": data["frames"][1]["metadata"]["timestamp"] = data["frames"][0]["metadata"]["timestamp"]
    if problem == "negative_start": data["startedAtMs"] = -1
    if problem == "missing_source_timestamp": data["frames"][0]["metadata"] = {}
    if problem == "missing_digest": data["frames"][0].pop("sha256")
    if problem == "duplicate_file": data["frames"][1]["file"] = data["frames"][0]["file"]
    capture.write_text(json.dumps(data))
    with pytest.raises(ValueError): video.encode(capture, output, 1)
    assert not commands


def test_non_monotonic_source_frames_are_rejected(tmp_path, monkeypatch):
    capture, output, data, _ = capture_fixture(tmp_path, monkeypatch)
    data["frames"][2]["metadata"]["timestamp"] -= 10
    capture.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="invalid_capture_timeline"):
        video.encode(capture, output, 1)


def test_shortening_maps_annotations_to_encoded_not_original_time(tmp_path, monkeypatch):
    capture, output, data, _ = capture_fixture(tmp_path, monkeypatch)
    start = data["startedAtMs"]
    for frame in data["frames"][1:]:
        frame["metadata"]["timestamp"] += 29
    data["endedAtMs"] += 29000
    data["markers"].append({**data["markers"][0], "atMs": start + 30000, "task": "Next record."})
    data["markers"][0].update(compressed=True, targetDurationSeconds=20)
    capture.write_text(json.dumps(data))
    monkeypatch.setattr(video.subprocess, "check_output", lambda *args, **kwargs: "28.000")
    result = video.encode(capture, output, 1)
    assert result["transcript"][1]["start"] == 20
    assert result["transcript"][1]["end"] == 28
    assert result["transcript"][1]["editedReadingHoldSeconds"] == 1
    assert "REPEATED ACTIONS TIME-COMPRESSED" in (output / "chapter-01.ass").read_text()
    assert "EDITED READING HOLD / NO NEW ACTIONS" in (output / "chapter-01.ass").read_text()
    assert result["segments"][-1]["sourceStart"] == result["segments"][-1]["sourceEnd"]
    assert result["segments"][-1]["frameIndex"] == 7


def test_long_unmarked_pause_is_preserved_not_capped_at_twelve_seconds(tmp_path, monkeypatch):
    capture, output, data, _ = capture_fixture(tmp_path, monkeypatch)
    for frame in data["frames"][1:]:
        frame["metadata"]["timestamp"] += 29
    data["endedAtMs"] += 29000
    capture.write_text(json.dumps(data))
    monkeypatch.setattr(video.subprocess, "check_output", lambda *args, **kwargs: "37.000")
    result = video.encode(capture, output, 1)
    assert result["seconds"] == result["sourceSeconds"] == 37
    assert result["segments"][0]["duration"] == 30
    assert result["timingEdits"] == []


def cue(**kwargs):
    return {"atMs": 1000, "task": "Read record.", "why": "Context.", "next": "Reviewer.", "effect": "Pending.", **kwargs}


def test_reading_budgets_include_orientation_word_count_and_report_emphasis():
    assert video.reading_budget(cue()) == 8
    long = cue(why=" ".join(["word"] * 70))
    words = len(video.annotation_text(long).replace(r"\N", " ").split())
    assert video.reading_budget(long) >= words / 2.3 + 3
    assert video.reading_budget(cue(emphasis="report")) == 25
    assert video.reading_budget(cue(emphasis="report", minimumDwellSeconds=30)) == 30


@pytest.mark.parametrize("values,error", [
    ({"minimumDwellSeconds": 7}, "minimum_dwell"),
    ({"minimumDwellSeconds": 121}, "minimum_dwell"),
    ({"minimumDwellSeconds": True}, "finite_capture_timestamp"),
    ({"minimumDwellSeconds": float("nan")}, "finite_capture_timestamp"),
    ({"emphasis": "fast"}, "unsupported_cue"),
    ({"compressed": "yes"}, "compression_flag"),
    ({"compressed": True}, "finite_capture_timestamp"),
    ({"compressed": True, "targetDurationSeconds": 8}, "compression_target"),
    ({"targetDurationSeconds": 10}, "requires_explicit_repetition"),
])
def test_unsafe_or_ambiguous_dwell_contracts_are_rejected(values, error):
    with pytest.raises(ValueError, match=error):
        video.reading_budget(cue(**values))


def test_explicit_report_hold_reuses_only_last_seen_frame_and_shifts_later_cues():
    segments, transcript, duration = video.build_timeline([1000, 2000, 3000, 4000], 6000,
        [cue(emphasis="report"), cue(atMs=3000, task="Next record.")])
    assert transcript[0]["end"] == transcript[1]["start"] == 25
    assert duration == 33
    holds = [segment for segment in segments if segment["kind"] == "edited_reading_hold"]
    assert [(segment["frameIndex"], segment["duration"]) for segment in holds] == [(1, 23), (3, 5)]
    assert [segment["frameIndex"] for segment in segments] == [0, 1, 1, 2, 3, 3]
    assert all(segment["sourceStart"] == segment["sourceEnd"] for segment in holds)


def test_marker_inside_unchanged_frame_splits_chronology_without_inventing_pixels():
    segments, transcript, _ = video.build_timeline([1000, 15000], 25000,
        [cue(), cue(atMs=11000, minimumDwellSeconds=12)])
    assert [(s["sourceStart"], s["sourceEnd"], s["frameIndex"]) for s in segments] == [
        (1000, 11000, 0), (11000, 15000, 0), (15000, 25000, 1)]
    assert transcript[1]["start"] == 10
    assert transcript[1]["end"] == 24


def test_caption_transcript_and_seek_links_share_edited_timeline(tmp_path):
    segments, cues, duration = video.build_timeline([1000, 2000, 3000], 6000, [cue(emphasis="report")])
    chapter = {"title": "Review <example>", "file": "chapters/01_PQC_Workflow.mp4", "seconds": duration,
               "masterStart": 42, "transcript": cues, "segments": segments}
    video.write_viewing_materials([chapter], tmp_path)
    captions = (tmp_path / "PQC_Assessment_End_to_End_Demo.vtt").read_text()
    assert "00:00:42.000 --> 00:00:47.000" in captions
    assert "00:00:47.000 --> 00:01:07.000" in captions
    assert "EDITED READING HOLD / NO NEW ACTIONS" in captions
    index = (tmp_path / "index.html").read_text()
    assert "#t=42.000" in index and "data-seek='42.000'" in index
    assert "Download chapter" in index and "Jump to a specific task" in index
    assert "Review &lt;example&gt;" in index and "Review <example>" not in index
    readable = (tmp_path / "Transcript.readable.html").read_text()
    assert "final 20.00 seconds repeat the last captured frame" in readable
    assert "00:00:42.000 – 00:01:07.000" in (tmp_path / "Transcript.md").read_text()


def test_edited_duration_remains_bounded():
    with pytest.raises(ValueError, match="edited_chapter_duration_limit"):
        video.build_timeline([1000], (video.MAX_CHAPTER_SECONDS + 2) * 1000, [cue()])


def test_process_calls_are_bounded_and_noninteractive(monkeypatch):
    calls = []
    monkeypatch.setattr(video.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    video.run(["ffmpeg", "test-only"])
    assert calls[0][1]["timeout"] == video.MAX_PROCESS_SECONDS
    assert calls[0][1]["stdin"] == video.subprocess.DEVNULL


def test_annotations_at_capture_end_or_same_timestamp_are_rejected(tmp_path, monkeypatch):
    capture, output, data, _ = capture_fixture(tmp_path, monkeypatch)
    data["markers"].append({**data["markers"][0]})
    capture.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="valid_ordered_annotations"):
        video.encode(capture, output, 1)
    data["markers"][-1]["atMs"] = data["endedAtMs"]
    capture.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="valid_ordered_annotations"):
        video.encode(capture, output, 1)


def test_timing_preflight_is_explicitly_labelled_and_not_named_as_workflow(tmp_path, monkeypatch):
    capture, output, _, _ = capture_fixture(tmp_path, monkeypatch)
    result = video.encode(capture, output, 1, timing_test=True)
    assert result["purpose"] == "capture_timing_test_not_workflow_proof"
    assert result["file"].endswith("01_Capture_Timing_Test.mp4")
    assert "CAPTURE TIMING TEST / NOT A WORKFLOW DEMONSTRATION" in (output / "chapter-01.ass").read_text()


def test_probe_nonfinite_duration_cannot_bypass_timing_guard(tmp_path, monkeypatch):
    capture, output, _, _ = capture_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(video.subprocess, "check_output", lambda *args, **kwargs: "nan")
    with pytest.raises(ValueError, match="finite_capture_timestamp_required"):
        video.encode(capture, output, 1)


def test_subtitle_markup_cannot_be_injected_and_long_annotations_fail():
    assert "{" not in video.ass_text(r"{\pos(0,0)}text")
    with pytest.raises(ValueError, match="annotation_too_long"):
        video.annotation_text({key: "Long annotation " * 100 for key in ["task", "why", "next", "effect"]})


def test_frame_hash_mismatch_fails_before_encoding(tmp_path, monkeypatch):
    capture, output, data, commands = capture_fixture(tmp_path, monkeypatch)
    data["frames"][0]["sha256"] = "0" * 64
    capture.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="capture_frame_digest_mismatch"):
        video.encode(capture, output, 1)
    assert not commands


def test_symlink_paths_and_missing_source_clock_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(video, "ROOT", tmp_path)
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink_not_allowed"):
        video.checked_path(link / "capture.json")
    with pytest.raises(ValueError, match="browser_frame_timestamp_required"):
        video.frame_timestamp({"capturedAtMs": 123})


def chapter_plan(*groups):
    return {"schemaVersion": "pqc.video-chapter-plan.v1", "chapters": list(groups)}


def test_chapter_grouping_retains_every_scene_and_exact_original_cue_times(tmp_path):
    import copy
    scenes = [{"title": f"Scene {i}", "file": f"chapters/{i:02d}_PQC_Workflow.mp4", "seconds": duration,
               "masterStart": start, "transcript": [{"start": 1, "end": duration - 1}]}
              for i, start, duration in [(1, 0, 20), (2, 20, 30), (3, 50, 25)]]
    before = copy.deepcopy(scenes)
    plan = video.validate_chapter_plan(chapter_plan({"title": "Scope", "scenes": [1, 2]},
                                                   {"title": "Independent review", "scenes": [3]}), 3)
    groups = video.group_chapters(scenes, plan)
    assert scenes == before
    assert [(g["masterStart"], g["seconds"]) for g in groups] == [(0, 50), (50, 25)]
    assert groups[0]["sceneNumbers"] == [1, 2]
    assert groups[0]["scenes"][1]["chapterStart"] == 20
    assert groups[1]["scenes"][0]["chapterStart"] == 0
    assert groups[0]["file"] == "workflow-chapters/01_PQC_Chapter.mp4"


@pytest.mark.parametrize("groups", [
    [{"title": "Missing", "scenes": [1, 3]}],
    [{"title": "Duplicate", "scenes": [1, 2, 2, 3]}],
    [{"title": "Reordered", "scenes": [2, 1, 3]}],
    [{"title": "Noncontiguous", "scenes": [1, 3]}, {"title": "Late", "scenes": [2]}],
    [{"title": "Out of range", "scenes": [0, 1, 2, 3]}],
])
def test_group_plan_cannot_hide_repeat_or_reorder_scenes(groups):
    with pytest.raises(ValueError, match="preserve_every_scene_once_in_order"):
        video.validate_chapter_plan(chapter_plan(*groups), 3)


@pytest.mark.parametrize("value,error", [
    ({"schemaVersion": "unknown", "chapters": []}, "unsupported_chapter_plan"),
    (chapter_plan(), "chapter_group_count_limit"),
    (chapter_plan({"title": " ", "scenes": [1]}), "invalid_chapter_title"),
    (chapter_plan({"title": "bad\nmetadata", "scenes": [1]}), "invalid_chapter_title"),
    (chapter_plan({"title": "Task", "scenes": [True]}), "integer_scene_numbers_required"),
    (chapter_plan({"title": "Task", "scenes": []}), "integer_scene_numbers_required"),
    (chapter_plan({"title": "Task", "scenes": [1], "speed": 2}), "invalid_chapter_group"),
])
def test_group_plan_rejects_ambiguous_fields(value, error):
    with pytest.raises(ValueError, match=error):
        video.validate_chapter_plan(value, 1)


def test_grouped_chapter_stays_bounded():
    scenes = [{"seconds": video.MAX_CHAPTER_SECONDS + 1}]
    with pytest.raises(ValueError, match="grouped_chapter_duration_limit"):
        video.group_chapters(scenes, [{"title": "Too long", "scenes": [1]}])


def test_grouped_index_preserves_individual_downloads_and_cue_seek_offsets(tmp_path):
    _, cues, duration = video.build_timeline([1000, 2000], 9000, [cue()])
    scenes = [{"title": f"Scene {i}", "file": f"chapters/{i:02d}.mp4", "seconds": duration,
               "masterStart": (i - 1) * duration, "transcript": cues} for i in (1, 2)]
    groups = video.group_chapters(scenes, [{"title": "Scope <and> review", "scenes": [1, 2]}])
    video.write_viewing_materials(scenes, tmp_path, groups)
    content = (tmp_path / "index.html").read_text()
    assert "Scope &lt;and&gt; review" in content
    assert "workflow-chapters/01_PQC_Chapter.mp4" in content
    assert "Scene 001:" in content and "Scene 002:" in content
    assert content.count("Download scene") == 2
    assert "separate recordings joined by explicit cuts" in content
    assert "data-seek='8.000'" in content
    assert "00:00:08.000 --> 00:00:16.000" in (tmp_path / "PQC_Assessment_End_to_End_Demo.vtt").read_text()


def test_capture_boundary_audit_records_real_gaps_and_rejects_overlap(tmp_path):
    files = []
    for index, (start, end) in enumerate([(1000, 9000), (14000, 22000)]):
        p = tmp_path / f"capture-{index}.json"
        p.write_text(json.dumps({"startedAtMs": start, "endedAtMs": end})); files.append(p)
    assert video.capture_boundaries(files)[1]["offCameraGapBeforeSeconds"] == 5
    with pytest.raises(ValueError, match="capture_order_or_overlap_invalid"):
        video.capture_boundaries(list(reversed(files)))


def encoded_stream(**updates):
    return {"codec_type": "video", "codec_name": "h264", "profile": "High", "level": 40,
            "width": 1920, "height": 1080, "pix_fmt": "yuv420p", "r_frame_rate": "30/1",
            "time_base": "1/15360", "extradata_hash": "SHA256:test", **updates}


def test_stream_copy_checks_codec_parameters_before_combining(tmp_path, monkeypatch):
    monkeypatch.setattr(video.subprocess, "check_output", lambda *a, **kw: json.dumps({"streams": [encoded_stream()]}))
    assert video.media_signature(tmp_path / "a.mp4")[:3] == ("h264", "High", 40)
    monkeypatch.setattr(video.subprocess, "check_output", lambda *a, **kw: json.dumps({"streams": [encoded_stream(width=1280)]}))
    with pytest.raises(ValueError, match="encoded_scene_format_required"):
        video.media_signature(tmp_path / "a.mp4")
    monkeypatch.setattr(video.subprocess, "check_output", lambda *a, **kw: json.dumps({"streams": [encoded_stream(), {"codec_type": "audio"}]}))
    with pytest.raises(ValueError, match="single_video_stream_required"):
        video.media_signature(tmp_path / "a.mp4")


def test_group_concat_is_lossless_bounded_and_timing_verified(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(video, "media_signature", lambda p: ("matching-codec",))
    monkeypatch.setattr(video, "run", lambda args: calls.append(args))
    monkeypatch.setattr(video.subprocess, "check_output", lambda *a, **kw: "50.000")
    monkeypatch.setattr(video, "file_sha256", lambda p: "mock-unencoded")
    result = video.concatenate_videos([tmp_path / "scene1.mp4", tmp_path / "scene2.mp4"],
        tmp_path / "group.mp4", tmp_path / "concat.txt", 50, decode=True)
    assert calls[0][calls[0].index("-c") + 1] == "copy"
    assert calls[0][calls[0].index("-threads") + 1] == "1"
    assert "-vf" not in calls[0] and "-t" not in calls[0] and "-r" not in calls[0]
    assert result["plannedSeconds"] == result["encodedSeconds"] == 50
    assert result["fullDecodePassed"] is True and len(calls) == 2
    monkeypatch.setattr(video.subprocess, "check_output", lambda *a, **kw: "51.000")
    with pytest.raises(ValueError, match="concatenated_timing_drift"):
        video.concatenate_videos([tmp_path / "scene1.mp4"], tmp_path / "bad.mp4", tmp_path / "bad.txt", 50)


def test_incompatible_group_is_rejected_before_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(video, "media_signature", lambda p: (p.name,))
    calls = []
    monkeypatch.setattr(video, "run", lambda args: calls.append(args))
    with pytest.raises(ValueError, match="incompatible_scene_streams"):
        video.concatenate_videos([tmp_path / "a.mp4", tmp_path / "b.mp4"], tmp_path / "out.mp4", tmp_path / "concat.txt", 10)
    assert not calls and not (tmp_path / "concat.txt").exists()


def test_video_hash_reads_bytes_in_bounded_blocks(tmp_path):
    import hashlib
    path = tmp_path / "synthetic-test-only.bin"
    value = b"A" * (1024 * 1024 + 13)
    path.write_bytes(value)
    assert video.file_sha256(path) == hashlib.sha256(value).hexdigest()


def test_main_groups_scenes_without_replacing_original_master_sources(tmp_path, monkeypatch):
    import sys
    monkeypatch.setattr(video, "ROOT", tmp_path)
    captures = []
    for index in range(3):
        path = tmp_path / f"capture-{index}.json"
        path.write_text(json.dumps({"startedAtMs": index * 30000, "endedAtMs": index * 30000 + 20000}))
        captures.append(path)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(chapter_plan({"title": "Scope", "scenes": [1, 2]}, {"title": "Review", "scenes": [3]})))
    output = tmp_path / "output"
    args = ["assembler", "--output", str(output), "--chapter-plan", str(plan_path)]
    for path in captures:
        args.extend(["--capture", str(path)])
    monkeypatch.setattr(sys, "argv", args)
    _, cues, _ = video.build_timeline([1000, 2000], 21000, [cue()])
    monkeypatch.setattr(video, "encode", lambda capture, out, index: {
        "title": f"Scene {index}", "file": f"chapters/{index:02d}.mp4", "seconds": 20,
        "sceneNumber": index, "transcript": cues, "captureSha256": "test-only", "sha256": "test-only"})
    calls = []
    def concat(files, destination, concat_path, expected, **kwargs):
        calls.append((files, destination, expected, kwargs))
        return {"plannedSeconds": expected, "encodedSeconds": expected, "streamCopy": True}
    monkeypatch.setattr(video, "concatenate_videos", concat)
    monkeypatch.setattr(video.subprocess, "check_output", lambda *a, **kw: "ffmpeg test-only")
    video.main()
    assert len(calls) == 3
    assert [p.name for p in calls[0][0]] == ["01.mp4", "02.mp4"]
    assert [p.name for p in calls[2][0]] == ["01.mp4", "02.mp4", "03.mp4"]
    assert calls[2][3]["decode"] is True
    groups = json.loads((output / "chapters.json").read_text())
    scenes = json.loads((output / "scenes.json").read_text())
    assert [c["masterStart"] for c in groups] == [0, 40]
    assert [s["masterStart"] for s in scenes] == [0, 20, 40]
    assert [s["offCameraGapBeforeSeconds"] for s in scenes] == [0, 10, 10]
    assert "END=40000" in (output / "chapters.ffmetadata").read_text()
    assert len(json.loads((output / "assembly.json").read_text())["grouping"]) == 2


def test_existing_concatenation_cannot_be_overwritten(tmp_path):
    existing = tmp_path / "existing.mp4"
    existing.write_bytes(b"existing-test-artifact")
    with pytest.raises(ValueError, match="existing_or_empty_concatenation_refused"):
        video.concatenate_videos([tmp_path / "a.mp4"], existing, tmp_path / "concat.txt", 8)
    assert existing.read_bytes() == b"existing-test-artifact"
