
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

echo "[STEP 0] Keeping stable Debian python3-openshot package"
echo "Note: Not building from source due to stability issues with Timeline API"
echo "Using system package python3-openshot (0.2.7) which is more stable"

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

# Prioritize /usr/local/lib/python3.11/dist-packages
alt = '/usr/local/lib/python3.11/dist-packages'
if alt not in sys.path:
  sys.path.insert(0, alt)

def try_import(path=None):
  if path and path not in sys.path:
    sys.path.insert(0, path)
  try:
    mod = importlib.import_module('openshot')
    print('OK: openshot imported from', getattr(mod, '__file__', 'unknown'))
    print('Has Project:', hasattr(mod, 'Project'))
    if hasattr(mod, 'Project'):
      sys.exit(0)
    else:
      print('ERROR: openshot module found but missing Project class')
      sys.exit(1)
  except Exception:
    traceback.print_exc()
    return 1

code = try_import()
if code:
  print('Import failed.')
  if os.path.isdir(alt):
    print('Listing', alt)
    print('\n'.join(sorted(os.listdir(alt))))
  sys.exit(2)
PYTEST
fi

echo "[STEP 6] Verify install"
python3 - <<'PYVERIFY'
import sys, importlib, traceback, os

# Prioritize /usr/local/lib/python3.11/dist-packages
alt = '/usr/local/lib/python3.11/dist-packages'
if alt not in sys.path:
  sys.path.insert(0, alt)

def try_import_and_report(path=None):
  if path and path not in sys.path:
    sys.path.insert(0, path)
  try:
    m = importlib.import_module('openshot')
    print('OK: openshot imported from', getattr(m, '__file__', 'unknown'))
    attrs = sorted([a for a in dir(m) if not a.startswith('_')])
    print('Top-level attributes:', ', '.join(attrs[:40]))
    print('Has Project attribute:', hasattr(m, 'Project'))
    if hasattr(m, 'Project'):
      print('SUCCESS: openshot module has Project class')
      return True
    else:
      print('WARNING: openshot module missing Project class')
      return False
  except Exception:
    traceback.print_exc()
    return False

ok = try_import_and_report()
if not ok:
  print('ERROR: openshot import failed or missing Project class')
  if os.path.isdir(alt):
    print('Contents of', alt)
    print('\n'.join(sorted(os.listdir(alt)))[0:10000])
  sys.exit(1)
sys.exit(0)
PYVERIFY

echo "========== BUILD COMPLETE =========="
ls -lh /usr/local/lib | grep openshot || true
ls -lh /usr/local/lib/python3.11/dist-packages | grep openshot || true

echo "[STEP 7] Configure Python to prioritize /usr/local/lib/python3.11/dist-packages"
# Create a .pth file to ensure /usr/local/lib/python3.11/dist-packages is in sys.path
echo "/usr/local/lib/python3.11/dist-packages" > /usr/local/lib/python3.11/site-packages/local-dist-packages.pth

# Also add to global environment for immediate use
echo 'export PYTHONPATH="/usr/local/lib/python3.11/dist-packages:$PYTHONPATH"' >> /etc/profile.d/openshot-python.sh
chmod +x /etc/profile.d/openshot-python.sh

echo ""
echo "========== BUILD SUCCESSFUL =========="
echo "libopenshot Python bindings installed successfully!"
echo "Version: $(python3 -c 'import sys; sys.path.insert(0, \"/usr/local/lib/python3.11/dist-packages\"); import openshot; print(openshot.OPENSHOT_VERSION_FULL)')"
echo ""
echo "The generate_openshot_project.py script has been updated to work with libopenshot."
echo "Test it with: python3 generate_openshot_project.py /workspace/test_data/test_audio.wav /workspace/test_data/photos output.osp"
echo "========================================="

echo "See $LOGFILE for full build log."
