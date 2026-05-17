# Dockerfile
FROM spark:python3

USER root

# Download MySQL Connector/J into Spark's jars directory
RUN curl -fsSL https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/8.3.0/mysql-connector-j-8.3.0.jar \
    -o /opt/spark/jars/mysql-connector-j-8.3.0.jar

USER spark