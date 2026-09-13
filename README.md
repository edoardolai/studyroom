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

The following accounts all use `password123!`.

| Username | Role |
| --- | --- |
| bob | Student, enrolled on both example courses |
| alice | Student, initially blocked from Web application design |
| john | Student, enrolled on Database practice |
| grant | Teacher Prof Grant, owns Database practice |
| mark | Teacher, owns Web application design |

Existing databases may differ after you have tried enrolment or moderation.
Running the loader does not undo those changes or reset passwords.

## Walkthrough

1. Log in as bob to view a profile, status updates, courses and feedback.
2. Log in as grant in a separate browser session. Open Database practice's roster
   and material upload page.
3. Open Database practice's chat in both sessions and exchange messages. Refresh
   to check saved history.
4. Use alice to enrol on Database practice, then check grant's Notifications page.
   Upload a material as grant and refresh the enrolled student's inbox.
5. Use mark to see the separate course roster and alice's block. Unblock alice,
   then enrol again as alice to demonstrate restored access.
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

## Railway deployment

The deployed project uses four Railway services: the Django web service,
PostgreSQL, Redis and a Celery worker. Only the web service needs a public domain.

First create an empty GitHub repository. Do not initialise it with another README
or `.gitignore`, then push this repository:

```sh
git remote add origin https://github.com/YOUR-USERNAME/studyroom.git
git push -u origin master
```

Create a blank Railway project and add PostgreSQL and Redis from the database
menu. Add the GitHub repository as a service and name it `web`. In its Variables
tab add:

```text
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
DJANGO_DEBUG=False
SECRET_KEY=your-long-random-secret
```

A suitable secret can be generated locally without storing it in Git:

```sh
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Set the web service's custom start command to `./start.sh`. The build command is
read from `railway.json`. Attach a volume to this service at `/app/media`; this
keeps profile photos and course files after a restart. Under Networking, generate
a Railway domain. Railway supplies that domain to Django automatically.

Add the same GitHub repository to the project a second time and name this service
`worker`. Give it the same four variables and set its custom start command to:

```sh
celery -A studyroom worker --loglevel=INFO --pool=solo
```

The worker needs no public domain or volume. Apply the staged changes and deploy.
The web start script collects static files, runs migrations and loads the repeatable
demo data before Daphne. It then listens on Railway's supplied port and supports
both HTTP and WebSockets.

After deployment, test login, one protected download, chat in two sessions, and a
material notification. Upload a small file, redeploy the web service and check the
file again to confirm that the volume is persistent. PostgreSQL and Redis should
remain private inside the Railway project.
