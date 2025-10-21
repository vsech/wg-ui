#!/bin/bash
set -e

echo "Удаление директорий __pycache__ и файлов .pyc, .pyo..."
find . | grep -E "(/__pycache__$|\.pyc$|\.pyo$)" | xargs rm -rf

echo "Передача директории backend..."
scp -r app root@178.20.46.152:/opt/wg-ui/
scp -r requirements.txt root@178.20.46.152:/opt/wg-ui/
scp -r main.py root@178.20.46.152:/opt/wg-ui/
scp -r start.py root@178.20.46.152:/opt/wg-ui/
scp -r wg_installer.py root@178.20.46.152:/opt/wg-ui/
scp -r wg_const.py root@178.20.46.152:/opt/wg-ui/
scp -r frontend/dist/* root@178.20.46.152:/var/www/html/

#ssh root@178.20.46.152 "cd /opt/wg-ui && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
