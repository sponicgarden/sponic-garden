-- Add hrsonnad@gmail.com to the site admin allowlist
UPDATE config
SET value = '["rahulioson@gmail.com","wingsiebird@gmail.com","hrsonnad@gmail.com"]',
    updated_at = now()
WHERE key = 'site.admin_emails';
