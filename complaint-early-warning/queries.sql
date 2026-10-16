-- Review candidates: explicit independent rules, not a misconduct ranking.
SELECT company, issue, recent, expected_28d, volume_ratio, late, known, late_pct
FROM investigation_queue
WHERE volume_signal=1 OR late_signal=1
ORDER BY volume_signal+late_signal DESC, excess DESC, recent DESC;

-- Trend series by company and receipt date.
SELECT received_date, company, SUM(complaints) AS published_complaints
FROM daily_volume GROUP BY received_date, company;

-- Drill down to public evidence using dashboard metadata for exact date windows.
SELECT complaint_id,received_date,company,issue,sub_issue,response,timely
FROM complaints WHERE company='JPMORGAN CHASE & CO.'
ORDER BY received_date DESC LIMIT 100;

-- Monitor actual additions/corrections per successful ingestion.
SELECT started_at,status,processed,inserted,updated FROM runs ORDER BY started_at DESC;
