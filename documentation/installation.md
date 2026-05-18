## Installation of mysqlclient
brew install mysql-client pkg-config
export PKG_CONFIG_PATH="$(brew --prefix)/opt/mysql-client/lib/pkgconfig"
pip install mysqlclient


python -m uvicorn main:app --reload

ping host.docker.internal - if it doesn't work follow below steps
ipconfig getifaddr en0 -> copy this private IP address
sudo sh -c 'echo "192.168.0.113 host.docker.internal" >> /etc/hosts' -> append it to /etc/hosts