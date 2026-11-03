import math
import os

MODULE_NUMBERS = tuple(range(1, 11))
MODULE_ENTRY_KEYS = ("lp1", "lp2", "reflection", "wrap_up")
PROJECT_ENTRY_KEYS = ("p1_checkin", "p2_checkin", "p32_checkin", "presentation")

STATUS_UNRECORDED = "unrecorded"
STATUS_INCOMPLETE = "incomplete"
STATUS_COMPLETE = "complete"
STATUS_INVALID = "invalid"

users    = [["admin", "1234"]]
students = []
scores   = []

is_authenticated = False

class EndOfInput(Exception):
    """Raised when the input stream ends (EOF) at any prompt."""

class ActionCancelled(Exception):
    """Raised when the user confirms they want to cancel the current action."""

def safe_input(prompt: str) -> str:
    """
    input() wrapper implementing the application-wide EOF policy.

    Returns the line the user typed. When the input stream has ended,
    raises EndOfInput so the event can propagate to the application
    boundary and end the program cleanly (one message, no traceback,
    no repeated prompts).
    """
    try:
        return input(prompt)
    except EOFError:
        raise EndOfInput from None

def clear_screen():
    """Clear the terminal for a clean, professional look."""
    os.system("cls" if os.name == "nt" else "clear")


def print_header(title: str):
    """Print a standardised section header with ASCII dividers."""
    clear_screen()
    print("=" * 65)
    print("  GRADETRACK  |  ITE 260 — Computer Programming 1")
    print("=" * 65)
    print(f"  {title}")
    print("-" * 65)


def press_enter():
    """
    Pause execution and wait for the user to press Enter.
    CTRL+C at a pause prompt is treated the same as pressing Enter.
    If the input stream ends here, EndOfInput propagates and the
    application exits cleanly at the top level.
    """
    try:
        safe_input("\n  [ Press ENTER to continue... ]")
    except KeyboardInterrupt:
        print()


def confirm_quit(prompt: str) -> bool:
    """
    Ask the user to confirm leaving the current screen. Accepts yes / no
    in any combination of upper or lower case. Returns True on yes.
    A CTRL+C during this prompt is treated as "no" (stay where you are).
    If the input stream ends here, EndOfInput propagates and the
    application exits cleanly at the top level.
    """
    while True:
        try:
            answer = safe_input(prompt).strip().lower()
        except KeyboardInterrupt:
            print()
            return False
        if answer in ("yes", "y"):
            return True
        if answer in ("no", "n"):
            return False
        print("  [!] Please answer yes or no.")


def guarded_input(prompt: str) -> str:
    """
    input() with in-place CTRL+C protection. Pressing CTRL+C asks:
      no  → re-prompt on the SAME field only — everything already typed
            (student ID, module, earlier scores) is kept exactly as is.
      yes → raise ActionCancelled so the calling action is cancelled.
    Saved student data is not deleted by a cancellation.

    If the input stream ends, EndOfInput propagates to the top level and
    the application exits — an interrupted entry therefore cannot
    overwrite a previously saved component.
    """
    while True:
        try:
            return safe_input(prompt)
        except KeyboardInterrupt:
            print()
            if confirm_quit("  Are you sure you want to cancel this action? (yes/no): "):
                raise ActionCancelled
            print("  [i] Staying — continue entering this field.")


def run_with_cancel_guard(action):
    """
    Universal guard wrapping every section.

    Because all prompts use guarded_input(), CTRL+C is handled right where
    it happens: answering "no" re-prompts only the current field and keeps
    every earlier input intact; answering "yes" cancels the action and
    returns to the caller's menu. Saved data is not removed by cancellation.

    EndOfInput is intentionally not caught here, so an exhausted input
    stream always reaches the application boundary instead of being
    retried by this loop.
    """
    while True:
        try:
            action()
            return
        except ActionCancelled:
            print("\n  [i] Action cancelled. Data saved earlier in this session is untouched.")
            press_enter()
            return
        except KeyboardInterrupt:
            # Safety net only — normal prompts are handled in guarded_input
            print()
            if confirm_quit("  Are you sure you want to cancel this action? (yes/no): "):
                print("\n  [i] Action cancelled. Data saved earlier in this session is untouched.")
                press_enter()
                return
            print("\n  [i] Staying in this section — please start the entry again.")


def parse_finite_number(text: str):
    """
    Convert text to a float, requiring a FINITE result.

    Returns the float value, or None when the text is not numeric or does
    not represent a finite number. This rejects 'inf', '+inf', '-inf',
    'infinity', 'nan' (any capitalisation) and numeric strings that
    overflow to infinity, such as '1e309', which plain float() would
    otherwise accept.
    """
    try:
        value = float(text)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(value):
        return None
    return value


def is_valid_entry(entry) -> bool:
    """
    True when entry is a [score, max] pair made of two finite numbers with
    max > 0 and 0 <= score <= max. Used as a defensive check on stored data
    so corrupted values can be identified and excluded instead of silently
    contributing to a grade or class average.
    """
    if not isinstance(entry, (list, tuple)) or len(entry) != 2:
        return False
    score, max_score = entry
    for value in entry:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not math.isfinite(value):
            return False
    return max_score > 0 and 0 <= score <= max_score


def get_validated_attendance() -> str:
    """
    Prompt for the attendance mark: P (Present) or A (Absent).
    Attendance is not a score — it is a character input only.
    Loops until a valid value is entered.
    """
    while True:
        value = guarded_input("  Enter Attendance (5%) [P - Present / A - Absent]: ").strip().upper()
        if value in ("P", "A"):
            return value
        print("  [!] Please enter P for Present or A for Absent.")


def get_score_with_max(label: str):
    """
    Prompt for a raw score followed by its max score. The max score is
    dynamic per entry (e.g. 45 out of 50, 18 out of 20, 90 out of 100).

    Validation applied to both numbers:
      * must be numeric AND finite — inf / -inf / nan and overflow values
        such as 1e309 are rejected with a clear message and a re-prompt;
      * score must be >= 0 (a recorded zero is a valid score);
      * max must be > 0;
      * score must not exceed max — otherwise the whole pair is re-entered.

    Returns a tuple: (score, max_score). The caller assigns the result to
    the record only after this function returns, so invalid or interrupted
    input can never overwrite a previously saved component.
    """
    while True:
        # Step 1 — raw score (any non-negative finite number)
        while True:
            score = parse_finite_number(guarded_input(f"  Enter {label} Score: ").strip())
            if score is None:
                print("  [!] Invalid input — please enter a finite numeric value "
                      "(inf, -inf and nan are not accepted).")
                continue
            if score >= 0.0:
                break
            print("  [!] Score cannot be negative. Try again.")

        while True:
            max_score = parse_finite_number(guarded_input("  Max Score: ").strip())
            if max_score is None:
                print("  [!] Invalid input — please enter a finite numeric value "
                      "(inf, -inf and nan are not accepted).")
                continue
            if max_score > 0.0:
                break
            print("  [!] Max score must be greater than 0. Try again.")

        # Step 3 — score must not exceed the max score
        if score <= max_score:
            return score, max_score
        print(f"  [!] Score cannot exceed the max score ({max_score:g}). Please re-enter.")

