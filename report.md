# Studyroom — CM3035 Final Coursework

> Draft status: accounts, profiles, courses/materials, feedback, teacher search, course moderation, notifications, course chat and the user REST API implemented. Clean installation, demo data and Railway configuration are complete; the live deployment and final submission packaging are still pending. The working target is 60–65 tests for the finished application, with 63 currently retained. This note tracks work remaining and is not part of the submission text.

## 1. Introduction and development approach

Studyroom is an eLearning application being built with Django. The coursework requires student and teacher accounts, course enrolment and materials, feedback, notifications, a user REST interface and real-time chat. The first development step establishes accounts and authentication, since the later features need to know who is making a request and what that person may do.

Development started with the project skeleton, then the custom user and migration, registration, and login/logout. The teacher student list provided the first place to test different permissions. The browser pages use Django templates and forms, with views in `views.py` and registration validation in `forms.py`.

The next step added member home pages and biography editing. Photo uploads followed once the editing workflow had ownership tests, then status updates added the first one-to-many relationship. These changes have separate migrations, so existing accounts receive the new optional fields without needing to be recreated.

Courses were built in three steps: creation and browsing, enrolment and rosters, then uploaded materials. This order gave each upload a course to belong to and an established permission rule for downloading it. The course work also exposed a repeated home-page context between normal viewing and an invalid status submission; a small helper now supplies the same course information to both.

Teacher search came next, using the existing member directory. Feedback then added a form for enrolled students, followed by removal and blocking controls on the roster. Adding blocking required revisiting downloads and home-page queries: a stored enrolment could now represent a block, so checking only whether the row existed was no longer enough.

## 2. Accounts and database design

The first model is `accounts.User`, which extends Django's `AbstractUser`. It retains Django's username, password, name and email fields and adds a `role` field with two values: student and teacher. One field makes the two account types mutually exclusive. The field choices validate form input; a database check constraint also rejects other role values when a write bypasses a form.

I used a custom user because the role belongs to the account and is needed whenever permissions are checked. `AbstractUser` keeps the standard authentication behaviour while allowing the additional field [1]. Configuring it before the first migration avoids replacing the user table once other models reference it. The admin extends `UserAdmin`, including the role on both its creation and editing forms.

To keep role values and their display labels together, I used `TextChoices`. A `CheckConstraint` enforces the two-value rule in SQLite, including writes made outside a form. The views then check the stored role to decide whether the user can perform an action.

Profile data stays on `User`: a biography of up to 1,000 characters and an optional photo. Both describe one account, so a separate profile table would add a join without a separate lifecycle to manage. The photo column stores a file path; the image itself is saved under `MEDIA_ROOT`.

Status updates belong in their own table because an account can post many of them. Each `StatusUpdate` stores its author, text and creation time. The author's name is read through the foreign key rather than copied into every update, so a name change does not leave old posts with stale names. Deleting an account cascades to its updates, which have no purpose without their author. The default ordering uses creation time and then primary key, both descending, so updates have a consistent order even when timestamps match.

`Course` has one teacher, a title, a description and a creation time. Its teacher uses `PROTECT`: deleting a teacher should not silently remove courses that students have joined. The teacher's name is retrieved through the relationship. Titles are not unique, since different teachers can reasonably offer courses with the same title; URLs identify courses by primary key.

`Enrolment` links a student and a course and records when they joined. A unique constraint on the pair prevents duplicate participation, including writes outside the web form. Its `is_blocked` flag defaults to false, preserving existing enrolments when the migration runs. A blocked row records that the student cannot rejoin; removal deletes the row. Course and student deletion cascade to their enrolments. Model validation checks the account role for course owners and enrolments; the web views separately enforce the role and assign the account from the session.

`CourseMaterial` stores a title, file path, upload time and course foreign key. The owning teacher is already available through the course, so it does not repeat that account reference. This structure keeps account details, course descriptions and individual materials in their respective tables, while enrolment represents the many-to-many student/course relationship.

