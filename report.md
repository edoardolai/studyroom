# Studyroom — CM3035 Final Coursework

## 1. Introduction and development approach

I built Studyroom as a Django eLearning application. I needed to cover student and teacher accounts, courses, materials, feedback, notifications, a REST interface and real-time chat. I started from accounts and authentication because every later feature needed to know who was making the request and what that user was allowed to do.

I created the project skeleton first, followed by the custom user model and migration, registration, and login/logout. I used the teacher student list as the first place to prove that the two roles had different permissions. For the browser pages I used Django templates and forms, with normal views in `views.py` and registration validation in `forms.py`.

Next I added member home pages and biography editing. I added photo uploads after the editing workflow had ownership tests, then status updates introduced the first one-to-many relationship. I kept these changes in separate migrations so I could update existing accounts without recreating them.

I built courses in three steps: creation and browsing, enrolment and rosters, and finally uploaded materials. This order meant that every upload already had a course and an established download rule. During this work I found repeated home-page context in the normal view and the invalid status form path, so I moved that small piece into a helper.

I added teacher search to the existing member directory, then feedback for enrolled students and the remove/block controls on the roster. Blocking made me revisit downloads and home-page queries because an enrolment row could now mean that access was blocked. I could no longer treat the existence of that row as enough evidence of access.

## 2. Accounts and database design

I made `accounts.User` extend Django's `AbstractUser`. This kept Django's username, password, name and email fields, while I added a `role` with the two allowed values, student and teacher. One field makes the account types mutually exclusive. I used field choices for form validation and a database constraint for writes which bypass a form.

I used a custom user because the role belongs to the account and is needed whenever permissions are checked. `AbstractUser` keeps the standard authentication behaviour while allowing the additional field [1]. Configuring it before the first migration avoids replacing the user table once other models reference it. The admin extends `UserAdmin`, including the role on both its creation and editing forms.

I used `TextChoices` to keep each role value beside its display label. I also added a `CheckConstraint` so SQLite rejects another value even if the write happens outside a form. I then check the stored role in the views before allowing an action.

I kept the biography and optional photo on `User` because both belong to exactly one account. A separate profile table would add another join without giving this data a separate lifecycle. The photo column stores its path, while the file is saved under `MEDIA_ROOT`.

I placed status updates in their own table because one account can post many updates. Each `StatusUpdate` stores the author, text and creation time. I read the author's name through the foreign key instead of copying it, so changing a name also changes how old posts are displayed. I used cascade deletion because an update has no purpose without its author, and I ordered updates by creation time and primary key so ties are predictable.

For `Course`, I stored one teacher, a title, a description and the creation time. I used `PROTECT` for the teacher because deleting an account should not silently delete a course which students joined. I did not make titles unique because two teachers could reasonably use the same title; the URL uses the primary key.

I used `Enrolment` to join a student and course and record when they joined. A unique constraint on the pair stops duplicate enrolment. I added `is_blocked` with a false default so the migration preserved existing rows. A blocked row prevents re-enrolment, while removal deletes the row. I validate account roles in the model and still enforce them in the web views, where the account comes from the session.

In `CourseMaterial` I stored the title, file path, upload time and course foreign key. I did not repeat the teacher because it is already available through the course. This keeps account, course and material data in their own tables, while enrolment represents the student/course many-to-many relationship.

For `Feedback`, I stored the student, course, text and last update time. I made the student/course pair unique to give each student one editable entry. I reference both records directly, so removing an enrolment does not erase earlier feedback. I limited the text to 2,000 characters and did not add a rating because the requirement only asks for written feedback.

I made each `ChatMessage` belong to a course and author. The course already identifies the chat room, so I did not add a separate room table. I assign the sender from the authenticated session rather than submitted JSON.

I show these fields and relationships in the ER diagram below. I left out Django's supporting authentication and session tables so the application model stays readable.

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

