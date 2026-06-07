"""Learner-facing endpoints for the Training Center."""

from __future__ import annotations

import json
import random

import frappe
from frappe.utils import cint, flt, now_datetime

from orderlift.orderlift_hr.api.assignment import (
    is_training_admin,
    resolve_assigned_programs,
)


# -- Public endpoints ---------------------------------------------------------


@frappe.whitelist()
def get_training_center_data(employee: str | None = None) -> dict:
    """Top-level payload for the Training Center page."""
    target_employee = _resolve_employee_or_admin(employee)
    if not target_employee:
        return _empty_payload()

    program_names = resolve_assigned_programs(target_employee)
    if not program_names:
        return _empty_payload(employee=target_employee)

    programs = frappe.get_all(
        "Training Program",
        filters={"name": ["in", program_names]},
        fields=["name", "program_name", "description", "is_required"],
        order_by="program_name asc",
    )

    user_id = frappe.db.get_value("Employee", target_employee, "user_id")
    progress_rows = frappe.get_all(
        "Employee Training Progress",
        filters={"employee": target_employee},
        fields=["module", "studied", "studied_on", "last_activity"],
    )
    progress_by_module = {row.module: row for row in progress_rows}

    program_payload = []
    for program in programs:
        program_payload.append(
            _build_program_summary(program, target_employee, progress_by_module)
        )

    next_module = _find_next_unstudied(program_payload)
    stats = _build_stats(target_employee, program_payload)

    return {
        "viewer": {
            "is_admin": is_training_admin(),
            "employee": target_employee,
            "user": user_id,
        },
        "programs": program_payload,
        "next_module": next_module,
        "stats": stats,
    }


@frappe.whitelist()
def get_module_detail(module: str) -> dict:
    """Returns module fields, file rows, and quiz metadata (no answers)."""
    if not module or not frappe.db.exists("Training Module", module):
        frappe.throw(frappe._("Module not found."))

    doc = frappe.get_doc("Training Module", module)
    files = [
        {
            "title": row.title,
            "file_type": row.file_type,
            "attachment": row.attachment,
            "url": row.url,
            "note_body": row.note_body,
            "sequence": row.sequence,
        }
        for row in sorted(doc.files or [], key=lambda r: r.sequence or 0)
    ]

    target_employee = _employee_for_session()
    quiz = _resolve_quiz_for_module(doc)
    quiz_meta = _build_quiz_meta(quiz, target_employee) if quiz else None

    progress = None
    if target_employee:
        progress = frappe.db.get_value(
            "Employee Training Progress",
            {"employee": target_employee, "module": module},
            ["studied", "studied_on"],
            as_dict=True,
        )

    return {
        "module": {
            "name": doc.name,
            "title": doc.title,
            "description": doc.description,
            "program": doc.program,
            "level": doc.level,
            "estimated_minutes": doc.estimated_minutes,
            "requires_quiz_pass": cint(doc.requires_quiz_pass),
            "linked_quiz": doc.linked_quiz,
        },
        "files": files,
        "quiz": quiz_meta,
        "progress": progress or {"studied": 0, "studied_on": None},
    }


@frappe.whitelist()
def mark_module_studied(module: str) -> dict:
    """Idempotently mark a module as studied for the current employee."""
    if not module or not frappe.db.exists("Training Module", module):
        frappe.throw(frappe._("Module not found."))

    employee = _employee_for_session()
    if not employee:
        frappe.throw(frappe._("No Employee record is linked to your user."))

    module_doc = frappe.get_doc("Training Module", module)

    progress_name = frappe.db.get_value(
        "Employee Training Progress",
        {"employee": employee, "module": module},
        "name",
    )

    if progress_name:
        doc = frappe.get_doc("Employee Training Progress", progress_name)
    else:
        doc = frappe.new_doc("Employee Training Progress")
        doc.employee = employee
        doc.module = module

    doc.program = module_doc.program
    doc.level = module_doc.level
    doc.user = frappe.db.get_value("Employee", employee, "user_id")
    doc.studied = 1
    if not doc.studied_on:
        doc.studied_on = now_datetime()
    doc.last_activity = now_datetime()
    doc.save(ignore_permissions=is_training_admin())

    program_summary = None
    if module_doc.program:
        program = frappe.db.get_value(
            "Training Program",
            module_doc.program,
            ["name", "program_name", "description", "is_required"],
            as_dict=True,
        )
        progress_rows = frappe.get_all(
            "Employee Training Progress",
            filters={"employee": employee},
            fields=["module", "studied"],
        )
        progress_by_module = {row.module: row for row in progress_rows}
        program_summary = _build_program_summary(program, employee, progress_by_module)

    return {"ok": True, "module": module, "program_summary": program_summary}


