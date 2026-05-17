use ecom_oltp_db;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE address;
TRUNCATE TABLE customers;
TRUNCATE TABLE delivery_partners;
TRUNCATE TABLE etl_watermark;
TRUNCATE TABLE items;
TRUNCATE TABLE order_events;
TRUNCATE TABLE order_events_archive;
TRUNCATE TABLE order_items;
TRUNCATE TABLE orders;
TRUNCATE TABLE restaurants;

SET FOREIGN_KEY_CHECKS = 1;

SET GLOBAL local_infile = 1;