`Feedback` stores the student, course, text and last update time. A unique student/course pair gives each student one editable entry. It references the course and student directly, so removing an enrolment does not erase what the student wrote. Deleting the account or course does cascade to its feedback. The text is limited to 2,000 characters; no rating scale was needed for the written feedback requirement.

`ChatMessage` belongs to a course and an author, with text and creation time. The course itself identifies the room, so a separate room table would duplicate the relationship. Deleting a course or author cascades to their messages. The sender is assigned from the authenticated session, never from submitted JSON.

The ER diagram shows these application fields and relationships. Django's supporting authentication and session tables are omitted.

```mermaid
erDiagram
    USER {
        bigint id PK
        varchar username UK
        varchar password "Django password hash"
        varchar first_name
        varchar last_name
        varchar email
        varchar role "student or teacher"
        text biography "optional, up to 1000 characters"
        varchar photo "optional file path"
        boolean is_active
        boolean is_staff
        boolean is_superuser
        datetime date_joined
        datetime last_login "nullable"
    }
    USER ||--o{ STATUS_UPDATE : posts
    STATUS_UPDATE {
        bigint id PK
        bigint author_id FK
        varchar body "up to 500 characters"
        datetime created_at
    }
    USER ||--o{ COURSE : teaches
    USER ||--o{ ENROLMENT : joins
    COURSE ||--o{ ENROLMENT : has
    COURSE ||--o{ COURSE_MATERIAL : contains
    COURSE {
        bigint id PK
        bigint teacher_id FK
        varchar title
        text description
        datetime created_at
    }
    ENROLMENT {
        bigint id PK
        bigint course_id FK "unique with student_id"
        bigint student_id FK
        datetime enrolled_at
        boolean is_blocked
    }
    COURSE_MATERIAL {
        bigint id PK
        bigint course_id FK
        varchar title
        varchar file "stored file path"
        datetime uploaded_at
    }
    USER ||--o{ FEEDBACK : writes
    COURSE ||--o{ FEEDBACK : receives
    FEEDBACK {
        bigint id PK
        bigint course_id FK "unique with student_id"
        bigint student_id FK
        text body "up to 2000 characters"
        datetime updated_at
    }
    USER ||--o{ NOTIFICATION : receives
    COURSE ||--o{ NOTIFICATION : concerns
    COURSE_MATERIAL |o--o{ NOTIFICATION : announces
    NOTIFICATION {
        bigint id PK
        bigint recipient_id FK "unique with non-null material_id"
        bigint course_id FK
        bigint material_id FK "nullable for enrolment notices"
        varchar message
        boolean is_read
        datetime created_at
    }
    USER ||--o{ CHAT_MESSAGE : sends
    COURSE ||--o{ CHAT_MESSAGE : stores
    CHAT_MESSAGE {
        bigint id PK
        bigint course_id FK
        bigint author_id FK
        varchar body "up to 1000 characters"
        datetime created_at
    }
```

## 3. Registration, authentication and permissions

Public registration creates student accounts. Teacher accounts are created or promoted through the admin, because letting a registrant choose teacher would also let them grant themselves access to student records. The registration form extends `UserCreationForm` and explicitly lists username, first name, last name and email. It does not accept role or administration flags. The password fields and validation come from Django. After saving a valid account, the view redirects to login and displays a confirmation; invalid input returns the bound form with field errors.

Login and logout use Django's built-in views and session authentication. Logout is a POST form with a CSRF token. Keeping the built-in login view also preserves its validation of the `next` destination: a user can return to a requested local page without the application redirecting them to an arbitrary external address supplied in the request.

The first teacher function is a paginated list of active student accounts. It shows username and real name, but not email or password information. Anonymous requests go to login; authenticated students receive 403. The template hides the student-list link from students, but the view checks the role independently, so entering the URL directly does not bypass the restriction. Teacher status is separate from `is_staff`: teachers have application permissions, while the staff flag controls entry to Django admin.

