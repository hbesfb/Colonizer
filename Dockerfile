
###############################################
# Stage 1 — Build Python dependencies + assets
###############################################
FROM python:3.11-slim-bookworm AS builder

ARG APP_HOME=/app/Colonizer

ENV APP_HOME=${APP_HOME} \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR ${APP_HOME}

# Build-time dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential=12.9 \
	libpq-dev=15.19-0+deb12u1 \
	curl=7.88.1-10+deb12u15 \
	unzip=6.0-28+deb12u1 \
	sassc=3.6.1+20201027-2+b1 \
	&& rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python3 -m venv ${APP_HOME}/venv

# Install Python dependencies
COPY requirements_k8s.txt .

RUN ${APP_HOME}/venv/bin/pip install \
		--no-cache-dir \
		-r requirements_k8s.txt

# Copy application files
COPY config/kubernetes.json ./config/
COPY migrations/initial_tables_k8s.sql ./migrations/
COPY hwlayer/client.py ./hwlayer/
COPY models ./models
COPY webdaemon ./webdaemon
COPY gunicorn_config.py kubernetes_startup.sh settings.py ./

# Bootstrap assets
WORKDIR ${APP_HOME}/webdaemon/static/bootstrap

RUN curl -fsSL \
		https://github.com/twbs/bootstrap/archive/v4.6.2.zip \
		-o /tmp/bootstrap.zip \
	&& unzip -q /tmp/bootstrap.zip -d /tmp \
	&& cp -r /tmp/bootstrap-4.6.2/dist/* ./ \
	&& mkdir -p scss \
	&& cp -r /tmp/bootstrap-4.6.2/scss/* scss/ \
	&& rm -rf /tmp/bootstrap-4.6.2 /tmp/bootstrap.zip

# FontAwesome assets
WORKDIR ${APP_HOME}/webdaemon/static/fontawesome

RUN curl -fsSL \
		https://use.fontawesome.com/releases/v5.15.4/fontawesome-free-5.15.4-web.zip \
		-o /tmp/fontawesome.zip \
	&& unzip -q /tmp/fontawesome.zip -d /tmp \
	&& cp -r /tmp/fontawesome-free-5.15.4-web/* ./ \
	&& rm -rf /tmp/fontawesome-free-5.15.4-web /tmp/fontawesome.zip

# Compile SCSS
WORKDIR ${APP_HOME}/webdaemon/static

RUN if [ -f scss/bs_theme.scss ]; then \
		sassc scss/bs_theme.scss css/bootstrap_themed.css; \
	fi


###############################################
# Stage 2 — Runtime
###############################################
FROM python:3.11-slim-bookworm AS runtime

ARG APP_USER=colonizer
ARG APP_HOME=/app/Colonizer

ENV APP_HOME=${APP_HOME} \
	PATH="${APP_HOME}/venv/bin:$PATH" \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR ${APP_HOME}

# Runtime dependencies - add later if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
	libgl1=1.6.0-1 \
	libglib2.0-0=2.74.6-2+deb12u9 \
	&& rm -rf /var/lib/apt/lists/*
	# add later if needed: libpq5=15.19-0+deb12u1 \

# Copy application and Python virtual environment
COPY --from=builder ${APP_HOME} ${APP_HOME}

# Create application user and required directories
RUN useradd -m -s /usr/sbin/nologin ${APP_USER} && \
	mkdir -p \
		"${APP_HOME}/run" \
		"/var/log/colonizer" \
		"/home/${APP_USER}/.config/matplotlib" && \
	chown -R ${APP_USER}:${APP_USER} \
		"${APP_HOME}" \
		"/home/${APP_USER}/.config" \
		"/var/log/colonizer" && \
	chmod -R 750 "${APP_HOME}" && \
	chmod +x "${APP_HOME}/kubernetes_startup.sh"

USER ${APP_USER}

EXPOSE 8000

ENTRYPOINT ["./kubernetes_startup.sh"]