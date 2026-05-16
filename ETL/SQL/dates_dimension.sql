OPTION (MAXRECURSION 366);
with recursive DateGenerator as (
    select CAST('2024-01-01' AS  date) as full_date
    UNION ALL
    SELECT (full_date + INTERVAL '1 day')
    FROM DateGenerator
    WHERE full_date < '2024-12-31'
)
INSERT INTO dim_date 
SELECT 
    CAST(FORMAT(full_date, 'yyyyMMdd') AS INT) AS date_id,
    full_date,
    DAY(full_date) AS day,
    MONTH(full_date) AS month,
    YEAR(full_date) AS year,
    DATENAME(month, full_date) AS month_name,
    DATEPART(quarter, full_date) AS quarter,
    DATEPART(weekday, full_date) AS day_of_week,
    DATENAME(weekday, full_date) AS day_name,
    CASE WHEN LOWER(DATENAME(weekday, full_date)) IN ('saturday', 'sunday') THEN 1 ELSE 0 END AS is_weekend,
    WEEKOFYEAR(full_date) AS week_of_year
FROM DateGenerator
