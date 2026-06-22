###############################################
# Stage 1 — Builder
###############################################
FROM debian:bookworm-slim@sha256:b4aa902587c2e61ce789849cb54c332b0400fe27b1ee33af4669e1f7e7c3e22f AS builder

ARG APP_USER=colonizer
ENV DEBIAN_FRONTEND=noninteractive \
	APP_HOME=/app/Colonizer \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR $APP_HOME

ARG SNAPSHOT=20260612T000000Z
RUN printf '%s\n' \
	"deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/${SNAPSHOT}/ bookworm main" \
	"deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/${SNAPSHOT}/ bookworm-updates main" \
	"deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/${SNAPSHOT}/ bookworm-security main" \
	> /etc/apt/sources.list

# Build-time dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
	python3=3.11.2-1+b1 \
	python3-venv=3.11.2-1+b1 \
	python3-dev=3.11.2-1+b1 \
	python3-pip=23.0.1+dfsg-1 \
	build-essential=12.9 \
	gcc=4:12.2.0-3 \
	libpq-dev=15.18-0+deb12u1 \
	unzip=6.0-28 \
	sassc=3.6.1+20201027-2+b1 \
	libgl1=1.6.0-1 \
	libglib2.0-0=2.74.6-2+deb12u9 \
	&& rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements_k8s.txt .
COPY wheeldir.tar.part-* .

# concatenate all parts into one TAR, extract and remove TARs
RUN cat wheeldir.tar.part-* > wheeldir.tar \
	&& rm wheeldir.tar.part-* \
	&& tar -xf wheeldir.tar \
	&& rm wheeldir.tar

RUN python3 -m venv $APP_HOME/venv \
	&& $APP_HOME/venv/bin/pip install --no-index --find-links=$APP_HOME/wheeldir -r requirements_k8s.txt \
	&& rm -rf $APP_HOME/wheeldir

# Copy source
COPY . .

# unzip and cleanup frontend assets
WORKDIR $APP_HOME/webdaemon/static/bootstrap
RUN unzip -q v4.6.2.zip \
	&& cp -r bootstrap-4.6.2/dist/* ./ \
	&& cp -r bootstrap-4.6.2/scss ./ \
	&& rm -rf bootstrap-4.6.2 v4.6.2.zip

WORKDIR $APP_HOME/webdaemon/static/fontawesome
RUN unzip -oq fontawesome-free-5.15.4-web.zip \
	&& cp -r fontawesome-free-5.15.4-web/* ./ \
	&& rm -rf fontawesome-free-5.15.4-web fontawesome-free-5.15.4-web.zip

# Compile SCSS
WORKDIR $APP_HOME/webdaemon/static
RUN if [ -f scss/bs_theme.scss ]; then \
		sassc scss/bs_theme.scss css/bootstrap_themed.css; \
	fi

###############################################
# Stage 2 — Runtime
###############################################
FROM debian:bookworm-slim@sha256:b4aa902587c2e61ce789849cb54c332b0400fe27b1ee33af4669e1f7e7c3e22f AS runtime

ARG APP_USER=colonizer
ENV DEBIAN_FRONTEND=noninteractive \
	APP_HOME=/app/Colonizer \
	PATH="/app/Colonizer/venv/bin:$PATH" \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR $APP_HOME
ARG SNAPSHOT=20260612T000000Z
RUN printf '%s\n' \
	"deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/${SNAPSHOT}/ bookworm main" \
	"deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/${SNAPSHOT}/ bookworm-updates main" \
	"deb [check-valid-until=no] https://snapshot.debian.org/archive/debian-security/${SNAPSHOT}/ bookworm-security main" \
	> /etc/apt/sources.list

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
	python3=3.11.2-1+b1 \
	python3-venv=3.11.2-1+b1 \
	libpq5=15.18-0+deb12u1 \
	redis-tools=5:7.0.15-1~deb12u6 \
	postgresql-client=15+248+deb12u1 \
	nginx=1.22.1-9+deb12u8 \
	fish=3.6.0-3.1+deb12u1 \
	sudo=1.9.13p3-1+deb12u2 \
	libgl1=1.6.0-1 \
	libglib2.0-0=2.74.6-2+deb12u9 \
	curl=7.88.1-10+deb12u14 \
	&& rm -rf /var/lib/apt/lists/*

# Copy app + venv from builder. Remove wheeldir, not needed at runtime
COPY --from=builder /app/Colonizer /app/Colonizer
RUN rm -rf $APP_HOME/wheeldir

# Install nginx config
RUN rm -f /etc/nginx/sites-enabled/default && \
	cp install/etc/nginx/sites-available/colonizer /etc/nginx/sites-enabled/colonizer

# Create user
RUN useradd -m -s /usr/bin/fish ${APP_USER} && \
	mkdir -p /home/${APP_USER}/.config/fish

# Ensure Matplotlib can write its cache directoryto remove "permission denied" warnings in logs
RUN mkdir -p /home/${APP_USER}/.config/matplotlib && \
	chown -R ${APP_USER}:${APP_USER} /home/${APP_USER}/.config

# Permissions
RUN chown -R ${APP_USER}:${APP_USER} $APP_HOME && \
	chmod -R 750 $APP_HOME && \
	mkdir -p /app/Colonizer/run /var/log/colonizer && \
	chown -R ${APP_USER}:www-data /app/Colonizer/run && \
	chmod 770 /app/Colonizer/run && \
	chown -R ${APP_USER}:${APP_USER} /var/log/colonizer && \
	chmod 755 /var/log/colonizer

# Make startup script executable
RUN chmod +x "$APP_HOME/kubernetes_startup.sh"

USER ${APP_USER}

EXPOSE 8000

ENTRYPOINT ["./kubernetes_startup.sh"]