@frappe.whitelist()
def start_quiz(quiz: str) -> dict:
    """Open a new Training Quiz Attempt and return questions with answer keys stripped."""
    if not quiz or not frappe.db.exists("Training Quiz", quiz):
        frappe.throw(frappe._("Quiz not found."))

    quiz_doc = frappe.get_doc("Training Quiz", quiz)
    if not quiz_doc.is_active:
        frappe.throw(frappe._("This quiz is not active."))

    employee = _employee_for_session()
    if not employee:
        frappe.throw(frappe._("No Employee record is linked to your user."))

    attempts_used, attempts_remaining = _attempts_remaining(quiz_doc, employee)
    if attempts_remaining is not None and attempts_remaining <= 0:
        frappe.throw(frappe._("You have reached the maximum number of attempts for this quiz."))

    questions = frappe.get_all(
        "Training Quiz Question",
        filters={"quiz": quiz},
        fields=["name", "question_text", "question_type", "points", "sequence"],
        order_by="sequence asc",
    )
    if not questions:
        frappe.throw(frappe._("This quiz has no questions yet."))

    if quiz_doc.randomize_questions:
        random.shuffle(questions)

    questions_payload = []
    max_score = 0.0
    for question in questions:
        options = frappe.get_all(
            "Training Quiz Option",
            filters={"parent": question.name, "parenttype": "Training Quiz Question"},
            fields=["name", "option_text"],
            order_by="idx asc",
        )
        max_score += flt(question.points)
        questions_payload.append(
            {
                "name": question.name,
                "question_text": question.question_text,
                "question_type": question.question_type,
                "points": flt(question.points),
                "options": [{"name": o.name, "option_text": o.option_text} for o in options],
            }
        )

    attempt = frappe.new_doc("Training Quiz Attempt")
    attempt.quiz = quiz
    attempt.employee = employee
    attempt.user = frappe.session.user
    attempt.started_on = now_datetime()
    attempt.max_score = max_score
    attempt.insert(ignore_permissions=True)

    return {
        "attempt": attempt.name,
        "quiz": {
            "name": quiz_doc.name,
            "quiz_name": quiz_doc.quiz_name,
            "pass_percentage": flt(quiz_doc.pass_percentage),
            "max_score": max_score,
            "attempts_used": attempts_used + 1,
            "attempts_limit": None if quiz_doc.unlimited_attempts else cint(quiz_doc.max_attempts),
        },
        "questions": questions_payload,
    }


@frappe.whitelist()
def submit_quiz_attempt(attempt: str, answers_json: str) -> dict:
    """Server-side scoring + freeze. Updates linked module completion if needed."""
    if not attempt or not frappe.db.exists("Training Quiz Attempt", attempt):
        frappe.throw(frappe._("Attempt not found."))

    attempt_doc = frappe.get_doc("Training Quiz Attempt", attempt)

    employee = _employee_for_session()
    if not is_training_admin() and attempt_doc.user != frappe.session.user:
        frappe.throw(frappe._("You can only submit your own quiz attempts."), frappe.PermissionError)

    if attempt_doc.completed_on:
        frappe.throw(frappe._("This attempt has already been submitted."))

    try:
        parsed = json.loads(answers_json or "[]")
    except json.JSONDecodeError:
        frappe.throw(frappe._("Answers payload is not valid JSON."))

    answers_by_question = {row.get("question"): row.get("selected_options", []) for row in parsed}

    questions = frappe.get_all(
        "Training Quiz Question",
        filters={"quiz": attempt_doc.quiz},
        fields=["name", "question_type", "points"],
    )

    score = 0.0
    max_score = 0.0
    attempt_doc.answers = []

    for question in questions:
        max_score += flt(question.points)
        selected = answers_by_question.get(question.name) or []
        correct_options = {
            row.name
            for row in frappe.get_all(
                "Training Quiz Option",
                filters={
                    "parent": question.name,
                    "parenttype": "Training Quiz Question",
                    "is_correct": 1,
                },
                fields=["name"],
            )
        }
        is_correct = set(selected) == correct_options and bool(correct_options)
        points_awarded = flt(question.points) if is_correct else 0.0
        score += points_awarded
        attempt_doc.append(
            "answers",
            {
                "question": question.name,
                "selected_options": json.dumps(list(selected)),
                "is_correct": 1 if is_correct else 0,
                "points_awarded": points_awarded,
            },
        )

    attempt_doc.score = score
    attempt_doc.max_score = max_score
    pass_percentage = flt(frappe.db.get_value("Training Quiz", attempt_doc.quiz, "pass_percentage"))
    score_percentage = (score / max_score * 100.0) if max_score else 0.0
    attempt_doc.score_percentage = score_percentage
    attempt_doc.passed = 1 if score_percentage >= pass_percentage else 0
    attempt_doc.completed_on = now_datetime()
    attempt_doc.save(ignore_permissions=True)

    _maybe_update_module_for_quiz(attempt_doc, employee)

    return {
        "attempt": attempt_doc.name,
        "score": attempt_doc.score,
        "max_score": attempt_doc.max_score,
        "score_percentage": attempt_doc.score_percentage,
        "passed": cint(attempt_doc.passed),
    }