I made public registration create student accounts only. I create or promote teachers through the admin, because a teacher option on the public form would let anybody give themselves access to student records. I extended `UserCreationForm` and explicitly listed username, first name, last name and email. I left the password fields and validation to Django and did not accept role or administration flags.

Login and logout use Django's built-in views and session authentication. Logout is a POST form with a CSRF token. Keeping the built-in login view also preserves its validation of the `next` destination: a user can return to a requested local page without the application redirecting them to an arbitrary external address supplied in the request.

The first teacher function is a paginated list of active student accounts. It shows username and real name, but not email or password information. Anonymous requests go to login; authenticated students receive 403. The template hides the student-list link from students, but the view checks the role independently, so entering the URL directly does not bypass the restriction. Teacher status is separate from `is_staff`: teachers have application permissions, while the staff flag controls entry to Django admin.

I used `login_required` to redirect anonymous visitors before a protected view runs, following the lectures' access-control pattern. Method decorators make each view's supported actions explicit: `require_POST` for enrolment and status submission, `require_http_methods(["GET", "POST"])` for forms, and `require_safe` for reading pages [12]. Unsupported methods receive HTTP 405. These checks do not establish course ownership or replace CSRF protection; the view still checks the role and relevant record. In admin, `admin.register` associates a model with its configuration, while `admin.display` labels the protected photo/material links [13].

The list covers active students across the site. To keep the table manageable as accounts are added, I used Django's `Paginator` to divide it into pages of 25. Since the page only displays records, `require_safe` limits it to GET and HEAD requests. The forms use `as_div` to render Django's fields and errors inside containers styled by the stylesheet.

## 4. Profiles, discovery and status updates

I added the Members page so students and teachers can find each other's home pages. I list active accounts but leave site administrators out of the directory. Each home page shows the member's name, username, role, biography, photo and status history. I require login and keep email addresses out of the directory and other members' pages.

I gave profile editing one route, `/accounts/profile/edit/`, with no target account ID. I pass `request.user` as the form instance, so an edit always applies to the logged-in account. The form lists the editable fields explicitly, which means an extra username, role, email or administration flag is ignored.

Photos use an `ImageField` and Pillow to check image content. The upload form uses `multipart/form-data`, and the view passes `request.FILES` alongside `request.POST` [3]. I limited uploads to JPEG and PNG, 2 MB, and 4096 pixels on either side to keep profile images reasonably bounded. Checking the content as well as the extension rejects a GIF renamed to `.png`. The shared field validator also applies when the model is validated through an admin form. It rewinds the file after inspecting it so storage can read the complete upload.

The photo URL identifies the account, and a Django view checks login and account activity before returning a `FileResponse`. The application does not expose a general `/media/` route. `never_cache` adds response headers telling browsers not to retain the authenticated image response. Removing a photo clears the current reference; trying to remove and replace it in the same submission returns an error rather than choosing one action silently. A review found that the admin's default file widget still linked to `/media/`, so its current-photo link was changed to use the authenticated route too.

Both students and teachers can post updates on their own home page. This covers the brief's student example and R1(i), which refers to users adding updates. A `ModelForm` validates non-blank text up to 500 characters. Only the text is accepted from the form: the view assigns the author from `request.user` before saving. Posting requires POST and a CSRF token. Status history is paginated in groups of ten, newest first. If validation fails, the existing updates remain visible alongside the error. Biography and status text use Django's template escaping, so submitted HTML is displayed as text.

The interface uses a shared template, labelled form fields and a small stylesheet. Members have a direct My home link, while other users' pages show neither the edit link nor the status form. Long text wraps inside the page, and the photo is displayed at a fixed size without stretching its aspect ratio. No JavaScript is needed for these forms.

## 5. Courses, enrolment and materials

I let members browse course descriptions before joining. Teachers create courses through a `ModelForm` exposing only title and description, while the view assigns the teacher from the session. Students enrol with a CSRF-protected POST. I used `get_or_create` as well as the unique database constraint so a repeated submission returns the existing enrolment. My courses changes its result according to the member's role.

