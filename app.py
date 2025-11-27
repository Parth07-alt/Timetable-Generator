from flask import Flask, render_template, request, jsonify, send_file
from datetime import datetime, timedelta
import random
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import io
import os

def get_teacher_initials(teacher_name):
    """Extract initials from teacher name"""
    if not teacher_name:
        return ""
    parts = teacher_name.split()
    if len(parts) >= 2:
        return "".join([p[0].upper() for p in parts[:2]])
    return teacher_name[:2].upper() if len(teacher_name) >= 2 else teacher_name.upper()

def format_time_slot(start, end):
    """Format time slot as '09:00 AM TO 09:55 AM'"""
    def format_time(time_str):
        hour, minute = time_str.split(':')
        hour_int = int(hour)
        period = "AM" if hour_int < 12 else "PM"
        if hour_int == 0:
            hour_int = 12
        elif hour_int > 12:
            hour_int -= 12
        return f"{hour_int:02d}:{minute} {period}"
    
    return f"{format_time(start)} TO {format_time(end)}"

def format_subject_display(subject_code, subject_name, teacher_name, is_lab=False, batch=None):
    """Format subject as 'IM51-SMA (SK)' or 'IML56-FPD Lab-B1(SK/SDK)'"""
    # Get short name from full name
    short_name = subject_name
    if "(" in subject_name:
        short_name = subject_name.split("(")[1].split(")")[0]
    elif "-" in subject_name:
        parts = subject_name.split("-")
        if len(parts) > 1:
            short_name = parts[1].split("(")[0].strip()
        else:
            short_name = subject_name.split("-")[0].strip()
    
    # Get teacher initials
    teacher_initials = get_teacher_initials(teacher_name)
    
    if is_lab and batch:
        # Format: IML56-FPD Lab-B1(SK/SDK)
        lab_code = subject_code.replace(" Lab", "")
        return f"{lab_code}-{short_name} Lab-{batch}({teacher_initials})"
    else:
        # Format: IM51-SMA (SK)
        return f"{subject_code}-{short_name} ({teacher_initials})"

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

