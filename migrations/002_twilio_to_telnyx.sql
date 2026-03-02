-- Telnyx Migration: Rename Twilio columns to Telnyx
-- Run against the superactive database

ALTER TABLE tenants RENAME COLUMN twilio_sid TO telnyx_api_key;
ALTER TABLE tenants RENAME COLUMN twilio_token TO telnyx_connection_id;
ALTER TABLE tenants RENAME COLUMN twilio_phone TO telnyx_phone;