I used `login_required` to redirect anonymous visitors before a protected view runs, following the lectures' access-control pattern. Method decorators make each view's supported actions explicit: `require_POST` for enrolment and status submission, `require_http_methods(["GET", "POST"])` for forms, and `require_safe` for reading pages [12]. Unsupported methods receive HTTP 405. These checks do not establish course ownership or replace CSRF protection; the view still checks the role and relevant record. In admin, `admin.register` associates a model with its configuration, while `admin.display` labels the protected photo/material links [13].

The list covers active students across the site. To keep the table manageable as accounts are added, I used Django's `Paginator` to divide it into pages of 25. Since the page only displays records, `require_safe` limits it to GET and HEAD requests. The forms use `as_div` to render Django's fields and errors inside containers styled by the stylesheet.

## 4. Profiles, discovery and status updates

The Members page gives students and teachers a way to find each other's home pages. It lists active accounts, excluding site administrators from the directory. Each home page shows the member's name, username, role, biography, photo and status history. These pages require login. Email addresses remain account information and are not rendered on the directory or another member's home page. This separates profile discovery from the teacher-only student list and its later course-management functions.

Profile editing has one route, `/accounts/profile/edit/`, with no target account ID. The view passes `request.user` as the form instance, so editing always applies to the logged-in account. The form lists the editable fields explicitly. Submitting an extra username, role, email or administration flag does not change it. Successful edits redirect to the member's home page; invalid edits return the form and errors without saving the profile.

Photos use an `ImageField` and Pillow to check image content. The upload form uses `multipart/form-data`, and the view passes `request.FILES` alongside `request.POST` [3]. I limited uploads to JPEG and PNG, 2 MB, and 4096 pixels on either side to keep profile images reasonably bounded. Checking the content as well as the extension rejects a GIF renamed to `.png`. The shared field validator also applies when the model is validated through an admin form. It rewinds the file after inspecting it so storage can read the complete upload.

The photo URL identifies the account, and a Django view checks login and account activity before returning a `FileResponse`. The application does not expose a general `/media/` route. `never_cache` adds response headers telling browsers not to retain the authenticated image response. Removing a photo clears the current reference; trying to remove and replace it in the same submission returns an error rather than choosing one action silently. A review found that the admin's default file widget still linked to `/media/`, so its current-photo link was changed to use the authenticated route too.

Both students and teachers can post updates on their own home page. This covers the brief's student example and R1(i), which refers to users adding updates. A `ModelForm` validates non-blank text up to 500 characters. Only the text is accepted from the form: the view assigns the author from `request.user` before saving. Posting requires POST and a CSRF token. Status history is paginated in groups of ten, newest first. If validation fails, the existing updates remain visible alongside the error. Biography and status text use Django's template escaping, so submitted HTML is displayed as text.

The interface uses a shared template, labelled form fields and a small stylesheet. Members have a direct My home link, while other users' pages show neither the edit link nor the status form. Long text wraps inside the page, and the photo is displayed at a fixed size without stretching its aspect ratio. No JavaScript is needed for these forms.

## 5. Courses, enrolment and materials

Members can browse course descriptions before joining. Teachers create courses through a `ModelForm` exposing only title and description; the view assigns the teacher. Students enrol with a CSRF-protected POST. `get_or_create` and the unique database constraint make a repeated submission return the existing enrolment instead of creating another one. My courses shows the teacher's own courses or the student's enrolments, depending on role.

The roster view checks that the requester is a teacher and retrieves the course filtered by that teacher. A different teacher cannot get a roster by changing the URL. Even enrolled students cannot open the roster. On home pages, teachers' courses are discoverable, while a student's enrolments are shown only to that student. These are different views of the same course relationships, rather than separately stored lists.

Materials are uploaded by the course teacher. The form accepts a title and file, and the course comes from the authorised URL lookup rather than a submitted field. Downloads check the same owner/enrolment rule used to show the material list. Knowing a material ID or storage path is insufficient to retrieve it. The response sends the file as an attachment and disables caching. Course descriptions remain visible to unenrolled members, but material titles and links do not.

