-- welfare_policy 테이블: 정규화된 복지 정책 데이터 저장
-- D1 데이터베이스용 스키마

CREATE TABLE IF NOT EXISTS welfare_policy (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  service_id        TEXT NOT NULL UNIQUE,         -- WLF0000...
  service_name      TEXT NOT NULL,                -- servNm

  -- 요약/설명
  summary           TEXT,                         -- 원문 요약 (servDgst 또는 wlfareInfoOutlCn)
  short_summary     TEXT,                         -- rag.shortSummary
  normalized_summary TEXT,                        -- rag.normalizedSummary
  long_summary      TEXT,                         -- rag.longSummary
  exclusion_summary TEXT,                         -- 제외 대상 요약

  -- 카테고리 (필터용)
  life_stage        TEXT,                         -- lifeArray / lifeNmArray (예: '청년,중장년')
  target_group      TEXT,                         -- trgterIndvdlArray / trgterIndvdlNmArray
  theme             TEXT,                         -- intrsThemaArray / intrsThemaNmArray

  -- 지역/주관
  region_sido       TEXT,                         -- ctpvNm
  region_sigungu    TEXT,                         -- sggNm (있을 때만)
  provider_org      TEXT,                         -- bizChrDeptNm or jurMnofNm

  -- 지원 방식/주기/금액
  support_type      TEXT,                         -- srvPvsnNm (현금지급, 감면, 서비스 등)
  support_cycle     TEXT,                         -- sprtCycNm (월, 연, 수시 등)
  amount_summary    TEXT,                         -- benefit.amountSummary (사람이 읽을 요약)

  -- 자격조건 요약
  income_criteria   TEXT,                         -- conditions.incomeSummary
  age_min           INTEGER,
  age_max           INTEGER,
  target_summary    TEXT,                         -- conditions.targetSummary
  region_criteria   TEXT,                         -- conditions.regionSummary

  -- 연락/법령
  contact_phone     TEXT,
  contact_url       TEXT,
  law_titles        TEXT,                         -- 콤마로 join한 문자열

  -- 원본 JSON 전체 (디버깅/향후 확장용)
  raw_json          TEXT NOT NULL,

  created_at        TEXT DEFAULT (datetime('now')),
  updated_at        TEXT DEFAULT (datetime('now'))
);

-- 검색 성능을 위한 인덱스
CREATE INDEX IF NOT EXISTS idx_welfare_policy_life_stage ON welfare_policy(life_stage);
CREATE INDEX IF NOT EXISTS idx_welfare_policy_target_group ON welfare_policy(target_group);
CREATE INDEX IF NOT EXISTS idx_welfare_policy_theme ON welfare_policy(theme);
CREATE INDEX IF NOT EXISTS idx_welfare_policy_region_sido ON welfare_policy(region_sido);
CREATE INDEX IF NOT EXISTS idx_welfare_policy_support_type ON welfare_policy(support_type);
