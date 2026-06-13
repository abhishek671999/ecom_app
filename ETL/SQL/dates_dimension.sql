
use ecom_olap_db;
INSERT INTO dim_date (
    date_id, 
    full_date, 
    day, 
    month, 
    year, 
    month_name, 
    quarter, 
    day_of_week, 
    day_name, 
    is_weekend, 
    week_of_year
)
WITH RECURSIVE DateGenerator AS (
    SELECT CAST('2024-01-01' AS DATE) AS full_date
    UNION ALL
    SELECT full_date + INTERVAL 1 DAY
    FROM DateGenerator
    WHERE full_date < '2024-12-31'
)
SELECT 
    CAST(DATE_FORMAT(full_date, '%Y%m%d') AS SIGNED) AS date_id,
    full_date,
    DAY(full_date) AS day,
    MONTH(full_date) AS month,
    YEAR(full_date) AS year,
    MONTHNAME(full_date) AS month_name,
    QUARTER(full_date) AS quarter,
    WEEKDAY(full_date) + 1 AS day_of_week, 
    DAYNAME(full_date) AS day_name,
    CASE WHEN WEEKDAY(full_date) IN (5, 6) THEN 1 ELSE 0 END AS is_weekend, 
    WEEK(full_date, 3) AS week_of_year 
FROM DateGenerator;
