# ENPM634_midterm-Team22

## Run Instructions

Use the published Docker Hub image:
 
 ```bash
 docker pull r1zzg0d/enpm634-midterm-team22:latest

 docker run -p 5000:5000 --name enpm634-app r1zzg0d/enpm634-midterm-team22:latest
 ```

Open the application at [http://localhost:5000](http://localhost:5000).

The published image supports both `linux/amd64` and `linux/arm64`.

### Troubleshooting

If port `5000` is already in use, start the container on a different host port such as `5008`:

```bash
docker run -p 5008:5000 --name enpm634-app r1zzg0d/enpm634-midterm-team22:latest
```

Then open the application at [http://localhost:5008](http://localhost:5008).

If you get a container-name conflict because `enpm634-app` already exists, remove the old container and start it again:

```bash
docker rm -f enpm634-app
docker run -p 5000:5000 --name enpm634-app r1zzg0d/enpm634-midterm-team22:latest
```

To stop the application:

```bash
docker stop enpm634-app
docker rm enpm634-app
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
- Mailbox view: Each account has a mailbox page that shows messages sent to the current account email. (Use the .local domain to receive messages here when registering, such as @test.local).
