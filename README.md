# Containerized Movie Explorer with Local AI

This challenge runs a movie browser, Flask API, MongoDB, and a local AI model as separate containers. The API filters movie records by category and asks Ollama for a short, grounded description of the movies in that category.

## Requirements

- Docker Engine with the Docker Compose plugin
- About 2 GB of free disk space for the default `llama3.2:1b` model; the first model download needs internet access

## Start the application

From this directory, run:

```sh
docker compose up --build -d
```

Compose builds the API and UI, starts MongoDB and Ollama, imports `mongo/init.json`, downloads the configured model, and then starts the application. The first start can take a few minutes while Docker downloads the model. To choose another Ollama model, set `OLLAMA_MODEL` before starting, for example `OLLAMA_MODEL=llama3.2:1b docker compose up --build -d`.

## Build images with tags

The application images are named for a Docker Hub namespace and version tag. For local development, Compose uses `local/movie-api:dev` and `local/movie-ui:dev`. For a release, set `DOCKERHUB_USER` to your Docker Hub username and set `IMAGE_TAG` to the release version:

```sh
export DOCKERHUB_USER="your-dockerhub-username"
export IMAGE_TAG="1.0.0"
docker login --username "$DOCKERHUB_USER"
docker compose build movie-api movie-ui
docker compose push movie-api movie-ui
docker image ls "$DOCKERHUB_USER/movie-api" "$DOCKERHUB_USER/movie-ui"
```

Docker prompts for a password or access token; use a Docker Hub access token. Do not put credentials in the Compose file or commit them. Use a release version such as `1.0.0` for a stable build, or a commit identifier such as `sha-a1b2c3d` for an image produced from a particular commit. In the trunk based workflow, CI can build and push a commit-tagged image from `main`, then add a version tag for a release. Avoid relying on `latest` for application releases.

## GitHub Actions deployment to this machine

`.github/workflows/deploy.yml` runs the backend tests on GitHub Actions, builds and pushes the API and UI images to Docker Hub, and deploys those images to a Linux self-hosted runner when code is pushed to `main` (or a `v*` release tag). Pull requests do not run on the self-hosted runner.

### 1. Put the project in a GitHub repository

Create a GitHub repository and push this project to its `main` branch. From an existing Git checkout, commit and push the deployment files:

```sh
git add .github/workflows/deploy.yml docker-compose.yml README.md .gitignore
git commit -m "Add GitHub Actions deployment"
git push origin main
```

This workspace may not itself be connected to GitHub. If `git status` reports that it is not a Git repository, create an empty repository on GitHub, clone it, then copy the project files into that clone without copying workspace metadata:

```sh
git clone https://github.com/YOUR_GITHUB_USER/YOUR_REPOSITORY.git ~/movie-app
rsync -av \
  --exclude='.git' --exclude='.agents' --exclude='.aws' --exclude='.codex' \
  /home/dtovar/CI-CD_challenge/ ~/movie-app/
cd ~/movie-app
git checkout -B main
git add .
git commit -m "Add movie app and deployment workflow"
git push -u origin main
```

Create Docker Hub repositories named `movie-api` and `movie-ui` under your account. In GitHub, open **Settings → Secrets and variables → Actions** and add:

| Name | Type | Value |
| --- | --- | --- |
| `DOCKERHUB_USER` | Repository variable | Your Docker Hub username |
| `DOCKERHUB_TOKEN` | Repository secret | A Docker Hub access token with permission to push and pull these repositories |

The username and image tag are configuration, not credentials. The access token stays in GitHub Secrets and is passed to `docker login` through standard input. This application does not currently configure MongoDB authentication, so it has no database password to store. MongoDB's host port is bound to `127.0.0.1` so it is not exposed to other machines on the network.

### 2. Register this computer as a self-hosted runner

On the GitHub repository, open **Settings → Actions → Runners → New self-hosted runner**. Choose Linux and follow GitHub's displayed download and configuration commands on the machine that should run the containers. Run the runner as a service so it can accept jobs after a reboot. The runner account needs permission to use Docker and Docker Compose.

On a Linux machine, if the runner account cannot access Docker, add that account to the Docker group, start a new login session, then verify access before registering or restarting the runner:

```sh
sudo usermod -aG docker "$USER"
newgrp docker
docker info
docker compose version
```

Before the first automated deploy, stop any manually started copy of this app on the machine so it does not hold the same ports:

```sh
docker compose down
```

The workflow expects the runner to have the default `self-hosted` and `linux` labels. Keep this repository private or restrict who can push to `main`; a self-hosted runner has access to the machine and its Docker engine.

### 3. Deploy

On a push to `main`, the workflow tests the code, publishes images tagged with the commit SHA, and deploys that exact tag to your machine. To make a versioned release, push a Git tag such as `v1.0.0`; the images are published and deployed with tag `1.0.0`.

You can also run **Actions → Movie App CI and Deploy → Run workflow** and supply an optional image tag. Check the workflow run for the test, publish, and deploy results. The deployed app is available on the runner machine at `http://localhost:8181`.

The deployment logs in with the GitHub Actions secret, pulls the tagged images, and starts the Compose stack without rebuilding. No credentials are written into the Dockerfiles or Compose file. The existing Docker Hub release remains available; this workflow publishes subsequent commits and releases there.

Open the UI at [http://localhost:8181](http://localhost:8181). Choose Drama, Comedy, or Thriller and use **Filter Movies** to browse. Use **AI category details** to ask the local model to summarize the selected category. The model is instructed to use only the titles and years from the database.

The API is available at `http://localhost:5001`:

```sh
curl "http://localhost:5001/api/movies?category=comedy"
curl "http://localhost:5001/api/category-details?category=comedy"
```

Services and ports:

| Service | Purpose | Host port |
| --- | --- | ---: |
| `movie-ui` | Browser interface | 8181 |
| `movie-api` | Movie and AI details API | 5001 |
| `movie-db` | MongoDB database | 27017 |
| `movie-ai` | Ollama local model API | 11434 |

The model weights persist in the `ollama-data` Docker volume, and movie data persists in `mongo-data`. Shut down the containers with `docker compose down`. To also erase the downloaded model and database, run `docker compose down --volumes`.

## API behavior

- `GET /api/movies?category=drama` returns matching movies; omit `category` to return all movies.
- `GET /api/category-details?category=drama` returns a generated description. A category is required. If the local model is not ready or reachable, the API returns HTTP 503.

## Tests and SonarQube

The workflow runs backend tests on a GitHub-hosted runner and uploads the coverage and JUnit reports. A SonarQube analysis job then runs on the self-hosted machine. It starts the persistent SonarQube container, waits for it to be ready at [http://localhost:9000](http://localhost:9000), analyzes the downloaded reports, and enforces the quality gate before images are published or deployed. The SonarQube data and extensions use persistent Docker volumes, so the server stays available after the workflow finishes.

One-time setup: after the first workflow starts SonarQube, open [http://localhost:9000](http://localhost:9000) on the self-hosted machine, complete the initial sign-in, create a project with key `movie-app`, and generate an analysis token. Add that token in the GitHub repository under **Settings → Secrets and variables → Actions → New repository secret** with the name `SONAR_TOKEN`. Then rerun the workflow. Do not commit the token. The self-hosted runner must have Docker Compose and permission to use Docker.

The workflow starts and analyzes SonarQube automatically on future runs. The `sonarqube` service binds to `127.0.0.1:9000`, so it is available only from the runner machine itself. Scanner settings are in `sonar-project.properties`; the scanner image is configured in `sonar/Dockerfile`. To stop SonarQube manually, run `docker compose --profile quality stop sonarqube` from the project directory.
