-- AfriMine AI — Seed Data
-- Initial reference data

-- ═══════════════════════════════════════════════════════════
-- MINERAL REFERENCE DATA
-- ═══════════════════════════════════════════════════════════

-- Market prices (initial baseline — updated by cron job)
INSERT INTO market_prices (mineral, price_usd, unit, source, fetched_at) VALUES
    ('gold',     2650.00, 'USD/oz', 'baseline', NOW()),
    ('copper',    4.20,   'USD/lb', 'baseline', NOW()),
    ('titanium',  8.50,   'USD/kg', 'baseline', NOW()),
    ('coltan',   45.00,   'USD/lb', 'baseline', NOW()),
    ('manganese',  4.80,   'USD/dmtu', 'baseline', NOW()),
    ('iron_ore', 108.00,   'USD/dmt', 'baseline', NOW());