def find_student(student_id: str):
    """
    Search the global `students` list for a matching student_id.
    Returns the student record [id, name, course, section] or None.
    """
    for student in students:
        if student[0] == student_id:
            return student
    return None


def find_score_record(student_id: str):
    """
    Search the global `scores` list for a matching student_id.
    Returns the score record (dict) or None.
    """
    for record in scores:
        if isinstance(record, dict) and record.get("student_id") == student_id:
            return record
    return None


def new_module_record():
    """Create one blank, independent module record."""
    return {
        "attendance": None,
        "lp1":        None,
        "lp2":        None,
        "reflection": None,
        "wrap_up":    None,
    }


def new_project_record():
    """Create the blank course-wide Final Project record."""
    return {
        "p1_checkin":   None,
        "p2_checkin":   None,
        "p32_checkin":  None,
        "presentation": None,
    }


def new_score_record(student_id: str):
    """
    Create a blank score record with ten independent module records and a
    separate course-wide project record. Every component starts as None.
    """
    return {
        "student_id":    student_id,
        "modules":       {module: new_module_record() for module in MODULE_NUMBERS},
        "project":       new_project_record(),
        "module_grades": {module: None for module in MODULE_NUMBERS},
        "overall_grade": None,
    }


def get_or_create_score_record(student_id: str):
    """Return the existing score record or create and register a blank one."""
    record = find_score_record(student_id)
    if record is None:
        record = new_score_record(student_id)
        scores.append(record)
    return record

def fmt_entry(entry) -> str:
    """Format a [score, max] entry as 'score/max', or a clear status."""
    if entry is None:
        return "not recorded"
    if not is_valid_entry(entry):
        return "invalid"
    return f"{entry[0]:g}/{entry[1]:g}"


def fmt_entry_compact(entry) -> str:
    """Short form used by summary tables."""
    if entry is None:
        return "—"
    if not is_valid_entry(entry):
        return "invalid"
    return f"{entry[0]:g}/{entry[1]:g}"


def status_label(status: str) -> str:
    """Human-readable label for an internal status constant."""
    return {
        STATUS_UNRECORDED: "Unrecorded",
        STATUS_INCOMPLETE: "Incomplete",
        STATUS_COMPLETE:   "Complete",
        STATUS_INVALID:    "Invalid",
    }.get(status, "Unknown")


def module_record_status(module) -> str:
    """
    Classify one module record as unrecorded, incomplete, complete, or
    invalid. A blank module is UNRECORDED, not complete and not incomplete.
    """
    if not isinstance(module, dict):
        return STATUS_INVALID

    required = ("attendance",) + MODULE_ENTRY_KEYS
    if any(key not in module for key in required):
        return STATUS_INVALID

    attendance = module["attendance"]
    if attendance is not None and attendance not in ("P", "A"):
        return STATUS_INVALID

    recorded = 0 if attendance is None else 1
    for key in MODULE_ENTRY_KEYS:
        entry = module[key]
        if entry is None:
            continue
        if not is_valid_entry(entry):
            return STATUS_INVALID
        recorded += 1

    if recorded == 0:
        return STATUS_UNRECORDED
    if recorded == 5:
        return STATUS_COMPLETE
    return STATUS_INCOMPLETE


def project_record_status(project) -> str:
    """Classify the course-wide Final Project record."""
    if not isinstance(project, dict):
        return STATUS_INVALID
    if any(key not in project for key in PROJECT_ENTRY_KEYS):
        return STATUS_INVALID

    recorded = 0
    for key in PROJECT_ENTRY_KEYS:
        entry = project[key]
        if entry is None:
            continue
        if not is_valid_entry(entry):
            return STATUS_INVALID
        recorded += 1

    if recorded == 0:
        return STATUS_UNRECORDED
    if recorded == 4:
        return STATUS_COMPLETE
    return STATUS_INCOMPLETE


def overall_record_status(record) -> str:
    """
    Classify a student's overall result. Overall is complete only when all
    ten module records are complete AND the course-wide project is complete.
    """
    if not isinstance(record, dict):
        return STATUS_INVALID
    modules = record.get("modules")
    if not isinstance(modules, dict):
        return STATUS_INVALID
    if any(module not in modules for module in MODULE_NUMBERS):
        return STATUS_INVALID

    project_state = project_record_status(record.get("project"))
    module_states = [module_record_status(modules[module]) for module in MODULE_NUMBERS]

    if project_state == STATUS_INVALID or STATUS_INVALID in module_states:
        return STATUS_INVALID
    if project_state == STATUS_UNRECORDED and all(
            state == STATUS_UNRECORDED for state in module_states):
        return STATUS_UNRECORDED
    if project_state == STATUS_COMPLETE and all(
            state == STATUS_COMPLETE for state in module_states):
        return STATUS_COMPLETE
    return STATUS_INCOMPLETE


def module_recorded_count(module) -> int:
    """Count entries currently present in a module record."""
    if not isinstance(module, dict):
        return 0
    count = 0
    if module.get("attendance") is not None:
        count += 1
    for key in MODULE_ENTRY_KEYS:
        if module.get(key) is not None:
            count += 1
    return count


def project_recorded_count(project) -> int:
    """Count entries currently present in the course-wide project record."""
    if not isinstance(project, dict):
        return 0
    return sum(1 for key in PROJECT_ENTRY_KEYS if project.get(key) is not None)


def overall_progress(record):
    """Return (completed module count, project status) for a student."""
    if not isinstance(record, dict):
        return 0, STATUS_INVALID
    modules = record.get("modules")
    if not isinstance(modules, dict):
        return 0, STATUS_INVALID
    complete = 0
    for module in MODULE_NUMBERS:
        module_data = modules.get(module)
        if module_record_status(module_data) == STATUS_COMPLETE:
            complete += 1
    return complete, project_record_status(record.get("project"))


def to_pct(entry) -> float:
    """Convert a valid [score, max] entry into a percentage (0-100)."""
    return (entry[0] / entry[1]) * 100


def compute_checkin_avg(project):
    """
    Average percentage of the three Final Project check-in grades.
    Returns None if any check-in grade is missing or invalid. The
    presentation is not required for this partial calculation.
    """
    if not isinstance(project, dict):
        return None
    entries = [project.get("p1_checkin"),
               project.get("p2_checkin"),
               project.get("p32_checkin")]
    if any(not is_valid_entry(entry) for entry in entries):
        return None
    return (to_pct(entries[0]) + to_pct(entries[1]) + to_pct(entries[2])) / 3


def compute_project_overall(project):
    """
    Final Project overall percentage:
      Check-in Grades Average x 0.65 + Final Output/Presentation x 0.35
    Returns None if any part of the project is missing or invalid.
    """
    checkin_avg = compute_checkin_avg(project)
    if checkin_avg is None or not isinstance(project, dict):
        return None
    presentation = project.get("presentation")
    if not is_valid_entry(presentation):
        return None
    return (checkin_avg * 0.65) + (to_pct(presentation) * 0.35)