# -- Helpers ------------------------------------------------------------------


def _resolve_employee_or_admin(employee: str | None) -> str | None:
    if is_training_admin():
        if employee:
            return employee
        return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
    return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


def _employee_for_session() -> str | None:
    return frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")


def _empty_payload(employee: str | None = None) -> dict:
    return {
        "viewer": {
            "is_admin": is_training_admin(),
            "employee": employee,
            "user": frappe.session.user,
        },
        "programs": [],
        "next_module": None,
        "stats": {
            "module_completion_pct": 0.0,
            "quiz_average_pct": 0.0,
            "modules_completed": 0,
            "modules_total": 0,
            "last_activity": None,
        },
    }


def _build_program_summary(
    program: dict, employee: str, progress_by_module: dict
) -> dict:
    levels = frappe.get_all(
        "Training Level",
        filters={"program": program["name"]},
        fields=["name", "level_name", "sequence", "unlock_rule", "is_required"],
        order_by="sequence asc, level_name asc",
    )
    modules = frappe.get_all(
        "Training Module",
        filters={"program": program["name"], "is_active": 1},
        fields=[
            "name",
            "title",
            "level",
            "sequence",
            "is_required",
            "estimated_minutes",
            "linked_quiz",
            "requires_quiz_pass",
        ],
        order_by="sequence asc, title asc",
    )

    modules_by_level: dict[str | None, list] = {}
    for module in modules:
        modules_by_level.setdefault(module.level, []).append(module)

    required_total = 0
    required_done = 0
    levels_payload = []

    for level in levels:
        level_modules = modules_by_level.get(level.name, [])
        level_required_total = 0
        level_required_done = 0
        modules_payload = []
        for module in level_modules:
            studied = _is_module_complete(module, employee, progress_by_module)
            if module.is_required:
                level_required_total += 1
                if studied:
                    level_required_done += 1
            modules_payload.append(
                {
                    "name": module.name,
                    "title": module.title,
                    "is_required": cint(module.is_required),
                    "studied": studied,
                    "estimated_minutes": cint(module.estimated_minutes),
                    "has_quiz": bool(module.linked_quiz),
                }
            )

        if level.is_required:
            required_total += level_required_total
            required_done += level_required_done

        level_pct = (level_required_done / level_required_total * 100.0) if level_required_total else 0.0
        levels_payload.append(
            {
                "name": level.name,
                "level_name": level.level_name,
                "sequence": cint(level.sequence),
                "unlock_rule": level.unlock_rule,
                "is_required": cint(level.is_required),
                "completion_pct": round(level_pct, 1),
                "modules": modules_payload,
            }
        )

    flat_modules = modules_by_level.get(None, [])
    flat_payload = []
    for module in flat_modules:
        studied = _is_module_complete(module, employee, progress_by_module)
        if module.is_required:
            required_total += 1
            if studied:
                required_done += 1
        flat_payload.append(
            {
                "name": module.name,
                "title": module.title,
                "is_required": cint(module.is_required),
                "studied": studied,
                "estimated_minutes": cint(module.estimated_minutes),
                "has_quiz": bool(module.linked_quiz),
            }
        )

    program_pct = (required_done / required_total * 100.0) if required_total else 0.0

    return {
        "name": program["name"],
        "program_name": program["program_name"],
        "description": program.get("description"),
        "is_required": cint(program.get("is_required")),
        "completion_pct": round(program_pct, 1),
        "required_done": required_done,
        "required_total": required_total,
        "levels": levels_payload,
        "flat_modules": flat_payload,
    }


def _is_module_complete(module, employee: str, progress_by_module: dict) -> bool:
    row = progress_by_module.get(module.name)
    if not row or not row.studied:
        return False
    if cint(module.requires_quiz_pass) and module.linked_quiz:
        passed = frappe.db.exists(
            "Training Quiz Attempt",
            {
                "quiz": module.linked_quiz,
                "employee": employee,
                "passed": 1,
            },
        )
        if not passed:
            return False
    return True


def _find_next_unstudied(programs_payload: list[dict]) -> dict | None:
    for program in programs_payload:
        for level in program.get("levels", []):
            for module in level.get("modules", []):
                if module.get("is_required") and not module.get("studied"):
                    return {
                        "program": program["name"],
                        "level": level["name"],
                        "module": module["name"],
                        "title": module["title"],
                    }
        for module in program.get("flat_modules", []):
            if module.get("is_required") and not module.get("studied"):
                return {
                    "program": program["name"],
                    "level": None,
                    "module": module["name"],
                    "title": module["title"],
                }
    return None


