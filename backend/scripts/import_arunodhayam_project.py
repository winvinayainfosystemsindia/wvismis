"""
Imports the Arunodhayam NGO Project Plan from Excel directly into the Dev Environment (https://dev-mis.winvinaya.com).
- Sets Aravindan as the Project Owner
- Sets Start Date: 2026-11-03 and End Date: 2026-11-30
- Maps tasks to Aravindan and Divya
- Sets start/end dates, estimated/actual hours, remarks, SPOC, and statuses (Completed vs Todo)
"""
import os
import sys
import datetime
import openpyxl
import requests

DEV_API_BASE = "https://dev-mis.winvinaya.com/api/v1"
ADMIN_USER = "dharanidaran.a@winvinaya.com"
ADMIN_PASS = "Testpass@123"
EXCEL_PATH = os.path.join(os.path.dirname(__file__), "Arunodhayam_NGO_Project_Plan.xlsx")


def main():
    print("=" * 70)
    print("IMPORTING ARUNODHAYAM NGO PROJECT PLAN TO DEV ENVIRONMENT")
    print(f"Target API: {DEV_API_BASE}")
    print(f"Excel File: {EXCEL_PATH}")
    print("=" * 70)

    # 1. Authenticate with dev backend
    print("\n[1/6] Authenticating as Super Admin...")
    login_res = requests.post(
        f"{DEV_API_BASE}/auth/login",
        json={"identifier": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15,
    )
    if login_res.status_code != 200:
        print(f"Error: Login failed with status {login_res.status_code}: {login_res.text}")
        sys.exit(1)

    token = login_res.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    print("✓ Successfully authenticated!")

    # 2. Get Users in Organization
    print("\n[2/6] Fetching organization users...")
    users_res = requests.get(f"{DEV_API_BASE}/users", headers=headers, timeout=15)
    if users_res.status_code != 200:
        print(f"Error fetching users: {users_res.status_code} {users_res.text}")
        sys.exit(1)

    users_list = users_res.json()
    if isinstance(users_list, dict):
        users_list = users_list.get("items", [])

    user_map = {}
    for u in users_list:
        name_lower = (u.get("full_name") or u.get("username") or "").lower()
        user_map[name_lower] = u["id"]
        user_map[u.get("username", "").lower()] = u["id"]
        user_map[u.get("email", "").lower()] = u["id"]
        print(f"  User found: {u.get('full_name')} ({u.get('email')}) -> ID {u['id']}")

    aravindan_id = user_map.get("aravindan") or user_map.get("aravindan.ganesamoorthy@winvinaya.com")
    divya_id = user_map.get("divya") or user_map.get("divya.ck@winvinaya.com")

    if not aravindan_id:
        print("Warning: Aravindan user not found in user map, finding by substring...")
        for k, v in user_map.items():
            if "aravind" in k:
                aravindan_id = v
                break

    if not divya_id:
        print("Warning: Divya user not found in user map, finding by substring...")
        for k, v in user_map.items():
            if "divya" in k:
                divya_id = v
                break

    print(f"\n✓ Resolved Assignees: Aravindan ID={aravindan_id}, Divya ID={divya_id}")

    # 3. Create or Find Project
    project_name = "Arunodhayam NGO - Phase 1"
    print(f"\n[3/6] Checking for existing project '{project_name}'...")
    list_res = requests.get(f"{DEV_API_BASE}/projects", headers=headers, timeout=15)
    existing_project = None
    if list_res.status_code == 200:
        p_data = list_res.json()
        projects = p_data.get("items", []) if isinstance(p_data, dict) else p_data
        for p in projects:
            if "arunodhayam" in p["name"].lower():
                existing_project = p
                print(f"  Found existing project: {p['name']} (public_id: {p['public_id']})")
                break

    if existing_project:
        project_public_id = existing_project["public_id"]
        print(f"✓ Using existing project: {project_public_id}")
    else:
        print("  Creating project in dev environment...")
        create_payload = {
            "name": project_name,
            "description": "Phase 1: Data structure, data entry process, Power BI Education and Therapy reports.",
            "owner_id": aravindan_id,
            "status": "in_progress",
            "start_date": "2026-11-03",
            "end_date": "2026-11-30",
            "currency": "INR",
            "phase": "Phase 1",
            "tags": ["NGO", "PowerBI", "Arunodhayam", "Education", "Therapy"],
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
        if s.get("is_initial_status") or "plan" in name:
            initial_status_id = s["id"]

    if not done_status_id and statuses:
        done_status_id = statuses[-1]["id"]
    if not initial_status_id and statuses:
        initial_status_id = statuses[0]["id"]

    print(f"✓ Resolved Statuses: Done/Completed ID={done_status_id}, Initial/Todo ID={initial_status_id}")

    # 5. Read Excel Rows
    print(f"\n[5/6] Reading tasks from Excel: {EXCEL_PATH}...")
    wb = openpyxl.load_workbook(EXCEL_PATH)
    sheet = wb["Project Plan"]

    tasks_to_create = []
    # Row 1 is header
    for r in range(2, sheet.max_row + 1):
        task_id = sheet.cell(r, 1).value
        desc = sheet.cell(r, 2).value
        owner = sheet.cell(r, 3).value
        spoc = sheet.cell(r, 4).value
        status_str = sheet.cell(r, 5).value
        hours_spent = sheet.cell(r, 6).value
        start_dt = sheet.cell(r, 7).value
        end_dt = sheet.cell(r, 8).value
        actual_end_dt = sheet.cell(r, 9).value
        remarks = sheet.cell(r, 10).value

        if not desc:
            continue

        start_str = start_dt.strftime("%Y-%m-%d") if isinstance(start_dt, datetime.date) else "2026-11-03"
        end_str = end_dt.strftime("%Y-%m-%d") if isinstance(end_dt, datetime.date) else start_str
        actual_end_str = actual_end_dt.strftime("%Y-%m-%d") if isinstance(actual_end_dt, datetime.date) else None

        owner_name = str(owner).strip().lower() if owner else "aravindan"
        assignee_id = aravindan_id if "aravind" in owner_name else divya_id

        is_completed = "complete" in str(status_str).lower()
        selected_status_id = done_status_id if is_completed else initial_status_id

        full_desc = []
        if spoc:
            full_desc.append(f"**SPOC / Stakeholders:** {spoc}")
        if remarks:
            full_desc.append(f"**Remarks:** {remarks}")
        if actual_end_str and actual_end_str != end_str:
            full_desc.append(f"**Actual Completion Date:** {actual_end_str}")

        hours_val = float(hours_spent) if hours_spent is not None else 0.0

        tasks_to_create.append({
            "task_id": task_id,
            "title": str(desc).strip(),
            "description": "\n\n".join(full_desc) if full_desc else None,
            "assignee_id": assignee_id,
            "status_id": selected_status_id,
            "start_date": start_str,
            "due_date": end_str,
            "estimated_hours": hours_val if not is_completed else None,
            "actual_hours": hours_val if is_completed else 0.0,
            "priority": "high" if is_completed else "medium",
            "is_subtask": task_id is None,
        })

    print(f"✓ Parsed {len(tasks_to_create)} tasks from Excel!")

    # 6. Insert Tasks into Project
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

        assignee_name = "Aravindan" if t["assignee_id"] == aravindan_id else "Divya"
        status_label = "Completed" if t["status_id"] == done_status_id else "Todo"

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
            print(f"  [{created_count:02d}/19] Created{sub_label}: '{t['title'][:45]}...' | Assignee: {assignee_name} | {t['start_date']} to {t['due_date']} | [{status_label}]")
        else:
            print(f"  [!] Failed to create task '{t['title'][:30]}': {res.status_code} {res.text}")

    print("\n" + "=" * 70)
    print("SUCCESS: Arunodhayam NGO Project Plan imported successfully into Dev!")
    print(f"Project: {project_name}")
    print(f"Project URL: https://dev-mis.winvinaya.com/org/cc05be2e-e443-4e71-aa30-6895e11fe2e7/projects/{project_public_id}")
    print(f"Total Tasks Created: {created_count}")
    print("=" * 70)


if __name__ == "__main__":
    main()
