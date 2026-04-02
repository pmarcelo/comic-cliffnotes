-- 1. Set your title here (ONLY CHANGE THIS LINE)
SET session.target_title = 'Demon Devourer';

-- 2. Pull everything using that variable
-- Get the series details
SELECT * FROM series WHERE title = current_setting('session.target_title');

-- Get all chapters for this series
SELECT * FROM chapters 
WHERE series_id = (SELECT id FROM series WHERE title = current_setting('session.target_title'));

-- Get processing status for those chapters
SELECT * FROM chapter_processing 
WHERE chapter_id IN (
    SELECT id FROM chapters 
    WHERE series_id = (SELECT id FROM series WHERE title = current_setting('session.target_title'))
);

-- Get OCR Results
SELECT * FROM ocr_results 
WHERE chapter_id IN (
    SELECT id FROM chapters 
    WHERE series_id = (SELECT id FROM series WHERE title = current_setting('session.target_title'))
);

-- Get Story Arcs
SELECT * FROM story_arcs 
WHERE series_id = (SELECT id FROM series WHERE title = current_setting('session.target_title'));= 'e046618f-0907-4fd7-851f-5dbc1eba82eb');
select * from story_arcs where series_id = 'eaf13163-0625-4292-b8dd-e0f9ade59c71';

-- DELETE Sequence
-- -- 1. Identify the target series by title
-- WITH target_series AS (
--     SELECT id FROM series WHERE title = 'Test 1' -- 👈 CHANGE ONLY THIS
-- ),
-- -- 2. Identify all chapters linked to that series
-- target_chapters AS (
--     SELECT id FROM chapters WHERE series_id = (SELECT id FROM target_series)
-- )
-- -- 3. Execute deletes in strict order (Child tables first)
-- -- Note: In a single block, you must chain these or run them sequentially.

-- -- Delete Summaries
-- DELETE FROM summaries WHERE chapter_id IN (SELECT id FROM target_chapters);

-- -- Delete OCR Results
-- DELETE FROM ocr_results WHERE chapter_id IN (SELECT id FROM target_chapters);

-- -- Delete Processing Status
-- DELETE FROM chapter_processing WHERE chapter_id IN (SELECT id FROM target_chapters);

-- -- Delete Chapters
-- DELETE FROM chapters WHERE series_id = (SELECT id FROM target_series);

-- -- Delete Story Arcs
-- DELETE FROM story_arcs WHERE series_id = (SELECT id FROM target_series);

-- -- Optional: Delete the Series itself (Uncomment if you want the series gone too)
-- -- DELETE FROM series WHERE id = (SELECT id FROM target_series);