I used Pillow for JPEG/PNG checks and added `pypdf` to read PDF structure, rather than treating a `.pdf` extension as proof of a valid document. The PDF reader uses strict mode and requires an unencrypted document with at least one page [4]. Images must match their extension and fit within 4096 by 4096 pixels. All materials have a 10 MB limit. These checks reject unsupported, malformed and oversized uploads; they are not malware scanning. Strict PDF parsing can also reject a damaged document that a viewer would repair, so the user may need to export a clean copy.

Course logic lives in the `courses` app. The HTML views remain short functions; the shared `can_access_course` helper prevents the course page and download endpoint from making different permission decisions. Course lists, rosters and materials are paginated. `select_related` retrieves teacher/student details with the corresponding rows rather than issuing another query for each displayed name.

### Feedback and teacher search

An enrolled student can write or update feedback through a `ModelForm` exposing only the text. The course comes from the URL and the student from the session. `update_or_create` uses that pair to save an entry, so submitting the form again updates it. Feedback is visible to signed-in members browsing the course, including those considering enrolment, and the form explains this before submission. Output is escaped and paginated independently from materials. Removed and blocked students keep their existing feedback but cannot change it without active enrolment.

Teachers search the Members page by username, first name or surname. Each word must match at least one of those fields, so a query such as “Prof Grant” can span first and last name. I used `Q` expressions to combine the alternatives within each word [6]. Results retain the directory's exclusions for inactive and administrator accounts, and do not expose email addresses. Students can still browse member home pages; supplying a non-empty search query as a student returns a permission error. Search text is limited to 150 characters, and pagination keeps it in the URL.

### Removing and blocking students

I interpreted removal and blocking as course-level decisions, since teachers manage their own rosters. They do not disable a student's account or affect another teacher's course. Removal deletes the enrolment and allows the student to join again. Blocking retains it with `is_blocked=True`, preventing re-enrolment, material access and feedback editing. Blocked records appear separately on the teacher's roster and are excluded from the student's home-page courses and My courses.

Each action opens a confirmation page explaining its effect; only a CSRF-protected POST changes the record. Both the course owner and the enrolment's membership of that course are checked on the server. The action comes from the URL configuration, rather than a submitted form value. Removal accepts only an unblocked enrolment, so submitting an old removal form cannot lift a newly applied block. Unblocking deletes the blocked record and lets the student choose whether to enrol again. Existing feedback remains visible, preventing removal from silently erasing criticism.

## 6. Photo cleanup

The first upload implementation left replaced photos on disk. During the file-handling work I added cleanup using user-model signals, so it also covers admin saves and queryset deletion. Before a save, the previous file name is remembered; after a successful save, a changed reference schedules cleanup. Account deletion schedules the same check.

Deletion uses `transaction.on_commit`: if a database transaction rolls back, its deletion callback is discarded [5]. Before deleting a file, the callback checks whether any account still references its name. This protects a shared file and leaves unrelated users' uploads alone. Cleanup errors are logged through the robust callback option, so a storage failure does not make an already-saved profile look like a failed edit. Direct queryset updates bypass these save signals and should not be used to replace photos.

## 7. Notifications and background tasks

Enrolment creates one notification for the course teacher. The enrolment and notice are saved in the same database transaction, so they succeed or roll back together. A repeated enrolment submission returns the existing record and creates no second notice. Removing a student and letting them join again is a new enrolment and produces a new notice.

Material uploads may need to notify a whole class, so I used Celery with Redis to do that work outside the upload request, following the task-worker arrangement from the lectures [7]. The project loads its Celery application alongside settings and discovers `tasks.py` in installed apps. The upload schedules the task after commit and passes only the material's primary key. The worker retrieves the saved material and finds students who joined before it was uploaded and are still active and unblocked. Students joining later already have access to the material and do not receive an old announcement.

`Notification` stores its recipient, course, message, creation time and read flag. Its optional material reference identifies upload notices. A unique recipient/material pair prevents a repeated task from creating duplicates. Enrolment notices have no material reference, so this constraint does not prevent later re-enrolment notices. The course reference gives both kinds a destination link; the message retains the names at the time it was created. Deleting a recipient, course or linked material removes the associated notices.

