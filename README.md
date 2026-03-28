# ENPM634_midterm-Team22

## Run Instructions

From the repository root:

```bash
docker compose up -d --build
```

Open the application at [http://localhost:5000](http://localhost:5000).

To stop the application:

```bash
docker compose down
```

## Features

This is a microblogging site in which users can make short text posts and leave comments on other users' posts.

- User authentication: Users can register, log in and log out with session-based authentication.
- User profiles: Each user has a profile page with username, bio, avatar and published posts.
- Profile editing: Logged-in users can update their bio and upload an avatar image.
- Blog posts: Users can create, view, edit and delete their own blog posts.
- Comments: Logged-in users can leave comments on blog posts.
- Draft posts: Users can save drafts, review them later and publish them when ready.
- Search: Posts can be searched through the search page and matching titles are shown.
- Admin dashboard: Admin users can view all users and remove posts.
- Email settings: Users can request an email change and complete a verification step from settings.
- Mailbox view: Each account has a mailbox page that shows messages sent to the current account email. (Use the .local domain to receive messages here when registering).
- Password reset: Users can request a password reset link and set a new password through the recovery flow.
