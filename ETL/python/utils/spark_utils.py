import pyspark
from pyspark.sql import functions as F
from pyspark.sql import SparkSession
import pymysql
from app.config import spark_settings


    
JDBC_CONFIG = {
    "driver": "com.mysql.cj.jdbc.Driver",
    "user": "root",
    "password": "password",
}

def get_spark_session():

    try:
        if spark_settings.spark_mode == 'local':
            spark = SparkSession.builder \
            .appName("LocalSparkTest") \
            .master("local[*]") \
            .config("spark.driver.memory", "4g") \
            .config("spark.jars.packages", "io.dataflint:dataflint-spark4_2.13:0.9.9") \
            .config("spark.plugins", "io.dataflint.spark.SparkDataflintPlugin") \
            .getOrCreate()
        elif spark_settings.spark_mode == 'k8_cluster':
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
        else:
            raise Exception('Invalid spark mode')
    except Exception as e:
        raise Exception('Unable to create pyspark')
    return spark


def read_table(db_name: str, table_name: str):
    spark = get_spark_session()
    return spark.read.format("jdbc").options(**JDBC_CONFIG).option("url", f"jdbc:mysql://host.docker.internal:3306/{db_name}").option("dbtable", table_name).load()

def write_table(db_name: str, table_name: str, dataframe: pyspark.sql.dataframe.DataFrame, mode='append'):
    try:
        dataframe.write.format("jdbc").options(**JDBC_CONFIG).option("url", f"jdbc:mysql://host.docker.internal:3306/{db_name}").option("dbtable", table_name)\
        .mode(mode).save()
    except Exception as e:
        print('Log: ', str(e))


def add_checksum(df, tracked_cols):
    return df.withColumn(
        "checksum",
        F.md5(F.concat_ws("||", *[F.col(c).cast("string") for c in tracked_cols]))
    )