The roster view checks that the requester is a teacher and retrieves the course filtered by that teacher. A different teacher cannot get a roster by changing the URL. Even enrolled students cannot open the roster. On home pages, teachers' courses are discoverable, while a student's enrolments are shown only to that student. These are different views of the same course relationships, rather than separately stored lists.

I allow only the course teacher to upload materials. The form accepts a title and file, and I take the course from the authorised URL lookup instead of a submitted field. Downloads check the same owner/enrolment rule used for the material list, so knowing an ID or storage path is not enough. I keep descriptions public to signed-in members but hide material titles and links from unenrolled students.

I used Pillow for JPEG/PNG checks and added `pypdf` to read PDF structure, rather than treating a `.pdf` extension as proof of a valid document. The PDF reader uses strict mode and requires an unencrypted document with at least one page [4]. Images must match their extension and fit within 4096 by 4096 pixels. All materials have a 10 MB limit. These checks reject unsupported, malformed and oversized uploads; they are not malware scanning. Strict PDF parsing can also reject a damaged document that a viewer would repair, so the user may need to export a clean copy.

Course logic lives in the `courses` app. The HTML views remain short functions; the shared `can_access_course` helper prevents the course page and download endpoint from making different permission decisions. Course lists, rosters and materials are paginated. `select_related` retrieves teacher/student details with the corresponding rows rather than issuing another query for each displayed name.

### Feedback and teacher search

An enrolled student can write or update feedback through a `ModelForm` exposing only the text. The course comes from the URL and the student from the session. `update_or_create` uses that pair to save an entry, so submitting the form again updates it. Feedback is visible to signed-in members browsing the course, including those considering enrolment, and the form explains this before submission. Output is escaped and paginated independently from materials. Removed and blocked students keep their existing feedback but cannot change it without active enrolment.

Teachers search the Members page by username, first name or surname. Each word must match at least one of those fields, so a query such as “Minerva McGonagall” can span first and last name. I used `Q` expressions to combine the alternatives within each word [6]. Results retain the directory's exclusions for inactive and administrator accounts, and do not expose email addresses. Students can still browse member home pages; supplying a non-empty search query as a student returns a permission error. Search text is limited to 150 characters, and pagination keeps it in the URL.

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

I wrote 63 automated tests and run them with `python manage.py test`. I used DRF's `APITestCase` and factory_boy in a similar structure to my midterm. The factories give me predictable records and correctly hashed passwords. Upload tests use temporary storage, so running the suite does not change the demonstration files. Following the lecturer's advice, I selected only eight representative tests to discuss here:

1. Registration creates a student and ignores submitted teacher or administrator fields.
2. A profile edit and status post always use the logged-in member, even if another account ID is submitted.
3. Repeating an enrolment request does not create a duplicate record or a second teacher notification.
4. An unenrolled, blocked or unrelated user cannot view or download protected course material.
5. Feedback can only be written by an enrolled student, and a second submission updates the same entry.
6. Course removal and blocking are limited to that course's teacher and immediately change the student's access.
7. A WebSocket test uses Channels' `WebsocketCommunicator` [9] to check authorised delivery and saved chat history; the surrounding socket tests cover access changes.
8. The REST test checks private-field filtering and confirms that a member can PATCH only their own allowed profile fields with CSRF protection.

The whole suite also checks validation and less common permission paths, but listing each case would repeat the code rather than explain my testing choices. I mock the Celery publisher where needed and use an in-memory channel layer, so Redis and a worker are not needed during tests. All 63 tests passed.

I also used separate teacher and student browser sessions for the full workflows. I tried uploads, enrolment, feedback, moderation, notifications and two-way chat. Reloading restored chat history, and blocking a student with their chat open stopped their next message. I checked the pages at a mobile width and used Swagger to update a temporary account while another member stayed read-only. These manual checks helped find integration and layout problems, but they are not a full accessibility or cross-browser audit.