def compute_module_score(module):
    """
    Weighted module score out of 70:
      Attendance x 0.05 + Let's Practice x 0.35
      + Reflection x 0.15 + Wrap-Up Quiz x 0.15
    Returns None unless every module component is present and valid.
    """
    if module_record_status(module) != STATUS_COMPLETE:
        return None

    att_pct = 100.0 if module["attendance"] == "P" else 0.0
    lp_pct = (to_pct(module["lp1"]) + to_pct(module["lp2"])) / 2
    refl_pct = to_pct(module["reflection"])
    wq_pct = to_pct(module["wrap_up"])

    return (att_pct * 0.05) + (lp_pct * 0.35) + \
           (refl_pct * 0.15) + (wq_pct * 0.15)


def compute_module_percentage(module):
    """Return the completed module score as a percentage of 70, or None."""
    score = compute_module_score(module)
    if score is None:
        return None
    return (score / 70.0) * 100.0


def compute_overall_breakdown(record):
    """
    Apply the confirmed overall formula. Returns a dictionary of component
    averages and contributions, or None while any required result is missing.

    Overall = average of the ten module scores (out of 70)
              + course-wide project percentage x 0.30
    This is mathematically the same as applying the five category weights
    once to the ten-module averages:
      Attendance 5% + Let's Practice 35% + Reflection 15%
      + Wrap-Up Quiz 15% + Final Project 30%.
    """
    if overall_record_status(record) != STATUS_COMPLETE:
        return None

    modules = record["modules"]
    module_scores = []
    att_pcts = []
    lp_pcts = []
    refl_pcts = []
    wq_pcts = []

    for module_num in MODULE_NUMBERS:
        module = modules[module_num]
        score = compute_module_score(module)
        if score is None:
            return None
        module_scores.append(score)
        att_pcts.append(100.0 if module["attendance"] == "P" else 0.0)
        lp_pcts.append((to_pct(module["lp1"]) + to_pct(module["lp2"])) / 2)
        refl_pcts.append(to_pct(module["reflection"]))
        wq_pcts.append(to_pct(module["wrap_up"]))

    project_pct = compute_project_overall(record["project"])
    if project_pct is None:
        return None

    att_avg = sum(att_pcts) / len(att_pcts)
    lp_avg = sum(lp_pcts) / len(lp_pcts)
    refl_avg = sum(refl_pcts) / len(refl_pcts)
    wq_avg = sum(wq_pcts) / len(wq_pcts)
    module_avg = sum(module_scores) / len(module_scores)

    att_points = att_avg * 0.05
    lp_points = lp_avg * 0.35
    refl_points = refl_avg * 0.15
    wq_points = wq_avg * 0.15
    project_points = project_pct * 0.30
    module_subtotal = att_points + lp_points + refl_points + wq_points
    final_raw = module_subtotal + project_points

    return {
        "att_avg":          att_avg,
        "lp_avg":           lp_avg,
        "refl_avg":         refl_avg,
        "wq_avg":           wq_avg,
        "att_points":       att_points,
        "lp_points":        lp_points,
        "refl_points":      refl_points,
        "wq_points":        wq_points,
        "module_avg":       module_avg,
        "module_subtotal":  module_subtotal,
        "project_pct":      project_pct,
        "project_points":   project_points,
        "final_raw":        final_raw,
        "final_grade":      round(final_raw, 2),
        "module_scores":    module_scores,
    }


def compute_overall_grade(record):
    """
    Return the rounded overall grade (0-100), or None while any module or
    the course-wide project is missing or invalid.
    """
    breakdown = compute_overall_breakdown(record)
    if breakdown is None:
        return None
    return breakdown["final_grade"]


def compute_grade(record):
    """Backward-compatible wrapper for the student's overall grade."""
    return compute_overall_grade(record)


def refresh_student_results(record):
    """
    Recompute and cache module scores and the overall grade after a
    successful update. Search and reports also call this refresh so their
    displayed results always agree with the stored entries.
    """
    if not isinstance(record, dict):
        return
    modules = record.get("modules")
    if not isinstance(modules, dict):
        return

    module_grades = record.get("module_grades")
    if not isinstance(module_grades, dict):
        module_grades = {module: None for module in MODULE_NUMBERS}
        record["module_grades"] = module_grades
    for module_num in MODULE_NUMBERS:
        module_data = modules.get(module_num)
        module_grades[module_num] = compute_module_score(module_data)
    record["overall_grade"] = compute_overall_grade(record)


def grade_remark(grade: float) -> str:
    """
    Return a descriptive remark based on the computed final grade.

    Current thresholds — carried over unchanged from the previous version:
      >= 90  Excellent
      >= 80  Very Good
      >= 75  Good
      >= 60  Passing
      <  60  Failed
    """
    if grade >= 90:
        return "Excellent"
    elif grade >= 80:
        return "Very Good"
    elif grade >= 75:
        return "Good"
    elif grade >= 60:
        return "Passing"
    else:
        return "Failed"

def login():
    """
    Prompt for username and PIN, then validate against the `users` list.
    Sets the global `is_authenticated` flag to True on success.
    """
    global is_authenticated

    print_header("LOGIN  —  Please authenticate to continue")

    username = guarded_input("  Username : ").strip()
    pin      = guarded_input("  PIN      : ").strip()

    # Iterate through users list to find a matching credential pair
    for user in users:
        if user[0] == username and user[1] == pin:
            is_authenticated = True
            clear_screen()
            print("=" * 65)
            print(f"  LOGIN SUCCESSFUL  —  Welcome, {username.upper()}!")
            print("=" * 65)
            press_enter()
            return

    # Credentials did not match any record
    print("\n  [!] Invalid username or PIN. Access denied.")
    press_enter()

def add_student():
    """
    Collect student details and append a new record to the `students` list.
    Prevents duplicate student IDs. The record is appended only after every
    field has been collected, so a cancelled or interrupted entry never
    adds a partially completed student.
    """
    print_header("ADD STUDENT  —  Enroll a new student")

    student_id = guarded_input("  Student ID  : ").strip()

    if not student_id:
        print("\n  [!] Student ID cannot be empty.")
        press_enter()
        return

    if find_student(student_id):
        print(f"\n  [!] Student ID '{student_id}' already exists.")
        press_enter()
        return

    name    = guarded_input("  Full Name   : ").strip()
    course  = guarded_input("  Course      : ").strip()
    section = guarded_input("  Section     : ").strip()

    if not name or not course or not section:
        print("\n  [!] All fields are required. Student not added.")
        press_enter()
        return

    # Append new student record to the global list
    students.append([student_id, name, course, section])

    print(f"\n  [+] Student '{name}' (ID: {student_id}) enrolled successfully.")
    press_enter()

def view_students():
    """
    Iterate through the `students` list and print a formatted ASCII table.
    """
    print_header("STUDENT LIST  —  All enrolled students")

    if not students:
        print("  No students enrolled yet.")
        press_enter()
        return

    # Table header
    print(f"  {'ID':<12} {'Name':<25} {'Course':<12} {'Section':<8}")
    print("  " + "-" * 61)

    # Iterate and print each student row
    for student in students:
        sid, name, course, section = student
        print(f"  {sid:<12} {name:<25} {course:<12} {section:<8}")

    print("  " + "=" * 61)
    print(f"  Total enrolled: {len(students)} student(s)")
    press_enter()

