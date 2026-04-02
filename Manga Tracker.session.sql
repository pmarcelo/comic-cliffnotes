SELECT * FROM series where title = 'Test 1';
-- eaf13163-0625-4292-b8dd-e0f9ade59c71
SELECT * FROM chapters where series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71';

SELECT * FROM chapter_processing where chapter_id IN (SELECT id FROM chapters WHERE series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71');

SELECT * FROM summaries where chapter_id IN (SELECT id FROM chapters WHERE series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71');
SELECT * FROM ocr_results where chapter_id IN (SELECT id FROM chapters WHERE series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71');
select * from story_arcs where series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71';

-- DELETE Sequence
-- 1. Wipe the summaries for these chapters
DELETE FROM summaries 
WHERE chapter_id IN (SELECT id FROM chapters WHERE series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71');

-- 2. Wipe the processing status for these chapters
DELETE FROM chapter_processing 
WHERE chapter_id IN (SELECT id FROM chapters WHERE series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71');

-- 3. Finally, delete the chapters themselves
DELETE FROM chapters 
WHERE series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71';