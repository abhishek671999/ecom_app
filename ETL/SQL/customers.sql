--- Implementing dim customers
ecom_oltp_db.customers -> ecom_olap_db.dim_customer

-- Initial load
INSERT INTO ecom_olap_db.dim_customer (
    customer_id,
    name,
    mobile_number,
    email,
    address,
    city,
    locality,
    pincode,
    status,
    valid_from,
    valid_to,
    is_current
)
SELECT
    c.id                                                      AS customer_id,
    c.name,
    c.mobile_number,
    c.email,
    CONCAT(a.house_number, ', ', a.street)                    AS address,
    a.city,
    a.locality,
    a.pincode,
    c.status,
    DATE(c.created_at)                                        AS valid_from,
    NULL                                                      AS valid_to,
    1                                                         AS is_current
FROM ecom_oltp_db.customers c
JOIN ecom_oltp_db.address a ON a.id = c.address_id;



DELIMITER $$

CREATE PROCEDURE ecom_olap_db.sp_load_dim_customer()
BEGIN
    -- 1. Expire changed rows
    UPDATE ecom_olap_db.dim_customer  dim
    JOIN   ecom_oltp_db.v_customer_staging src
        ON src.customer_id = dim.customer_id
    SET
        dim.valid_to   = DATE(src.updated_at) - INTERVAL 1 DAY,
        dim.is_current = 0
    WHERE
        dim.is_current  = 1
        AND dim.checksum != src.checksum;

    -- 2. Insert new version for changed customers
    INSERT INTO ecom_olap_db.dim_customer (
        customer_id, name, mobile_number, email,
        address, city, locality, pincode,
        status, checksum, valid_from, valid_to, is_current
    )
    SELECT
        src.customer_id, src.name, src.mobile_number, src.email,
        src.address, src.city, src.locality, src.pincode,
        src.status, src.checksum, DATE(src.updated_at), NULL, 1
    FROM ecom_oltp_db.v_customer_staging src
    JOIN ecom_olap_db.dim_customer dim
        ON  src.customer_id = dim.customer_id
        AND dim.is_current  = 0
        AND dim.valid_to    = DATE(src.updated_at) - INTERVAL 1 DAY;

    -- 3. Insert net-new customers
    INSERT INTO ecom_olap_db.dim_customer (
        customer_id, name, mobile_number, email,
        address, city, locality, pincode,
        status, checksum, valid_from, valid_to, is_current
    )
    SELECT
        src.customer_id, src.name, src.mobile_number, src.email,
        src.address, src.city, src.locality, src.pincode,
        src.status, src.checksum, DATE(src.updated_at), NULL, 1
    FROM ecom_oltp_db.v_customer_staging src
    LEFT JOIN ecom_olap_db.dim_customer dim
        ON src.customer_id = dim.customer_id
    WHERE dim.customer_id IS NULL;
END $$

DELIMITER ;

-- Schedule via MySQL Event Scheduler (e.g. nightly at 2 AM)
CREATE EVENT ecom_olap_db.evt_load_dim_customer
ON SCHEDULE EVERY 1 DAY STARTS '2024-01-01 02:00:00'
DO CALL ecom_olap_db.sp_load_dim_customer();