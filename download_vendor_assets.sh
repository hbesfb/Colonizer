
# remove existing to start with fresh
rm -rf wheeldir wheeldir.tar wheeldir.tar.part-*
mkdir -p wheeldir

# FontAwesome
mkdir -p webdaemon/static/fontawesome
wget https://github.com/FortAwesome/Font-Awesome/releases/download/5.15.4/fontawesome-free-5.15.4-web.zip -O webdaemon/static/fontawesome/fontawesome-free-5.15.4-web.zip

# Bootstrap
mkdir -p webdaemon/static/bootstrap
wget https://github.com/twbs/bootstrap/archive/v4.6.2.zip -O webdaemon/static/bootstrap/v4.6.2.zip

# jQuery
mkdir -p webdaemon/static/jquery
wget https://code.jquery.com/jquery-3.7.1.min.js -O webdaemon/static/jquery/jquery.min.js
wget https://code.jquery.com/jquery-3.7.1.js -O webdaemon/static/jquery/jquery.js
wget https://code.jquery.com/jquery-3.7.1.min.map -O webdaemon/static/jquery/jquery.min.map

# jsoneditor
mkdir -p webdaemon/static/jsoneditor/img
wget https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.js -O webdaemon/static/jsoneditor/jsoneditor.js
wget https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.min.js -O webdaemon/static/jsoneditor/jsoneditor.min.js
wget https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.css -O webdaemon/static/jsoneditor/jsoneditor.css
wget https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/jsoneditor.min.css -O webdaemon/static/jsoneditor/jsoneditor.min.css
wget https://cdnjs.cloudflare.com/ajax/libs/jsoneditor/10.1.0/img/jsoneditor-icons.svg -O webdaemon/static/jsoneditor/img/jsoneditor-icons.svg

# TensorFlow.js
mkdir -p webdaemon/static/tensorflow
wget https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.8.0/dist/tf.min.js -O webdaemon/static/tensorflow/tf.min.js
wget https://cdn.jsdelivr.net/npm/@tensorflow/tfjs@4.8.0/dist/tf.min.js.map -O webdaemon/static/tensorflow/tf.min.js.map

# download and compress .whls files for packages in requirements_k8s.txt
pip download --python-version 3.11 --abi cp311 --platform manylinux2014_x86_64 --only-binary=:all: \
	-r requirements_k8s.txt -d wheeldir/ 

# Create reproducible tar archive
tar \
  --sort=name \
  --mtime='UTC 2020-01-01' \
  --owner=0 \
  --group=0 \
  --numeric-owner \
  -cf wheeldir.tar wheeldir

#Split archive into multiple chunks of less than 100MB and cleanup
split -b 90M wheeldir.tar wheeldir.tar.part-

#cleanup
rm -rf wheeldir/
rm wheeldir.tar


# rm -rf wheeldir
# mkdir wheeldir

# pip download \
#   --python-version 3.11 \
#   --abi cp311 \
#   --platform manylinux2014_x86_64 \
#   --only-binary=:all: \
#   -r requirements_k8s.txt \
#   -d wheeldir

# find wheeldir -type f -exec sha256sum {} \; | sort > checksums2.txt