def select_student_for_recording():
    """
    Prompt for a student ID and return (student, record). A blank score
    record is created on first entry so components can be recorded one at
    a time. Enter 0 to return to the Main Menu.
    """
    while True:
        print_header("RECORD / UPDATE SCORES  —  Select Student")

        student_id = guarded_input(
            "  Enter Student ID (0 to go back): ").strip()

        if student_id == "0":
            return None, None
        if not student_id:
            print("\n  [!] Student ID cannot be empty.")
            press_enter()
            continue

        student = find_student(student_id)
        if not student:
            print(f"\n  [!] Student ID '{student_id}' not found.")
            press_enter()
            continue

        record = get_or_create_score_record(student_id)
        print(f"\n  Student selected: {student[1]} ({student_id})")
        return student, record


def select_module(student=None, record=None,
                  title="SELECT MODULE", back_label="Back"):
    """
    Prompt for a whole-number module from 1 to 10. Enter 0 to go back.

    Only whole-number selections in the range 1–10 are accepted. Decimals,
    signs, words, and out-of-range numbers are rejected and re-prompted.
    """
    while True:
        clear_screen()
        print("=" * 65)
        print(f"  GRADETRACK  |  {title}")
        print("=" * 65)

        if student is not None:
            print(f"  Student : {student[1]}  ({student[0]})")
            print("  Select the module you want to work with.")
            print("-" * 65)

        if record is not None:
            modules = record.get("modules")
            if not isinstance(modules, dict):
                modules = {}
            for module_num in MODULE_NUMBERS:
                module = modules.get(module_num)
                status = module_record_status(module)
                if status == STATUS_COMPLETE:
                    score = compute_module_score(module)
                    detail = f"score {score:5.2f}/70 ({score / 70 * 100:6.2f}%)"
                elif status == STATUS_INCOMPLETE:
                    detail = f"{module_recorded_count(module)}/5 entries recorded"
                elif status == STATUS_INVALID:
                    detail = "invalid stored data"
                else:
                    detail = "no entries yet"
                print(f"   [{module_num:>2}] Module {module_num:<2}  "
                      f"{status_label(status):<11}  {detail}")
        else:
            for module_num in MODULE_NUMBERS:
                print(f"   [{module_num:>2}] Module {module_num}")

        print("-" * 65)
        print(f"   [ 0] {back_label}")
        print("   Select a whole number from 1 to 10.")
        print("=" * 65)

        try:
            choice = safe_input("  Select Module: ").strip()
        except KeyboardInterrupt:
            print()
            if confirm_quit("  Are you sure you want to go back? (yes/no): "):
                return None
            continue

        if choice == "0":
            return None

        if (not choice.isascii() or not choice.isdigit()
                or len(choice) > 2):
            print("\n  [!] Invalid module selection — enter a whole number from 1 to 10.")
            press_enter()
            continue

        module_num = int(choice)
        if module_num in MODULE_NUMBERS:
            return module_num

        print("\n  [!] Module must be from 1 to 10.")
        press_enter()


def show_current_module_values(module):
    """Print the currently stored values for the active module."""
    attendance = module.get("attendance")
    if attendance not in ("P", "A"):
        attendance = "—"
    print(f"  Current : Attendance {attendance}   "
          f"LP1 {fmt_entry_compact(module.get('lp1'))}   "
          f"LP2 {fmt_entry_compact(module.get('lp2'))}")
    print(f"            Reflection {fmt_entry_compact(module.get('reflection'))}   "
          f"Wrap-Up {fmt_entry_compact(module.get('wrap_up'))}")


def show_record_menu(student, module_num, record):
    """Render the component menu while keeping the student and module visible."""
    module = record["modules"][module_num]
    status = module_record_status(module)

    clear_screen()
    print("=" * 65)
    print("       GRADETRACK  —  Record / Update Scores")
    print("=" * 65)
    print(f"  Student : {student[1]}  ({student[0]})")
    print(f"  Module  : Module {module_num}  —  {status_label(status)}")
    print("-" * 65)
    show_current_module_values(module)
    print("-" * 65)
    print(f"  MODULE {module_num} COMPONENTS")
    print("   [A]  Attendance (5%)")
    print("   [B]  Let's Practice (35%)  — LP1 then LP2")
    print("   [C]  Reflection (15%)")
    print("   [D]  Wrap-Up Quiz (15%)")
    print()
    print("  COURSE-WIDE FINAL PROJECT/OUTPUT/TASK (30%)")
    print(f"  (Recorded once per student — NOT stored in Module {module_num}.)")
    print("   [E]  P1 Check-in Grade")
    print("   [F]  P2 Check-in Grade")
    print("   [G]  P3.2 Check-in Grade")
    print("   [H]  Final Output/Presentation Grade")
    print("-" * 65)
    print("   [M]  Change Module")
    print("   [S]  Select Another Student")
    print("   [0]  Back to Main Menu")
    print("   Tip  : CTRL+C asks to confirm — answering 'no' keeps your inputs")
    print("=" * 65)


def show_component_header(student, module_num, title, status=None,
                          course_wide=False):
    """Show the selected student/module context before every score entry."""
    clear_screen()
    print("=" * 65)
    print(f"  GRADETRACK  |  {title}")
    print("=" * 65)
    print(f"  Student : {student[1]}  ({student[0]})")
    if course_wide:
        print("  Scope   : COURSE-WIDE FINAL PROJECT (outside Modules 1–10)")
        print(f"  Module context: Module {module_num} (only context — "
              "project is stored separately)")
    else:
        print(f"  Module  : Module {module_num}  —  {status_label(status)}")
    print("-" * 65)


def record_attendance(student, record, module_num):
    """Record / update Attendance for the selected student and module."""
    module = record["modules"][module_num]
    show_component_header(
        student, module_num,
        f"RECORD ATTENDANCE — MODULE {module_num}",
        module_record_status(module))

    if module["attendance"] is not None:
        print(f"  Current Attendance: {module['attendance']}")
    else:
        print("  Current Attendance: not recorded")

    # Assignment happens only after validation succeeds.
    module["attendance"] = get_validated_attendance()
    refresh_student_results(record)

    print(f"\n  [+] Attendance saved for {student[1]} — Module {module_num}: "
          f"{module['attendance']}")
    press_enter()


def record_lets_practice(student, record, module_num):
    """
    Record / update ONE Let's Practice entry in the selected module.
    LP1 is recorded first, then LP2. When both entries exist, the instructor
    chooses which one to update.
    """
    module = record["modules"][module_num]
    show_component_header(
        student, module_num,
        f"RECORD LET'S PRACTICE — MODULE {module_num}",
        module_record_status(module))

    print(f"  Current  ->  LP1: {fmt_entry(module['lp1'])}  |  "
          f"LP2: {fmt_entry(module['lp2'])}")

    lp1, lp2 = module["lp1"], module["lp2"]

    if lp1 is None:
        entry_key, label = "lp1", "Let's Practice 1"
    elif lp2 is None:
        entry_key, label = "lp2", "Let's Practice 2"
    elif not is_valid_entry(lp1):
        entry_key, label = "lp1", "Let's Practice 1"
    elif not is_valid_entry(lp2):
        entry_key, label = "lp2", "Let's Practice 2"
    else:
        while True:
            which = guarded_input(
                "  Both entries are recorded. Update which one? [1/2]: ").strip()
            if which == "1":
                entry_key, label = "lp1", "Let's Practice 1"
                break
            if which == "2":
                entry_key, label = "lp2", "Let's Practice 2"
                break
            print("  [!] Please enter 1 or 2.")

    print(f"  Recording {label} for Module {module_num}.")
    print("  One entry per selection — choose [B] again to record the other entry.")
    print("  " + "-" * 50)

    new_entry = list(get_score_with_max(label))
    module[entry_key] = new_entry
    refresh_student_results(record)

    print(f"\n  [+] {label} saved for {student[1]} — Module {module_num}.")
    press_enter()


