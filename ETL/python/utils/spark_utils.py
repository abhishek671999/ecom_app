import pyspark
import mysql.connector
from pyspark.sql import SparkSession


spark = SparkSession.builder \
    .appName("EcomApp_MySQL_Read") \
    .master("spark://localhost:7077") \
    .config("spark.driver.host", "host.docker.internal")\
    .config("spark.driver.bindAddress", "0.0.0.0") \
    .config("spark.executor.extraClassPath", "/opt/spark/jars/mysql-connector-j-8.3.0.jar") \
    .config("spark.driver.extraClassPath", "/opt/spark/jars/mysql-connector-j-8.3.0.jar") \
    .config("spark.executor.memory", "512m") \
    .config("spark.executor.cores", "1") \
    .config("spark.cores.max", "2") \
    .getOrCreate()
    
JDBC_CONFIG = {
    "driver": "com.mysql.cj.jdbc.Driver",
    "user": "root",
    "password": "password",
}

def get_spark_session():
    return spark


def read_table(db_name: str, table_name: str):
    return spark.read.format("jdbc").options(**JDBC_CONFIG).option("url", f"jdbc:mysql://host.docker.internal:3306/{db_name}").option("dbtable", table_name).load()

def write_table(db_name: str, table_name: str, dataframe: pyspark.sql.dataframe.DataFrame):
    try:
        dataframe.write.format("jdbc").options(**JDBC_CONFIG).option("url", f"jdbc:mysql://host.docker.internal:3306/{db_name}").option("dbtable", table_name)\
        .option("truncate", "true").mode("overwrite").save()
    except Exception as e:
        print('Log: ', str(e))


def overwrite_table(db_name: str, table_name: str, dataframe: pyspark.sql.dataframe.DataFrame):
    try:
        # Step 1: Clear the table using DELETE (allows constraint bypass)
        conn = mysql.connector.connect(
            host="host.docker.internal",
            port=3306,
            database=db_name,
            user="root",
            password="password"
        )
        cursor = conn.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        cursor.execute(f"DELETE FROM {table_name};")  # Safe to bypass with FK checks = 0
        conn.commit()
        cursor.close()
        conn.close()
        print('Table cleared successfully')

        # Step 2: Append fresh data, forcing Spark's JDBC session to also ignore FKs
        dataframe.write.format("jdbc") \
            .options(**JDBC_CONFIG) \
            .option("url", f"jdbc:mysql://host.docker.internal:3306/{db_name}") \
            .option("dbtable", table_name) \
            .option("sessionInitStatement", "SET FOREIGN_KEY_CHECKS = 0;") \
            .mode("append") \
            .save()
            
        print('Data write successful')

    except Exception as e:
        print('Log: ', str(e))