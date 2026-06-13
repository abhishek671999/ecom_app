-- ============================================================
-- OLAP DDL — Ecom / Food Delivery App
-- Star Schema — Data Warehouse
-- Database: MySQL 8.0+ / Redshift / BigQuery / Snowflake
-- ============================================================

-- =======================================================s=====
-- DIMENSION TABLES
-- Slowly Changing Dimension Type 2 (SCD2) where noted
-- Dimension tables surround the central fact table
-- ============================================================


-- ============================================================
-- 1. dim_date
-- Pre-populated date dimension — one row per calendar day
-- Allows fast slicing by day / month / quarter / year
-- without expensive date functions on the fact table
-- ============================================================
create database if not exists ecom_olap_db;
use ecom_olap_db;

CREATE TABLE dim_date (
    date_id        INT           NOT NULL COMMENT 'Format: YYYYMMDD e.g. 20240101',
    full_date      DATE          NOT NULL,
    day            TINYINT       NOT NULL COMMENT '1-31',
    month          TINYINT       NOT NULL COMMENT '1-12',
    month_name     VARCHAR(10)   NOT NULL COMMENT 'January ... December',
    quarter        TINYINT       NOT NULL COMMENT '1-4',
    year           SMALLINT      NOT NULL,
    day_of_week    TINYINT       NOT NULL COMMENT '1=Monday ... 7=Sunday',
    day_name       VARCHAR(10)   NOT NULL COMMENT 'Monday ... Sunday',
    is_weekend     TINYINT(1)    NOT NULL DEFAULT 0,
    is_holiday     TINYINT(1)    NOT NULL DEFAULT 0,
    week_of_year   TINYINT       NOT NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Date dimension — pre-populated, one row per calendar day';


-- ============================================================
-- 2. dim_customer
-- SCD Type 2 — preserves full history of customer changes
-- Multiple rows per customer when city/address changes
-- valid_to = NULL means current active record
-- ============================================================
CREATE TABLE dim_customer (
    surrogate_key        INT           NOT NULL,
    customer_id          INT           NOT NULL ,
    name                 VARCHAR(100)  NOT NULL,
    mobile_number        VARCHAR(15)   NOT NULL,
    email                VARCHAR(150)      NULL,
    address              VARCHAR(2000) NOT NULL,
    city                 VARCHAR(100)  NOT NULL,
    locality             VARCHAR(100)  NOT NULL,
    pincode              VARCHAR(10)   NOT NULL,
    status               VARCHAR(20)   NOT NULL DEFAULT 'active',

    -- SCD Type 2 validity window
    valid_from           DATETIME      NOT NULL,
    valid_to             DATETIME          NULL COMMENT 'NULL = current active record',
    is_current           TINYINT(1)    NOT NULL,

    created_at           DATETIME      NOT NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Customer dimension — SCD Type 2, full history preserved';


-- ============================================================
-- 3. dim_restaurant
-- SCD Type 2 — preserves restaurant name / location history
-- ============================================================
CREATE TABLE dim_restaurant (
    restaurant_id      INT           NOT NULL,
    name                   VARCHAR(150)  NOT NULL,
    mobile_number          VARCHAR(15)   NOT NULL,
    address              VARCHAR(2000) NOT NULL,
    city                 VARCHAR(100)  NOT NULL,
    locality             VARCHAR(100)  NOT NULL,
    pincode              VARCHAR(10)   NOT NULL,
    status               VARCHAR(20)   NOT NULL,

    -- SCD Type 2 validity window
    valid_from             DATETIME      NOT NULL,
    valid_to               DATETIME          NULL COMMENT 'NULL = current active record',
    is_current             TINYINT(1)    NOT NULL,

    created_at             DATETIME      NOT NULL

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Restaurant dimension — SCD Type 2';


-- ============================================================
--  dim_delivery_partner
-- SCD Type 1 — overwrite current record
-- (history of delivery partner location not usually needed)
-- ============================================================
CREATE TABLE dim_delivery_partner (
    delivery_partner_id   INT           NOT NULL,
    name                      VARCHAR(100)  NOT NULL,
    mobile_number             VARCHAR(15)   NOT NULL,
    address                   VARCHAR(2000) NOT NULL,
    city                      VARCHAR(100)  NOT NULL,
    locality                  VARCHAR(100)  NOT NULL,
    pincode                   VARCHAR(10)   NOT NULL,
    status                    VARCHAR(20)   NOT NULL,
    created_at                DATETIME      NOT NULL,
    updated_at                DATETIME      NOT NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Delivery partner dimension — SCD Type 1 (overwrite)';

-- ============================================================
-- FACT TABLES
-- Central tables — append only, never update
-- Store foreign keys to dimensions + measurable values
-- ============================================================

-- ============================================================
-- 7. fact_order_events  (Base Fact Table)
-- One row per order event (created, paid, delivered etc.)
-- Append only — ETL inserts here nightly from order_events
-- Never update rows in this table
-- ============================================================
CREATE TABLE fact_orders(
    order_id                  BIGINT          NOT NULL COMMENT 'OLTP order_id',

    -- order metadata
    create_timestamp          DATETIME            NULL,
    confirmed_timestamp       DATETIME            NULL,
    prepared_timestamp        DATETIME            NULL,
    OFD_timestamp             DATETIME            NULL,
    delivered_timestamp       DATETIME            NULL,
    cancelled_timestamp       DATETIME            NULL,

    -- Foreign keys to dimension tables
    dim_date_id               INT             NOT NULL,
    dim_customer_id           INT             NOT NULL,
    dim_restaurant_id         INT             NOT NULL,
    dim_delivery_partner_id   INT                 NULL COMMENT 'NULL until partner is assigned',

    -- Measures (what actually gets aggregated)
    order_amount                    DECIMAL(10, 2)  NOT NULL,
    order_quantity                  INT             NOT NULL,
    order_item_collection			JSON			NOT NULL,
    

    -- ETL audit columns
    etl_batch_id              VARCHAR(50)         NULL COMMENT 'ETL run identifier for traceability',
    etl_loaded_at             DATETIME        NOT NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Base fact table — one row per order event, append only';

-- ============================================================
-- AGGREGATE FACT TABLES (Sub Fact Tables)
-- Pre-summarised for dashboard / reporting performance
-- Refreshed nightly by ETL after base fact is loaded
-- Queries hit these instead of scanning fact_order_events
-- ============================================================


-- ============================================================
-- 8. fact_orders_daily_agg
-- Daily aggregation — orders and revenue per restaurant per day
-- Powers daily sales dashboards
-- ============================================================
CREATE TABLE fact_orders_daily_agg (
    dim_date_id          INT             NOT NULL,
    dim_restaurant_id    INT             NOT NULL,
    dim_location_id      INT             NOT NULL,

    -- Pre-aggregated measures
    total_orders         INT             NOT NULL,
    total_revenue        DECIMAL(15, 2)  NOT NULL,
    avg_order_value      DECIMAL(10, 2)  NOT NULL,
    total_items_sold     INT             NOT NULL,
    unique_customers     INT             NOT NULL,

    -- ETL audit
    etl_loaded_at        DATETIME        NOT NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Daily aggregate fact — revenue and orders per restaurant per day';


-- ============================================================
-- 9. fact_orders_monthly_agg
-- Monthly aggregation — for trend reports and BI dashboards
-- ============================================================
CREATE TABLE fact_orders_monthly_agg (
    year                 SMALLINT        NOT NULL,
    month                TINYINT         NOT NULL,
    dim_restaurant_id    INT             NOT NULL,

    -- Pre-aggregated measures
    total_orders         INT             NOT NULL,
    total_revenue        DECIMAL(15, 2)  NOT NULL,
    avg_order_value      DECIMAL(10, 2)  NOT NULL,
    total_items_sold     INT             NOT NULL,
    unique_customers     INT             NOT NULL,

    -- ETL audit
    etl_loaded_at        DATETIME        NOT NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Monthly aggregate fact — revenue trends per restaurant';


-- ============================================================
-- ETL SUPPORT TABLE
-- ============================================================


-- ============================================================
-- 10. olap_etl_log
-- Audit log for every ETL run — helps debug and replay
-- ============================================================
CREATE TABLE olap_etl_log (
    id               INT           NOT NULL,
    batch_id         VARCHAR(50)   NOT NULL COMMENT 'Unique ID per ETL run',
    table_name       VARCHAR(100)  NOT NULL,
    rows_extracted   INT           NOT NULL,
    rows_loaded      INT           NOT NULL,
    status           VARCHAR(20)   NOT NULL COMMENT 'running | success | failed',
    error_message    TEXT              NULL,
    started_at       DATETIME      NOT NULL,
    completed_at     DATETIME          NULL
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='ETL audit log — one row per table per ETL run';


-- ============================================================
-- SAMPLE ETL REFRESH QUERIES
-- Run these at the end of each nightly ETL job
-- ============================================================

-- Refresh daily aggregate for yesterday
-- INSERT INTO fact_orders_daily_agg
--     (dim_date_id, dim_restaurant_id, dim_location_id,
--      total_orders, total_revenue, avg_order_value,
--      total_items_sold, unique_customers)
-- SELECT
--     foe.dim_date_id,
--     foe.dim_restaurant_id,
--     foe.dim_location_id,
--     COUNT(DISTINCT foe.order_id)    AS total_orders,
--     SUM(foe.amount)                 AS total_revenue,
--     AVG(foe.amount)                 AS avg_order_value,
--     SUM(foe.quantity)               AS total_items_sold,
--     COUNT(DISTINCT foe.dim_customer_id) AS unique_customers
-- FROM fact_order_events foe
-- WHERE foe.dim_date_id = DATE_FORMAT(CURDATE() - INTERVAL 1 DAY, '%Y%m%d')
--   AND foe.event_type = 'delivered'
-- GROUP BY foe.dim_date_id, foe.dim_restaurant_id, foe.dim_location_id
-- ON DUPLICATE KEY UPDATE
--     total_orders     = VALUES(total_orders),
--     total_revenue    = VALUES(total_revenue),
--     avg_order_value  = VALUES(avg_order_value),
--     total_items_sold = VALUES(total_items_sold),
--     unique_customers = VALUES(unique_customers),
--     etl_loaded_at    = NOW();


-- ============================================================
-- SAMPLE ANALYTICAL QUERIES
-- ============================================================

-- Top 5 restaurants by revenue last month
-- SELECT
--     dr.name               AS restaurant,
--     dr.city               AS city,
--     SUM(agg.total_revenue) AS revenue
-- FROM fact_orders_monthly_agg agg
-- JOIN dim_restaurant dr ON dr.dim_restaurant_id = agg.dim_restaurant_id
--                        AND dr.is_current = 1
-- WHERE agg.year  = YEAR(CURDATE() - INTERVAL 1 MONTH)
--   AND agg.month = MONTH(CURDATE() - INTERVAL 1 MONTH)
-- GROUP BY dr.name, dr.city
-- ORDER BY revenue DESC
-- LIMIT 5;

-- Daily order trend for a restaurant
-- SELECT
--     dd.full_date,
--     agg.total_orders,
--     agg.total_revenue
-- FROM fact_orders_daily_agg agg
-- JOIN dim_date dd ON dd.date_id = agg.dim_date_id
-- WHERE agg.dim_restaurant_id = :restaurant_id
--   AND dd.full_date >= CURDATE() - INTERVAL 30 DAY
-- ORDER BY dd.full_date;

-- Revenue by city this quarter
-- SELECT
--     dl.city,
--     SUM(foe.amount) AS total_revenue,
--     COUNT(DISTINCT foe.order_id) AS total_orders
-- FROM fact_order_events foe
-- JOIN dim_date     dd ON dd.date_id = foe.dim_date_id
-- JOIN dim_location dl ON dl.dim_location_id = foe.dim_location_id
-- WHERE dd.year    = YEAR(CURDATE())
--   AND dd.quarter = QUARTER(CURDATE())
--   AND foe.event_type = 'delivered'
-- GROUP BY dl.city
-- ORDER BY total_revenue DESC;


-- ============================================================
-- Summary of OLAP tables
-- ============================================================
--
--  DIMENSION TABLES (surround the fact)
--  ─────────────────────────────────────
--  dim_date              Pre-populated calendar dimension
--  dim_customer          SCD Type 2 — full history
--  dim_restaurant        SCD Type 2 — full history
--  dim_item              SCD Type 2 — tracks price changes
--  dim_delivery_partner  SCD Type 1 — overwrite
--  dim_location          City / locality / pincode lookup
--
--  FACT TABLES (centre of the star)
--  ─────────────────────────────────
--  fact_order_events     Base fact — append only, one row per event
--  fact_orders_daily_agg  Aggregate — daily revenue per restaurant
--  fact_orders_monthly_agg Aggregate — monthly revenue trends
--
--  SUPPORT
--  ───────
--  olap_etl_log          ETL audit log per run
--
-- ============================================================