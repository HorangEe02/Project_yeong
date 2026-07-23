-- Native Supabase Postgres schema for the meeting-recorder worker (DB_BACKEND=postgres).
--
-- This schema is ALREADY APPLIED in Supabase (project YOUR-PROJECT-REF, public schema).
-- This file exists for version control and for bootstrapping a local Postgres instance.
-- It reproduces the live schema: native types (uuid PK, text[]/uuid[] arrays, jsonb,
-- boolean, timestamptz), ON DELETE CASCADE from child tables to meetings, and the demo
-- columns meetings.hotwords (text[]) / meetings.source_device (text) and the *_index
-- ordering columns on the summary child tables.
--
-- The worker (app/db.py) does NOT run this DDL for the postgres backend; it only seeds the
-- default profile. Apply this file manually (psql / Supabase SQL editor) when creating a
-- fresh database.

create extension if not exists pgcrypto;

create table if not exists profiles (
  id uuid primary key default gen_random_uuid(),
  email text,
  display_name text,
  created_at timestamptz not null default now()
);

create table if not exists meetings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id),
  title text not null,
  recorded_at timestamptz not null,
  duration_ms integer,
  language text not null default 'ko',
  source_device text,
  hotwords text[],
  status text not null default 'uploaded',
  recording_consent_confirmed boolean not null default false,
  recording_consent_confirmed_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meetings_status_check check (
    status in ('uploaded', 'normalizing_audio', 'transcribing',
               'summarizing', 'ready_for_review', 'failed')
  )
);

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id) on delete cascade,
  status text not null default 'uploaded',
  progress numeric(5, 4) not null default 0,
  current_stage text,
  error_code text,
  error_message text,
  attempts integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint jobs_status_check check (
    status in ('uploaded', 'normalizing_audio', 'transcribing',
               'summarizing', 'ready_for_review', 'failed')
  )
);

create table if not exists recording_files (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id) on delete cascade,
  user_id uuid not null references profiles(id),
  kind text not null,
  storage_path text not null,
  mime_type text,
  size_bytes bigint,
  sample_rate integer,
  channels integer,
  duration_ms integer,
  checksum_sha256 text,
  created_at timestamptz not null default now(),
  constraint recording_files_kind_check check (
    kind in ('original', 'normalized', 'export_audio_clip')
  )
);

create table if not exists transcript_segments (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id) on delete cascade,
  segment_index integer not null,
  speaker_label text not null,
  speaker_name text,
  start_ms integer not null,
  end_ms integer not null,
  text text not null,
  corrected_text text,
  confidence numeric(5, 4),
  bookmarked boolean not null default false,
  source text not null default 'asr',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint transcript_time_check check (start_ms >= 0 and end_ms > start_ms),
  unique (meeting_id, segment_index)
);

create table if not exists speaker_aliases (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id) on delete cascade,
  speaker_label text not null,
  speaker_name text not null,
  updated_at timestamptz not null default now(),
  unique (meeting_id, speaker_label)
);

create table if not exists summary_versions (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id) on delete cascade,
  version integer not null,
  source text not null,
  title text not null,
  summary text not null,
  raw_json jsonb not null,
  raw_model_output text,
  created_by uuid references profiles(id),
  created_at timestamptz not null default now(),
  constraint summary_versions_source_check check (source in ('ai', 'user', 'regenerated')),
  unique (meeting_id, version)
);

create table if not exists meeting_bookmarks (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id) on delete cascade,
  at_ms integer not null,
  label text,
  created_at timestamptz not null default now()
);

create table if not exists summary_sections (
  id uuid primary key default gen_random_uuid(),
  summary_version_id uuid not null references summary_versions(id) on delete cascade,
  section_index integer not null,
  start_ms integer,
  end_ms integer,
  heading text,
  text text not null,
  source_segment_ids uuid[] not null default '{}'
);

create table if not exists summary_decisions (
  id uuid primary key default gen_random_uuid(),
  summary_version_id uuid not null references summary_versions(id) on delete cascade,
  decision_index integer not null,
  text text not null,
  source_segment_ids uuid[] not null default '{}'
);

create table if not exists action_items (
  id uuid primary key default gen_random_uuid(),
  summary_version_id uuid not null references summary_versions(id) on delete cascade,
  item_index integer not null default 0,
  owner text,
  task text not null,
  due_date date,
  source_segment_ids uuid[] not null default '{}',
  confidence numeric(5, 4),
  status text not null default 'open',
  constraint action_items_status_check check (status in ('open', 'done', 'dismissed'))
);

