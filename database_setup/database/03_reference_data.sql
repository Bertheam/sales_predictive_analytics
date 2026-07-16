-- ============================================================
-- 03_reference_data.sql
-- Données de référence initiales
-- ============================================================

INSERT INTO users (username, full_name, email, role)
VALUES ('admin', 'Administrateur', 'admin@example.com', 'ADMIN')
ON CONFLICT (username) DO NOTHING;

INSERT INTO product_categories (code, name, description) VALUES
('EAU', 'Eau minérale', 'Eaux plates et gazeuses'),
('GAZ', 'Boisson gazeuse', 'Sodas et boissons gazeuses'),
('JUS', 'Jus', 'Jus de fruits et nectars'),
('ENERGY', 'Boisson énergétique', 'Boissons énergétiques'),
('MALT', 'Boisson maltée', 'Boissons maltées sans alcool')
ON CONFLICT (code) DO NOTHING;

INSERT INTO customer_types (code, name) VALUES
('BOUTIQUE', 'Boutique'),
('RESTAURANT', 'Restaurant'),
('HOTEL', 'Hôtel'),
('BAR', 'Bar'),
('SUPERMARCHE', 'Supermarché'),
('REVENDEUR', 'Revendeur'),
('PARTICULIER', 'Particulier'),
('ENTREPRISE', 'Entreprise')
ON CONFLICT (code) DO NOTHING;

-- Produits de démonstration
WITH c AS (
    SELECT id, code FROM product_categories
)
INSERT INTO products
(code, name, brand, category_id, volume_value, volume_unit, package_type, units_per_package,
 purchase_price, selling_price, minimum_stock, reorder_quantity)