## 11. Current local setup

The development environment is macOS 26.6.2 with Python 3.12.9. The main dependencies are Django 5.2.17, DRF 3.18.1, factory_boy 3.3.3, Pillow 12.3.0, pypdf 6.18.1, Celery 5.6.3, Channels 4.3.2, Daphne 4.2.3 and drf-spectacular 0.29.0. Django 5.2 was selected as the supported LTS alternative to the originally proposed 5.1 series [2]. Psycopg provides the deployed PostgreSQL connection, dj-database-url reads it from the environment, and WhiteNoise serves collected static assets. `requirements.txt` pins the packages and their dependencies.

The complete package and version list is:

```text
amqp==5.3.1
asgiref==3.12.1
attrs==26.1.0
autobahn==26.7.1
Automat==25.4.16
billiard==4.2.4
cbor2==6.1.4
celery==5.6.3
cffi==2.1.1
channels==4.3.2
channels_redis==4.3.0
click==8.5.0
click-didyoumean==0.3.1
click-plugins==1.1.1.2
click-repl==0.3.0
constantly==23.10.4
cryptography==46.0.5
daphne==4.2.3
Django==5.2.17
dj-database-url==3.0.1
djangorestframework==3.18.1
drf-spectacular==0.29.0
drf-spectacular-sidecar==2026.9.1
factory_boy==3.3.3
Faker==40.38.0
hyperlink==21.0.0
idna==3.19
Incremental==24.11.0
inflection==0.5.1
jsonschema==4.26.0
jsonschema-specifications==2025.9.1
kombu==5.6.2
msgpack==1.2.2
packaging==26.3
pillow==12.3.0
prompt_toolkit==3.0.53
psycopg==3.2.10
psycopg-binary==3.2.10
pyasn1==0.6.1
pyasn1_modules==0.4.2
pycparser==3.0
pyOpenSSL==25.3.0
pypdf==6.18.1
python-dateutil==2.9.0.post0
PyYAML==6.0.3
redis==6.4.0
referencing==0.37.0
rpds-py==2026.6.3
service-identity==24.2.0
six==1.17.0
sqlparse==0.6.0
Twisted==26.4.0
txaio==26.6.1
typing_extensions==4.16.0
tzdata==2026.4
tzlocal==5.4.4
ujson==6.0.0
uritemplate==4.2.0
vine==5.1.0
wcwidth==0.8.3
whitenoise==6.11.0
zope.interface==8.6
```

Extract the supplied source archive, then create an environment and install the dependencies:

```sh
unzip Studyroom_Source.zip -d Studyroom
cd Studyroom
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

The local worker uses one process and a `studyroom` queue. Chat shares Redis with a separate key prefix. Daphne is first in `INSTALLED_APPS`, so `manage.py runserver` serves ASGI and accepts WebSockets. Tests do not require Redis or Celery.

Open `http://127.0.0.1:8000/`. Registration is at `/accounts/register/`, login at `/accounts/login/`, the teacher student list at `/students/`, and administration at `/admin/`. Run the tests with `python manage.py test`; no demo-data loading is required for tests.

After login, Members opens `/members/` and My home opens the current user's `/members/<id>/` page. Edit my profile allows name, biography and photo changes; the status form is on the home page. Log in as another member to see the shared information without editing controls. Uploaded photos are stored in `media/profiles/`, which is excluded from Git but must be preserved when copying the populated application.

Courses opens `/courses/`; My courses opens `/courses/mine/`. A teacher can create a course, then upload its materials and view its roster from the detail page. A student sees an Enrol button until they have joined, after which the materials become available. Course files are stored in `media/course_materials/` and must also be included when copying the populated application.

