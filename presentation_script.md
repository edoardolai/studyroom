# Studyroom presentation script

Target length: about 8–9 minutes. Text in **bold** is an action on screen and is not spoken.

## Before recording

- Open the project in the terminal and keep the Mermaid ER diagram ready.
- Have the local application, Redis and Celery stopped at the beginning.
- Prepare two browser sessions: a normal window for Harry and a private window for Snape.
- Keep `password123!` ready to paste, but do not leave the password visible longer than needed.
- Use the local application for the installation/test demonstration and the deployed address near the end.

## 0:00–0:35 — Introduction

**Show the project folder, then the home page.**

“Hi, this is Studyroom, my final coursework for Advanced Web Development. It is an eLearning application built with Django. The two main account types are students and teachers, and their permissions are different throughout the application. Students can enrol, post updates, give feedback and join course chats. Teachers can create courses, upload materials, search members and manage their enrolled students.”

## 0:35–1:15 — Installation and project structure

**Show `requirements.txt`, then the `accounts`, `courses` and `studyroom` folders.**

“The project targets Python 3.12. From a clean copy I create a virtual environment, activate it, and install the exact package versions from requirements.txt.”

**Run or show these commands:**

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python load_data.py
```

“I split the application into an accounts app and a courses app. Normal page views, REST views, serializers, forms, models and WebSocket consumers have separate files, so each part has a fairly limited job. The loader creates the demonstration data and can be run more than once without duplicating it.”

## 1:15–2:05 — Database design

**Show the rendered Mermaid ER diagram from the report. Zoom in enough to read the relationships.**

“This is the database model. I extended Django’s user model with a role, biography and photo. A user can write many status updates. Each course has one teacher, while enrolment joins students to courses. That many-to-many relationship needs its own model because it also stores the enrolment time and whether the student is blocked.”

**Point to Feedback, CourseMaterial, Notification and ChatMessage.**

“Feedback is unique for each student and course, so a student updates their existing feedback instead of creating duplicates. Course materials and chat messages belong to a course. Notifications have a recipient and can refer to a course or a new material. Foreign keys avoid copying user or course details into each table, and database constraints protect the role and unique relationship rules.”

## 2:05–2:35 — Tests

**Return to the terminal and run:**

```sh
python manage.py test
```

“The application has 63 tests. They cover authentication, role permissions, profile access, uploads, course enrolment, feedback, moderation, notifications, chat and the REST interface. The tests use temporary data, and upload tests use temporary storage so they do not alter the demonstration files.”

**Pause on the final `OK` result.**

## 2:35–3:00 — Start the complete local application

**In three terminals, start Redis, Celery and Django:**

```sh
redis-server --bind 127.0.0.1 --dir /tmp --dbfilename studyroom-redis.rdb
```

```sh
celery -A studyroom worker --loglevel=INFO --pool=solo
```

```sh
python manage.py runserver
```

“Redis is used by Channels for live messages and by Celery as its broker. Daphne serves the ASGI application, which is needed because the same project handles normal HTTP requests and WebSockets.”

## 3:00–4:05 — Student account, profile and courses

**Open `http://127.0.0.1:8000/`, log in as `harry`, and briefly show the navigation.**

“I am logged in as Harry, a student. His home page combines profile information, status updates and his current courses. Other authenticated users can discover this page, but only Harry gets the profile editing and status controls.”

**Post a short status such as `Revising for the Potions practical.` Show it appearing on the page.**

“The author comes from the session, rather than a value submitted by the browser.”

**Open Courses, then Potions. Show the Potion ingredients PDF and feedback.**

“Students can browse available courses and enrol themselves. An enrolled, non-blocked student can download the material and write one feedback entry for the course. Submitting again updates that entry. The PDF is checked as a real readable PDF during upload, rather than trusting only the filename.”

## 4:05–5:20 — Teacher permissions, search and moderation

**Switch to the private window, log in as `snape`, and open Members. Search for `Hermione Granger`.**

“This is Professor Snape’s teacher account. Teachers can search by username or by parts of a real name. A student can browse member pages but cannot use this search or open the teacher student-list view.”

**Open My courses, Potions, then the roster. Show the remove/block controls without confirming an action.**

“A teacher only sees rosters for courses they own. Removing an enrolment allows the student to enrol again. Blocking also stops course materials and chat access, and the teacher must unblock the student before they can re-enrol. These checks are in the views and WebSocket consumer as well as the templates.”

**Show the course creation form and material upload form. Do not submit unless a prepared test file is available.**

“The teacher creates a course through a model form, and ownership is assigned from the logged-in teacher. Material uploads accept PDF, JPEG and PNG files with size and content validation.”

## 5:20–6:05 — Notifications and Celery

**In the Harry window, use Draco instead if a fresh unenrolled example is needed. Enrol on Potions, then switch to Snape’s Notifications page.**

“When a student enrols, the teacher receives a notification saved with that enrolment. New material uses a Celery task because one upload can notify several students. Blocked and inactive accounts are excluded.”

**Upload a small prepared PDF as Snape. Show the Celery terminal receiving the task, then refresh Harry’s Notifications page.**

“The page now shows the new-material notification. Redis carries the task to the worker, while the resulting notification is stored in the database.”

## 6:05–7:10 — Real-time chat

**Open the Potions chat in the Harry and Snape sessions and place the windows side by side.**

“The real-time feature is a course chat implemented with Django Channels. The socket uses the existing Django session, and the consumer checks that the user currently has access to this course.”

**Send `Professor, should we add the crushed ingredients first?` as Harry. Reply `Yes, before heating the cauldron.` as Snape.**

“Both messages appear immediately without refreshing. Each message is stored before it is broadcast, so refreshing the page restores the recent history. The production version uses secure WSS through the same HTTPS domain.”

## 7:10–7:50 — REST interface

**Open `/api/docs/`, expand GET `/api/users/`, and execute it. Then show PATCH `/api/users/me/` without changing permanent data, or make a small biography update.**

“The REST interface uses Django REST Framework and session authentication. The list and detail endpoints expose shared profile information but exclude passwords, email addresses and admin flags. Another member is read-only. The `me` endpoint allows a user to update only their own name and biography. Swagger is generated from the OpenAPI schema and its assets are stored locally.”

## 7:50–8:35 — Deployment and conclusion

**Open `https://edoardo-studyroom.duckdns.org` and show that it loads over HTTPS. Briefly show `docker compose ps` on the VM if desired.**

“I deployed Studyroom on an Oracle Cloud Ubuntu VM. Docker Compose runs PostgreSQL, Redis, Celery, Daphne and Caddy. Caddy provides HTTPS and proxies both HTTP and WebSocket traffic. Database, Redis and uploaded files use persistent volumes, and the private services do not expose public ports.”

“I initially tried Railway because its managed services were quick to configure. Since I do not know when the project will be marked, I moved away from its time-limited free allowance. I had previously used an Oracle free VM, Docker and DuckDNS for a simpler Streamlit website, so I adapted that approach to this larger Django application.”

**Return to the Studyroom home page.**

“The finished application implements the required accounts, roles, profiles, courses, enrolment, feedback, moderation, notifications, REST API and real-time WebSocket feature. Thank you.”
