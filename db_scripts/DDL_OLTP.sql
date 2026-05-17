-- ============================================================
-- Database: MySQL 8.0+
-- ============================================================
CREATE database IF NOT EXISTS ecom_oltp_db;

use ecom_oltp_db;

-- ============================================================
-- 1. address
-- ============================================================
CREATE TABLE address (
    id           BIGINT        NOT NULL AUTO_INCREMENT,
    address_type         VARCHAR(20)   NOT NULL COMMENT 'home | work | restaurant | other',
    house_number VARCHAR(20)   NOT NULL,
    street       VARCHAR(100)  NOT NULL,
    locality     VARCHAR(100)  NOT NULL,
    city         VARCHAR(100)  NOT NULL,
    pincode      VARCHAR(6)    NOT NULL,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_city    (city),
    INDEX idx_pincode (pincode),

    CONSTRAINT chk_type CHECK ( address_type IN ('home', 'work', 'restaurant', 'other')),
    CONSTRAINT chk_pincode CHECK (pincode REGEXP '^[0-9]{6}$'))

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Shared address table for all entities';


-- ============================================================
-- 2. customers -- End users who place orders
-- ============================================================
CREATE TABLE customers (
    id             BIGINT        NOT NULL AUTO_INCREMENT,
    address_id     BIGINT        NOT NULL,
    name           VARCHAR(100)  NOT NULL,
    mobile_number  VARCHAR(15)   NOT NULL,
    email          VARCHAR(150)      NULL,
    status         VARCHAR(20)   NOT NULL DEFAULT 'active'
                                 COMMENT 'active | inactive | blocked',
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE  idx_mobile         (mobile_number),
    INDEX   idx_address        (address_id),
    INDEX   idx_status         (status),

    CONSTRAINT fk_customers_address
        FOREIGN KEY (address_id) REFERENCES address (id),
    CONSTRAINT chk_status CHECK (status IN ('active', 'inactive', 'blocked'))
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='App users / buyers';


-- ============================================================
-- 3. restaurants - Partner restaurants that list items
-- ============================================================
CREATE TABLE restaurants (
    id             BIGINT        NOT NULL AUTO_INCREMENT,
    address_id     BIGINT        NOT NULL,
    name           VARCHAR(150)  NOT NULL,
    mobile_number  VARCHAR(10)   NOT NULL,
    status         VARCHAR(20)   NOT NULL DEFAULT 'active'
                                 COMMENT 'active | inactive | suspended',
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_address (address_id),
    INDEX idx_status  (status),

    CONSTRAINT fk_restaurants_address
        FOREIGN KEY (address_id) REFERENCES address (id),
    CONSTRAINT chk_rest_status CHECK (status IN ('active', 'inactive', 'blocked')),
    CONSTRAINT chk_mbl_num CHECK ( (mobile_number LIKE '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'))
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Partner restaurants';


-- ============================================================
-- 4. delivery_partners - Delivery agents who fulfil orders
-- ============================================================
CREATE TABLE delivery_partners (
    id             BIGINT        NOT NULL AUTO_INCREMENT,
    address_id     BIGINT        NOT NULL,
    name           VARCHAR(100)  NOT NULL,
    mobile_number  VARCHAR(15)   NOT NULL,
    status         VARCHAR(20)   NOT NULL DEFAULT 'available'
                                 COMMENT 'available | on_trip | offline | suspended',
    created_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE  idx_mobile   (mobile_number),
    INDEX   idx_address  (address_id),
    INDEX   idx_status   (status),

    CONSTRAINT fk_delivery_partners_address
        FOREIGN KEY (address_id) REFERENCES address (id),
    CONSTRAINT chk_del_partner_status CHECK (status in ('available', 'on_trip', 'offline', 'suspended'))
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Delivery agents';


-- ============================================================
-- 5. items - Menu items listed by restaurants
-- ============================================================
CREATE TABLE items (
    id             BIGINT          NOT NULL AUTO_INCREMENT,
    restaurant_id  BIGINT          NOT NULL,
    name           VARCHAR(150)    NOT NULL,
    price          DECIMAL(10, 2)  NOT NULL,
    is_available   TINYINT(1)      NOT NULL DEFAULT 1,
    created_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_restaurant  (restaurant_id),
    INDEX idx_available   (is_available),

    CONSTRAINT fk_items_restaurant
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
        
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Menu items per restaurant';


-- ============================================================
-- 6. orders - One row per order — stores current state only
-- Historical state is tracked in order_events
-- ============================================================
CREATE TABLE orders (
    order_id              BIGINT          NOT NULL AUTO_INCREMENT,
    customer_id           BIGINT          NOT NULL,
    restaurant_id         BIGINT          NOT NULL,
    delivery_partner_id   BIGINT              NULL COMMENT 'Assigned after order is accepted',
    total_amount          DECIMAL(10, 2)  NOT NULL,
    status                VARCHAR(30)     NOT NULL DEFAULT 'created'
                                          COMMENT 'created | confirmed | preparing | out_for_delivery | delivered | cancelled',
    delivery_address_id   BIGINT          NOT NULL COMMENT 'Snapshot of delivery location',
    created_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (order_id),
    INDEX idx_customer         (customer_id),
    INDEX idx_restaurant       (restaurant_id),
    INDEX idx_delivery_partner (delivery_partner_id),
    INDEX idx_status           (status),
    INDEX idx_created_at       (created_at),

    CONSTRAINT fk_orders_customer
        FOREIGN KEY (customer_id)         REFERENCES customers (id),
    CONSTRAINT fk_orders_restaurant
        FOREIGN KEY (restaurant_id)       REFERENCES restaurants (id),
    CONSTRAINT fk_orders_delivery_partner
        FOREIGN KEY (delivery_partner_id) REFERENCES delivery_partners (id),
    CONSTRAINT fk_orders_delivery_address
        FOREIGN KEY (delivery_address_id) REFERENCES address (id)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='One row per order — current state only';


-- ============================================================
-- 7. order_items
-- Line items within an order (one row per item per order)
-- ============================================================
CREATE TABLE order_items (
    id            BIGINT          NOT NULL AUTO_INCREMENT,
    order_id      BIGINT          NOT NULL,
    item_id       BIGINT          NOT NULL,
    quantity      INT             NOT NULL DEFAULT 1,
    unit_price    DECIMAL(10, 2)  NOT NULL COMMENT 'Price snapshot at time of order',
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_order (order_id),
    INDEX idx_item  (item_id),

    CONSTRAINT fk_order_items_order
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
    CONSTRAINT fk_order_items_item
        FOREIGN KEY (item_id)  REFERENCES items (id)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Line items per order — append only';


-- ============================================================
-- 8. order_events
-- Append-only event log — one row per state transition
-- This is the ETL source for fact_order_events in OLAP
-- NEVER UPDATE this table — only INSERT
-- ============================================================
CREATE TABLE order_events (
    id               BIGINT        NOT NULL AUTO_INCREMENT,
    order_id         BIGINT        NOT NULL,
    event_type       VARCHAR(50)   NOT NULL
                                   COMMENT 'created | confirmed | preparing | out_for_delivery | delivered | cancelled',
    event_timestamp  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triggered_by     VARCHAR(50)       NULL COMMENT 'system | customer | restaurant | delivery_partner',
    notes            TEXT              NULL,
    created_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    INDEX idx_order_id        (order_id),
    INDEX idx_event_type      (event_type),
    INDEX idx_event_timestamp (event_timestamp),

    CONSTRAINT fk_order_events_order
        FOREIGN KEY (order_id) REFERENCES orders (order_id),
    CONSTRAINT chk_event_type CHECK (event_type in ('created', 'confirmed', 'prepared', 'out_for_delivery', 'delivered', 'cancelled'))
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='Append-only event log per order — ETL source for OLAP';


-- ============================================================
-- 9. etl_watermark
-- Tracks last successful ETL run per table
-- Used by ETL pipeline to extract only new rows
-- ============================================================
CREATE TABLE etl_watermark (
    id           INT           NOT NULL AUTO_INCREMENT,
    table_name   VARCHAR(100)  NOT NULL,
    last_run     DATETIME      NOT NULL,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE idx_table_name (table_name)
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COMMENT='ETL watermark — tracks last successful extraction per table';

-- ============================================================
-- 10. order_events_archive
-- Rows older than 90 days are moved here from order_events
-- Same schema as order_events — cold storage tier
-- ============================================================
CREATE TABLE order_events_archive LIKE order_events;

ALTER TABLE order_events_archive COMMENT = 'Archive of order_events older than 90 days';

