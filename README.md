# Studyroom

Django eLearning coursework with student/teacher accounts, courses, feedback,
notifications and course chat.

## Local setup

Use Python 3.12 and Redis. From the extracted project folder:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
```

The submission should include `db.sqlite3` and `media/`. If starting from a Git
checkout or an empty database, populate the examples with:

```sh
python load_data.py
```

The loader can be run again. It keeps existing accounts, passwords, profile
edits and moderation state. It creates missing examples, so it is a setup script,
not a way to reset the database after testing.

Run these in separate terminals. Activate the virtual environment and use the
project folder for the Python/Celery commands:

```sh
redis-server --bind 127.0.0.1 --dir /tmp --dbfilename studyroom-redis.rdb
```

```sh
celery -A studyroom worker --loglevel=INFO --pool=solo
```

```sh
python manage.py runserver
```

If Redis is already running on port 6379, use that instance. Open
<http://127.0.0.1:8000/>. Redis is needed for chat; Celery delivers material
notifications. These settings are for a local demonstration.

## Demo accounts

Newly created demo accounts all use `Studyroom-demo-482!`.

| Username | Role |
| --- | --- |
| alex | Student, enrolled on both example courses |
| sam | Student, initially blocked from Web application design |
| morgan | Teacher, owns Database practice |
| riley | Teacher, owns Web application design |
| admin | Site administrator at `/admin/` |

Existing databases may differ after you have tried enrolment or moderation.
Running the loader does not undo those changes or reset passwords.

## Walkthrough

1. Log in as alex to view a profile, status updates, courses and feedback.
2. Log in as morgan in a separate browser session. Open Database practice's roster
   and material upload page.
3. Open Database practice's chat in both sessions and exchange messages. Refresh
   to check saved history.
4. Use sam to enrol on Database practice, then check morgan's Notifications page.
   Upload a material as morgan and refresh the enrolled student's inbox.
5. Use riley to see the separate course roster and sam's block. Unblock sam, then
   enrol again as sam to demonstrate restored access.
6. After login, open `/api/docs/` for Swagger or `/api/users/me/` for the browsable
   API. PATCH supports changes to your name and biography.

## Checks

```sh
python manage.py test
python manage.py check
python manage.py spectacular --file /tmp/studyroom-schema.yaml --validate --fail-on-warn
```

There are 63 tests. They use temporary data and do not require Redis or Celery.
`report.md` contains the development discussion; `er_diagram.mmd` contains the
same model diagram embedded in the report. The final report PDF and video are
separate deliverables.