The Notifications page filters by the logged-in recipient, shows unread status and paginates the history. Marking a notice as read uses POST with CSRF protection and checks ownership again. Its course link goes through the normal course permissions: a historical notice does not grant continued access after removal or blocking. The page needs refreshing to show new notices.

The task retries temporary database errors up to three times. If publishing fails because the broker is unavailable, a small wrapper logs the failure and creates the notices directly. This preserves the normal workflow during local development, at the cost of making that upload slower. When Redis accepts a task but no worker is running, the task waits in the queue instead. No result backend is configured because the outcome is stored in the notification table.

## 8. Course chat over WebSockets

I built chat in three increments: Channels routing and an authenticated connection, then saved messages with access checks, then the browser interface. Daphne serves HTTP and WebSocket traffic through the project's ASGI application. HTTP still uses Django's normal handler; `/ws/courses/<id>/chat/` routes to an asynchronous consumer. `AuthMiddlewareStack` supplies the session, and `AllowedHostsOriginValidator` restricts connection origins [8].

Each course has a shared room for its teacher and enrolled, unblocked students. I moved the existing material-access rule into `permissions.py` so the HTTP chat view and socket use the same decision. On connection and each incoming or outgoing message, the consumer reloads the database-backed session and checks membership. This catches logout in another tab, removal and blocking during a connection. A revoked socket closes on its next activity; there is no separate background check of idle sockets.

The consumer accepts text of 1–1,000 characters. It saves the author and message before publishing a `chat.message` event to the course's Redis group. `database_sync_to_async` keeps synchronous ORM work out of the asynchronous consumer. Redis transports live events; SQLite retains history. Connecting loads the latest 50 saved messages in order. The frontend uses message IDs to avoid showing duplicates when history overlaps a broadcast, and inserts text with `textContent` so HTML stays text.

The page chooses `ws://` locally or `wss://` under HTTPS, shows connection status and disables sending after disconnection. Reconnect reloads the page and its saved history. This small interface supports the required teacher/student conversation without introducing a separate frontend framework.

## 9. User REST interface

The API exposes user data through DRF generic views in `accounts/api.py`, with serializers in `serializers.py`. This follows the lectures' separation between retrieving records and converting or validating their data [10]. All user endpoints require session authentication. The member list and detail return shared profile fields, exclude inactive/admin accounts, and omit email and password data. Photo values point to the existing authenticated photo view rather than raw media paths.

| Endpoint | Methods | Purpose |
| --- | --- | --- |
| `/api/users/` | GET | Shared member profiles, 20 per page |
| `/api/users/<id>/` | GET | One member's shared profile |
| `/api/users/me/` | GET, PATCH | Read your profile, including email; update name and biography |

The own-profile view takes its object from `request.user`, so an ID in submitted JSON cannot select another account. Its serializer accepts only first name, last name and biography as editable data, using the same length and blank-name rules as the HTML form. Identity, email and role are read-only; passwords and admin flags are not serializer fields. Photo changes remain on the existing upload form. Session-authenticated PATCH requests require a CSRF token.

I added `drf-spectacular` to generate OpenAPI from the views and serializers, with Swagger at `/api/docs/` [11]. Its sidecar package supplies the JavaScript and CSS locally, avoiding a CDN dependency during marking. The generated schema validates without warnings and the documentation's descriptions come from the API view docstrings.

## 10. Testing

The current suite contains 63 tests, run with `python manage.py test`. Tests use DRF's `APITestCase` and factory_boy, following the structure from my midterm. Factories provide predictable records and hashed passwords. Upload tests use temporary storage so they do not change real demonstration files.

Coverage focuses on the main workflows and ownership decisions: registration and login, profile editing, status posting, course creation/enrolment, material permissions, feedback, search and moderation. Invalid input and forged account IDs are checked where the application accepts changes. Separate database tests verify role values and duplicate enrolment constraints. Photo cleanup checks distinguish committed changes from rolled-back edits.