def record_reflection(student, record, module_num):
    """Record / update Reflection for the selected student and module."""
    module = record["modules"][module_num]
    show_component_header(
        student, module_num,
        f"RECORD REFLECTION — MODULE {module_num}",
        module_record_status(module))

    if module["reflection"] is not None:
        print(f"  Current Reflection: {fmt_entry(module['reflection'])}")
    else:
        print("  Current Reflection: not recorded")

    new_entry = list(get_score_with_max("Reflection (15%)"))
    module["reflection"] = new_entry
    refresh_student_results(record)

    print(f"\n  [+] Reflection saved for {student[1]} — Module {module_num}.")
    press_enter()


def record_wrap_up(student, record, module_num):
    """Record / update the Wrap-Up Quiz for the selected student and module."""
    module = record["modules"][module_num]
    show_component_header(
        student, module_num,
        f"RECORD WRAP-UP QUIZ — MODULE {module_num}",
        module_record_status(module))

    if module["wrap_up"] is not None:
        print(f"  Current Wrap-Up Quiz: {fmt_entry(module['wrap_up'])}")
    else:
        print("  Current Wrap-Up Quiz: not recorded")

    new_entry = list(get_score_with_max("Wrap-Up Quiz (15%)"))
    module["wrap_up"] = new_entry
    refresh_student_results(record)

    print(f"\n  [+] Wrap-Up Quiz saved for {student[1]} — Module {module_num}.")
    press_enter()


def record_final_project_part(student, record, module_num, field, label):
    """
    Record / update one part of the course-wide Final Project (30%).
    This value is stored once per student and is never placed in a module.
    """
    project = record["project"]
    show_component_header(
        student, module_num,
        f"RECORD {label.upper()}",
        project_record_status(project),
        course_wide=True)

    print("  This score belongs to the course-wide Final Project (30%).")
    print(f"  It is not stored in Module {module_num} or any other module.")
    print("  " + "-" * 50)

    if project[field] is not None:
        print(f"  Current {label}: {fmt_entry(project[field])}")
    else:
        print(f"  Current {label}: not recorded")

    new_entry = list(get_score_with_max(label))
    project[field] = new_entry
    refresh_student_results(record)

    print(f"\n  [+] {label} saved for {student[1]} (course-wide project).")
    press_enter()


def record_scores():
    """
    Module-aware recording and updating.

    Flow:
      Select Student → Select Module 1–10 → Select Component → Enter Score

    After a save, the student and module stay active. The instructor can
    record another component immediately, change modules, or select another
    student. Returning from an untouched module leaves it UNRECORDED.
    """
    while True:
        student, record = select_student_for_recording()
        if not student:
            return

        while True:
            module_num = select_module(
                student, record,
                title="RECORD / UPDATE SCORES — SELECT MODULE",
                back_label="Back to Student Selection")
            if module_num is None:
                break

            leave_student = False
            while True:
                show_record_menu(student, module_num, record)

                try:
                    choice = safe_input("  Select a component: ").strip().upper()
                except KeyboardInterrupt:
                    print()
                    if confirm_quit(
                            "  Are you sure you want to leave Record Scores? (yes/no): "):
                        return
                    continue

                if choice == "0":
                    return

                if choice == "M":
                    break

                if choice == "S":
                    leave_student = True
                    break

                if choice == "A":
                    run_with_cancel_guard(
                        lambda: record_attendance(student, record, module_num))
                elif choice == "B":
                    run_with_cancel_guard(
                        lambda: record_lets_practice(student, record, module_num))
                elif choice == "C":
                    run_with_cancel_guard(
                        lambda: record_reflection(student, record, module_num))
                elif choice == "D":
                    run_with_cancel_guard(
                        lambda: record_wrap_up(student, record, module_num))
                elif choice == "E":
                    run_with_cancel_guard(
                        lambda: record_final_project_part(
                            student, record, module_num,
                            "p1_checkin", "P1 Check-in Grade"))
                elif choice == "F":
                    run_with_cancel_guard(
                        lambda: record_final_project_part(
                            student, record, module_num,
                            "p2_checkin", "P2 Check-in Grade"))
                elif choice == "G":
                    run_with_cancel_guard(
                        lambda: record_final_project_part(
                            student, record, module_num,
                            "p32_checkin", "P3.2 Check-in Grade"))
                elif choice == "H":
                    run_with_cancel_guard(
                        lambda: record_final_project_part(
                            student, record, module_num,
                            "presentation", "Final Output/Presentation Grade"))
                else:
                    print("\n  [!] Invalid option. Please choose a letter from the menu.")
                    press_enter()

            if leave_student:
                break

def display_module_grade(student, record, module_num):
    """Show the recorded values and weighted contributions for one module."""
    modules = record.get("modules")
    module = modules.get(module_num) if isinstance(modules, dict) else None
    status = module_record_status(module)
    if not isinstance(module, dict):
        module = {}

    clear_screen()
    print("=" * 65)
    print(f"  GRADE COMPUTATION  —  MODULE {module_num} ONLY")
    print("=" * 65)
    print(f"  Student : {student[1]}  ({student[0]})")
    print(f"  Scope   : Module {module_num} only — course-wide project is NOT included")
    print(f"  Status  : {status_label(status)}")
    print("-" * 65)

    attendance = module.get("attendance")
    if attendance in ("P", "A"):
        att_pct = 100.0 if attendance == "P" else 0.0
        att_word = "Present" if attendance == "P" else "Absent"
        print(f"  Attendance (5%)       : {attendance} ({att_word})  "
              f"= {att_pct:>6.2f}%  x 0.05 = {att_pct * 0.05:>5.2f} / 5")
    elif attendance is None:
        print("  Attendance (5%)       : not recorded")
    else:
        print("  Attendance (5%)       : invalid stored value")

    lp1, lp2 = module.get("lp1"), module.get("lp2")
    if is_valid_entry(lp1) and is_valid_entry(lp2):
        p1, p2 = to_pct(lp1), to_pct(lp2)
        lp_pct = (p1 + p2) / 2
        print(f"  Let's Practice (35%)  : LP1 {fmt_entry(lp1)} ({p1:6.2f}%) | "
              f"LP2 {fmt_entry(lp2)} ({p2:6.2f}%)")
        print(f"                          average {lp_pct:6.2f}%  "
              f"x 0.35 = {lp_pct * 0.35:>5.2f} / 35")
    else:
        print(f"  Let's Practice (35%)  : LP1 {fmt_entry(lp1)} | "
              f"LP2 {fmt_entry(lp2)} — both entries required")

    reflection = module.get("reflection")
    if is_valid_entry(reflection):
        refl_pct = to_pct(reflection)
        print(f"  Reflection (15%)      : {fmt_entry(reflection):>12}  "
              f"= {refl_pct:>6.2f}%  x 0.15 = {refl_pct * 0.15:>5.2f} / 15")
    elif reflection is None:
        print("  Reflection (15%)      : not recorded")
    else:
        print("  Reflection (15%)      : invalid stored value")

    wrap_up = module.get("wrap_up")
    if is_valid_entry(wrap_up):
        wq_pct = to_pct(wrap_up)
        print(f"  Wrap-Up Quiz (15%)    : {fmt_entry(wrap_up):>12}  "
              f"= {wq_pct:>6.2f}%  x 0.15 = {wq_pct * 0.15:>5.2f} / 15")
    elif wrap_up is None:
        print("  Wrap-Up Quiz (15%)    : not recorded")
    else:
        print("  Wrap-Up Quiz (15%)    : invalid stored value")

    print("-" * 65)
    score = compute_module_score(module)
    if score is not None:
        pct = (score / 70.0) * 100.0
        print(f"  MODULE SCORE          : {round(score, 2):.2f} / 70  "
              f"({pct:.2f}%)")
        print(f"  REMARK                : {grade_remark(round(pct, 2))}")
    else:
        print(f"  MODULE SCORE          : N/A — {status_label(status)}")
        if status == STATUS_INCOMPLETE:
            print(f"  Recorded entries      : {module_recorded_count(module)}/5")
            print("  No module grade is produced until all five entries are complete.")
        elif status == STATUS_INVALID:
            print("  Invalid stored data — no module grade was produced.")
        else:
            print("  No entries have been recorded for this module.")
    print("=" * 65)
    press_enter()


