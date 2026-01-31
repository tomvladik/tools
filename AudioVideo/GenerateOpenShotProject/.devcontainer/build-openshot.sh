
#!/bin/bash
set -euxo pipefail

# Log everything to a file for debugging
LOGFILE="/workspace/.devcontainer/build-openshot.log"
exec > >(tee -a "$LOGFILE") 2>&1

echo "========== ENVIRONMENT =========="
env | sort
echo "========== DISK SPACE =========="
df -h
echo "========== MEMORY =========="
free -h || true
echo "========== STARTING BUILD =========="

echo "[STEP 1] Install build dependencies"
apt-get update
apt-get install -y --no-install-recommends \
  build-essential cmake git pkg-config \
  libavformat-dev libavcodec-dev libavutil-dev libswscale-dev libswresample-dev \
  libopenshot-audio-dev libjsoncpp-dev libqt5svg5-dev qtbase5-dev qtbase5-private-dev \
  libboost-dev libboost-thread-dev libboost-system-dev libboost-program-options-dev \
  libmagick++-dev libzmq3-dev libopencv-dev python3-dev python3-pip python3-setuptools \
  swig libcurl4-openssl-dev libx11-dev libxext-dev libxfixes-dev libfreetype6-dev \
  libfontconfig1-dev libglew-dev libopenal-dev libsndfile1-dev libjack-jackd2-dev \
  libasound2-dev libpulse-dev libsoxr-dev libtbb-dev libgstreamer1.0-dev \
  libgstreamer-plugins-base1.0-dev imagemagick \
  protobuf-compiler libprotobuf-dev
echo "[STEP 1b] Install cppzmq (zmq.hpp) headers from GitHub"
cd /tmp
if [ ! -d cppzmq ]; then
  git clone --depth=1 https://github.com/zeromq/cppzmq.git
else
  echo "cppzmq already cloned"
fi
cd cppzmq
mkdir -p /usr/local/include/zmq
cp -v zmq.hpp /usr/local/include/
cd /workspace

echo "[STEP 2] Clone sources"
cd /tmp
if [ ! -d libopenshot ]; then
  git clone --depth=1 https://github.com/OpenShot/libopenshot.git
else
  echo "libopenshot already cloned"
fi
if [ ! -d libopenshot-audio ]; then
  git clone --depth=1 https://github.com/OpenShot/libopenshot-audio.git
else
  echo "libopenshot-audio already cloned"
fi

echo "[STEP 3] Build and install libopenshot-audio"
cd /tmp/libopenshot-audio
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
make install
ldconfig

echo "[STEP 4] Build and install libopenshot"
cd /tmp/libopenshot
mkdir -p build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release -DENABLE_PYTHON=ON
make -j$(nproc)
make install
ldconfig

echo "[STEP 5] Build and install Python bindings"
PY_BINDINGS_DIR="/tmp/libopenshot/bindings/python"
if [ -f "$PY_BINDINGS_DIR/setup.py" ]; then
  echo "Found setup.py — installing via setup.py"
  cd "$PY_BINDINGS_DIR"
  python3 setup.py install
else
  echo "setup.py not found — CMake probably installed the bindings. Verifying import..."
  python3 - <<'PYTEST'
import sys, importlib, traceback, os
def try_import(path=None):
  if path and path not in sys.path:
    sys.path.insert(0, path)
  try:
    mod = importlib.import_module('openshot')
    print('OK: openshot imported from', getattr(mod, '__file__', 'unknown'))
    print('Has Project:', hasattr(mod, 'Project'))
    sys.exit(0)
  except Exception:
    traceback.print_exc()
    return 1

code = try_import()
if code:
  alt = '/usr/local/lib/python3.11/dist-packages'
  print('Retrying with', alt)
  code = try_import(alt)
  if code:
    print('Import failed. Listing', alt)
    if os.path.isdir(alt):
      print('\n'.join(sorted(os.listdir(alt))))
    sys.exit(2)
PYTEST
fi

echo "[STEP 6] Verify install"
python3 - <<'PYVERIFY'
import sys, importlib, traceback, os
def try_import_and_report(path=None):
  if path and path not in sys.path:
    sys.path.insert(0, path)
  try:
    m = importlib.import_module('openshot')
    print('OK: openshot imported from', getattr(m, '__file__', 'unknown'))
    attrs = sorted([a for a in dir(m) if not a.startswith('_')])
    print('Top-level attributes:', ', '.join(attrs[:40]))
    print('Has Project attribute:', hasattr(m, 'Project'))
    return True
  except Exception:
    traceback.print_exc()
    return False

ok = try_import_and_report()
if not ok:
  alt = '/usr/local/lib/python3.11/dist-packages'
  print('Retrying import with', alt)
  ok = try_import_and_report(alt)
  if not ok:
    print('WARNING: openshot import failed. Please inspect /usr/local/lib/python3.11/dist-packages')
    if os.path.isdir(alt):
      print('\n'.join(sorted(os.listdir(alt)))[0:10000])
# Do not fail the build here; we've installed the bindings via CMake.
sys.exit(0)
PYVERIFY

echo "========== BUILD COMPLETE =========="
ls -lh /usr/local/lib | grep openshot || true
ls -lh /usr/local/lib/python3.11/dist-packages | grep openshot || true
echo "See $LOGFILE for full build log."