Four notification tests cover enrolment notices, private inboxes, material recipients and broker failure. The publisher is mocked while task logic uses the test database. Six asynchronous socket tests use Channels' `WebsocketCommunicator` [9] and an in-memory channel layer to check delivery/history, membership, invalid messages, blocking, logout and untrusted origins. Neither Redis nor Celery is required to run the tests.

Five API tests cover authenticated member data, read-only detail records, own-profile updates, invalid PATCH data and CSRF enforcement. Tests that need CSRF use `APIClient(enforce_csrf_checks=True)` because the normal test client skips that check. All 63 tests passed. This is focused coverage, not an exhaustive test of every field boundary or Django behaviour.

Browser walkthroughs complemented the suite. Separate teacher and student sessions exercised uploads/downloads, enrolment, feedback and moderation. Real Redis/Celery processes delivered a material notification, and real WebSockets carried two-way chat. Reloading restored chat history; blocking an open tab stopped the next message. Screenshots and overflow checks covered desktop and 320/390-pixel mobile layouts. A long unbroken course title exposed horizontal scrolling and was fixed by allowing the heading to wrap.

Swagger's Try it out successfully updated a temporary account using the session and CSRF token. Requests without that token were rejected, and another member's detail remained read-only. External browser requests were blocked during this check to verify local Swagger assets. Temporary accounts, courses and uploaded files were removed afterwards. The OpenAPI schema also passed `manage.py spectacular --validate --fail-on-warn`. These focused walkthroughs are not a complete accessibility or cross-browser audit.

## 11. Current local setup

The current development environment is macOS 26.6.2 with a separate Python 3.12.9 environment. The main dependencies are Django 5.2.17, DRF 3.18.1, factory_boy 3.3.3, Pillow 12.3.0, pypdf 6.18.1, Celery 5.6.3, Channels 4.3.2, Daphne 4.2.3 and drf-spectacular 0.29.0. The local Redis server is version 8.8.0. Pillow supports photo uploads, pypdf checks course materials, and Celery/Redis handle notifications. Django 5.2 was selected as the supported LTS alternative to the originally proposed 5.1 series [2]. Railway support adds psycopg for PostgreSQL, dj-database-url for its supplied connection string, and WhiteNoise for static assets. `requirements.txt` pins these packages and their dependencies. Redis must be installed separately for local use.

From the project directory, create an environment and install the dependencies:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

For background material notifications, run Redis and a Celery worker in separate terminals. The worker command runs from the project directory with the virtual environment activated:

```sh
redis-server --bind 127.0.0.1 --dir /tmp --dbfilename studyroom-redis.rdb
```

```sh
celery -A studyroom worker --loglevel=INFO --pool=solo
```

The local worker uses one process, suitable for the small SQLite demonstration. Redis listens on port 6379, database 0, with a `studyroom` task queue. Its development snapshot is in `/tmp`; deployment will need persistent storage. If Redis is already running on that port, use the existing local instance. Chat uses the same Redis server with a separate `studyroom-chat` key prefix. Daphne is first in `INSTALLED_APPS`, so `manage.py runserver` now serves ASGI and accepts WebSockets. Tests do not require Redis or Celery.

Open `http://127.0.0.1:8000/`. Registration is at `/accounts/register/`, login at `/accounts/login/`, the teacher student list at `/students/`, and administration at `/admin/`. Run the tests with `python manage.py test`; no demo-data loading is required for tests.

After login, Members opens `/members/` and My home opens the current user's `/members/<id>/` page. Edit my profile allows name, biography and photo changes; the status form is on the home page. Log in as another member to see the shared information without editing controls. Uploaded photos are stored in `media/profiles/`, which is excluded from Git but must be preserved when copying the populated application.

Courses opens `/courses/`; My courses opens `/courses/mine/`. A teacher can create a course, then upload its materials and view its roster from the detail page. A student sees an Enrol button until they have joined, after which the materials become available. Course files are stored in `media/course_materials/` and must also be included when copying the populated application.

The demo course, Database practice, belongs to Prof Grant and contains a sample PDF called Week one exercise. Bob and John are enrolled; Alice is not, allowing both download permission cases to be tried.

