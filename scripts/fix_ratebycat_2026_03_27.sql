-- FINAL ratebycat SQL — All venues with rate plans
-- Generated: 2026-03-27
-- Source: Hotel.Tools pricing page audit
-- BoardId: 1=RO, 2=BB | CategoryId: 1=Std, 2=Spr, 4=Dlx, 12=Suite

BEGIN TRANSACTION;

-- Venue 5113 (HotelId=66737) Cavalier Hotel [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 66737;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (66737, 1, 1, '12103', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (66737, 2, 1, '12866', 'Stnd');

-- Venue 5119 (HotelId=854710) citizenM Miami South Beach [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 854710;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (854710, 1, 1, '12107', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (854710, 1, 1, '13551', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (854710, 2, 1, '13556', 'Stnd');

-- Venue 5266 (HotelId=6654) Dorchester Hotel [not flowing MP open]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 6654;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (6654, 1, 1, '13488', 'Stnd');

-- Venue 5082 (HotelId=733781) DoubleTree Hilton Doral [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 733781;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (733781, 1, 1, '12046', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (733781, 1, 12, '12046', 'Suite');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (733781, 2, 1, '13171', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (733781, 2, 12, '13171', 'Suite');

-- Venue 5268 (HotelId=19977) Fontainebleau Miami Beach [not flowing MP open]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 19977;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (19977, 1, 4, '13489', 'DLX');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (19977, 1, 1, '13489', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (19977, 2, 4, '13562', 'DLX');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (19977, 2, 1, '13562', 'Stnd');

-- Venue 5278 (HotelId=852725) Gale Miami Hotel [MP closed NOW OPEN]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 852725;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (852725, 1, 1, '13567', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (852725, 2, 1, '13568', 'Stnd');

-- Venue 5274 (HotelId=701659) Generator Miami [not flowing MP open]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 701659;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (701659, 1, 1, '13493', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (701659, 2, 1, '13563', 'Stnd');

-- Venue 5124 (HotelId=68833) Grand Beach Hotel [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 68833;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (68833, 1, 1, '12112', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (68833, 1, 1, '13552', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (68833, 2, 1, '13557', 'Stnd');

-- Venue 5279 (HotelId=301640) Hilton Garden Inn [not flowing MP open]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 301640;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (301640, 1, 1, '13494', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (301640, 2, 1, '13564', 'Stnd');

-- Venue 5083 (HotelId=20706) Hilton Miami Airport [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 20706;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (20706, 1, 4, '12047', 'DLX');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (20706, 1, 1, '12047', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (20706, 1, 12, '12047', 'Suite');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (20706, 2, 4, '13172', 'DLX');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (20706, 2, 1, '13172', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (20706, 2, 12, '13172', 'Suite');

-- Venue 5130 (HotelId=67387) Holiday Inn Express [not flowing MP open]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 67387;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (67387, 1, 1, '12118', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (67387, 1, 1, '13553', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (67387, 2, 1, '13558', 'Stnd');

-- Venue 5265 (HotelId=414146) Hotel Belleza [not flowing MP open]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 414146;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (414146, 1, 1, '13490', 'Stnd');

-- Venue 5064 (HotelId=32687) Hotel Chelsea [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 32687;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (32687, 1, 1, '12109', 'Stnd');

-- Venue 5131 (HotelId=286236) Hotel Croydon [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 286236;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (286236, 1, 1, '12119', 'Stnd');

-- Venue 5132 (HotelId=277280) Hotel Gaythering [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 277280;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (277280, 1, 1, '12120', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (277280, 1, 1, '13554', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (277280, 2, 1, '13559', 'Stnd');

-- Venue 5276 (HotelId=6482) InterContinental Miami [MP closed NOW OPEN]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 6482;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (6482, 1, 1, '13569', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (6482, 2, 1, '13570', 'Stnd');

-- Venue 5136 (HotelId=31226) Kimpton Anglers [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 31226;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (31226, 1, 1, '12124', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (31226, 1, 1, '13491', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (31226, 2, 1, '13565', 'Stnd');

-- Venue 5116 (HotelId=846428) Kimpton Palomar [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 846428;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (846428, 1, 1, '12105', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (846428, 1, 1, '13523', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (846428, 2, 1, '13536', 'Stnd');

-- Venue 5073 (HotelId=6661) Loews Miami Beach [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 6661;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (6661, 1, 1, '12033', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (6661, 1, 12, '12033', 'Suite');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (6661, 2, 1, '12886', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (6661, 2, 12, '12886', 'Suite');

-- Venue 5141 (HotelId=31433) Metropole South Beach [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 31433;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (31433, 1, 1, '12129', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (31433, 1, 1, '13555', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (31433, 2, 1, '13560', 'Stnd');

-- Venue 5275 (HotelId=21842) Miami Intl Airport Hotel [not flowing MP open]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 21842;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (21842, 1, 1, '13492', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (21842, 2, 1, '13566', 'Stnd');

-- Venue 5102 (HotelId=237547) Notebook Miami Beach [not flowing MP open]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 237547;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (237547, 1, 1, '12070', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (237547, 2, 1, '13156', 'Stnd');

-- Venue 5139 (HotelId=851939) SERENA Aventura [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 851939;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13522', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13535', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13534', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13533', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13532', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13531', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13530', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13529', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13528', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13527', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13526', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13525', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 2, 1, '13524', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '12127', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13521', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13520', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13519', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13518', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13517', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13516', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13515', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13514', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13513', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13512', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851939, 1, 1, '13511', 'Stnd');

-- Venue 5117 (HotelId=855711) The Albion Hotel [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 855711;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (855711, 1, 1, '13486', 'Stnd');

-- Venue 5277 (HotelId=87197) The Catalina Hotel [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 87197;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (87197, 1, 1, '13487', 'Stnd');

-- Venue 5140 (HotelId=301583) The Gates Hotel [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 301583;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (301583, 1, 1, '12128', 'Stnd');

-- Venue 5138 (HotelId=851633) THE LANDON BAY HARBOR [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 851633;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (851633, 1, 1, '12126', 'Stnd');

-- Venue 5075 (HotelId=193899) Villa Casa Casuarina [connected]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 193899;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (193899, 1, 1, '13508', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (193899, 2, 1, '13538', 'Stnd');

-- Venue 5089 (HotelId=117491) Fairwind Hotel [ok]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 117491;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (117491, 1, 4, '12059', 'DLX');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (117491, 1, 1, '12059', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (117491, 2, 4, '13167', 'DLX');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (117491, 2, 1, '13167', 'Stnd');

-- Venue 5094 (HotelId=855865) The Grayson Hotel [ok]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 855865;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (855865, 1, 4, '12063', 'DLX');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (855865, 1, 1, '12063', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (855865, 1, 12, '12063', 'Suite');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (855865, 2, 4, '13163', 'DLX');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (855865, 2, 1, '13163', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (855865, 2, 12, '13163', 'Suite');

-- Venue 5095 (HotelId=173508) Cadet Hotel [ok]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 173508;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (173508, 1, 1, '12064', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (173508, 2, 1, '13162', 'Stnd');

-- Venue 5100 (HotelId=64390) Crystal Beach Suites [ok]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 64390;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (64390, 1, 1, '12069', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (64390, 2, 1, '13157', 'Stnd');

-- Venue 5104 (HotelId=88282) Sole Miami [ok]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 88282;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (88282, 1, 1, '12072', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (88282, 2, 1, '13154', 'Stnd');

-- Venue 5110 (HotelId=66814) Breakwater South Beach [ok]
DELETE FROM Med_Hotels_ratebycat WHERE HotelId = 66814;
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (66814, 1, 1, '12078', 'Stnd');
INSERT INTO Med_Hotels_ratebycat (HotelId, BoardId, CategoryId, RatePlanCode, InvTypeCode) VALUES (66814, 2, 1, '12867', 'Stnd');

COMMIT;

-- Summary: 34 venues, 106 rows
-- Verify: SELECT COUNT(*) FROM Med_Hotels_ratebycat WHERE HotelId IN (66737,854710,6654,733781,19977,852725,701659,68833,301640,20706,67387,414146,32687,286236,277280,6482,31226,846428,6661,31433,21842,237547,851939,855711,87197,301583,851633,193899,117491,855865,173508,64390,88282,66814);
