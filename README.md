# 5th Semester IEM Timetable Generator

A Flask web application for generating weekly timetables for the 5th Semester IEM program with optimal scheduling and constraint handling.

## Features

- ✅ Automatic timetable generation with random distribution
- ✅ Handles all core subjects, electives, and labs
- ✅ Respects teacher availability and prevents conflicts
- ✅ Generates separate timetables for full class and each batch (B1, B2, B3)
- ✅ Beautiful, modern web interface
- ✅ PDF export functionality
- ✅ Responsive design

## Installation

1. **Clone or download this repository**

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - Windows: `venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Set up environment variables**:
   - Copy `env_template.txt` to `.env`
   - Update `SECRET_KEY` with a secure random string
   - Note: The app will work without a `.env` file, but it's recommended for production

## Running the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Usage

1. Open the web application in your browser
2. Enter teacher names for each subject
3. Click "Generate Timetable"
4. Review the generated timetables (full class and batch-wise)
5. Click "Export as PDF" to download the timetable

## Environment Variables

Create a `.env` file with the following variables:

- `SECRET_KEY`: Flask secret key for session management (required)
- `FLASK_ENV`: Environment mode (development/production) - optional
- `FLASK_DEBUG`: Enable/disable debug mode - optional
- `FLASK_HOST`: Host to bind to (default: 0.0.0.0) - optional
- `FLASK_PORT`: Port to run on (default: 5000) - optional

## Timetable Structure

### Time Slots
- 09:00 - 16:15 (with break 10:55-11:05 and lunch 12:55-13:45)
- Monday through Saturday

### Core Subjects
- IM51 (SMA): 5 hrs/week (3 theory + 2 tutorials)
- IM52 (CIM): 4 hrs/week (2 theory + 2-hr lab Saturday)
- IM53 (OM): 3 hrs/week
- IM54 (ERP): 3 hrs/week
- HS510 (EVS): 1 hr/week
- IMAEC59 (Risk Management): 1 hr/week
- AL58 (Research Methodology & IPR): 3 hrs/week

### Electives (Run Simultaneously)
- IM551 (HFE)
- IM552 (DBMS)
- IM555 (Digital Manufacturing)

### Labs
- FPD Lab / ERP Lab: 3 hrs/week per batch
- Fixed schedule for Monday, Tuesday, and Thursday

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

Quick deployment options:
- **Render.com** (Recommended - Free & Easy)
- **Railway.app** (Free tier available)
- **Heroku** (Free tier discontinued, paid only)
- **PythonAnywhere** (Free tier available)
- **VPS** (DigitalOcean, AWS, etc.)

## License

This project is for educational purposes.