As Bob, open Database practice and choose Write or update your feedback. As Prof Grant, open Members to search, or the course's enrolled-student list to remove/block Bob. Each action explains its effect before confirmation. To restore access after a block, unblock Bob and then log in as Bob to enrol again.

Notifications opens `/courses/notifications/`. To demonstrate it, log in as Alice and enrol on Database practice, then check Prof Grant's inbox. Upload a new material as Prof Grant and refresh the enrolled student's inbox after the worker runs. Existing enrolments and files from before this feature do not create notices retroactively.

To try chat, open Database practice as Prof Grant and as an enrolled student in a separate browser profile or private window. Choose Open course chat on each course page and exchange messages. Refreshing restores the latest 50 messages. An unenrolled or blocked student cannot open the chat page or socket.

For the API, log in normally and open `/api/users/` or `/api/users/me/` in the browser. Swagger is at `/api/docs/`, with the schema at `/api/schema/`. In Swagger, expand PATCH `/api/users/me/`, choose Try it out, enter e.g. `{"biography": "Practising Django."}` and Execute. The normal login session and CSRF token are used automatically. A separate JSON client must send the session cookie and `X-CSRFToken` for PATCH.

The demo loader supplies these accounts:

| Username | Account |
| --- | --- |
| bob | Student, Bob |
| alice | Student, Alice |
| john | Student, John |
| grant | Teacher, Prof Grant |
| mark | Teacher, Mark |

For an empty database, run `python load_data.py`. The accounts use `password123!`, stored with Django's password hashing. This shared password is limited to non-administrator demonstration accounts. The script uses `get_or_create` to preserve later profile edits and moderation state. It supplies statuses, feedback, saved chat messages, a PDF and example notices without requiring a worker. A second teacher and course demonstrate separate ownership; Alice starts blocked from that course. Re-running the script creates missing examples rather than resetting later edits. The database is excluded from Git but will be included, together with the required media, in the submission ZIP. The virtual environment will be excluded from that ZIP.

I rehearsed setup in a separate project copy with a fresh virtual environment, database and media directory. Installation, migrations, all 63 tests and schema validation passed; the package dependency check found no conflicts. Running the loader twice kept record counts stable and preserved deliberately changed passwords, biography, block state and notification read state. `README.md` provides the shorter setup and demonstration walkthrough.

## 12. Deployment plan

> Planning note: Railway was selected because one project can contain the ASGI web service, PostgreSQL, Redis and a Celery worker [14]. A volume mounted on the web service preserves uploaded files [15]. The repository now contains its build and start commands, but the live deployment has not yet been carried out. After deployment I will verify HTTPS/WSS, permissions, uploads and persistence across restarts, then replace this note with the observed result.

## References

