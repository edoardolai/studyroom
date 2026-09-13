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

## Oracle VM deployment

The production setup uses Docker Compose on an Ubuntu 24.04 VM. Caddy handles
HTTPS and forwards HTTP and WebSocket connections to Daphne. PostgreSQL, Redis
and the Celery worker are kept on the private Docker network.

Point a DNS name at the VM and allow inbound TCP ports 80 and 443 in the Oracle
network security rules. On a new Ubuntu server, install Git and Docker Engine from
Docker's Ubuntu repository, then clone the project:

```sh
git clone https://github.com/edoardolai/studyroom.git
cd studyroom
cp .env.example .env
```

Generate two values and copy them into `.env`. The first is the Django secret and
the second is the PostgreSQL password:

```sh
openssl rand -hex 32
openssl rand -hex 24
nano .env
```

Set `DOMAIN` to the public DNS name. Do not commit `.env`. Start the application:

```sh
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 web worker caddy
```

The first start collects static files, runs migrations and loads the repeatable
demo data before Daphne starts. The named Docker volumes preserve PostgreSQL,
Redis, uploaded files and Caddy certificates. To deploy a later commit:

```sh
git pull
docker compose up -d --build
```

After deployment, test login, one protected download, chat in two browser
sessions and a material notification. Upload a small file, restart with
`docker compose restart`, then check the file and chat history again to confirm
that the volumes are persistent.
