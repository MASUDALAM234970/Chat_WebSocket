# ⚡ Real-Time Chat Application
### Django Channels · WebSocket · JWT Auth · REST API

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tech Stack](#tech-stack)
3. [Project Structure](#project-structure)
4. [Installation & Setup](#installation--setup)
5. [REST API Reference](#rest-api-reference)
6. [WebSocket Protocol](#websocket-protocol)
7. [Postman Testing Guide](#postman-testing-guide)
8. [Authentication Flow](#authentication-flow)
9. [Database Models](#database-models)
10. [Deployment](#deployment)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT (Browser / App)                   │
│                                                                 │
│   REST requests ──────────────────────────► HTTP/HTTPS          │
│   WebSocket connection ────────────────────► ws:// / wss://     │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DAPHNE / ASGI SERVER                          │
│                                                                 │
│   ProtocolTypeRouter                                            │
│   ├── HTTP  ──► Django (DRF REST API + JWT Auth)                │
│   └── WebSocket ──► JWTAuthMiddleware                           │
│                        └──► URLRouter                           │
│                               └──► ChatConsumer (AsyncWS)       │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                  CHANNEL LAYER (Redis)                          │
│                                                                 │
│   group: chat_<room-slug>  ──► all connected consumers          │
│   group: user_<user-id>    ──► personal notifications           │
└───────────────────────┬─────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATABASE (SQLite / PostgreSQL)                │
│                                                                 │
│   User  ──  Room  ──  RoomMember  ──  Message  ──  ReadStatus   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Component        | Technology                      |
|------------------|---------------------------------|
| Framework        | Django 4.2                      |
| Real-Time        | Django Channels 4.0 (WebSocket) |
| ASGI Server      | Daphne                          |
| Channel Backend  | Redis via channels-redis         |
| REST API         | Django REST Framework 3.14      |
| Authentication   | SimpleJWT (JWT tokens)          |
| API Docs         | drf-spectacular (Swagger/ReDoc) |
| CORS             | django-cors-headers             |
| Database         | SQLite (dev) / PostgreSQL (prod)|

---

## Project Structure

```
realtime_chat/
├── manage.py
├── requirements.txt
│
├── realtime_chat/               # Project config
│   ├── settings.py              # All settings including Channels
│   ├── asgi.py                  # ASGI + Channels routing
│   ├── wsgi.py
│   └── urls.py                  # Root URL config
│
├── accounts/                    # User auth app
│   ├── models.py                # Custom User model
│   ├── serializers.py           # Registration, login, profile
│   ├── views.py                 # Auth + user API views
│   └── urls.py
│
├── chat/                        # Chat app
│   ├── models.py                # Room, Message, RoomMember, ReadStatus
│   ├── consumers.py             # ⭐ WebSocket consumer (ChatConsumer)
│   ├── middleware.py            # JWT auth for WebSocket
│   ├── routing.py               # WebSocket URL patterns
│   ├── serializers.py
│   ├── views.py                 # REST API views
│   ├── urls.py                  # REST URL patterns
│   └── ui_urls.py               # Browser test UI
│
├── templates/
│   └── chat/
│       ├── index.html           # Landing page
│       └── room.html            # Browser WebSocket test UI
│
└── docs/
    ├── README.md                # This file
    └── RealTimeChat_API.postman_collection.json
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Redis server running on `localhost:6379`
- pip

### Step 1 — Clone & install dependencies

```bash
cd realtime_chat
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2 — Configure environment

Edit `realtime_chat/settings.py` or create a `.env` file:

```ini
SECRET_KEY=your-secret-key-here
DEBUG=True
REDIS_URL=redis://127.0.0.1:6379
```

### Step 3 — Run Redis

```bash
# macOS (Homebrew)
brew services start redis

# Ubuntu / Debian
sudo systemctl start redis

# Docker
docker run -d -p 6379:6379 redis:alpine
```

### Step 4 — Apply migrations

```bash
python manage.py makemigrations accounts
python manage.py makemigrations chat
python manage.py migrate
```

### Step 5 — Create superuser (optional)

```bash
python manage.py createsuperuser
```

### Step 6 — Start the server

```bash
# Development (Daphne ASGI server — supports HTTP + WebSocket)
daphne -b 0.0.0.0 -p 8000 realtime_chat.asgi:application

# OR using Django's runserver (Channels patches it automatically)
python manage.py runserver
```

> ⚠️ For WebSocket support in development, Daphne is recommended.

### Step 7 — Access

| URL | Purpose |
|-----|---------|
| `http://localhost:8000/` | Landing page |
| `http://localhost:8000/api/docs/` | Swagger UI |
| `http://localhost:8000/api/redoc/` | ReDoc |
| `http://localhost:8000/admin/` | Django Admin |

---

## REST API Reference

### Base URL
```
http://localhost:8000/api/v1/
```

### Authentication Header
All protected endpoints require:
```
Authorization: Bearer <access_token>
```

---

### 🔐 Auth Endpoints

#### POST `/auth/register/`
Register a new user account.

**Request Body:**
```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "StrongPass123!",
  "password_confirm": "StrongPass123!",
  "bio": "Hello world"
}
```

**Response 201:**
```json
{
  "message": "User registered successfully.",
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "bio": "Hello world",
    "avatar_url": "https://ui-avatars.com/...",
    "is_online": false,
    "last_seen": "2024-01-01T00:00:00Z",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

#### POST `/auth/login/`
Authenticate and receive JWT tokens.

**Request Body:**
```json
{
  "email": "alice@example.com",
  "password": "StrongPass123!"
}
```

**Response 200:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com",
    "is_online": false
  }
}
```

---

#### POST `/auth/token/refresh/`
Get a new access token using the refresh token.

**Request Body:**
```json
{ "refresh": "<refresh_token>" }
```

---

#### POST `/auth/logout/`
Blacklist the refresh token.

**Request Body:**
```json
{ "refresh_token": "<refresh_token>" }
```

---

#### GET `/auth/profile/`
Get the authenticated user's profile.

#### PATCH `/auth/profile/`
Update username, bio, avatar.

#### GET `/auth/users/`
List all users (for starting new chats).

#### GET `/auth/users/{id}/`
Get a specific user's public profile.

#### PUT `/auth/change-password/`
Change password.

```json
{
  "old_password": "StrongPass123!",
  "new_password": "NewPass456!",
  "confirm_password": "NewPass456!"
}
```

---

### 🏠 Room Endpoints

#### GET `/chat/rooms/`
List all rooms the authenticated user is a member of.

**Response:**
```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "name": "General Discussion",
      "slug": "general-discussion-abc123",
      "room_type": "group",
      "members_count": 5,
      "last_message": {
        "id": 42,
        "content": "Hey everyone!",
        "sender": "alice",
        "created_at": "2024-01-01T10:00:00Z"
      },
      "unread_count": 3
    }
  ]
}
```

---

#### POST `/chat/rooms/`
Create a new group room.

**Request Body:**
```json
{
  "name": "Project Alpha",
  "description": "Team room for Project Alpha",
  "room_type": "group",
  "is_private": false,
  "member_ids": [2, 3, 4]
}
```

---

#### POST `/chat/rooms/direct/`
Get or create a 1-on-1 DM room.

```json
{ "user_id": 2 }
```

---

#### GET `/chat/rooms/{slug}/`
Room details.

#### PATCH `/chat/rooms/{slug}/`
Update room (admin only).

#### DELETE `/chat/rooms/{slug}/`
Delete room (admin only).

#### GET `/chat/rooms/{slug}/members/`
List room members with roles.

#### POST `/chat/rooms/{slug}/members/add/`
Add a user to the room (admin only).
```json
{ "user_id": 5 }
```

#### POST `/chat/rooms/{slug}/leave/`
Leave a room.

---

### 💬 Message Endpoints

#### GET `/chat/rooms/{slug}/messages/`
Paginated message history (oldest first).

**Query params:** `?page=1`

**Response:**
```json
{
  "count": 150,
  "next": "http://localhost:8000/api/v1/chat/rooms/general-abc/messages/?page=2",
  "results": [
    {
      "id": 1,
      "sender": {
        "id": 1,
        "username": "alice",
        "avatar_url": "..."
      },
      "content": "Hello everyone!",
      "message_type": "text",
      "is_edited": false,
      "is_deleted": false,
      "reply_to": null,
      "created_at": "2024-01-01T09:00:00Z"
    }
  ]
}
```

---

#### POST `/chat/messages/`
Send a message via REST (also broadcasts to WebSocket). Use for file uploads.

```json
{
  "room": 1,
  "content": "Hello from REST!",
  "message_type": "text"
}
```

---

#### PATCH `/chat/messages/{id}/`
Edit a message (sender only). Broadcasts `message_edited` to WebSocket.

```json
{ "content": "Updated message content" }
```

---

#### DELETE `/chat/messages/{id}/`
Soft-delete a message. Broadcasts `message_deleted` to WebSocket.

#### POST `/chat/messages/{id}/read/`
Mark a message as read (creates a read receipt).

---

## WebSocket Protocol

### Connection URL

```
ws://localhost:8000/ws/chat/<room-slug>/?token=<jwt_access_token>
```

> **Authentication:** The JWT access token must be passed as a query parameter because browsers cannot set custom headers on WebSocket connections.

### Error Codes

| Code | Meaning |
|------|---------|
| 4001 | Not authenticated (missing/invalid token) |
| 4003 | Not a member of this room |

---

### Messages: Client → Server

#### Send a chat message
```json
{
  "type": "chat_message",
  "message": "Hello world!"
}
```

#### Reply to a message
```json
{
  "type": "chat_message",
  "message": "I agree!",
  "parent_id": 42
}
```

#### Typing indicators
```json
{ "type": "typing_start" }
{ "type": "typing_stop" }
```

#### Mark message as read
```json
{
  "type": "mark_read",
  "message_id": 99
}
```

#### Ping / keepalive
```json
{ "type": "ping" }
```

---

### Messages: Server → Client

#### On connect — message history
```json
{
  "type": "message_history",
  "messages": [
    {
      "id": 1,
      "content": "Hey!",
      "sender_id": 2,
      "sender_username": "bob",
      "sender_avatar": "https://...",
      "created_at": "2024-01-01T08:00:00Z",
      "message_type": "text",
      "parent_id": null,
      "is_edited": false
    }
  ]
}
```

#### New message
```json
{
  "type": "chat_message",
  "message_id": 101,
  "room_slug": "general-abc123",
  "content": "Hello world!",
  "sender_id": 1,
  "sender_username": "alice",
  "sender_avatar": "https://...",
  "parent_id": null,
  "created_at": "2024-01-01T10:30:00Z",
  "message_type": "text"
}
```

#### Typing indicator
```json
{
  "type": "typing_indicator",
  "user_id": 3,
  "username": "charlie",
  "is_typing": true
}
```

#### User presence (online/offline)
```json
{
  "type": "user_presence",
  "user_id": 2,
  "username": "bob",
  "is_online": true
}
```

#### Read receipt
```json
{
  "type": "read_receipt",
  "message_id": 99,
  "user_id": 2,
  "username": "bob"
}
```

#### Message edited
```json
{
  "type": "message_edited",
  "message_id": 45,
  "new_content": "Corrected message"
}
```

#### Message deleted
```json
{
  "type": "message_deleted",
  "message_id": 45
}
```

#### Pong (keepalive response)
```json
{
  "type": "pong",
  "timestamp": "2024-01-01T10:00:00Z"
}
```

#### Error
```json
{
  "type": "error",
  "message": "Message cannot be empty."
}
```

---

## Postman Testing Guide

### Import Collection

1. Open Postman → **Import**
2. Select `docs/RealTimeChat_API.postman_collection.json`
3. Collection opens with all folders and requests

### Set Variables

Go to the collection's **Variables** tab:

| Variable | Value |
|----------|-------|
| `base_url` | `http://127.0.0.1:8000` |
| `access_token` | *(auto-filled after Login)* |
| `refresh_token` | *(auto-filled after Login)* |
| `room_slug` | *(auto-filled after Create Room)* |
| `message_id` | *(auto-filled after Send Message)* |

### Quick Start Flow

```
1. 🔐 Auth → Register User       → creates your account
2. 🔐 Auth → Login               → access_token auto-saved
3. 🏠 Rooms → Create Group Room  → room_slug auto-saved
4. 💬 Messages → Get History     → paginated messages
5. 💬 Messages → Send Message    → message_id auto-saved
6. 🔌 WebSocket → Connect        → real-time chat!
```

### WebSocket Testing in Postman

1. Click **New** → **WebSocket**
2. URL: `ws://127.0.0.1:8000/ws/chat/{{room_slug}}/?token={{access_token}}`
3. Click **Connect**
4. In the **Message** box, paste and send:

```json
{ "type": "chat_message", "message": "Hello from Postman WebSocket!" }
```

5. Watch real-time responses appear in the Messages panel

---

## Authentication Flow

```
┌──────────┐      POST /auth/register/     ┌──────────────┐
│  Client  │ ─────────────────────────────► │    Django    │
│          │ ◄─────────────────────────────  │    REST API  │
│          │      201 { user: {...} }        │              │
│          │                                │              │
│          │      POST /auth/login/         │              │
│          │ ─────────────────────────────► │              │
│          │ ◄─────────────────────────────  │              │
│          │  200 { access, refresh, user } │              │
│          │                                │              │
│          │  GET /api/... (Bearer token)   │              │
│          │ ─────────────────────────────► │              │
│          │                                │              │
│          │  ws://host/ws/chat/room/?token=│              │
│          │ ─────────────────────────────► │  Channels    │
│          │      WebSocket connected       │  Consumer    │
└──────────┘                                └──────────────┘
```

- **Access token** lifetime: 24 hours
- **Refresh token** lifetime: 7 days (rotated on use)
- **WebSocket auth**: JWT passed as `?token=` query param

---

## Database Models

### User (accounts_user)
| Field | Type | Notes |
|-------|------|-------|
| id | AutoField | PK |
| username | CharField | Unique |
| email | EmailField | Unique, login field |
| password | CharField | Hashed |
| avatar | ImageField | Optional |
| bio | TextField | 300 chars max |
| is_online | BooleanField | Updated on WS connect/disconnect |
| last_seen | DateTimeField | Updated on disconnect |

### Room (rooms)
| Field | Type | Notes |
|-------|------|-------|
| id | AutoField | PK |
| name | CharField | Display name |
| slug | SlugField | Unique URL identifier |
| room_type | CharField | `group` or `direct` |
| is_private | BooleanField | |
| created_by | FK→User | |
| members | M2M→User | Through RoomMember |

### RoomMember (room_members)
| Field | Type | Notes |
|-------|------|-------|
| room | FK→Room | |
| user | FK→User | |
| role | CharField | `admin` or `member` |
| joined_at | DateTimeField | |
| is_muted | BooleanField | |

### Message (messages)
| Field | Type | Notes |
|-------|------|-------|
| id | AutoField | PK |
| room | FK→Room | |
| sender | FK→User | Nullable (deleted users) |
| content | TextField | |
| message_type | CharField | `text`, `image`, `file`, `system` |
| file | FileField | Optional attachment |
| parent | FK→self | For threaded replies |
| is_edited | BooleanField | |
| is_deleted | BooleanField | Soft delete |

### MessageReadStatus (message_read_statuses)
| Field | Type | Notes |
|-------|------|-------|
| message | FK→Message | |
| user | FK→User | |
| read_at | DateTimeField | |

---

## Deployment

### Production Checklist

```python
# settings.py
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com']
SECRET_KEY = os.environ['SECRET_KEY']

# Use PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ['DB_HOST'],
    }
}

# Redis for Channels
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': { 'hosts': [os.environ['REDIS_URL']] },
    }
}

# CORS
CORS_ALLOWED_ORIGINS = ['https://yourdomain.com']
```

### Nginx + Daphne

```nginx
# /etc/nginx/sites-available/chat
upstream daphne {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name yourdomain.com;

    location /ws/ {
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://daphne;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /static/ {
        alias /var/www/chat/staticfiles/;
    }
}
```

### Start with systemd

```ini
# /etc/systemd/system/chat.service
[Unit]
Description=RealTime Chat Django Channels
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/chat
ExecStart=/var/www/chat/venv/bin/daphne -b 0.0.0.0 -p 8000 realtime_chat.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable chat
systemctl start chat
```

---

## Quick Reference

```bash
# Run migrations
python manage.py migrate

# Start server (with WebSocket support)
daphne -b 0.0.0.0 -p 8000 realtime_chat.asgi:application

# Collect static files
python manage.py collectstatic

# Create admin
python manage.py createsuperuser

# API Docs
open http://localhost:8000/api/docs/
```

---

*Built with Django Channels 4.0 · WebSocket · JWT Authentication*