def display_overall_grade(student, record):
    """Show the ten module results and the confirmed overall calculation."""
    status = overall_record_status(record)
    complete_modules, project_state = overall_progress(record)

    clear_screen()
    print("=" * 65)
    print("  GRADE COMPUTATION  —  OVERALL RESULT")
    print("=" * 65)
    print(f"  Student : {student[1]}  ({student[0]})")
    print("  Scope   : OVERALL — Modules 1–10 plus course-wide Final Project")
    print(f"  Status  : {status_label(status)}")
    print("-" * 65)

    print("  MODULE RESULTS (all ten modules are equally weighted)")
    print(f"  {'Mod':<4} {'Status':<12} {'Score':>10} {'Percent':>10}")
    modules = record.get("modules")
    if not isinstance(modules, dict):
        modules = {}
    for module_num in MODULE_NUMBERS:
        module = modules.get(module_num)
        module_state = module_record_status(module)
        score = compute_module_score(module)
        if score is not None:
            pct = (score / 70.0) * 100.0
            print(f"  {module_num:<4} {status_label(module_state):<12} "
                  f"{score:>7.2f}/70 {pct:>9.2f}%")
        else:
            print(f"  {module_num:<4} {status_label(module_state):<12} "
                  f"{'—':>10} {'—':>10}")

    print()
    print("  COURSE-WIDE FINAL PROJECT/OUTPUT/TASK (30%)")
    project = record.get("project")
    project_display_keys = (
        ("p1_checkin", "P1 Check-in Grade"),
        ("p2_checkin", "P2 Check-in Grade"),
        ("p32_checkin", "P3.2 Check-in Grade"),
        ("presentation", "Final Output/Presentation"),
    )
    for key, label in project_display_keys:
        entry = project.get(key) if isinstance(project, dict) else None
        if is_valid_entry(entry):
            print(f"    {label:<28}: {fmt_entry(entry):>12}  "
                  f"= {to_pct(entry):>6.2f}%")
        elif entry is None:
            print(f"    {label:<28}: not recorded")
        else:
            print(f"    {label:<28}: invalid stored value")

    if isinstance(project, dict):
        checkin_avg = compute_checkin_avg(project)
        if checkin_avg is not None:
            print(f"    Check-in Average            = {checkin_avg:>6.2f}%  "
                  f"x 0.65 = {checkin_avg * 0.65:>5.2f}%")
        presentation = project.get("presentation")
        if is_valid_entry(presentation):
            print(f"    Presentation                = {to_pct(presentation):>6.2f}%  "
                  f"x 0.35 = {to_pct(presentation) * 0.35:>5.2f}%")

    project_pct = None
    if isinstance(project, dict):
        project_pct = compute_project_overall(project)
    if project_pct is not None:
        print(f"    Project Overall             = {project_pct:>6.2f}%")
        print(f"    Project Contribution        = {project_pct:>6.2f}%  "
              f"x 0.30 = {project_pct * 0.30:>5.2f} / 30")
    else:
        print(f"    Project Status              : "
              f"{status_label(project_record_status(project))}")

    print("-" * 65)
    breakdown = compute_overall_breakdown(record)
    if breakdown is not None:
        print("  TEN-MODULE CATEGORY AVERAGES (each weight applied once)")
        print(f"    Attendance                  : "
              f"{breakdown['att_avg']:>6.2f}%  x 0.05 = "
              f"{breakdown['att_points']:>5.2f}")
        print(f"    Let's Practice              : "
              f"{breakdown['lp_avg']:>6.2f}%  x 0.35 = "
              f"{breakdown['lp_points']:>5.2f}")
        print(f"    Reflection                  : "
              f"{breakdown['refl_avg']:>6.2f}%  x 0.15 = "
              f"{breakdown['refl_points']:>5.2f}")
        print(f"    Wrap-Up Quiz                : "
              f"{breakdown['wq_avg']:>6.2f}%  x 0.15 = "
              f"{breakdown['wq_points']:>5.2f}")
        print(f"    MODULE SUBTOTAL             : "
              f"{breakdown['module_subtotal']:>6.2f} / 70")
        print(f"    PROJECT (30%)               : "
              f"{breakdown['project_points']:>6.2f} / 30")
        print(f"  FINAL GRADE                   : "
              f"{breakdown['final_grade']:>6.2f}  —  "
              f"{grade_remark(breakdown['final_grade'])}")
    else:
        print("  OVERALL GRADE                 : N/A")
        print(f"  Modules complete              : {complete_modules}/10")
        print(f"  Project status                : {status_label(project_state)}")
        print("  No overall grade is produced until all ten modules and the")
        print("  course-wide Final Project are complete.")
    print("=" * 65)
    press_enter()


def compute_final_grade():
    """
    Find a student, let the instructor choose a module-only or overall
    computation, and display the recorded values and weighted contributions.
    """
    print_header("COMPUTE GRADE  —  Selected module or overall result")

    student_id = guarded_input("  Enter Student ID (0 to go back): ").strip()
    if student_id == "0":
        return

    student = find_student(student_id)
    if not student:
        print(f"\n  [!] Student ID '{student_id}' not found.")
        press_enter()
        return

    record = find_score_record(student_id)
    if not record:
        print(f"\n  [!] No scores found for '{student[1]}'. Record scores first.")
        press_enter()
        return

    refresh_student_results(record)

    while True:
        complete_modules, project_state = overall_progress(record)
        status = overall_record_status(record)

        clear_screen()
        print("=" * 65)
        print("       GRADETRACK  —  Compute Grade")
        print("=" * 65)
        print(f"  Student : {student[1]}  ({student_id})")
        print(f"  Overall : {status_label(status)}  "
              f"({complete_modules}/10 modules complete; "
              f"project {status_label(project_state).lower()})")
        print("-" * 65)
        print("   [1]  Compute a selected module (Module 1–10)")
        print("   [2]  Compute overall (all 10 modules + course project)")
        print("   [0]  Back to Main Menu")
        print("=" * 65)

        try:
            choice = safe_input("  Select an option: ").strip()
        except KeyboardInterrupt:
            print()
            if confirm_quit("  Are you sure you want to leave Compute Grade? (yes/no): "):
                return
            continue

        if choice == "0":
            return
        if choice == "1":
            module_num = select_module(
                student, record,
                title="COMPUTE GRADE — SELECT MODULE",
                back_label="Back to Compute Menu")
            if module_num is None:
                continue
            display_module_grade(student, record, module_num)
        elif choice == "2":
            display_overall_grade(student, record)
        else:
            print("\n  [!] Invalid option. Please choose 1, 2, or 0.")
            press_enter()