SELECT * FROM (
    VALUES
    ('PRD-000001','Eau Minérale 50 cl','Aqua Sahel',(SELECT id FROM c WHERE code='EAU'),50,'CL','PACK',12,1800,2300,80,180),
    ('PRD-000002','Eau Minérale 1.5 L','Aqua Sahel',(SELECT id FROM c WHERE code='EAU'),1.5,'L','PACK',6,2000,2600,70,160),
    ('PRD-000003','Eau Minérale 5 L','Aqua Sahel',(SELECT id FROM c WHERE code='EAU'),5,'L','PACK',4,3500,4300,35,80),
    ('PRD-000004','Eau Gazeuse 50 cl','Aqua Sahel',(SELECT id FROM c WHERE code='EAU'),50,'CL','CARTON',24,6500,7800,30,80),
    ('PRD-000005','Cola 33 cl','Bamako Cola',(SELECT id FROM c WHERE code='GAZ'),33,'CL','CARTON',24,6200,7500,60,150),
    ('PRD-000006','Cola 50 cl','Bamako Cola',(SELECT id FROM c WHERE code='GAZ'),50,'CL','CARTON',24,7200,8600,65,160),
    ('PRD-000007','Orange Soda 50 cl','Savana',(SELECT id FROM c WHERE code='GAZ'),50,'CL','CARTON',24,7000,8400,55,140),
    ('PRD-000008','Citron Soda 50 cl','Savana',(SELECT id FROM c WHERE code='GAZ'),50,'CL','CARTON',24,7000,8400,45,120),
    ('PRD-000009','Tonic 33 cl','Savana',(SELECT id FROM c WHERE code='GAZ'),33,'CL','CARTON',24,6800,8200,30,90),
    ('PRD-000010','Ginger 33 cl','Savana',(SELECT id FROM c WHERE code='GAZ'),33,'CL','CARTON',24,6800,8200,25,80),
    ('PRD-000011','Jus Mangue 1 L','Fruity Mali',(SELECT id FROM c WHERE code='JUS'),1,'L','CARTON',12,8500,10200,35,90),
    ('PRD-000012','Jus Orange 1 L','Fruity Mali',(SELECT id FROM c WHERE code='JUS'),1,'L','CARTON',12,8500,10200,35,90),
    ('PRD-000013','Jus Ananas 1 L','Fruity Mali',(SELECT id FROM c WHERE code='JUS'),1,'L','CARTON',12,8700,10400,25,70),
    ('PRD-000014','Jus Cocktail 1 L','Fruity Mali',(SELECT id FROM c WHERE code='JUS'),1,'L','CARTON',12,9000,10800,25,70),
    ('PRD-000015','Jus Mangue 25 cl','Fruity Mali',(SELECT id FROM c WHERE code='JUS'),25,'CL','CARTON',24,5800,7000,40,100),
    ('PRD-000016','Energy Drink 25 cl','PowerMax',(SELECT id FROM c WHERE code='ENERGY'),25,'CL','CARTON',24,11000,13200,30,80),
    ('PRD-000017','Energy Drink 33 cl','PowerMax',(SELECT id FROM c WHERE code='ENERGY'),33,'CL','CARTON',24,12500,15000,25,70),
    ('PRD-000018','Energy Drink Premium 25 cl','Volt',(SELECT id FROM c WHERE code='ENERGY'),25,'CL','CARTON',24,18000,21500,15,50),
    ('PRD-000019','Malt Classique 33 cl','Mali Malt',(SELECT id FROM c WHERE code='MALT'),33,'CL','CARTON',24,9500,11400,35,90),
    ('PRD-000020','Malt Pomme 33 cl','Mali Malt',(SELECT id FROM c WHERE code='MALT'),33,'CL','CARTON',24,9800,11750,30,80),
    ('PRD-000021','Eau Minérale 33 cl','Source Koulouba',(SELECT id FROM c WHERE code='EAU'),33,'CL','PACK',12,1500,1950,75,170),
    ('PRD-000022','Eau Minérale 1 L','Source Koulouba',(SELECT id FROM c WHERE code='EAU'),1,'L','PACK',6,1850,2400,60,140),
    ('PRD-000023','Cola Zero 33 cl','Bamako Cola',(SELECT id FROM c WHERE code='GAZ'),33,'CL','CARTON',24,7000,8500,20,60),
    ('PRD-000024','Orange Soda 33 cl','Savana',(SELECT id FROM c WHERE code='GAZ'),33,'CL','CARTON',24,6200,7600,35,90),
    ('PRD-000025','Jus Bissap 25 cl','Fruity Mali',(SELECT id FROM c WHERE code='JUS'),25,'CL','CARTON',24,5400,6600,35,90),
    ('PRD-000026','Jus Gingembre 25 cl','Fruity Mali',(SELECT id FROM c WHERE code='JUS'),25,'CL','CARTON',24,5500,6800,30,80),
    ('PRD-000027','Energy Drink 50 cl','PowerMax',(SELECT id FROM c WHERE code='ENERGY'),50,'CL','CARTON',12,9000,11000,20,60),
    ('PRD-000028','Malt Ananas 33 cl','Mali Malt',(SELECT id FROM c WHERE code='MALT'),33,'CL','CARTON',24,9900,11900,25,70),
    ('PRD-000029','Eau Minérale 10 L','Aqua Sahel',(SELECT id FROM c WHERE code='EAU'),10,'L','UNITE',1,1800,2300,20,50),
    ('PRD-000030','Cola 1.5 L','Bamako Cola',(SELECT id FROM c WHERE code='GAZ'),1.5,'L','CARTON',6,6200,7600,40,100)
) AS v(code,name,brand,category_id,volume_value,volume_unit,package_type,units_per_package,purchase_price,selling_price,minimum_stock,reorder_quantity)
ON CONFLICT (code) DO NOTHING;

INSERT INTO suppliers (code, name, phone, city) VALUES
('FRS-0001','Sahel Distribution','+22370000001','Bamako'),
('FRS-0002','Mali Boissons Distribution','+22370000002','Bamako'),
('FRS-0003','Savana Grossiste','+22370000003','Bamako'),
('FRS-0004','Fruity Mali Distribution','+22370000004','Bamako'),
('FRS-0005','Power Drinks Mali','+22370000005','Bamako'),
('FRS-0006','Source Koulouba Distribution','+22370000006','Bamako'),
('FRS-0007','Mali Malt Distribution','+22370000007','Bamako'),
('FRS-0008','Dépôt Central Boissons','+22370000008','Kati')
ON CONFLICT (code) DO NOTHING;
