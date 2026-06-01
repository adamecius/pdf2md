# Semantic Calibration Report

- schema: pdf2md.semantic_calibration_report 1.0.0
- examples: example01, example02, example3
- semantic backends: consensus, grobid, regex, vlm_v4
- OCR candidate sources: consensus, deepseek, mineru, paddleocr
- source graphs: 44
- adjudication corrections applied: 0

## Entity Counts

| example | consensus | deepseek | mineru | paddleocr |
|---|---|---|---|---|
| example01 | 173 | 106 | 105 | 74 |
| example02 | 530 | 251 | 283 | 198 |
| example3 | 5268 | 4205 | 4897 | 0 |

## Cross-Backend Matrix

Resolution rates aggregate all semantic backends and examples by OCR candidate source.

| marker_type | consensus | deepseek | mineru | paddleocr |
|---|---|---|---|---|
| bibliography | 68.4% (4984/7289) | 68.4% (4984/7289) | 68.4% (4984/7289) | 3.4% (250/7289) |
| chapter | 47.9% (318/664) | 25.0% (166/664) | 25.9% (172/664) | 0.0% (0/664) |
| corollary | 0.0% (0/126) | 0.0% (0/126) | 0.0% (0/126) | 0.0% (0/126) |
| definition | 0.0% (0/58) | 0.0% (0/58) | 0.0% (0/58) | 0.0% (0/58) |
| equation | 95.9% (2452/2556) | 95.9% (2452/2556) | 95.6% (2444/2556) | 0.2% (6/2556) |
| example | 0.0% (0/116) | 0.0% (0/116) | 0.0% (0/116) | 0.0% (0/116) |
| figure | 60.2% (1362/2262) | 51.5% (1165/2262) | 53.7% (1215/2262) | 0.0% (0/2262) |
| footnote | 38.8% (384/990) | 38.6% (382/990) | 38.4% (380/990) | 0.2% (2/990) |
| proof | 0.0% (0/32) | 0.0% (0/32) | 0.0% (0/32) | 0.0% (0/32) |
| section | 85.5% (653/764) | 84.7% (647/764) | 83.9% (641/764) | 0.3% (2/764) |
| table | 47.7% (51/107) | 47.7% (51/107) | 47.7% (51/107) | 0.0% (0/107) |
| theorem | 0.0% (0/138) | 0.0% (0/138) | 0.0% (0/138) | 0.0% (0/138) |

## Per-Combination Summary

