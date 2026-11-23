"""
Import script for HDBF - Document Remediation project into Dev environment.
Uses strictly: backend/scripts/Class9_Mathematics_Book_Remediation_Project_Plan.xlsx
Owner: Anusha
Assignees: Anusha, Dharanipathy
"""
import sys
import datetime
import openpyxl
import requests

DEV_BASE = "https://dev-mis.winvinaya.com"
DEV_API_BASE = f"{DEV_BASE}/api/v1"
EXCEL_PATH = r"c:\External-projects\WinVinaya\wvismis\backend\scripts\Class9_Mathematics_Book_Remediation_Project_Plan.xlsx"

def main():
    print("=" * 70)
    print("IMPORTING: HDBF - Document Remediation Project into Dev")
    print("=" * 70)

    # 1. Login
    print("\n[1/6] Authenticating with Dev API...")
    login_payload = {
        "identifier": "dharanidaran.a@winvinaya.com",
        "password": "Testpass@123",
    }
    login_res = requests.post(f"{DEV_API_BASE}/auth/login", json=login_payload, timeout=15)
    if login_res.status_code != 200:
        print(f"Login failed: {login_res.status_code} {login_res.text}")
        sys.exit(1)
    
    token = login_res.json().get("access_token")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    print("✓ Successfully authenticated!")

    # 2. Get Users
    print("\n[2/6] Resolving users (Anusha, Dharanipathy)...")
    users_res = requests.get(f"{DEV_API_BASE}/users", headers=headers, timeout=15)
    data = users_res.json()
    users = data.get("items", data) if isinstance(data, dict) else data

    anusha_id = None
    dharanipathy_id = None
    for u in users:
        uname = (u.get("username") or "").lower()
        fname = (u.get("first_name") or "").lower()
        email = (u.get("email") or "").lower()
        if "anusha" in uname or "anusha" in fname or "anusha" in email:
            anusha_id = u["id"]
        if "dharanipathy" in uname or "dharanipathy" in fname or "dharanipathy" in email:
            dharanipathy_id = u["id"]

    print(f"✓ Anusha ID: {anusha_id}")
    print(f"✓ Dharanipathy ID: {dharanipathy_id}")

    if not anusha_id:
        print("ERROR: Could not find user Anusha in Dev environment.")
        sys.exit(1)

    # 3. Check or Create Project
    project_name = "HDBF - Document Remediation"
    print(f"\n[3/6] Checking if project '{project_name}' exists...")
    projects_res = requests.get(f"{DEV_API_BASE}/projects", headers=headers, timeout=15)
    projects_data = projects_res.json()
    projects = projects_data.get("items", projects_data) if isinstance(projects_data, dict) else projects_data

    existing_project = None
    for p in projects:
        if p.get("name", "").strip().lower() == project_name.lower():
            existing_project = p
            break

    if existing_project:
        project_public_id = existing_project["public_id"]
        print(f"✓ Found existing project: {project_public_id}")
    else:
        print(f"Creating new project: '{project_name}'...")
        scope_description = (
            "Class 9 Mathematics Book Remediation into accessible EPUB format with MathML, "
            "MathJax rendering in Thorium Reader, and screen-reader accessibility.\n\n"
            "Deliverables & Scope:\n"
            "1. Output in accessible EPUB format.\n"
            "2. All equations, fractions, and math symbols tagged using MathML.\n"
            "3. Proper rendering in Thorium Reader & MathJax.\n"
            "4. Content fidelity matching textbook numbers, formulas, and units.\n"
            "5. Structured headings and working Table of Contents.\n"
            "6. Print edition page-number parity.\n"
            "7. Meaningful alternative text on all diagrams and figures.\n"
            "8. Accessible table structures and language tagging (Tamil and English)."
        )

        create_payload = {
            "name": project_name,
            "description": scope_description,
            "owner_id": anusha_id,
            "status": "in_progress",
            "start_date": "2026-11-04",
            "end_date": None,
            "currency": "INR",
            "phase": "Remediation",
            "tags": ["HDBF", "Document Remediation", "EPUB", "Mathematics", "Accessibility"],
        }
        create_res = requests.post(f"{DEV_API_BASE}/projects", json=create_payload, headers=headers, timeout=15)
        if create_res.status_code not in (200, 201):
            print(f"Error creating project: {create_res.status_code} {create_res.text}")
            sys.exit(1)
        created_p = create_res.json()
        project_public_id = created_p["public_id"]
        print(f"✓ Project created successfully! Public ID: {project_public_id}")

    # 4. Fetch Task Statuses for this Project
    print(f"\n[4/6] Fetching task statuses for project {project_public_id}...")
    statuses_res = requests.get(f"{DEV_API_BASE}/projects/{project_public_id}/task-statuses", headers=headers, timeout=15)
    statuses = statuses_res.json() if statuses_res.status_code == 200 else []

    status_map = {}
    done_status_id = None
    initial_status_id = None
    for s in statuses:
        name = s["name"].lower()
        status_map[name] = s["id"]
        if "complete" in name:
            done_status_id = s["id"]
        if s.get("is_initial_status") or "plan" in name or "todo" in name:
            initial_status_id = s["id"]

    if not done_status_id and statuses:
        done_status_id = statuses[-1]["id"]
    if not initial_status_id and statuses:
        initial_status_id = statuses[0]["id"]

    print(f"✓ Resolved Statuses: Done/Completed ID={done_status_id}, Initial/Todo ID={initial_status_id}")

    # 5. Read Excel Rows
    print(f"\n[5/6] Reading tasks strictly from: {EXCEL_PATH}...")
    wb = openpyxl.load_workbook(EXCEL_PATH)
    sheet = wb["Project Plan"]

    tasks_to_create = []
    # Row 1 is header: ['Task ID', 'Task Description', 'Owner', 'Status', 'Hours Spent', 'Start Date', 'End Date ', 'Actual End Date ', 'Remarks']
    for r in range(2, sheet.max_row + 1):
        task_id = sheet.cell(r, 1).value
        desc = sheet.cell(r, 2).value
        owner = sheet.cell(r, 3).value
        status_str = sheet.cell(r, 4).value
        hours_spent = sheet.cell(r, 5).value
        start_dt = sheet.cell(r, 6).value
        end_dt = sheet.cell(r, 7).value
        actual_end_dt = sheet.cell(r, 8).value
        remarks = sheet.cell(r, 9).value

        if not desc:
            continue

        # Keep dates exactly as in excel (None if not provided)
        start_str = start_dt.strftime("%Y-%m-%d") if isinstance(start_dt, (datetime.date, datetime.datetime)) else None
        end_str = end_dt.strftime("%Y-%m-%d") if isinstance(end_dt, (datetime.date, datetime.datetime)) else None
        actual_end_str = actual_end_dt.strftime("%Y-%m-%d") if isinstance(actual_end_dt, (datetime.date, datetime.datetime)) else None

        owner_name = str(owner).strip().lower() if owner else "anusha"
        if "dharani" in owner_name:
            assignee_id = dharanipathy_id
        else:
            assignee_id = anusha_id

        is_completed = bool(status_str and "complete" in str(status_str).lower())
        selected_status_id = done_status_id if is_completed else initial_status_id

        full_desc = []
        if remarks:
            full_desc.append(f"**Remarks:** {remarks}")
        if actual_end_str:
            full_desc.append(f"**Actual Completion Date:** {actual_end_str}")

        hours_val = float(hours_spent) if hours_spent is not None else None

        tasks_to_create.append({
            "task_id": task_id,
            "title": str(desc).strip(),
            "description": "\n\n".join(full_desc) if full_desc else None,
            "assignee_id": assignee_id,
            "status_id": selected_status_id,
            "start_date": start_str,
            "due_date": end_str,
            "estimated_hours": hours_val if not is_completed else None,
            "actual_hours": hours_val if is_completed else None,
            "priority": "high" if is_completed else "medium",
            "is_subtask": task_id is None,
        })

    print(f"✓ Parsed {len(tasks_to_create)} tasks from Excel!")

    # 6. Check existing tasks to avoid duplication
    existing_tasks_res = requests.get(f"{DEV_API_BASE}/projects/{project_public_id}/tasks", headers=headers, timeout=15)
    existing_tasks = existing_tasks_res.json() if existing_tasks_res.status_code == 200 else []
    if isinstance(existing_tasks, dict):
        existing_tasks = existing_tasks.get("items", [])

    if len(existing_tasks) >= len(tasks_to_create):
        print(f"Tasks already exist in project ({len(existing_tasks)} tasks found). Skipping re-creation.")
        return

    # Create Tasks
    print("\n[6/6] Creating tasks in dev environment...")
    parent_task_id = None
    created_count = 0

    for idx, t in enumerate(tasks_to_create, start=1):
        payload = {
            "title": t["title"],
            "description": t["description"],
            "assignee_id": t["assignee_id"],
            "status_id": t["status_id"],
            "start_date": t["start_date"],
            "due_date": t["due_date"],
            "estimated_hours": t["estimated_hours"],
            "actual_hours": t["actual_hours"],
            "priority": t["priority"],
            "order": idx,
        }

        assignee_name = "Dharanipathy" if t["assignee_id"] == dharanipathy_id else "Anusha"
        status_label = "Completed" if t["status_id"] == done_status_id else "Planning"

        if t["is_subtask"] and parent_task_id:
            # Create subtask under parent
            res = requests.post(
                f"{DEV_API_BASE}/project-tasks/{parent_task_id}/subtasks",
                json=payload,
                headers=headers,
                timeout=15,
            )
            sub_label = " (Subtask)"
        else:
            # Create top-level task
            res = requests.post(
                f"{DEV_API_BASE}/projects/{project_public_id}/tasks",
                json=payload,
                headers=headers,
                timeout=15,
            )
            sub_label = ""
            if res.status_code in (200, 201):
                parent_task_id = res.json().get("public_id")

        if res.status_code in (200, 201):
            created_count += 1
            date_info = f"{t['start_date']} to {t['due_date']}" if t['start_date'] else "No dates"
            print(f"  [{created_count:02d}/{len(tasks_to_create)}] Created{sub_label}: '{t['title'][:40]}...' | {assignee_name} | [{status_label}] | {date_info}")
        else:
            print(f"  [!] Failed to create task '{t['title'][:30]}': {res.status_code} {res.text}")

    # Fetch final summary
    final_p_res = requests.get(f"{DEV_API_BASE}/projects/{project_public_id}", headers=headers, timeout=15)
    final_p = final_p_res.json() if final_p_res.status_code == 200 else {}

    print("\n" + "=" * 70)
    print("SUCCESS: HDBF - Document Remediation imported successfully into Dev!")
    print(f"Project Name: {project_name}")
    print(f"Project URL: https://dev-mis.winvinaya.com/org/cc05be2e-e443-4e71-aa30-6895e11fe2e7/projects/{project_public_id}")
    print(f"Owner: Anusha (ID: {anusha_id})")
    print(f"Tasks: {final_p.get('completed_task_count', 0)} completed / {final_p.get('task_count', created_count)} total")
    print("=" * 70)

if __name__ == "__main__":
    main()