The Potions course belongs to Professor Snape and contains a matching Potion ingredients PDF. Harry, Ron and Hermione are enrolled. Draco is blocked from Professor McGonagall's Transfiguration course, allowing the normal and blocked permission cases to be tried. The original seed PDFs are kept in `demo_materials/`; `load_data.py` copies them into `media/course_materials/`, where the populated database expects uploaded files. I kept these two locations separate so runtime uploads can change without removing the files needed to rebuild the demo.

As Harry, open Potions and choose Write or update your feedback. As Professor Snape, open Members to search, or the course roster to remove/block Harry. Each action explains its effect before confirmation. To restore access after a block, unblock the student and ask them to enrol again.

Notifications opens `/courses/notifications/`. To demonstrate it, log in as Draco and enrol on Potions, then check Professor Snape's inbox. Upload a new material as Snape and refresh the enrolled student's inbox after the worker runs. Existing enrolments and files from before this feature do not create notices retroactively.

To try chat, open Potions as Professor Snape and Harry in separate browser sessions. Choose Open course chat on each course page and exchange messages. Refreshing restores the latest 50 messages. An unenrolled or blocked student cannot open the chat page or socket.

For the API, log in and open `/api/users/` or `/api/users/me/`. Swagger is at `/api/docs/`, with the schema at `/api/schema/`. Its PATCH `/api/users/me/` operation can update the current biography. A separate JSON client must send the session cookie and `X-CSRFToken`.

The demo loader supplies these accounts:

| Username | Account |
| --- | --- |
| harry | Student, Harry Potter |
| ron | Student, Ron Weasley |
| hermione | Student, Hermione Granger |
| draco | Student, Draco Malfoy |
| snape | Teacher, Professor Snape |
| mcgonagall | Teacher, Professor McGonagall |
| admin | Django administrator |

For an empty database, run `python load_data.py`. All listed accounts use `password123!`, stored with Django's password hashing; `/admin/` is the administrator login. The script uses `get_or_create` to preserve later profile edits and moderation state. It supplies statuses, feedback, saved chat messages, two PDFs and example notices without requiring a worker. Re-running it creates missing examples rather than resetting later edits. The database and media will be included in the submission ZIP; the virtual environment will not.

I rehearsed setup in a fresh project copy. Installation, migrations, all 63 tests and schema validation passed, and the dependency check found no conflicts. Running the loader twice kept counts stable and preserved changed passwords, biographies and moderation state. `README.md` provides the shorter walkthrough.

## 12. Deployment

I first deployed the application on Railway. Its managed PostgreSQL and Redis services made the first setup quick, but the free allowance was time-limited. I do not know whether the coursework will be marked in one month or four months, so after reading the usage terms I decided that leaving it there risked either an unavailable demonstration or an unexpected charge.

I moved the final deployment to an Oracle Cloud Ubuntu 24.04 VM using its Always Free resources and the DuckDNS name `edoardo-studyroom.duckdns.org`. I had used the same basic VM, Docker Compose and DuckDNS approach for the website of my girlfriend's father, where the main requirement was to keep the running cost at zero. That earlier application was simpler, using Streamlit with Supabase as its database, but the experience made the server and DNS work familiar. Studyroom needed a larger Compose setup because it also runs PostgreSQL, Redis, a Celery worker and an ASGI web process.

The same application image is used for Daphne and Celery, reducing differences between the two Python processes. PostgreSQL, Redis and uploaded media use named volumes, while the database and broker have no public ports. Caddy is the only public service and provides HTTPS, redirects HTTP, and proxies both normal requests and secure WebSockets. Environment variables hold the domain, database password and Django secret outside Git. The web startup collects static files, applies migrations and runs the repeatable data loader before Daphne.