| example | semantic_backend | ocr_backend | resolved | total | rate |
|---|---|---|---:|---:|---:|
| example01 | consensus | consensus | 216 | 216 | 100.0% |
| example01 | consensus | deepseek | 215 | 216 | 99.5% |
| example01 | consensus | mineru | 203 | 216 | 94.0% |
| example01 | consensus | paddleocr | 39 | 216 | 18.1% |
| example01 | grobid | consensus | 101 | 132 | 76.5% |
| example01 | grobid | deepseek | 101 | 132 | 76.5% |
| example01 | grobid | mineru | 94 | 132 | 71.2% |
| example01 | grobid | paddleocr | 18 | 132 | 13.6% |
| example01 | regex | consensus | 129 | 129 | 100.0% |
| example01 | regex | deepseek | 129 | 129 | 100.0% |
| example01 | regex | mineru | 121 | 129 | 93.8% |
| example01 | regex | paddleocr | 23 | 129 | 17.8% |
| example01 | vlm_v4 | consensus | 17 | 17 | 100.0% |
| example01 | vlm_v4 | deepseek | 16 | 17 | 94.1% |
| example01 | vlm_v4 | mineru | 15 | 17 | 88.2% |
| example01 | vlm_v4 | paddleocr | 1 | 17 | 5.9% |
| example02 | consensus | consensus | 172 | 292 | 58.9% |
| example02 | consensus | deepseek | 172 | 292 | 58.9% |
| example02 | consensus | mineru | 166 | 292 | 56.8% |
| example02 | consensus | paddleocr | 70 | 292 | 24.0% |
| example02 | grobid | consensus | 135 | 197 | 68.5% |
| example02 | grobid | deepseek | 135 | 197 | 68.5% |
| example02 | grobid | mineru | 135 | 197 | 68.5% |
| example02 | grobid | paddleocr | 68 | 197 | 34.5% |
| example02 | regex | consensus | 90 | 152 | 59.2% |
| example02 | regex | deepseek | 90 | 152 | 59.2% |
| example02 | regex | mineru | 84 | 152 | 55.3% |
| example02 | regex | paddleocr | 40 | 152 | 26.3% |
| example02 | vlm_v4 | consensus | 5 | 59 | 8.5% |
| example02 | vlm_v4 | deepseek | 5 | 59 | 8.5% |
| example02 | vlm_v4 | mineru | 5 | 59 | 8.5% |
| example02 | vlm_v4 | paddleocr | 1 | 59 | 1.7% |
| example3 | consensus | consensus | 3791 | 4838 | 78.4% |
| example3 | consensus | deepseek | 3698 | 4838 | 76.4% |
| example3 | consensus | mineru | 3655 | 4838 | 75.5% |
| example3 | consensus | paddleocr | 0 | 4838 | 0.0% |
| example3 | grobid | consensus | 3246 | 6053 | 53.6% |
| example3 | grobid | deepseek | 3063 | 6053 | 50.6% |
| example3 | grobid | mineru | 3229 | 6053 | 53.3% |
| example3 | grobid | paddleocr | 0 | 6053 | 0.0% |
| example3 | vlm_v4 | consensus | 2302 | 3017 | 76.3% |
| example3 | vlm_v4 | deepseek | 2223 | 3017 | 73.7% |
| example3 | vlm_v4 | mineru | 2180 | 3017 | 72.3% |
| example3 | vlm_v4 | paddleocr | 0 | 3017 | 0.0% |

## Per-Type Breakdown

