FROM python:3.12-slim

# ---------------- Build args ----------------
ARG NO_PROXY
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG APP_USER=colonizer

# ---------------- Environment ----------------
ENV HTTP_PROXY=${HTTP_PROXY} \
	http_proxy=${HTTP_PROXY} \
	HTTPS_PROXY=${HTTPS_PROXY} \
	https_proxy=${HTTP_PROXY} \
	NO_PROXY=${NO_PROXY} \
	no_proxy=${NO_PROXY} \
	PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	DEBIAN_FRONTEND=noninteractive \
	APP_HOME=/app/Colonizer

WORKDIR $APP_HOME

# ---------------- System dependencies ----------------
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential=12.12 \
	libgl1=1.7.0-1+b2 \
	libglib2.0-0 \
	gcc=4:14.2.0-1 \
	libpq-dev \
	curl=8.14.1-2 \
	wget=1.25.0-2 \
	unzip=6.0-29 \
	git \
	redis-server=5:8.0.2-3 \
	postgresql-client=17+278 \
	python3-venv=3.13.5-1 \
	nodejs=20.19.2+dfsg-1 \
	npm=9.2.0~ds1-3 \
	nginx \
	&& rm -rf /var/lib/apt/lists/*

# ---------------- Install Sass globally ----------------
RUN npm install -g sass@1.91.0

# ---------------- Create user ----------------
RUN useradd -m -s /bin/bash ${APP_USER}

# ---------------- Frontend assets ----------------
WORKDIR $APP_HOME/webdaemon/static/bootstrap
RUN wget -q https://github.com/twbs/bootstrap/archive/v4.6.2.zip \
	&& unzip -q v4.6.2.zip \
	&& cp -r bootstrap-4.6.2/dist/* ./ \
	&& cp -r bootstrap-4.6.2/scss ./ \
	&& rm -rf bootstrap-4.6.2 v4.6.2.zip

WORKDIR $APP_HOME/webdaemon/static/jquery
RUN wget -q https://code.jquery.com/jquery-3.7.1.min.js -O jquery.min.js \
	&& wget -q https://code.jquery.com/jquery-3.7.1.js -O jquery.js \
	&& wget -q https://code.jquery.com/jquery-3.7.1.min.map -O jquery.min.map

WORKDIR $APP_HOME/webdaemon/static/fontawesome
RUN wget -q https://use.fontawesome.com/releases/v5.15.4/fontawesome-free-5.15.4-web.zip \
	&& unzip -oq fontawesome-free-5.15.4-web.zip \
	&& mv fontawesome-free-5.15.4-web/* ./ \
	&& rm -rf fontawesome-free-5.15.4-web fontawesome-free-5.15.4-web.zip

WORKDIR $APP_HOME/webdaemon/static/jsoneditor
RUN wget -q https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.js \
	&& wget -q https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.min.js \
	&& wget -q https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.css \
	&& wget -q https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.min.css \
	&& wget -q https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/img/jsoneditor-icons.svg -P img

# ---------------- Copy application & requirements ----------------
WORKDIR $APP_HOME
COPY requirements.txt . 
COPY . .

# ---------------- Python virtual environment ----------------
RUN python3 -m venv $APP_HOME/venv \
	&& $APP_HOME/venv/bin/pip install --no-cache-dir --upgrade pip \
	&& $APP_HOME/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------------- SCSS compilation ----------------
WORKDIR $APP_HOME/webdaemon/static
RUN if [ -f scss/bs_theme.scss ]; then \
		sass scss/bs_theme.scss css/bootstrap_themed.css; \
	fi

# Ensure venv executables are always in PATH
ENV PATH="$APP_HOME/venv/bin:$PATH"

# ---------------- Nginx ----------------
WORKDIR $APP_HOME
RUN rm -f /etc/nginx/sites-enabled/default \
	&& cp install/etc/nginx/sites-available/colonizer /etc/nginx/sites-enabled/colonizer

# ---------------- Set ownership ----------------
RUN chown -R ${APP_USER}:www-data $APP_HOME

# ---------------- Switch to non-root user ----------------
USER ${APP_USER}