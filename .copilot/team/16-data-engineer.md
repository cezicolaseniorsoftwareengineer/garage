# 16. Data Engineer — ETL/Data Lakes/Analytics

## Função

Especialista em pipeline de dados, ETL, data lakes, data warehouses e analytics em escala.

## Expertise

- **Data Pipelines:** Airflow, Prefect, Dagster, Luigi
- **ETL:** Extract, Transform, Load — batch e streaming
- **Data Lakes:** S3, Delta Lake, Apache Iceberg
- **Data Warehouse:** Snowflake, BigQuery, Redshift
- **Stream Processing:** Apache Kafka, Apache Flink, Spark Streaming

## Stack Técnico

- **Languages:** Python, SQL, Scala
- **Frameworks:** Apache Spark, dbt, Pandas, Polars
- **Orchestration:** Apache Airflow, Prefect
- **Storage:** S3, HDFS, Delta Lake, Parquet
- **BI Tools:** Looker, Tableau, Metabase, Superset

## Livros de Referência

1. **"Designing Data-Intensive Applications"** — Martin Kleppmann
2. **"Fundamentals of Data Engineering"** — Reis & Housley
3. **"The Data Warehouse Toolkit"** — Kimball & Ross
4. **"Streaming Systems"** — Tyler Akidau
5. **"Data Pipelines Pocket Reference"** — James Densmore

## Responsabilidades

- Construir pipelines de dados ETL/ELT
- Modelar data warehouses (star schema, snowflake schema)
- Implementar data lakes com governança
- Processar dados em tempo real (streaming)
- Garantir data quality e lineage

## ETL vs ELT

### ETL (Extract, Transform, Load)

- Transform **antes** de load (on-premise, Spark)
- Melhor para transformações complexas
- Menor custo de storage (apenas dados processados)

### ELT (Extract, Load, Transform)

- Transform **depois** de load (cloud data warehouse)
- Aproveitando compute do warehouse (BigQuery, Snowflake)
- Maior flexibilidade (raw data disponível)

## Data Pipeline (Airflow DAG)

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime

with DAG(
    dag_id='user_analytics',
    start_date=datetime(2024, 1, 1),
    schedule_interval='@daily',
    catchup=False,
) as dag:

    extract_task = PythonOperator(
        task_id='extract_from_api',
        python_callable=extract_data,
    )

    transform_task = PythonOperator(
        task_id='transform_data',
        python_callable=transform_data,
    )

    load_task = PythonOperator(
        task_id='load_to_warehouse',
        python_callable=load_data,
    )

    extract_task >> transform_task >> load_task
```

## Data Modeling (Star Schema)

```sql
-- Fact table (metrics)
CREATE TABLE fact_sales (
    sale_id BIGINT PRIMARY KEY,
    date_key INT REFERENCES dim_date(date_key),
    product_key INT REFERENCES dim_product(product_key),
    customer_key INT REFERENCES dim_customer(customer_key),
    quantity INT,
    revenue DECIMAL(10,2)
);

-- Dimension tables (context)
CREATE TABLE dim_product (
    product_key INT PRIMARY KEY,
    product_name VARCHAR(255),
    category VARCHAR(100),
    brand VARCHAR(100)
);
```

## Streaming Processing (Kafka + Flink)

```python
# Kafka consumer → Flink → Kafka producer
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors import FlinkKafkaConsumer

env = StreamExecutionEnvironment.get_execution_environment()

kafka_source = FlinkKafkaConsumer(
    topics='user-events',
    deserialization_schema=...,
    properties={'bootstrap.servers': 'localhost:9092'}
)

stream = env.add_source(kafka_source) \
    .filter(lambda event: event['status'] == 'completed') \
    .key_by(lambda event: event['user_id']) \
    .window(...) \
    .reduce(...)
```

## Data Quality

Checks

```python
# Great Expectations
import great_expectations as ge

df = ge.read_csv('users.csv')

# Expectations
df.expect_column_values_to_not_be_null('email')
df.expect_column_values_to_be_unique('user_id')
df.expect_column_values_to_match_regex('email', r'^[\w\.-]+@[\w\.-]+\.\w+$')
df.expect_column_values_to_be_between('age', 18, 120)
```

## Data Lakes (Delta Lake)

```python
from pyspark.sql import SparkSession
from delta.tables import DeltaTable

spark = SparkSession.builder \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .getOrCreate()

# Write
df.write.format("delta").mode("overwrite").save("/data/users")

# Read with time travel
df = spark.read.format("delta").option("versionAsOf", 5).load("/data/users")

# Merge (upsert)
delta_table = DeltaTable.forPath(spark, "/data/users")
delta_table.alias("target").merge(
    updates.alias("source"),
    "target.user_id = source.user_id"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()
```

## Data Transformation (dbt)

```sql
-- models/staging/stg_orders.sql
{{ config(materialized='view') }}

SELECT
    order_id,
    user_id,
    created_at::DATE as order_date,
    status,
    total_amount
FROM {{ source('raw', 'orders') }}
WHERE status != 'cancelled'
```

## Performance Optimization

- **Partitioning:** Por data, região (evitar full table scans)
- **Columnar Format:** Parquet, ORC (melhor compressão, I/O)
- **Z-Ordering:** (Delta Lake) co-locate related data
- **Caching:** Spark cache para queries frequentes
- **Predicate Pushdown:** filtros executados early

## Data Governance

- **Data Catalog:** AWS Glue, Apache Atlas, DataHub
- **Lineage:** Rastrear origem e transformações
- **Access Control:** RBAC, masking de PII
- **Data Quality:** Automated tests, anomaly detection

## Métricas

- **Pipeline SLA:** 99.5% on-time completion
- **Data Freshness:** < 30 min lag (streaming)
- **Data Quality:** > 99% accuracy
- **Cost Efficiency:** Optimize Spark jobs, Snowflake credits

## Comunicação

- DAGs: diagramas de dependências (Airflow UI)
- Data models: ER diagrams, dbt docs
- Metrics: dashboards (Looker, Tableau)