def search_student():
    """
    Search for a student by ID and display the profile, every module's
    recorded components and completion status, the course-wide project,
    and the overall result when all requirements are complete.
    """
    print_header("SEARCH STUDENT  —  Look up a student record")

    student_id = guarded_input("  Enter Student ID to search (0 to go back): ").strip()
    if student_id == "0":
        return

    student = find_student(student_id)
    if not student:
        print(f"\n  [!] No student found with ID '{student_id}'.")
        press_enter()
        return

    sid, name, course, section = student

    print(f"\n  STUDENT PROFILE")
    print("  " + "-" * 45)
    print(f"  Student ID : {sid}")
    print(f"  Full Name  : {name}")
    print(f"  Course     : {course}")
    print(f"  Section    : {section}")

    record = find_score_record(student_id)
    if not record:
        print("\n  [i] No score record found for this student.")
        press_enter()
        return

    refresh_student_results(record)

    print("\n  MODULE SCORE SUMMARY")
    print("  (module results exclude the course-wide Final Project)")
    print(f"  {'Mod':<4} {'Status':<12} {'Att':<7} {'LP1':<11} {'LP2':<11} "
          f"{'Refl':<11} {'Quiz':<11} {'Score':>12}")
    print("  " + "-" * 96)

    modules = record.get("modules")
    if not isinstance(modules, dict):
        modules = {}
    for module_num in MODULE_NUMBERS:
        module = modules.get(module_num)
        status = module_record_status(module)
        module_data = module if isinstance(module, dict) else {}

        attendance = module_data.get("attendance")
        if attendance in ("P", "A"):
            att_display = attendance
        elif attendance is None:
            att_display = "—"
        else:
            att_display = "invalid"

        score = compute_module_score(module)
        score_display = f"{score:.2f}/70" if score is not None else "—"

        print(f"  {module_num:<4} {status_label(status):<12} {att_display:<7} "
              f"{fmt_entry_compact(module_data.get('lp1')):<11} "
              f"{fmt_entry_compact(module_data.get('lp2')):<11} "
              f"{fmt_entry_compact(module_data.get('reflection')):<11} "
              f"{fmt_entry_compact(module_data.get('wrap_up')):<11} "
              f"{score_display:>12}")

    project = record.get("project")
    project_state = project_record_status(project)
    print("\n  COURSE-WIDE FINAL PROJECT/OUTPUT/TASK (30%)")
    print("  Recorded once per student — outside Modules 1–10.")
    print("  " + "-" * 55)
    if isinstance(project, dict):
        print(f"    P1 Check-in Grade    : {fmt_entry(project.get('p1_checkin'))}")
        print(f"    P2 Check-in Grade    : {fmt_entry(project.get('p2_checkin'))}")
        print(f"    P3.2 Check-in Grade  : {fmt_entry(project.get('p32_checkin'))}")
        print(f"    Output/Presentation  : {fmt_entry(project.get('presentation'))}")
        checkin_avg = compute_checkin_avg(project)
        if checkin_avg is not None:
            print(f"    Check-in Average     : {checkin_avg:.2f}%")
        project_pct = compute_project_overall(project)
        if project_pct is not None:
            print(f"    Project Overall      : {project_pct:.2f}%")
    print(f"    Project Status       : {status_label(project_state)}")

    complete_modules, _ = overall_progress(record)
    overall_status = overall_record_status(record)
    overall_grade = compute_overall_grade(record)

    print("\n  OVERALL RESULT")
    print("  " + "-" * 55)
    print(f"    Modules complete     : {complete_modules}/10")
    if overall_grade is not None:
        print(f"    Overall Grade        : {overall_grade:.2f}  —  "
              f"{grade_remark(overall_grade)}")
    else:
        print(f"    Overall Grade        : N/A  —  {status_label(overall_status)}")
        print("    All ten modules and the course-wide project are required.")
    print("  " + "=" * 55)

    press_enter()

def report_module(module_num):
    """
    Print a class report for ONE selected module. The report is explicitly
    labelled as module-only; the course-wide project is not included.
    Only complete, valid module results are included in the class average.
    """
    print_header(f"GRADE REPORT  —  MODULE {module_num} ONLY")
    print(f"  Scope : Module {module_num} only — course-wide Final Project is NOT included.")
    print("  " + "=" * 65)

    if not students:
        print("  No students enrolled.")
        press_enter()
        return

    print(f"  {'ID':<12} {'Name':<20} {'Course':<8} {'Sec':<5} "
          f"{'Score':>10} {'Pct':>8}  Status / Remark")
    print("  " + "-" * 90)

    counts = {
        STATUS_COMPLETE:   0,
        STATUS_INCOMPLETE: 0,
        STATUS_UNRECORDED: 0,
        STATUS_INVALID:    0,
    }
    eligible_scores = []

    for student in students:
        sid, name, course, section = student
        record = find_score_record(sid)

        if record is None:
            status = STATUS_UNRECORDED
            module = None
        else:
            refresh_student_results(record)
            modules = record.get("modules")
            module = modules.get(module_num) if isinstance(modules, dict) else None
            status = module_record_status(module)

        if status == STATUS_COMPLETE:
            score = compute_module_score(module)
            if score is None:
                status = STATUS_INVALID
            else:
                counts[STATUS_COMPLETE] += 1
                eligible_scores.append(score)
                pct = (score / 70.0) * 100.0
                score_text = f"{score:.2f}/70"
                pct_text = f"{pct:.2f}%"
                detail = f"Complete — {grade_remark(round(pct, 2))}"
                print(f"  {sid:<12} {name:<20} {course:<8} {section:<5} "
                      f"{score_text:>10} {pct_text:>8}  {detail}")
                continue

        counts[status] += 1
        if status == STATUS_INCOMPLETE:
            detail = (f"Incomplete ({module_recorded_count(module)}/5 entries) "
                      "— excluded from average")
        elif status == STATUS_INVALID:
            detail = "Invalid record — excluded from average"
        else:
            detail = "Unrecorded — no module entries"
        print(f"  {sid:<12} {name:<20} {course:<8} {section:<5} "
              f"{'—':>10} {'—':>8}  {detail}")

    print("  " + "=" * 65)
    print(f"  Total students : {len(students)}")
    print(f"  Complete       : {counts[STATUS_COMPLETE]}")
    print(f"  Incomplete     : {counts[STATUS_INCOMPLETE]}")
    print(f"  Unrecorded     : {counts[STATUS_UNRECORDED]}")
    print(f"  Invalid        : {counts[STATUS_INVALID]}")

    if eligible_scores:
        avg_score = sum(eligible_scores) / len(eligible_scores)
        avg_pct = (avg_score / 70.0) * 100.0
        print(f"  Class Average  : {avg_score:.2f}/70 ({avg_pct:.2f}%)  —  "
              f"{grade_remark(round(avg_pct, 2))}")
        print(f"  Eligible       : {len(eligible_scores)} complete module result(s)")
    else:
        print(f"  Class Average  : N/A — no complete Module {module_num} results")
        print("  Eligible       : 0")
    print("  " + "=" * 65)
    press_enter()