# Time slots configuration (matching reference format)
TIME_SLOTS = [
    ("09:00", "09:55"),
    ("09:55", "10:50"),
    ("11:05", "12:00"),
    ("12:00", "12:55"),
    ("12:55", "13:45"),  # Break
    ("13:45", "14:40"),
    ("14:40", "15:35"),
    ("15:35", "16:30"),
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# Core subjects configuration
CORE_SUBJECTS = {
    "IM51": {"name": "SMA (Simulation Modelling & Analysis)", "hours": 5, "theory": 3, "tutorial": 2},
    "IM52": {"name": "CIM (Computer Integrated Manufacturing)", "hours": 4, "theory": 2, "lab": 2},
    "IM53": {"name": "OM (Operations Management)", "hours": 3, "theory": 3},
    "IM54": {"name": "ERP (Enterprise Resource Planning)", "hours": 3, "theory": 3},
    "HS510": {"name": "EVS (Environmental Science)", "hours": 1, "theory": 1},
    "IMAEC59": {"name": "Risk Management", "hours": 1, "theory": 1},
    "AL58": {"name": "Research Methodology & IPR", "hours": 3, "theory": 3},
}

# Electives (run simultaneously)
ELECTIVES = {
    "IM551": {"name": "HFE (Human Factors Engineering)"},
    "IM552": {"name": "DBMS (Database Management Systems)"},
    "IM555": {"name": "Digital Manufacturing"},
}

# Lab schedule (fixed)
LAB_SCHEDULE = {
    "Monday": {
        "B1": {"lab": "FPD", "teachers": ["SK", "Sudheer"]},
        "B2": {"lab": "ERP", "teachers": ["Hamritha", "Niranjan"]},
        "B3": {"lab": "Free", "teachers": []},
    },
    "Tuesday": {
        "B1": {"lab": "Free", "teachers": []},
        "B2": {"lab": "FPD", "teachers": ["SK", "Niranjan"]},
        "B3": {"lab": "ERP", "teachers": ["Hamritha", "Sudheer"]},
    },
    "Thursday": {
        "B1": {"lab": "ERP", "teachers": ["SK", "Hema"]},
        "B2": {"lab": "Free", "teachers": []},
        "B3": {"lab": "FPD", "teachers": ["Hamritha", "Sudheer"]},
    },
}

def is_break_or_lunch(slot_idx):
    """Check if slot is break"""
    return slot_idx == 4  # Break at 12:55-13:45

def get_available_slots(day, slot_idx, timetable, batch=None):
    """Get available time slots for scheduling"""
    if is_break_or_lunch(slot_idx):
        return False
    
    if batch:
        # Check batch-specific timetable
        if day in timetable.get("batches", {}).get(batch, {}):
            return timetable["batches"][batch][day][slot_idx] is None
    else:
        # Check main timetable
        if day in timetable.get("main", {}):
            return timetable["main"][day][slot_idx] is None
    
    return True

def assign_subject(timetable, day, slot_idx, subject_code, subject_name, teacher, batch=None, is_elective=False, is_lab=False):
    """Assign a subject to a time slot"""
    if is_lab:
        subject_type = "lab"
    elif is_elective:
        subject_type = "elective"
    else:
        subject_type = "core"
    
    slot_data = {
        "subject": subject_code,
        "name": subject_name,
        "teacher": teacher,
        "type": subject_type
    }
    
    if batch:
        if "batches" not in timetable:
            timetable["batches"] = {}
        if batch not in timetable["batches"]:
            timetable["batches"][batch] = {}
        if day not in timetable["batches"][batch]:
            timetable["batches"][batch][day] = [None] * len(TIME_SLOTS)
        timetable["batches"][batch][day][slot_idx] = slot_data
    else:
        if "main" not in timetable:
            timetable["main"] = {}
        if day not in timetable["main"]:
            timetable["main"][day] = [None] * len(TIME_SLOTS)
        timetable["main"][day][slot_idx] = slot_data

def check_teacher_conflict(timetable, day, slot_idx, teacher, batch=None):
    """Check if teacher is already assigned at this time"""
    # Check main timetable
    if day in timetable.get("main", {}):
        if timetable["main"][day][slot_idx] and timetable["main"][day][slot_idx].get("teacher") == teacher:
            return True
    
    # Check all batches
    if "batches" in timetable:
        for b in timetable["batches"]:
            if day in timetable["batches"][b]:
                if timetable["batches"][b][day][slot_idx] and timetable["batches"][b][day][slot_idx].get("teacher") == teacher:
                    return True
    
    return False

def find_consecutive_slots(day, timetable, batch=None, num_slots=3):
    """Find consecutive available slots for a lab"""
    available_ranges = []
    current_start = None
    current_count = 0
    
    for slot_idx in range(len(TIME_SLOTS)):
        if is_break_or_lunch(slot_idx):
            if current_start is not None:
                if current_count >= num_slots:
                    available_ranges.append((current_start, current_start + num_slots - 1))
                current_start = None
                current_count = 0
            continue
        
        if get_available_slots(day, slot_idx, timetable, batch):
            if current_start is None:
                current_start = slot_idx
            current_count += 1
        else:
            if current_start is not None and current_count >= num_slots:
                available_ranges.append((current_start, current_start + num_slots - 1))
            current_start = None
            current_count = 0
    
    if current_start is not None and current_count >= num_slots:
        available_ranges.append((current_start, current_start + num_slots - 1))
    
    return available_ranges

def check_teacher_conflict_for_lab(timetable, day, slot_range, teachers):
    """Check if any teacher in the list has a conflict"""
    for slot_idx in slot_range:
        for teacher in teachers:
            if check_teacher_conflict(timetable, day, slot_idx, teacher):
                return True
    return False

def generate_timetable(teachers_dict):
    """Generate timetable based on teacher assignments"""
    timetable = {"main": {}, "batches": {"B1": {}, "B2": {}, "B3": {}}}
    
    # Initialize all days
    for day in DAYS:
        timetable["main"][day] = [None] * len(TIME_SLOTS)
        for batch in ["B1", "B2", "B3"]:
            timetable["batches"][batch][day] = [None] * len(TIME_SLOTS)
    
    # Assign labs first (fixed schedule) - 2 hours (2 consecutive slots)
    # Based on reference: Labs are at slot 6 (14:40-15:35) on Mon/Tue, slot 2 (11:05-12:00) on Thu
    lab_slot_preferences = {
        "Monday": 6,  # 14:40-15:35
        "Tuesday": 6,  # 14:40-15:35
        "Thursday": 2,  # 11:05-12:00
    }
    
    for day, batches in LAB_SCHEDULE.items():
        for batch, lab_info in batches.items():
            if lab_info["lab"] != "Free":
                # Try preferred slot first, then find 2 consecutive slots
                preferred_slot = lab_slot_preferences.get(day, 6)
                
                # Check if preferred slot and next slot are available
                if preferred_slot < len(TIME_SLOTS) - 1 and not is_break_or_lunch(preferred_slot) and not is_break_or_lunch(preferred_slot + 1):
                    if (get_available_slots(day, preferred_slot, timetable, batch) and 
                        get_available_slots(day, preferred_slot + 1, timetable, batch)):
                        slot_range = [preferred_slot, preferred_slot + 1]
                        if not check_teacher_conflict_for_lab(timetable, day, slot_range, lab_info["teachers"]):
                            for slot_idx in slot_range:
                                assign_subject(
                                    timetable, day, slot_idx,
                                    f"{lab_info['lab']} Lab",
                                    f"{lab_info['lab']} Lab",
                                    ", ".join(lab_info["teachers"]),
                                    batch=batch,
                                    is_lab=True
                                )
                            continue
                
                # Fallback: find 2 consecutive slots
                available_ranges = find_consecutive_slots(day, timetable, batch, 2)
                if available_ranges:
                    # Prefer afternoon slots for labs
                    afternoon_ranges = [r for r in available_ranges if r[0] >= 5]
                    if afternoon_ranges:
                        selected_range = random.choice(afternoon_ranges)
                    else:
                        selected_range = random.choice(available_ranges)
                    
                    # Check teacher conflicts
                    slot_range = list(range(selected_range[0], selected_range[1] + 1))
                    if not check_teacher_conflict_for_lab(timetable, day, slot_range, lab_info["teachers"]):
                        for slot_idx in slot_range:
                            assign_subject(
                                timetable, day, slot_idx,
                                f"{lab_info['lab']} Lab",
                                f"{lab_info['lab']} Lab",
                                ", ".join(lab_info["teachers"]),
                                batch=batch,
                                is_lab=True
                            )
    
    # Assign CIM lab on Saturday 09:55-10:50 (slot 1) - matching reference
    cim_teacher = teachers_dict.get("IM52", "Teacher")
    if not check_teacher_conflict(timetable, "Saturday", 1, cim_teacher):
        assign_subject(
            timetable, "Saturday", 1,
            "IM52 Lab", "CIM Lab",
            cim_teacher,
            batch=None,
            is_lab=True
        )
    
    # Track remaining hours for each subject
    remaining_hours = {}
    for code, info in CORE_SUBJECTS.items():
        remaining_hours[code] = {
            "theory": info.get("theory", 0),
            "tutorial": info.get("tutorial", 0),
            "lab": info.get("lab", 0)
        }
    
    # Prioritize morning slots (slots 0, 1, 2, 3 before break)
    morning_slots = [0, 1, 2, 3]
    afternoon_slots = [5, 6, 7]  # After break
    
    # Assign core subjects (theory and tutorials) - DISTRIBUTE across days properly
    for code, info in CORE_SUBJECTS.items():
        teacher = teachers_dict.get(code, "Teacher")
        
        # Get all available slots across all days for this subject
        available_assignments = []
        for day in DAYS:
            for slot_idx in morning_slots + afternoon_slots:
                if is_break_or_lunch(slot_idx):
                    continue
                if get_available_slots(day, slot_idx, timetable) and not check_teacher_conflict(timetable, day, slot_idx, teacher):
                    available_assignments.append((day, slot_idx))
        
        # Shuffle to randomize
        random.shuffle(available_assignments)
        
        # Assign theory classes - DISTRIBUTE across different days
        theory_assigned = 0
        used_days_theory = set()
        
        # First pass: assign to different days
        for day, slot_idx in available_assignments:
            if theory_assigned >= remaining_hours[code]["theory"]:
                break
            if day not in used_days_theory:
                if get_available_slots(day, slot_idx, timetable) and not check_teacher_conflict(timetable, day, slot_idx, teacher):
                    assign_subject(timetable, day, slot_idx, code, info["name"], teacher)
                    used_days_theory.add(day)
                    theory_assigned += 1
        
        # Second pass: if still need more theory classes, allow same days
        if theory_assigned < remaining_hours[code]["theory"]:
            for day, slot_idx in available_assignments:
                if theory_assigned >= remaining_hours[code]["theory"]:
                    break
                if get_available_slots(day, slot_idx, timetable) and not check_teacher_conflict(timetable, day, slot_idx, teacher):
                    assign_subject(timetable, day, slot_idx, code, info["name"], teacher)
                    theory_assigned += 1
        
        # Assign tutorial classes - DISTRIBUTE across different days
        tutorial_assigned = 0
        used_days_tutorial = set()
        
        # First pass: prefer days not used for theory
        for day, slot_idx in available_assignments:
            if tutorial_assigned >= remaining_hours[code]["tutorial"]:
                break
            if day not in used_days_theory and day not in used_days_tutorial:
                if get_available_slots(day, slot_idx, timetable) and not check_teacher_conflict(timetable, day, slot_idx, teacher):
                    assign_subject(timetable, day, slot_idx, f"{code} (T)", f"{info['name']} (Tutorial)", teacher)
                    used_days_tutorial.add(day)
                    tutorial_assigned += 1
        
        # Second pass: allow any available day
        if tutorial_assigned < remaining_hours[code]["tutorial"]:
            for day, slot_idx in available_assignments:
                if tutorial_assigned >= remaining_hours[code]["tutorial"]:
                    break
                if day not in used_days_tutorial:
                    if get_available_slots(day, slot_idx, timetable) and not check_teacher_conflict(timetable, day, slot_idx, teacher):
                        assign_subject(timetable, day, slot_idx, f"{code} (T)", f"{info['name']} (Tutorial)", teacher)
                        used_days_tutorial.add(day)
                        tutorial_assigned += 1
    
    # Assign electives simultaneously (same time slot, different batches)
    # But distribute across different days and time slots (not consecutive)
    elective_slots_needed = 3  # 3 hours per week
    elective_days = [d for d in DAYS if d != "Saturday"]
    random.shuffle(elective_days)
    
    # Get all possible elective slots across different days
    elective_slot_options = []
    for elective_day in elective_days:
        for slot_idx in morning_slots + afternoon_slots:
            if is_break_or_lunch(slot_idx):
                continue
            
            # Check if slot is available for all batches
            all_available = True
            for batch in ["B1", "B2", "B3"]:
                if not get_available_slots(elective_day, slot_idx, timetable, batch):
                    all_available = False
                    break
            
            if not all_available:
                continue
            
            # Check if teachers are available
            elective_teachers = [
                teachers_dict.get("IM551", "Teacher1"),
                teachers_dict.get("IM552", "Teacher2"),
                teachers_dict.get("IM555", "Teacher3")
            ]
            
            can_assign = True
            for teacher in elective_teachers:
                if check_teacher_conflict(timetable, elective_day, slot_idx, teacher):
                    can_assign = False
                    break
            
            if can_assign:
                elective_slot_options.append((elective_day, slot_idx))
    
    # Shuffle to randomize
    random.shuffle(elective_slot_options)
    
    # Assign electives - ensure different days and time slots
    used_elective_days = set()
    used_elective_slots = set()
    elective_assigned = 0
    
    # First pass: assign to different days and different time slots
    for elective_day, slot_idx in elective_slot_options:
        if elective_assigned >= elective_slots_needed:
            break
        
        # Prefer different days and different time slots
        if (elective_day not in used_elective_days or len(used_elective_days) >= len(elective_days)) and slot_idx not in used_elective_slots:
            # Double-check availability
            all_available = True
            for batch in ["B1", "B2", "B3"]:
                if not get_available_slots(elective_day, slot_idx, timetable, batch):
                    all_available = False
                    break
            
            if all_available:
                elective_teachers = [
                    teachers_dict.get("IM551", "Teacher1"),
                    teachers_dict.get("IM552", "Teacher2"),
                    teachers_dict.get("IM555", "Teacher3")
                ]
                
                can_assign = True
                for teacher in elective_teachers:
                    if check_teacher_conflict(timetable, elective_day, slot_idx, teacher):
                        can_assign = False
                        break
                
                if can_assign:
                    # Assign to all three batches simultaneously
                    assign_subject(timetable, elective_day, slot_idx, "IM551", ELECTIVES["IM551"]["name"], elective_teachers[0], batch="B1", is_elective=True)
                    assign_subject(timetable, elective_day, slot_idx, "IM552", ELECTIVES["IM552"]["name"], elective_teachers[1], batch="B2", is_elective=True)
                    assign_subject(timetable, elective_day, slot_idx, "IM555", ELECTIVES["IM555"]["name"], elective_teachers[2], batch="B3", is_elective=True)
                    used_elective_days.add(elective_day)
                    used_elective_slots.add(slot_idx)
                    elective_assigned += 1
    
    # Second pass: if still need more, allow same day but different time slot
    if elective_assigned < elective_slots_needed:
        for elective_day, slot_idx in elective_slot_options:
            if elective_assigned >= elective_slots_needed:
                break
            
            if slot_idx not in used_elective_slots:
                all_available = True
                for batch in ["B1", "B2", "B3"]:
                    if not get_available_slots(elective_day, slot_idx, timetable, batch):
                        all_available = False
                        break
                
                if all_available:
                    elective_teachers = [
                        teachers_dict.get("IM551", "Teacher1"),
                        teachers_dict.get("IM552", "Teacher2"),
                        teachers_dict.get("IM555", "Teacher3")
                    ]
                    
                    can_assign = True
                    for teacher in elective_teachers:
                        if check_teacher_conflict(timetable, elective_day, slot_idx, teacher):
                            can_assign = False
                            break
                    
                    if can_assign:
                        assign_subject(timetable, elective_day, slot_idx, "IM551", ELECTIVES["IM551"]["name"], elective_teachers[0], batch="B1", is_elective=True)
                        assign_subject(timetable, elective_day, slot_idx, "IM552", ELECTIVES["IM552"]["name"], elective_teachers[1], batch="B2", is_elective=True)
                        assign_subject(timetable, elective_day, slot_idx, "IM555", ELECTIVES["IM555"]["name"], elective_teachers[2], batch="B3", is_elective=True)
                        used_elective_slots.add(slot_idx)
                        elective_assigned += 1
    
    return timetable

def generate_pdf(timetable_data, teachers_dict):
    """Generate PDF from timetable data"""
    buffer = io.BytesIO()
    # Use landscape orientation for better width
    doc = SimpleDocTemplate(buffer, pagesize=(11*inch, 8.5*inch), 
                           topMargin=0.4*inch, bottomMargin=0.4*inch,
                           leftMargin=0.3*inch, rightMargin=0.3*inch)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Create custom styles for better text wrapping
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontSize=7,
        leading=9,
        alignment=1,  # Center
        textColor=colors.black,
        fontName='Helvetica'
    )
    
    cell_style_bold = ParagraphStyle(
        'CellStyleBold',
        parent=cell_style,
        fontSize=7,
        leading=9,
        fontName='Helvetica-Bold'
    )
    
    cell_style_small = ParagraphStyle(
        'CellStyleSmall',
        parent=cell_style,
        fontSize=6,
        leading=8,
        fontName='Helvetica'
    )
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=20,
        alignment=1
    )
    
    heading_style = ParagraphStyle(
        'HeadingStyle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=10,
        spaceBefore=10
    )
    
    # Header information matching reference format
    header_table_data = [
        ["DEPARTMENT: IEM", "SEMESTER: V"],
        ["TERM: 10-09-2025", "ROOM NO.: ESB-329"]
    ]
    header_table = Table(header_table_data, colWidths=[5.5*inch, 5.5*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Helper function to get cell content
    def get_cell_content(day, slot_idx, batch=None):
        batch_slot = None
        main_slot = None
        
        if batch:
            batch_slot = timetable_data["batches"].get(batch, {}).get(day, [None] * len(TIME_SLOTS))[slot_idx]
        main_slot = timetable_data["main"].get(day, [None] * len(TIME_SLOTS))[slot_idx]
        
        if is_break_or_lunch(slot_idx):
            return "BREAK"
        
        # Check for electives at same time (they run simultaneously)
        if main_slot and main_slot.get('type') == 'elective':
            elective_texts = []
            for b in ["B1", "B2", "B3"]:
                batch_elective = timetable_data["batches"].get(b, {}).get(day, [None] * len(TIME_SLOTS))[slot_idx]
                if batch_elective and batch_elective.get('type') == 'elective':
                    elective_texts.append(format_subject_display(
                        batch_elective['subject'],
                        batch_elective['name'],
                        batch_elective['teacher']
                    ))
            if elective_texts:
                return ", ".join(elective_texts)
        
        if batch_slot:
            return format_subject_display(
                batch_slot['subject'],
                batch_slot['name'],
                batch_slot['teacher'],
                is_lab=(batch_slot.get('type') == 'lab'),
                batch=batch
            )
        
        if main_slot:
            return format_subject_display(
                main_slot['subject'],
                main_slot['name'],
                main_slot['teacher'],
                is_lab=(main_slot.get('type') == 'lab')
            )
        
        return ""
    
    # Create main timetable table
    main_data = []
    header_row = [Paragraph("<b>TIME</b>", cell_style_bold)]
    for day in DAYS:
        header_row.append(Paragraph(f"<b>{day.upper()}</b>", cell_style_bold))
    main_data.append(header_row)
    
    for slot_idx, (start, end) in enumerate(TIME_SLOTS):
        time_text = "BREAK" if is_break_or_lunch(slot_idx) else format_time_slot(start, end)
        row = [Paragraph(time_text, cell_style_bold)]
        
        for day in DAYS:
            slot = timetable_data["main"].get(day, [None] * len(TIME_SLOTS))[slot_idx]
            if slot:
                cell_text = format_subject_display(
                    slot['subject'],
                    slot['name'],
                    slot['teacher'],
                    is_lab=(slot.get('type') == 'lab')
                )
                row.append(Paragraph(cell_text, cell_style))
            elif is_break_or_lunch(slot_idx):
                row.append(Paragraph("BREAK", cell_style_bold))
            else:
                row.append(Paragraph("", cell_style))
        main_data.append(row)
    
        for day in DAYS:
            cell_content = get_cell_content(day, slot_idx)
            if cell_content:
                row.append(Paragraph(cell_content, cell_style))
            else:
                row.append(Paragraph("", cell_style))
        main_data.append(row)
    
    # Table styling
    time_col_width = 1.3*inch
    day_col_width = (11*inch - 0.8*inch - time_col_width) / 6
    main_table = Table(main_data, colWidths=[time_col_width] + [day_col_width]*6, repeatRows=1)
    main_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    
    story.append(main_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'FooterStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=2,  # Right
        spaceBefore=20
    )
    current_date = datetime.now().strftime("%d/%m/%Y")
    story.append(Paragraph(f"Date: {current_date}", footer_style))
    story.append(Spacer(1, 0.1*inch))
    story.append(Paragraph("Signature", footer_style))
    story.append(Paragraph("Professor & Head, Dept. of Industrial Engg. & Management", footer_style))
    story.append(Paragraph("RAMAIAH INSTITUTE OF TECHNOLOGY", footer_style))
    
    story.append(PageBreak())
    
    # Batch timetables
    for batch in ["B1", "B2", "B3"]:
        # Header for batch
        batch_header = Table([["DEPARTMENT: IEM", "SEMESTER: V"], 
                             [f"BATCH: {batch}", "ROOM NO.: ESB-329"]], 
                            colWidths=[5.5*inch, 5.5*inch])
        batch_header.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(batch_header)
        story.append(Spacer(1, 0.2*inch))
        
        batch_data = []
        header_row = [Paragraph("<b>TIME</b>", cell_style_bold)]
        for day in DAYS:
            header_row.append(Paragraph(f"<b>{day.upper()}</b>", cell_style_bold))
        batch_data.append(header_row)
        
        for slot_idx, (start, end) in enumerate(TIME_SLOTS):
            time_text = "BREAK" if is_break_or_lunch(slot_idx) else format_time_slot(start, end)
            row = [Paragraph(time_text, cell_style_bold)]
            
            for day in DAYS:
                cell_content = get_cell_content(day, slot_idx, batch=batch)
                if cell_content:
                    row.append(Paragraph(cell_content, cell_style))
                else:
                    row.append(Paragraph("", cell_style))
            batch_data.append(row)
        
        batch_table = Table(batch_data, colWidths=[time_col_width] + [day_col_width]*6, repeatRows=1)
        batch_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1565c0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        story.append(batch_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Footer for batch
        story.append(Paragraph(f"Date: {current_date}", footer_style))
        story.append(Spacer(1, 0.1*inch))
        story.append(Paragraph("Signature", footer_style))
        story.append(Paragraph("Professor & Head, Dept. of Industrial Engg. & Management", footer_style))
        story.append(Paragraph("RAMAIAH INSTITUTE OF TECHNOLOGY", footer_style))
        
        if batch != "B3":
            story.append(PageBreak())
    
    doc.build(story)
    buffer.seek(0)
    return buffer

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        teachers = data.get('teachers', {})
        
        # Generate timetable
        timetable = generate_timetable(teachers)
        
        return jsonify({
            'success': True,
            'timetable': timetable
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/export_pdf', methods=['POST'])
def export_pdf():
    try:
        data = request.json
        timetable_data = data.get('timetable', {})
        teachers_dict = data.get('teachers', {})
        
        pdf_buffer = generate_pdf(timetable_data, teachers_dict)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'timetable_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        )
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

