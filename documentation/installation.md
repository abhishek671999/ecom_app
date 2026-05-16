## Installation of mysqlclient
brew install mysql-client pkg-config
export PKG_CONFIG_PATH="$(brew --prefix)/opt/mysql-client/lib/pkgconfig"
pip install mysqlclient


python -m uvicorn main:app --reload