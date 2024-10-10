#!/bin/bash

# quit if any step fail
set -e

INSTALL_DIR=/app/Colonizer
echo Installing into $INSTALL_DIR

# check if root
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

# update apt
apt update
apt install upgrade -y

# install via apt
apt install -y --no-install-recommends python3-virtualenv
apt install -y --no-install-recommends unixodbc unixodbc-dev odbcinst git
apt install -y --no-install-recommends libcamera-dev libcap-dev
apt install -y --no-install-recommends nginx supervisor redis watchdog

# clone source code from git
cd /app
git clone https://github.com/elenhinan/Colonizer.git $INSTALL_DIR

# install python packages
apt install -y python3-libcamera python3-picamera2
cd $INSTALL_DIR
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# setup nginx and supervisor
cp -rv install/etc/* /etc/
ln -s /etc/nginx/sites-available/colonizer /etc/nginx/sites-enabled/colonizer
rm /etc/nginx/sites-enabled/default
systemctl stop nginx
systemctl disable nginx

# enable SPI
#raspi-config

# download and compile freetds (more recent version)
cd /tmp
wget -nv http://ftp.freetds.org/pub/freetds/stable/freetds-patched.tar.gz
tar -zxvf freetds-patched.tar.gz
rm freetds-patched.tar.gz
cd freetds-*
./configure --prefix=/usr --sysconfdir=/etc --with-unixodbc=/usr --with-tdsver=7.4
make
sudo make install
cd samples
sudo odbcinst -i -d -f unixodbc.freetds.driver.template

# install bootstrap 4.6
BOOTSTRAP_DIR=$INSTALL_DIR/webdaemon/static/bootstrap
mkdir -p $BOOTSTRAP_DIR
wget https://github.com/twbs/bootstrap/archive/v4.6.2.zip
unzip v4.6.2.zip
cp -r bootstrap-4.6.2/dist/* $BOOTSTRAP_DIR
cp -r bootstrap-4.6.2/scss $BOOTSTRAP_DIR

# install jquery
JQUERY_DIR=$INSTALL_DIR/webdaemon/static/jquery
mkdir -p $JQUERY_DIR
wget -nv https://code.jquery.com/jquery-3.7.1.min.js -P $JQUERY_DIR -O jquery.min.js
wget -nv https://code.jquery.com/jquery-3.7.1.js -P $JQUERY_DIR -O jquery.js
wget -nv https://code.jquery.com/jquery-3.7.1.min.map -P $JQUERY_DIR -O jquery.min.map

# install fontawesome 5
wget -nv https://use.fontawesome.com/releases/v5.15.4/fontawesome-free-5.15.4-web.zip
unzip fontawesome-free-5.15.4-web.zip
mv fontawesome-free-5.15.4-web $INSTALL_DIR/webdaemon/static/fontawesome

# install tensorflow js
TF_DIR=$INSTALL_DIR/webdaemon/static/tensorflow
mkdir -p $TF_DIR
wget -nv https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@3.9/dist/tf.min.js -P $TF_DIR
wget -nv https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@3.9/dist/tf.min.js.map -P $TF_DIR

# install jsoneditor js
JE_DIR=$INSTALL_DIR/webdaemon/static/jsoneditor
mkdir -p $JE_DIR $JE_DIR/img
wget -nv https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.js -P $JE_DIR
wget -nv https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.map -P $JE_DIR
wget -nv https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.css -P $JE_DIR
wget -nv https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/img/jsoneditor-icons.svg $JE_DIR/img

# install sass
cd /tmp
wget https://github.com/sass/dart-sass/releases/download/1.77.5/dart-sass-1.77.5-linux-arm64.tar.gz
unzip dart-sass-1.77.5-linux-arm64.tar.gz
mv dart-sass $INSTALL_DIR/sass

# compile css
cd $INSTALL_DIR/webdaemon/static
$INSTALL_DIR/sass/sass scss/bs_theme.scss css/bootstrap_themed.css

# create folder for smb share
mkdir -p /mnt/data

# setup auto-remount in crontab
crontab -e
add "*/5 * * * * grep -q "/mnt/petra" /proc/mounts || sudo mount /mnt/petra"
pico /etc/fstab
add "#//yourfileserver/sharename  /mnt/data      cifs    uid=colonizer,iocharset=utf8,file_mode=0700,dir_mode=0700,noserverino,credentials=/home/pi/.smbcredentials    0    0"
add "username=<username>\npassword=<password>" to ~/.smbcredentials

# set permissions
chown colonizer:www-data /mnt/data
chmod 770 /mnt/data
chown colonizer:www-data -R $INSTALL_DIR
find $INSTALL_DIR -type f -exec chmod 640 {} \;
find $INSTALL_DIR -type d -exec chmod 750 {} \;

# setup watchdog
apt install watchdog
cd $INSTALL_DIR
cp install/etc/watchdog.conf /etc/watchdog.conf
chown root:root /etc/watchdog.conf
chmod +x repair.sh
systemctl enable watchdog

# create folder
mkdir -p $INSTALL_DIR/{log,run}