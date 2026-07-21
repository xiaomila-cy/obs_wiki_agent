#!/usr/bin/env python3
"""Create and check deterministic wall-clock deadlines for one Skill run."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


NORMAL_CONTENT_STOP_SECONDS = 440
CONTENT_WRITE_DEADLINE_SECONDS = 455
FINISH_START_DEADLINE_SECONDS = 475
CONTENT_SEAL_SECONDS = 476
HARD_LIMIT_SECONDS = 480

PROGRESS_CHECKPOINTS = (
    (1500, 210.0),
    (4000, 325.0),
)
FINAL_CHECKPOINT = (6900, float(FINISH_START_DEADLINE_SECONDS))
REQUIRED_CHECKPOINTS = (*PROGRESS_CHECKPOINTS, FINAL_CHECKPOINT)

PHASES = (
    (40, "research", "只确认书籍并建立最小充分证据表。"),
    (50, "outline", "停止检索，锁定结构、三块字符配额和听觉导航。"),
    (210, "chunk_one", "写完第一块并运行第一项软进度检查。"),
    (325, "chunk_two", "写完第二块并运行第二项软进度检查。"),
    (
        NORMAL_CONTENT_STOP_SECONDS,
        "chunk_three",
        "一次写完第三块与收束，正常在第 440 秒前达到至少 6900 字。",
    ),
    (
        CONTENT_WRITE_DEADLINE_SECONDS,
        "recovery",
        "只允许已在运行的末块返回或做已核实的小缺口恢复，禁止新增研究。",
    ),
    (
        FINISH_START_DEADLINE_SECONDS,
        "finalize",
        "正文已经绝对封口，禁止发起新正文调用，立即运行原子 finish。",
    ),
    (
        CONTENT_SEAL_SECONDS,
        "content_seal",
        "最终检查门已过，只允许已经启动的 finish 完成留证。",
    ),
    (
        HARD_LIMIT_SECONDS,
        "emergency",
        "文件封口已经生效，只允许保存现有失败证据。",
    ),
)


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def render_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_state(started_at: datetime) -> dict[str, object]:
    state: dict[str, object] = {"started_at": render_timestamp(started_at)}
    for seconds, phase, _ in PHASES:
        state[f"{phase}_deadline"] = render_timestamp(
            started_at + timedelta(seconds=seconds)
        )
    return state


def budget_status(started_at: datetime, now: datetime) -> dict[str, object]:
    elapsed = max(0.0, (now - started_at).total_seconds())
    phase = "expired"
    instruction = "硬上限已过，立即停止并如实记录超时。"
    next_deadline = started_at + timedelta(seconds=HARD_LIMIT_SECONDS)

    for seconds, candidate, candidate_instruction in PHASES:
        if elapsed < seconds:
            phase = candidate
            instruction = candidate_instruction
            next_deadline = started_at + timedelta(seconds=seconds)
            break

    return {
        "phase": phase,
        "elapsed_seconds": round(elapsed, 3),
        "remaining_seconds": round(HARD_LIMIT_SECONDS - elapsed, 3),
        "next_deadline": render_timestamp(next_deadline),
        "instruction": instruction,
        "expired": elapsed >= HARD_LIMIT_SECONDS,
    }


def read_state(path: Path) -> tuple[dict[str, object], datetime]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    started_at = payload.get("started_at")
    if not isinstance(started_at, str):
        raise ValueError("runtime state has no valid started_at")
    return payload, parse_timestamp(started_at)


def check_transcript(path: Path, title: str) -> dict[str, object]:
    checker_path = Path(__file__).with_name("check_transcript.py")
    spec = importlib.util.spec_from_file_location(
        "runtime_guard_check_transcript", checker_path
    )
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load transcript checker: {checker_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    text = path.read_text(encoding="utf-8-sig")
    return module.analyze_text(text, title=title)


def visible_length(value: str) -> int:
    return sum(not character.isspace() for character in value)


def measurement_status(
    started_at: datetime,
    now: datetime,
    transcript: Path,
) -> dict[str, object]:
    timing = budget_status(started_at, now)
    characters = (
        visible_length(transcript.read_text(encoding="utf-8-sig"))
        if transcript.is_file()
        else 0
    )
    return {**timing, "characters": characters}


def checkpoint_status(
    started_at: datetime,
    now: datetime,
    transcript: Path,
    *,
    min_chars: int,
    max_elapsed: float,
) -> dict[str, object]:
    measurement = measurement_status(started_at, now, transcript)
    characters = int(measurement["characters"])
    errors: list[str] = []
    warnings: list[str] = []
    expected = (min_chars, float(max_elapsed)) in REQUIRED_CHECKPOINTS
    is_final = (min_chars, float(max_elapsed)) == FINAL_CHECKPOINT
    if not expected:
        errors.append("checkpoint does not match the required schedule")
    if measurement["expired"]:
        errors.append("hard deadline expired")
    schedule_target_met = measurement["elapsed_seconds"] <= max_elapsed
    character_target_met = characters >= min_chars
    if not schedule_target_met:
        message = f"checkpoint exceeded target {max_elapsed:g} seconds"
        (errors if is_final else warnings).append(message)
    if not character_target_met:
        message = f"transcript has {characters} characters; target is {min_chars}"
        (errors if is_final else warnings).append(message)

    seconds_left = max(
        0.0,
        CONTENT_WRITE_DEADLINE_SECONDS - float(measurement["elapsed_seconds"]),
    )
    chars_needed = max(0, FINAL_CHECKPOINT[0] - characters)
    productive_seconds = max(1.0, float(measurement["elapsed_seconds"]) - PHASES[1][0])
    observed_rate = characters / productive_seconds
    safe_capacity = observed_rate * seconds_left * 0.85
    if characters >= FINAL_CHECKPOINT[0]:
        pace = "ready_to_finish"
    elif seconds_left <= 0:
        pace = "hard_stop"
    elif safe_capacity < chars_needed:
        pace = "critical"
    elif warnings:
        pace = "warning"
    else:
        pace = "on_track"
    if pace == "critical":
        warnings.append(
            "observed pace cannot safely reach the final target before content seal"
        )

    runtime_valid = not bool(measurement["expired"])
    return {
        **measurement,
        "characters": characters,
        "min_characters": min_chars,
        "max_elapsed_seconds": max_elapsed,
        "expected_checkpoint": expected,
        "character_target_met": character_target_met,
        "schedule_target_met": schedule_target_met,
        "runtime_valid": runtime_valid,
        "seconds_left_for_content": round(seconds_left, 3),
        "characters_needed": chars_needed,
        "observed_characters_per_second": round(observed_rate, 3),
        "pace": pace,
        "warnings": warnings,
        "passed": expected and runtime_valid and not errors,
        "errors": errors,
    }


def write_meta(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def record_checkpoint(
    state_path: Path,
    state: dict[str, object],
    checked_at: datetime,
    result: dict[str, object],
) -> None:
    checkpoints = state.setdefault("checkpoints", [])
    if not isinstance(checkpoints, list):
        checkpoints = []
        state["checkpoints"] = checkpoints
    checkpoints.append(
        {
            "stage": result.get("stage"),
            "checked_at": render_timestamp(checked_at),
            "min_characters": result["min_characters"],
            "max_elapsed_seconds": result["max_elapsed_seconds"],
            "elapsed_seconds": result["elapsed_seconds"],
            "characters": result["characters"],
            "character_target_met": result["character_target_met"],
            "schedule_target_met": result["schedule_target_met"],
            "runtime_valid": result["runtime_valid"],
            "pace": result["pace"],
            "passed": result["passed"],
            "warnings": result["warnings"],
            "errors": result["errors"],
        }
    )
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def has_passed_checkpoint(
    state: dict[str, object],
    min_chars: int,
    max_elapsed: float,
) -> bool:
    checkpoints = state.get("checkpoints")
    records = checkpoints if isinstance(checkpoints, list) else []
    return any(
        isinstance(record, dict)
        and record.get("min_characters") == min_chars
        and record.get("max_elapsed_seconds") == max_elapsed
        and record.get("passed") is True
        for record in records
    )


def checkpoint_evidence_errors(state: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if state.get("invalidated_at"):
        errors.append(str(state.get("invalidation_reason") or "runtime invalidated"))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start")
    start.add_argument("state", type=Path)
    start.add_argument("--started-at")

    status = subparsers.add_parser("status")
    status.add_argument("state", type=Path)
    status.add_argument("--now")

    measure = subparsers.add_parser("measure")
    measure.add_argument("state", type=Path)
    measure.add_argument("transcript", type=Path)
    measure.add_argument("--now")

    checkpoint = subparsers.add_parser("checkpoint")
    checkpoint.add_argument("state", type=Path)
    checkpoint.add_argument("transcript", type=Path)
    checkpoint.add_argument(
        "--stage",
        type=int,
        choices=range(1, len(PROGRESS_CHECKPOINTS) + 1),
        required=True,
    )
    checkpoint.add_argument("--now")

    finish = subparsers.add_parser("finish")
    finish.add_argument("state", type=Path)
    finish.add_argument("meta", type=Path, nargs="?")
    finish.add_argument("--completed-at")
    finish.add_argument("--transcript", type=Path)
    finish.add_argument("--title")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.command == "start":
        started_at = (
            parse_timestamp(args.started_at)
            if args.started_at
            else datetime.now(timezone.utc)
        )
        payload = build_state(started_at)
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    state, started_at = read_state(args.state)
    now = (
        parse_timestamp(args.now)
        if getattr(args, "now", None)
        else datetime.now(timezone.utc)
    )

    if args.command == "status":
        payload = budget_status(started_at, now)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if payload["expired"]:
            raise SystemExit(1)
        return

    if args.command == "measure":
        payload = measurement_status(started_at, now, args.transcript)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if payload["expired"]:
            raise SystemExit(1)
        return

    if args.command == "checkpoint":
        min_chars, max_elapsed = PROGRESS_CHECKPOINTS[args.stage - 1]
        payload = checkpoint_status(
            started_at,
            now,
            args.transcript,
            min_chars=min_chars,
            max_elapsed=max_elapsed,
        )
        payload["stage"] = args.stage
        record_checkpoint(args.state, state, now, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not payload["passed"]:
            raise SystemExit(1)
        return

    meta_path = args.meta or args.state.with_name("generation-meta.json")
    requested_completed_at = (
        parse_timestamp(args.completed_at) if args.completed_at else None
    )
    precheck_at = requested_completed_at or datetime.now(timezone.utc)
    precheck_duration = max(0.0, (precheck_at - started_at).total_seconds())
    if precheck_duration > HARD_LIMIT_SECONDS:
        payload = {
            "passed": False,
            "started_at": render_timestamp(started_at),
            "completed_at": render_timestamp(precheck_at),
            "duration_seconds": round(precheck_duration, 3),
            "format_check_passed": False,
            "failure_reason": "hard deadline expired before format check",
        }
        write_meta(meta_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(1)

    if args.transcript and args.title:
        final_min_chars, final_max_elapsed = FINAL_CHECKPOINT
        evidence_errors = checkpoint_evidence_errors(state)
        if precheck_duration > FINISH_START_DEADLINE_SECONDS:
            evidence_errors.append(
                f"finish started after {FINISH_START_DEADLINE_SECONDS} seconds"
            )

        if not has_passed_checkpoint(state, final_min_chars, final_max_elapsed):
            final_checkpoint = checkpoint_status(
                started_at,
                precheck_at,
                args.transcript,
                min_chars=final_min_chars,
                max_elapsed=final_max_elapsed,
            )
            final_checkpoint["stage"] = len(PROGRESS_CHECKPOINTS) + 1
            record_checkpoint(args.state, state, precheck_at, final_checkpoint)
            evidence_errors.extend(str(error) for error in final_checkpoint["errors"])

        if args.transcript.is_file():
            modified_at = datetime.fromtimestamp(
                args.transcript.stat().st_mtime, tz=timezone.utc
            )
            seal_at = started_at + timedelta(seconds=CONTENT_WRITE_DEADLINE_SECONDS)
            if modified_at > seal_at:
                evidence_errors.append(
                    "transcript was modified after the content write deadline"
                )
        if evidence_errors:
            payload = {
                "passed": False,
                "started_at": render_timestamp(started_at),
                "completed_at": render_timestamp(precheck_at),
                "duration_seconds": round(precheck_duration, 3),
                "format_check_passed": False,
                "failure_reason": "runtime checkpoint evidence failed",
                "checkpoint_errors": evidence_errors,
            }
            write_meta(meta_path, payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            raise SystemExit(1)

    format_result: dict[str, object] | None = None
    if args.transcript or args.title:
        if not args.transcript or not args.title:
            raise ValueError("finish requires both --transcript and --title")
        format_result = check_transcript(args.transcript, args.title)

    completed_at = requested_completed_at or datetime.now(timezone.utc)
    duration = max(0.0, (completed_at - started_at).total_seconds())
    payload = {
        "passed": False,
        "started_at": render_timestamp(started_at),
        "completed_at": render_timestamp(completed_at),
        "duration_seconds": round(duration, 3),
    }
    if format_result is not None:
        payload["format_check_passed"] = bool(format_result["passed"])
        payload["format_metrics"] = format_result["metrics"]
        if not format_result["passed"]:
            payload["format_issues"] = format_result["issues"]
    if duration > HARD_LIMIT_SECONDS:
        payload["failure_reason"] = "hard deadline expired during format check"
        write_meta(meta_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(1)
    if format_result is not None and not format_result["passed"]:
        payload["failure_reason"] = "transcript format check failed"
        write_meta(meta_path, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    payload["passed"] = True
    write_meta(meta_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