| example | semantic_backend | ocr_backend | marker_type | resolved | total | rate |
|---|---|---|---|---:|---:|---:|
| example01 | consensus | consensus | bibliography | 171 | 171 | 100.0% |
| example01 | consensus | consensus | equation | 19 | 19 | 100.0% |
| example01 | consensus | consensus | figure | 25 | 25 | 100.0% |
| example01 | consensus | consensus | footnote | 1 | 1 | 100.0% |
| example01 | consensus | deepseek | bibliography | 171 | 171 | 100.0% |
| example01 | consensus | deepseek | equation | 19 | 19 | 100.0% |
| example01 | consensus | deepseek | figure | 25 | 25 | 100.0% |
| example01 | consensus | deepseek | footnote | 0 | 1 | 0.0% |
| example01 | consensus | mineru | bibliography | 171 | 171 | 100.0% |
| example01 | consensus | mineru | equation | 16 | 19 | 84.2% |
| example01 | consensus | mineru | figure | 16 | 25 | 64.0% |
| example01 | consensus | mineru | footnote | 0 | 1 | 0.0% |
| example01 | consensus | paddleocr | bibliography | 38 | 171 | 22.2% |
| example01 | consensus | paddleocr | equation | 0 | 19 | 0.0% |
| example01 | consensus | paddleocr | figure | 0 | 25 | 0.0% |
| example01 | consensus | paddleocr | footnote | 1 | 1 | 100.0% |
| example01 | grobid | consensus | bibliography | 85 | 109 | 78.0% |
| example01 | grobid | consensus | equation | 4 | 5 | 80.0% |
| example01 | grobid | consensus | figure | 12 | 18 | 66.7% |
| example01 | grobid | deepseek | bibliography | 85 | 109 | 78.0% |
| example01 | grobid | deepseek | equation | 4 | 5 | 80.0% |
| example01 | grobid | deepseek | figure | 12 | 18 | 66.7% |
| example01 | grobid | mineru | bibliography | 85 | 109 | 78.0% |
| example01 | grobid | mineru | equation | 3 | 5 | 60.0% |
| example01 | grobid | mineru | figure | 6 | 18 | 33.3% |
| example01 | grobid | paddleocr | bibliography | 18 | 109 | 16.5% |
| example01 | grobid | paddleocr | equation | 0 | 5 | 0.0% |
| example01 | grobid | paddleocr | figure | 0 | 18 | 0.0% |
| example01 | regex | consensus | bibliography | 109 | 109 | 100.0% |
| example01 | regex | consensus | equation | 3 | 3 | 100.0% |
| example01 | regex | consensus | figure | 17 | 17 | 100.0% |
| example01 | regex | deepseek | bibliography | 109 | 109 | 100.0% |
| example01 | regex | deepseek | equation | 3 | 3 | 100.0% |
| example01 | regex | deepseek | figure | 17 | 17 | 100.0% |
| example01 | regex | mineru | bibliography | 109 | 109 | 100.0% |
| example01 | regex | mineru | equation | 2 | 3 | 66.7% |
| example01 | regex | mineru | figure | 10 | 17 | 58.8% |
| example01 | regex | paddleocr | bibliography | 23 | 109 | 21.1% |
| example01 | regex | paddleocr | equation | 0 | 3 | 0.0% |
| example01 | regex | paddleocr | figure | 0 | 17 | 0.0% |
| example01 | vlm_v4 | consensus | bibliography | 1 | 1 | 100.0% |
| example01 | vlm_v4 | consensus | equation | 12 | 12 | 100.0% |
| example01 | vlm_v4 | consensus | figure | 3 | 3 | 100.0% |
| example01 | vlm_v4 | consensus | footnote | 1 | 1 | 100.0% |
| example01 | vlm_v4 | deepseek | bibliography | 1 | 1 | 100.0% |
| example01 | vlm_v4 | deepseek | equation | 12 | 12 | 100.0% |
| example01 | vlm_v4 | deepseek | figure | 3 | 3 | 100.0% |
| example01 | vlm_v4 | deepseek | footnote | 0 | 1 | 0.0% |
| example01 | vlm_v4 | mineru | bibliography | 1 | 1 | 100.0% |
| example01 | vlm_v4 | mineru | equation | 11 | 12 | 91.7% |
| example01 | vlm_v4 | mineru | figure | 3 | 3 | 100.0% |
| example01 | vlm_v4 | mineru | footnote | 0 | 1 | 0.0% |
| example01 | vlm_v4 | paddleocr | bibliography | 0 | 1 | 0.0% |
| example01 | vlm_v4 | paddleocr | equation | 0 | 12 | 0.0% |
| example01 | vlm_v4 | paddleocr | figure | 0 | 3 | 0.0% |
| example01 | vlm_v4 | paddleocr | footnote | 1 | 1 | 100.0% |
| example02 | consensus | consensus | bibliography | 131 | 133 | 98.5% |
| example02 | consensus | consensus | chapter | 0 | 4 | 0.0% |
| example02 | consensus | consensus | corollary | 0 | 28 | 0.0% |
| example02 | consensus | consensus | definition | 0 | 16 | 0.0% |
| example02 | consensus | consensus | equation | 25 | 31 | 80.6% |
| example02 | consensus | consensus | example | 0 | 20 | 0.0% |
| example02 | consensus | consensus | figure | 15 | 15 | 100.0% |
| example02 | consensus | consensus | footnote | 0 | 3 | 0.0% |
| example02 | consensus | consensus | proof | 0 | 6 | 0.0% |
| example02 | consensus | consensus | section | 1 | 4 | 25.0% |
| example02 | consensus | consensus | table | 0 | 6 | 0.0% |
| example02 | consensus | consensus | theorem | 0 | 26 | 0.0% |
| example02 | consensus | deepseek | bibliography | 131 | 133 | 98.5% |
| example02 | consensus | deepseek | chapter | 0 | 4 | 0.0% |
| example02 | consensus | deepseek | corollary | 0 | 28 | 0.0% |
| example02 | consensus | deepseek | definition | 0 | 16 | 0.0% |
| example02 | consensus | deepseek | equation | 25 | 31 | 80.6% |
| example02 | consensus | deepseek | example | 0 | 20 | 0.0% |
| example02 | consensus | deepseek | figure | 15 | 15 | 100.0% |
| example02 | consensus | deepseek | footnote | 0 | 3 | 0.0% |
| example02 | consensus | deepseek | proof | 0 | 6 | 0.0% |
| example02 | consensus | deepseek | section | 1 | 4 | 25.0% |
| example02 | consensus | deepseek | table | 0 | 6 | 0.0% |
| example02 | consensus | deepseek | theorem | 0 | 26 | 0.0% |
| example02 | consensus | mineru | bibliography | 131 | 133 | 98.5% |
| example02 | consensus | mineru | chapter | 0 | 4 | 0.0% |
| example02 | consensus | mineru | corollary | 0 | 28 | 0.0% |
| example02 | consensus | mineru | definition | 0 | 16 | 0.0% |
| example02 | consensus | mineru | equation | 25 | 31 | 80.6% |
| example02 | consensus | mineru | example | 0 | 20 | 0.0% |
| example02 | consensus | mineru | figure | 9 | 15 | 60.0% |
| example02 | consensus | mineru | footnote | 0 | 3 | 0.0% |
| example02 | consensus | mineru | proof | 0 | 6 | 0.0% |
| example02 | consensus | mineru | section | 1 | 4 | 25.0% |
| example02 | consensus | mineru | table | 0 | 6 | 0.0% |
| example02 | consensus | mineru | theorem | 0 | 26 | 0.0% |
| example02 | consensus | paddleocr | bibliography | 68 | 133 | 51.1% |
| example02 | consensus | paddleocr | chapter | 0 | 4 | 0.0% |
| example02 | consensus | paddleocr | corollary | 0 | 28 | 0.0% |
| example02 | consensus | paddleocr | definition | 0 | 16 | 0.0% |
| example02 | consensus | paddleocr | equation | 1 | 31 | 3.2% |
| example02 | consensus | paddleocr | example | 0 | 20 | 0.0% |
| example02 | consensus | paddleocr | figure | 0 | 15 | 0.0% |
| example02 | consensus | paddleocr | footnote | 0 | 3 | 0.0% |
| example02 | consensus | paddleocr | proof | 0 | 6 | 0.0% |
| example02 | consensus | paddleocr | section | 1 | 4 | 25.0% |
| example02 | consensus | paddleocr | table | 0 | 6 | 0.0% |
| example02 | consensus | paddleocr | theorem | 0 | 26 | 0.0% |
| example02 | grobid | consensus | bibliography | 108 | 158 | 68.4% |
| example02 | grobid | consensus | corollary | 0 | 1 | 0.0% |
| example02 | grobid | consensus | equation | 26 | 36 | 72.2% |
| example02 | grobid | consensus | example | 0 | 1 | 0.0% |
| example02 | grobid | consensus | figure | 1 | 1 | 100.0% |
| example02 | grobid | deepseek | bibliography | 108 | 158 | 68.4% |
| example02 | grobid | deepseek | corollary | 0 | 1 | 0.0% |
| example02 | grobid | deepseek | equation | 26 | 36 | 72.2% |
| example02 | grobid | deepseek | example | 0 | 1 | 0.0% |
| example02 | grobid | deepseek | figure | 1 | 1 | 100.0% |
| example02 | grobid | mineru | bibliography | 108 | 158 | 68.4% |
| example02 | grobid | mineru | corollary | 0 | 1 | 0.0% |
| example02 | grobid | mineru | equation | 26 | 36 | 72.2% |
| example02 | grobid | mineru | example | 0 | 1 | 0.0% |
| example02 | grobid | mineru | figure | 1 | 1 | 100.0% |
| example02 | grobid | paddleocr | bibliography | 63 | 158 | 39.9% |
| example02 | grobid | paddleocr | corollary | 0 | 1 | 0.0% |
| example02 | grobid | paddleocr | equation | 5 | 36 | 13.9% |
| example02 | grobid | paddleocr | example | 0 | 1 | 0.0% |
| example02 | grobid | paddleocr | figure | 0 | 1 | 0.0% |
| example02 | regex | consensus | bibliography | 72 | 73 | 98.6% |
| example02 | regex | consensus | corollary | 0 | 18 | 0.0% |
| example02 | regex | consensus | definition | 0 | 13 | 0.0% |
| example02 | regex | consensus | equation | 7 | 9 | 77.8% |
| example02 | regex | consensus | example | 0 | 10 | 0.0% |
| example02 | regex | consensus | figure | 11 | 11 | 100.0% |
| example02 | regex | consensus | proof | 0 | 2 | 0.0% |
| example02 | regex | consensus | theorem | 0 | 16 | 0.0% |
| example02 | regex | deepseek | bibliography | 72 | 73 | 98.6% |
| example02 | regex | deepseek | corollary | 0 | 18 | 0.0% |
| example02 | regex | deepseek | definition | 0 | 13 | 0.0% |
| example02 | regex | deepseek | equation | 7 | 9 | 77.8% |
| example02 | regex | deepseek | example | 0 | 10 | 0.0% |
| example02 | regex | deepseek | figure | 11 | 11 | 100.0% |
| example02 | regex | deepseek | proof | 0 | 2 | 0.0% |
| example02 | regex | deepseek | theorem | 0 | 16 | 0.0% |
| example02 | regex | mineru | bibliography | 72 | 73 | 98.6% |
| example02 | regex | mineru | corollary | 0 | 18 | 0.0% |
| example02 | regex | mineru | definition | 0 | 13 | 0.0% |
| example02 | regex | mineru | equation | 7 | 9 | 77.8% |
| example02 | regex | mineru | example | 0 | 10 | 0.0% |
| example02 | regex | mineru | figure | 5 | 11 | 45.5% |
| example02 | regex | mineru | proof | 0 | 2 | 0.0% |
| example02 | regex | mineru | theorem | 0 | 16 | 0.0% |
| example02 | regex | paddleocr | bibliography | 40 | 73 | 54.8% |
| example02 | regex | paddleocr | corollary | 0 | 18 | 0.0% |
| example02 | regex | paddleocr | definition | 0 | 13 | 0.0% |
| example02 | regex | paddleocr | equation | 0 | 9 | 0.0% |
| example02 | regex | paddleocr | example | 0 | 10 | 0.0% |
| example02 | regex | paddleocr | figure | 0 | 11 | 0.0% |
| example02 | regex | paddleocr | proof | 0 | 2 | 0.0% |
| example02 | regex | paddleocr | theorem | 0 | 16 | 0.0% |
| example02 | vlm_v4 | consensus | chapter | 0 | 4 | 0.0% |
| example02 | vlm_v4 | consensus | corollary | 0 | 9 | 0.0% |
| example02 | vlm_v4 | consensus | definition | 0 | 3 | 0.0% |
| example02 | vlm_v4 | consensus | equation | 1 | 4 | 25.0% |
| example02 | vlm_v4 | consensus | example | 0 | 9 | 0.0% |
| example02 | vlm_v4 | consensus | figure | 3 | 3 | 100.0% |
| example02 | vlm_v4 | consensus | footnote | 0 | 3 | 0.0% |
| example02 | vlm_v4 | consensus | proof | 0 | 4 | 0.0% |
| example02 | vlm_v4 | consensus | section | 1 | 4 | 25.0% |
| example02 | vlm_v4 | consensus | table | 0 | 6 | 0.0% |
| example02 | vlm_v4 | consensus | theorem | 0 | 10 | 0.0% |
| example02 | vlm_v4 | deepseek | chapter | 0 | 4 | 0.0% |
| example02 | vlm_v4 | deepseek | corollary | 0 | 9 | 0.0% |
| example02 | vlm_v4 | deepseek | definition | 0 | 3 | 0.0% |
| example02 | vlm_v4 | deepseek | equation | 1 | 4 | 25.0% |
| example02 | vlm_v4 | deepseek | example | 0 | 9 | 0.0% |
| example02 | vlm_v4 | deepseek | figure | 3 | 3 | 100.0% |
| example02 | vlm_v4 | deepseek | footnote | 0 | 3 | 0.0% |
| example02 | vlm_v4 | deepseek | proof | 0 | 4 | 0.0% |
| example02 | vlm_v4 | deepseek | section | 1 | 4 | 25.0% |
| example02 | vlm_v4 | deepseek | table | 0 | 6 | 0.0% |
| example02 | vlm_v4 | deepseek | theorem | 0 | 10 | 0.0% |
| example02 | vlm_v4 | mineru | chapter | 0 | 4 | 0.0% |
| example02 | vlm_v4 | mineru | corollary | 0 | 9 | 0.0% |
| example02 | vlm_v4 | mineru | definition | 0 | 3 | 0.0% |
| example02 | vlm_v4 | mineru | equation | 1 | 4 | 25.0% |
| example02 | vlm_v4 | mineru | example | 0 | 9 | 0.0% |
| example02 | vlm_v4 | mineru | figure | 3 | 3 | 100.0% |
| example02 | vlm_v4 | mineru | footnote | 0 | 3 | 0.0% |
| example02 | vlm_v4 | mineru | proof | 0 | 4 | 0.0% |
| example02 | vlm_v4 | mineru | section | 1 | 4 | 25.0% |
| example02 | vlm_v4 | mineru | table | 0 | 6 | 0.0% |
| example02 | vlm_v4 | mineru | theorem | 0 | 10 | 0.0% |
| example02 | vlm_v4 | paddleocr | chapter | 0 | 4 | 0.0% |
| example02 | vlm_v4 | paddleocr | corollary | 0 | 9 | 0.0% |
| example02 | vlm_v4 | paddleocr | definition | 0 | 3 | 0.0% |
| example02 | vlm_v4 | paddleocr | equation | 0 | 4 | 0.0% |
| example02 | vlm_v4 | paddleocr | example | 0 | 9 | 0.0% |
| example02 | vlm_v4 | paddleocr | figure | 0 | 3 | 0.0% |
| example02 | vlm_v4 | paddleocr | footnote | 0 | 3 | 0.0% |
| example02 | vlm_v4 | paddleocr | proof | 0 | 4 | 0.0% |
| example02 | vlm_v4 | paddleocr | section | 1 | 4 | 25.0% |
| example02 | vlm_v4 | paddleocr | table | 0 | 6 | 0.0% |
| example02 | vlm_v4 | paddleocr | theorem | 0 | 10 | 0.0% |
| example3 | consensus | consensus | bibliography | 1491 | 1827 | 81.6% |
| example3 | consensus | consensus | chapter | 158 | 325 | 48.6% |
| example3 | consensus | consensus | corollary | 0 | 35 | 0.0% |
| example3 | consensus | consensus | definition | 0 | 13 | 0.0% |
| example3 | consensus | consensus | equation | 1146 | 1157 | 99.0% |
| example3 | consensus | consensus | example | 0 | 38 | 0.0% |
| example3 | consensus | consensus | figure | 464 | 505 | 91.9% |
| example3 | consensus | consensus | footnote | 191 | 491 | 38.9% |
| example3 | consensus | consensus | proof | 0 | 10 | 0.0% |
| example3 | consensus | consensus | section | 325 | 377 | 86.2% |
| example3 | consensus | consensus | table | 16 | 17 | 94.1% |
| example3 | consensus | consensus | theorem | 0 | 43 | 0.0% |
| example3 | consensus | deepseek | bibliography | 1491 | 1827 | 81.6% |
| example3 | consensus | deepseek | chapter | 82 | 325 | 25.2% |
| example3 | consensus | deepseek | corollary | 0 | 35 | 0.0% |
| example3 | consensus | deepseek | definition | 0 | 13 | 0.0% |
| example3 | consensus | deepseek | equation | 1146 | 1157 | 99.0% |
| example3 | consensus | deepseek | example | 0 | 38 | 0.0% |
| example3 | consensus | deepseek | figure | 450 | 505 | 89.1% |
| example3 | consensus | deepseek | footnote | 191 | 491 | 38.9% |
| example3 | consensus | deepseek | proof | 0 | 10 | 0.0% |
| example3 | consensus | deepseek | section | 322 | 377 | 85.4% |
| example3 | consensus | deepseek | table | 16 | 17 | 94.1% |
| example3 | consensus | deepseek | theorem | 0 | 43 | 0.0% |
| example3 | consensus | mineru | bibliography | 1491 | 1827 | 81.6% |
| example3 | consensus | mineru | chapter | 86 | 325 | 26.5% |
| example3 | consensus | mineru | corollary | 0 | 35 | 0.0% |
| example3 | consensus | mineru | definition | 0 | 13 | 0.0% |
| example3 | consensus | mineru | equation | 1145 | 1157 | 99.0% |
| example3 | consensus | mineru | example | 0 | 38 | 0.0% |
| example3 | consensus | mineru | figure | 408 | 505 | 80.8% |
| example3 | consensus | mineru | footnote | 190 | 491 | 38.7% |
| example3 | consensus | mineru | proof | 0 | 10 | 0.0% |
| example3 | consensus | mineru | section | 319 | 377 | 84.6% |
| example3 | consensus | mineru | table | 16 | 17 | 94.1% |
| example3 | consensus | mineru | theorem | 0 | 43 | 0.0% |
| example3 | consensus | paddleocr | bibliography | 0 | 1827 | 0.0% |
| example3 | consensus | paddleocr | chapter | 0 | 325 | 0.0% |
| example3 | consensus | paddleocr | corollary | 0 | 35 | 0.0% |
| example3 | consensus | paddleocr | definition | 0 | 13 | 0.0% |
| example3 | consensus | paddleocr | equation | 0 | 1157 | 0.0% |
| example3 | consensus | paddleocr | example | 0 | 38 | 0.0% |
| example3 | consensus | paddleocr | figure | 0 | 505 | 0.0% |
| example3 | consensus | paddleocr | footnote | 0 | 491 | 0.0% |
| example3 | consensus | paddleocr | proof | 0 | 10 | 0.0% |
| example3 | consensus | paddleocr | section | 0 | 377 | 0.0% |
| example3 | consensus | paddleocr | table | 0 | 17 | 0.0% |
| example3 | consensus | paddleocr | theorem | 0 | 43 | 0.0% |
| example3 | grobid | consensus | bibliography | 2763 | 4627 | 59.7% |
| example3 | grobid | consensus | chapter | 14 | 21 | 66.7% |
| example3 | grobid | consensus | equation | 64 | 124 | 51.6% |
| example3 | grobid | consensus | figure | 371 | 1203 | 30.8% |
| example3 | grobid | consensus | section | 15 | 16 | 93.8% |
| example3 | grobid | consensus | table | 19 | 62 | 30.6% |
| example3 | grobid | deepseek | bibliography | 2763 | 4627 | 59.7% |
| example3 | grobid | deepseek | chapter | 13 | 21 | 61.9% |
| example3 | grobid | deepseek | equation | 64 | 124 | 51.6% |
| example3 | grobid | deepseek | figure | 189 | 1203 | 15.7% |
| example3 | grobid | deepseek | section | 15 | 16 | 93.8% |
| example3 | grobid | deepseek | table | 19 | 62 | 30.6% |
| example3 | grobid | mineru | bibliography | 2763 | 4627 | 59.7% |
| example3 | grobid | mineru | chapter | 2 | 21 | 9.5% |
| example3 | grobid | mineru | equation | 64 | 124 | 51.6% |
| example3 | grobid | mineru | figure | 366 | 1203 | 30.4% |
| example3 | grobid | mineru | section | 15 | 16 | 93.8% |
| example3 | grobid | mineru | table | 19 | 62 | 30.6% |
| example3 | grobid | paddleocr | bibliography | 0 | 4627 | 0.0% |
| example3 | grobid | paddleocr | chapter | 0 | 21 | 0.0% |
| example3 | grobid | paddleocr | equation | 0 | 124 | 0.0% |
| example3 | grobid | paddleocr | figure | 0 | 1203 | 0.0% |
| example3 | grobid | paddleocr | section | 0 | 16 | 0.0% |
| example3 | grobid | paddleocr | table | 0 | 62 | 0.0% |
| example3 | vlm_v4 | consensus | bibliography | 53 | 81 | 65.4% |
| example3 | vlm_v4 | consensus | chapter | 146 | 310 | 47.1% |
| example3 | vlm_v4 | consensus | corollary | 0 | 35 | 0.0% |
| example3 | vlm_v4 | consensus | definition | 0 | 13 | 0.0% |
| example3 | vlm_v4 | consensus | equation | 1145 | 1156 | 99.0% |
| example3 | vlm_v4 | consensus | example | 0 | 38 | 0.0% |
| example3 | vlm_v4 | consensus | figure | 440 | 461 | 95.4% |
| example3 | vlm_v4 | consensus | footnote | 191 | 491 | 38.9% |
| example3 | vlm_v4 | consensus | proof | 0 | 10 | 0.0% |
| example3 | vlm_v4 | consensus | section | 311 | 363 | 85.7% |
| example3 | vlm_v4 | consensus | table | 16 | 16 | 100.0% |
| example3 | vlm_v4 | consensus | theorem | 0 | 43 | 0.0% |
| example3 | vlm_v4 | deepseek | bibliography | 53 | 81 | 65.4% |
| example3 | vlm_v4 | deepseek | chapter | 71 | 310 | 22.9% |
| example3 | vlm_v4 | deepseek | corollary | 0 | 35 | 0.0% |
| example3 | vlm_v4 | deepseek | definition | 0 | 13 | 0.0% |
| example3 | vlm_v4 | deepseek | equation | 1145 | 1156 | 99.0% |
| example3 | vlm_v4 | deepseek | example | 0 | 38 | 0.0% |
| example3 | vlm_v4 | deepseek | figure | 439 | 461 | 95.2% |
| example3 | vlm_v4 | deepseek | footnote | 191 | 491 | 38.9% |
| example3 | vlm_v4 | deepseek | proof | 0 | 10 | 0.0% |
| example3 | vlm_v4 | deepseek | section | 308 | 363 | 84.8% |
| example3 | vlm_v4 | deepseek | table | 16 | 16 | 100.0% |
| example3 | vlm_v4 | deepseek | theorem | 0 | 43 | 0.0% |
| example3 | vlm_v4 | mineru | bibliography | 53 | 81 | 65.4% |
| example3 | vlm_v4 | mineru | chapter | 84 | 310 | 27.1% |
| example3 | vlm_v4 | mineru | corollary | 0 | 35 | 0.0% |
| example3 | vlm_v4 | mineru | definition | 0 | 13 | 0.0% |
| example3 | vlm_v4 | mineru | equation | 1144 | 1156 | 99.0% |
| example3 | vlm_v4 | mineru | example | 0 | 38 | 0.0% |
| example3 | vlm_v4 | mineru | figure | 388 | 461 | 84.2% |
| example3 | vlm_v4 | mineru | footnote | 190 | 491 | 38.7% |
| example3 | vlm_v4 | mineru | proof | 0 | 10 | 0.0% |
| example3 | vlm_v4 | mineru | section | 305 | 363 | 84.0% |
| example3 | vlm_v4 | mineru | table | 16 | 16 | 100.0% |
| example3 | vlm_v4 | mineru | theorem | 0 | 43 | 0.0% |
| example3 | vlm_v4 | paddleocr | bibliography | 0 | 81 | 0.0% |
| example3 | vlm_v4 | paddleocr | chapter | 0 | 310 | 0.0% |
| example3 | vlm_v4 | paddleocr | corollary | 0 | 35 | 0.0% |
| example3 | vlm_v4 | paddleocr | definition | 0 | 13 | 0.0% |
| example3 | vlm_v4 | paddleocr | equation | 0 | 1156 | 0.0% |
| example3 | vlm_v4 | paddleocr | example | 0 | 38 | 0.0% |
| example3 | vlm_v4 | paddleocr | figure | 0 | 461 | 0.0% |
| example3 | vlm_v4 | paddleocr | footnote | 0 | 491 | 0.0% |
| example3 | vlm_v4 | paddleocr | proof | 0 | 10 | 0.0% |
| example3 | vlm_v4 | paddleocr | section | 0 | 363 | 0.0% |
| example3 | vlm_v4 | paddleocr | table | 0 | 16 | 0.0% |
| example3 | vlm_v4 | paddleocr | theorem | 0 | 43 | 0.0% |