I built and exercised the ARM64 image locally before copying the setup to the VM. This exposed an incompatible `cryptography` wheel, which I replaced with a compatible maintained release rather than discovering it on the live server. On Oracle I confirmed HTTPS login, PostgreSQL and Redis health, the Celery worker, file access and two-way WSS chat. The live application is available at the DuckDNS address. Docker Compose makes the deployment repeatable, although one free VM is still a single point of failure and requires me to apply updates and monitor storage myself [14–16].

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
14. Docker documentation, [Control startup order](https://docs.docker.com/compose/how-tos/startup-order/).
15. Caddy documentation, [Automatic HTTPS](https://caddyserver.com/docs/automatic-https).
16. Oracle Cloud documentation, [Always Free Resources](https://docs.oracle.com/iaas/Content/FreeTier/freetier.htm).

## 13. Critical evaluation

I reused Django's password and session handling, which left me less application-specific security code to maintain. My tests show that the role difference is enforced on a real page and cannot be selected through registration. I think one role field is enough for the coursework's two account types, but I would reconsider it if one person could teach some courses and attend others as a student.

Creating teachers through admin prevents self-assignment of teacher privileges, but I accept that every new teacher needs an administrator's action. I check email format but do not verify who owns the address, and I have not added application-level login rate limiting. I would address these limits before using the account workflow for real students.

I serve photos through Django to keep the member access check in one place, although this makes the web process handle every image request. For a larger deployment I would measure that cost before choosing another delivery method. My upload validation also runs after Django receives the request, so it does not replace a request-size limit at the web server.

The database and filesystem remain separate systems, so a failed storage operation or transaction rollback can leave an orphan. Course-material changes through admin can also leave old files. Images are validated but not resized or stripped of metadata, and status updates have no user-facing edit or delete action.

Each course has one teacher and is available for enrolment as soon as it is created. There is no draft/published state, capacity limit or student withdrawal flow. This covers the current coursework workflow with a small schema, but a real teaching service would need to decide those policies. Role checks in model validation do not run on arbitrary ORM saves; the current web paths assign roles and relationships explicitly, while admin changes still require care. SQLite is sufficient for the local demonstration, but the sequential duplicate-enrolment tests do not establish behaviour under concurrent write load.

Keeping blocking on the enrolment made access rules easy to test, but it means that row existence alone no longer proves membership. Material notifications now exclude blocked records; chat also checks current course access. Removal and unblocking leave no moderation history; a service handling disputes would need reasons, timestamps and an audit trail. A permission check also cannot retract a file already downloaded, and concurrent moderation during an in-progress request has not been load-tested.

One editable feedback entry avoids repeated reviews from the same student, but does not preserve earlier versions. Retaining it after removal protects criticism, while abusive feedback still needs administrator intervention. Search is adequate for a small directory, although SQLite's case-insensitive matching is limited for non-ASCII text and it offers no ranking or typo correction. These are areas to revisit with realistic usage data.

Celery adds two processes to run and monitor. The direct fallback handles an unavailable broker during publishing, but is not a complete delivery guarantee: a worker crash, lost Redis data or exhausted database retries can still leave notices missing. There is no scheduled reconciliation or delivery dashboard. Notifications are triggered by the application's enrolment and upload views; direct admin/ORM changes do not send them. For a larger service I would review delivery monitoring and notification retention, and decide whether live updates are worth adding to the inbox.

Chat reuses course membership, which keeps its permissions understandable, but new members can read the recent history and messages cannot yet be edited or deleted individually. Only the latest 50 are loaded on connection; older messages remain stored without a browsing interface. Rechecking sessions and membership adds database work per event. A busy service would need to measure that cost and add message-rate limits. Saving before broadcasting preserves history if live delivery fails, but there are no delivery receipts or automatic resend: after a connection problem, users should reconnect and check the history before repeating a message.

The REST interface deliberately exposes profile data rather than every model. Reusing session authentication keeps it consistent with the website, but an independent mobile client would need an authentication design of its own. Profile validation now exists in both a form and serializer; future changes need to keep them aligned. Registration and photo updates remain in the HTML interface; the API does not offer password changes.