1. Django documentation, [Substituting a custom User model](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/#substituting-a-custom-user-model).
2. Django, [Supported versions](https://www.djangoproject.com/download/#supported-versions).
3. Django documentation, [File uploads](https://docs.djangoproject.com/en/5.2/topics/http/file-uploads/).
4. pypdf documentation, [PdfReader](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html).
5. Django documentation, [Performing actions after commit](https://docs.djangoproject.com/en/5.2/topics/db/transactions/#performing-actions-after-commit).
6. Django documentation, [Complex lookups with Q objects](https://docs.djangoproject.com/en/5.2/topics/db/queries/#complex-lookups-with-q-objects).

7. Celery documentation, [First steps with Django](https://docs.celeryq.dev/en/stable/django/first-steps-with-django.html).

8. Channels documentation, [Authentication](https://channels.readthedocs.io/en/stable/topics/authentication.html) and [WebSocket security](https://channels.readthedocs.io/en/stable/topics/security.html).
9. Channels documentation, [Testing](https://channels.readthedocs.io/en/stable/topics/testing.html).

10. Django REST framework, [Generic views](https://www.django-rest-framework.org/api-guide/generic-views/) and [Session authentication](https://www.django-rest-framework.org/api-guide/authentication/#sessionauthentication).
11. drf-spectacular, [Documentation](https://drf-spectacular.readthedocs.io/en/latest/readme.html).
12. Django documentation, [View decorators](https://docs.djangoproject.com/en/5.2/topics/http/decorators/).
13. Django documentation, [The admin site](https://docs.djangoproject.com/en/5.2/ref/contrib/admin/).
14. Railway documentation, [Deploy a Django app](https://docs.railway.com/guides/django).
15. Railway documentation, [Using volumes](https://docs.railway.com/volumes).

## 13. Critical evaluation

The account foundation reuses Django's password and session handling, leaving a small amount of application-specific code to inspect. The tests demonstrate that the role difference is enforced on a real page and cannot be selected through registration. Using one role field is sufficient for the coursework's two account types, but it would need reconsideration if a person could teach some courses and attend others as a student.

Creating teachers through admin prevents self-assignment of teacher privileges, but each new teacher needs an administrator's action. Email format is checked, but ownership of the address is not verified. Login also has no application-level rate limiting. First and last names are required by registration but remain optional on the admin form, so an administrator can create incomplete records. These are limits to address before using the account workflow for real students.

Serving photos through Django keeps member access checks in one place, but makes the web process handle each image request. A larger deployment would need to measure that cost before choosing a different delivery method. Upload limits are validated after Django receives the request; they do not replace request-size limits at the production web server.

Old profile photos are now deleted after committed replacement/removal, but the database and filesystem are still separate systems: a failed storage operation or a newly uploaded file followed by transaction rollback can leave an orphan. A periodic reconciliation would be useful for a deployed application. Course-material replacement/deletion through admin also leaves its old files on disk; there is no user-facing material replacement workflow yet. Images are validated but not resized or stripped of metadata. Status updates can be posted and read, but users cannot yet edit or delete individual posts; the admin can manage them.

Each course has one teacher and is available for enrolment as soon as it is created. There is no draft/published state, capacity limit or student withdrawal flow. This covers the current coursework workflow with a small schema, but a real teaching service would need to decide those policies. Role checks in model validation do not run on arbitrary ORM saves; the current web paths assign roles and relationships explicitly, while admin changes still require care. SQLite is sufficient for the local demonstration, but the sequential duplicate-enrolment tests do not establish behaviour under concurrent write load.

Keeping blocking on the enrolment made access rules easy to test, but it means that row existence alone no longer proves membership. Material notifications now exclude blocked records; chat also checks current course access. Removal and unblocking leave no moderation history; a service handling disputes would need reasons, timestamps and an audit trail. A permission check also cannot retract a file already downloaded, and concurrent moderation during an in-progress request has not been load-tested.

One editable feedback entry avoids repeated reviews from the same student, but does not preserve earlier versions. Retaining it after removal protects criticism, while abusive feedback still needs administrator intervention. Search is adequate for a small directory, although SQLite's case-insensitive matching is limited for non-ASCII text and it offers no ranking or typo correction. These are areas to revisit with realistic usage data.

Celery adds two processes to run and monitor. The direct fallback handles an unavailable broker during publishing, but is not a complete delivery guarantee: a worker crash, lost Redis data or exhausted database retries can still leave notices missing. There is no scheduled reconciliation or delivery dashboard. Notifications are triggered by the application's enrolment and upload views; direct admin/ORM changes do not send them. For a larger service I would review delivery monitoring and notification retention, and decide whether live updates are worth adding to the inbox.

Chat reuses course membership, which keeps its permissions understandable, but new members can read the recent history and messages cannot yet be edited or deleted individually. Only the latest 50 are loaded on connection; older messages remain stored without a browsing interface. Rechecking sessions and membership adds database work per event. A busy service would need to measure that cost and add message-rate limits. Saving before broadcasting preserves history if live delivery fails, but there are no delivery receipts or automatic resend: after a connection problem, users should reconnect and check the history before repeating a message.

The REST interface deliberately exposes profile data rather than every model. Reusing session authentication keeps it consistent with the website, but an independent mobile client would need an authentication design of its own. Profile validation now exists in both a form and serializer; future changes need to keep them aligned. Registration and photo updates remain in the HTML interface; the API does not offer password changes.