create table if not exists calendar_candidates (
  id uuid primary key default gen_random_uuid(),
  summary_version_id uuid not null references summary_versions(id) on delete cascade,
  item_index integer not null default 0,
  title text not null,
  start_at timestamptz,
  end_at timestamptz,
  attendees text[] not null default '{}',
  source_segment_ids uuid[] not null default '{}',
  confidence numeric(5, 4),
  status text not null default 'pending',
  created_calendar_url text,
  constraint calendar_candidates_status_check check (status in ('pending', 'approved', 'dismissed'))
);

create table if not exists exports (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id) on delete cascade,
  summary_version_id uuid references summary_versions(id),
  format text not null,
  include_transcript boolean not null default true,
  storage_path text,
  status text not null default 'pending',
  error_message text,
  created_at timestamptz not null default now(),
  constraint exports_format_check check (format in ('md', 'txt', 'docx', 'mp3', 'm4a', 'wav')),
  constraint exports_status_check check (status in ('pending', 'ready', 'failed'))
);

create table if not exists share_logs (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id) on delete cascade,
  summary_version_id uuid references summary_versions(id),
  provider text not null,
  target_label text,
  status text not null,
  request_payload jsonb,
  response_status integer,
  response_body text,
  sent_at timestamptz,
  created_at timestamptz not null default now(),
  constraint share_logs_provider_check check (provider in ('slack_webhook', 'slack_oauth')),
  constraint share_logs_status_check check (status in ('pending', 'sent', 'failed'))
);

create table if not exists audit_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id),
  meeting_id uuid references meetings(id),
  event_type text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

-- Indexes
create index if not exists meetings_user_recorded_idx on meetings(user_id, recorded_at desc);
create index if not exists jobs_meeting_idx on jobs(meeting_id);
create index if not exists transcript_segments_meeting_time_idx on transcript_segments(meeting_id, start_ms);
create index if not exists meeting_bookmarks_meeting_idx on meeting_bookmarks(meeting_id, at_ms);
create index if not exists summary_sections_version_idx on summary_sections(summary_version_id, section_index);
create index if not exists summary_versions_meeting_version_idx on summary_versions(meeting_id, version desc);
create index if not exists exports_meeting_idx on exports(meeting_id, created_at desc);
create index if not exists share_logs_meeting_idx on share_logs(meeting_id, created_at desc);
create index if not exists audit_logs_meeting_idx on audit_logs(meeting_id, created_at desc);


-- ---------------------------------------------------------------------------
-- Row Level Security
--
-- 이 앱은 서버(FastAPI)가 service_role 키로만 DB 에 접근한다. service_role 은
-- RLS 를 우회하므로 앱 동작에는 영향이 없다.
-- RLS 를 켜고 정책을 두지 않으면 anon/authenticated 키로는 아무것도 읽지 못한다
-- (deny-all). 이 파일에 이 구문이 없으면 새 환경에 스키마를 부으면 RLS 가 꺼진
-- 채로 생성돼, 공개된 anon 키만으로 전 회의록이 열린다.
-- 라이브 DB(2026-07-23 확인)는 13개 테이블 모두 RLS on / policy 0 상태이며,
-- 아래 구문은 그 상태를 코드로 고정한 것이다.
-- ---------------------------------------------------------------------------
alter table profiles enable row level security;
alter table meetings enable row level security;
alter table jobs enable row level security;
alter table recording_files enable row level security;
alter table transcript_segments enable row level security;
alter table speaker_aliases enable row level security;
alter table summary_versions enable row level security;
alter table summary_sections enable row level security;
alter table meeting_bookmarks enable row level security;
alter table summary_decisions enable row level security;
alter table action_items enable row level security;
alter table calendar_candidates enable row level security;
alter table exports enable row level security;
alter table share_logs enable row level security;
alter table audit_logs enable row level security;

-- ---------------------------------------------------------------------------
-- 전역 검색 인덱스 (pg_trgm)
--
-- 한국어는 교착어라 to_tsvector('simple') 로는 "업데이트하고" 가 "업데이트" 검색에
-- 걸리지 않는다. 부분 일치(ILIKE '%q%')가 실질적으로 유일하게 쓸 만한 방식이고,
-- pg_trgm GIN 이 그 부분 일치를 인덱싱한다.
-- ---------------------------------------------------------------------------
create extension if not exists pg_trgm;
create index if not exists meetings_title_trgm_idx on meetings using gin (title gin_trgm_ops);
create index if not exists transcript_segments_text_trgm_idx on transcript_segments using gin (text gin_trgm_ops);
create index if not exists transcript_segments_corrected_trgm_idx on transcript_segments using gin (corrected_text gin_trgm_ops);
create index if not exists summary_versions_summary_trgm_idx on summary_versions using gin (summary gin_trgm_ops);
create index if not exists summary_versions_title_trgm_idx on summary_versions using gin (title gin_trgm_ops);
create index if not exists summary_sections_text_trgm_idx on summary_sections using gin (text gin_trgm_ops);