def report_overall():
    """
    Print a class report for the overall result: all ten modules plus the
    course-wide Final Project. Only complete, valid overall results are
    included in the class average.
    """
    print_header("GRADE REPORT  —  OVERALL RESULT")
    print("  Scope : OVERALL — all ten modules plus the course-wide Final Project.")
    print("  " + "=" * 65)

    if not students:
        print("  No students enrolled.")
        press_enter()
        return

    print(f"  {'ID':<12} {'Name':<20} {'Course':<8} {'Sec':<5} "
          f"{'Grade':>7}  Status / Remark")
    print("  " + "-" * 85)

    counts = {
        STATUS_COMPLETE:   0,
        STATUS_INCOMPLETE: 0,
        STATUS_UNRECORDED: 0,
        STATUS_INVALID:    0,
    }
    eligible_grades = []

    for student in students:
        sid, name, course, section = student
        record = find_score_record(sid)

        if record is None:
            status = STATUS_UNRECORDED
            detail = "Unrecorded — no scores"
            grade_text = "—"
        else:
            refresh_student_results(record)
            status = overall_record_status(record)

            if status == STATUS_COMPLETE:
                grade = compute_overall_grade(record)
                if grade is None:
                    status = STATUS_INVALID
                    detail = "Invalid record — excluded from average"
                    grade_text = "—"
                else:
                    eligible_grades.append(grade)
                    grade_text = f"{grade:.2f}"
                    detail = f"Complete — {grade_remark(grade)}"
            elif status == STATUS_INCOMPLETE:
                complete_modules, project_state = overall_progress(record)
                detail = (f"Incomplete ({complete_modules}/10 modules; "
                          f"project {status_label(project_state).lower()}) "
                          "— excluded from average")
                grade_text = "—"
            elif status == STATUS_INVALID:
                detail = "Invalid record — excluded from average"
                grade_text = "—"
            else:
                detail = "Unrecorded — no scores"
                grade_text = "—"

        counts[status] += 1
        print(f"  {sid:<12} {name:<20} {course:<8} {section:<5} "
              f"{grade_text:>7}  {detail}")

    print("  " + "=" * 65)
    print(f"  Total students : {len(students)}")
    print(f"  Complete       : {counts[STATUS_COMPLETE]}")
    print(f"  Incomplete     : {counts[STATUS_INCOMPLETE]}")
    print(f"  Unrecorded     : {counts[STATUS_UNRECORDED]}")
    print(f"  Invalid        : {counts[STATUS_INVALID]}")

    if eligible_grades:
        class_avg = round(sum(eligible_grades) / len(eligible_grades), 2)
        print(f"  Class Average  : {class_avg:.2f}  —  {grade_remark(class_avg)}")
        print(f"  Eligible       : {len(eligible_grades)} complete overall result(s)")
    else:
        print("  Class Average  : N/A — no complete overall results")
        print("  Eligible       : 0")
    print("  " + "=" * 65)
    press_enter()


def generate_report():
    """
    Choose between a selected-module report and an overall report. The
    scope is stated in the report title so the two results cannot be
    confused.
    """
    while True:
        print_header("GRADE REPORT  —  Choose report scope")
        print("   [1]  Module report (select Module 1–10)")
        print("   [2]  Overall report (all 10 modules + course project)")
        print("   [0]  Back to Main Menu")
        print("=" * 65)

        try:
            choice = safe_input("  Select an option: ").strip()
        except KeyboardInterrupt:
            print()
            if confirm_quit("  Are you sure you want to leave Grade Reports? (yes/no): "):
                return
            continue

        if choice == "0":
            return
        if choice == "1":
            module_num = select_module(
                title="GRADE REPORT — SELECT MODULE",
                back_label="Back to Report Menu")
            if module_num is not None:
                report_module(module_num)
        elif choice == "2":
            report_overall()
        else:
            print("\n  [!] Invalid option. Please choose 1, 2, or 0.")
            press_enter()

def show_main_menu():
    """
    Render the main navigation menu. Locked options are visually indicated
    when the user is not authenticated.
    """
    clear_screen()
    lock = "[X]" if not is_authenticated else "   "

    print("=" * 65)
    print("       GRADETRACK  —  ITE 260 Grade Management System")
    print("=" * 65)

    if is_authenticated:
        print("  Status : ADMIN")
    else:
        print("  Status : NOT LOGGED IN  — Please select Option [1] to Login")

    print("-" * 65)
    print("   [1]  Login")
    print(f"{lock} [2]  Add Student")
    print(f"{lock} [3]  View Student List")
    print(f"{lock} [4]  Record / Update Scores")
    print(f"{lock} [5]  Compute Final Grade")
    print(f"{lock} [6]  Search Student Record")
    print(f"{lock} [7]  Generate Grade Report")
    print("-" * 65)
    print("   [0]  Exit System   |   CTRL+C also exits (with confirmation)")
    print("=" * 65)

def main():
    """
    Entry point. Runs a continuous while True loop driving the main menu.
    Routes user choices to the appropriate feature functions.

    Invalid menu input is re-prompted without crashing. If the input
    stream ends anywhere in the program, EndOfInput propagates to the
    top level, which ends the application cleanly.
    """
    while True:
        show_main_menu()

        try:
            choice = int(safe_input("  Select an option: ").strip())
        except KeyboardInterrupt:
            print()
            if confirm_quit("  Are you sure you want to exit the system? (yes/no): "):
                clear_screen()
                print("=" * 65)
                print("  Thank you for using GradeTrack. Goodbye!")
                print("=" * 65)
                break
            continue
        except ValueError:
            print("\n  [!] Invalid input — please enter a menu number.")
            press_enter()
            continue

        if choice == 0:
            clear_screen()
            print("=" * 65)
            print("  Thank you for using GradeTrack. Goodbye!")
            print("=" * 65)
            break

        if choice == 1:
            run_with_cancel_guard(login)

        elif not is_authenticated:
            print("\n  [!] Access denied. Please login first (Option 1).")
            press_enter()

        elif choice == 2:
            run_with_cancel_guard(add_student)

        elif choice == 3:
            run_with_cancel_guard(view_students)

        elif choice == 4:
            run_with_cancel_guard(record_scores)

        elif choice == 5:
            run_with_cancel_guard(compute_final_grade)

        elif choice == 6:
            run_with_cancel_guard(search_student)

        elif choice == 7:
            run_with_cancel_guard(generate_report)

        else:
            print("\n  [!] Invalid option. Please choose a number from the menu.")
            press_enter()


main()