def _build_stats(employee: str, programs_payload: list[dict]) -> dict:
    total = 0
    done = 0
    for program in programs_payload:
        total += program["required_total"]
        done += program["required_done"]

    module_completion_pct = (done / total * 100.0) if total else 0.0

    attempts = frappe.get_all(
        "Training Quiz Attempt",
        filters={"employee": employee, "completed_on": ["is", "set"]},
        fields=["quiz", "score_percentage", "completed_on"],
        order_by="completed_on desc",
    )
    latest_by_quiz: dict[str, float] = {}
    for row in attempts:
        if row.quiz in latest_by_quiz:
            continue
        latest_by_quiz[row.quiz] = flt(row.score_percentage)
    quiz_average_pct = (
        sum(latest_by_quiz.values()) / len(latest_by_quiz) if latest_by_quiz else 0.0
    )

    latest_row = frappe.get_all(
        "Employee Training Progress",
        filters={"employee": employee},
        fields=["last_activity"],
        order_by="last_activity desc",
        limit=1,
    )
    last_activity = latest_row[0].last_activity if latest_row else None

    return {
        "module_completion_pct": round(module_completion_pct, 1),
        "quiz_average_pct": round(quiz_average_pct, 1),
        "modules_completed": done,
        "modules_total": total,
        "last_activity": str(last_activity) if last_activity else None,
    }


def _resolve_quiz_for_module(module_doc) -> str | None:
    if module_doc.linked_quiz:
        return module_doc.linked_quiz
    return None


def _build_quiz_meta(quiz_name: str, employee: str | None) -> dict | None:
    quiz = frappe.db.get_value(
        "Training Quiz",
        quiz_name,
        ["name", "quiz_name", "pass_percentage", "max_attempts", "unlimited_attempts", "is_active"],
        as_dict=True,
    )
    if not quiz:
        return None
    attempts_used, remaining = _attempts_remaining(
        frappe._dict(quiz), employee
    ) if employee else (0, cint(quiz.max_attempts))
    return {
        "name": quiz.name,
        "quiz_name": quiz.quiz_name,
        "pass_percentage": flt(quiz.pass_percentage),
        "is_active": cint(quiz.is_active),
        "attempts_used": attempts_used,
        "attempts_remaining": remaining,
        "unlimited_attempts": cint(quiz.unlimited_attempts),
    }


def _attempts_remaining(quiz_doc, employee: str | None) -> tuple[int, int | None]:
    if not employee:
        return 0, None
    used = frappe.db.count(
        "Training Quiz Attempt",
        {"quiz": quiz_doc.name, "employee": employee, "completed_on": ["is", "set"]},
    )
    if quiz_doc.unlimited_attempts:
        return used, None
    return used, max(cint(quiz_doc.max_attempts) - used, 0)


def _maybe_update_module_for_quiz(attempt_doc, employee: str | None) -> None:
    if not employee:
        return
    modules = frappe.get_all(
        "Training Module",
        filters={"linked_quiz": attempt_doc.quiz, "requires_quiz_pass": 1},
        fields=["name"],
    )
    for module in modules:
        existing = frappe.db.get_value(
            "Employee Training Progress",
            {"employee": employee, "module": module.name},
            "name",
        )
        if not existing:
            continue
        doc = frappe.get_doc("Employee Training Progress", existing)
        doc.last_activity = now_datetime()
        doc.save(ignore_permissions=True)


# -- Permission hooks ---------------------------------------------------------


def has_permission(doc, ptype: str, user: str) -> bool:
    """Used for Training Quiz Attempt and Employee Training Progress in hooks.py."""
    if is_training_admin(user):
        return True
    if doc.get("user") and doc.get("user") == user:
        return True
    if doc.get("employee"):
        employee_user = frappe.db.get_value("Employee", doc.get("employee"), "user_id")
        if employee_user == user:
            return True
    return False


def quiz_attempt_query(user: str | None = None) -> str:
    """Restrict non-admin users to their own Training Quiz Attempt rows."""
    user = user or frappe.session.user
    if is_training_admin(user):
        return ""
    safe_user = frappe.db.escape(user)
    return f"`tabTraining Quiz Attempt`.`user` = {safe_user}"


def progress_query(user: str | None = None) -> str:
    """Restrict non-admin users to their own Employee Training Progress rows."""
    user = user or frappe.session.user
    if is_training_admin(user):
        return ""
    safe_user = frappe.db.escape(user)
    return f"`tabEmployee Training Progress`.`user` = {safe_user}"
