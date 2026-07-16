# DB 스키마

## 기준

MVP의 목표 DB는 Supabase Postgres이다. Mac 로컬 단독 실행이 필요하면 동일한 논리 스키마를 SQLite 또는 로컬 Postgres로 축소해 사용할 수 있지만, API와 도메인 필드명은 이 문서를 기준으로 유지한다.

## Storage 경로

```text
/users/{user_id}/meetings/{meeting_id}/original.{ext}
/users/{user_id}/meetings/{meeting_id}/normalized.wav
/users/{user_id}/meetings/{meeting_id}/exports/{export_id}.{ext}
```

## 확장

```sql
create extension if not exists pgcrypto;
create extension if not exists vector;
```

`vector` 확장은 embedding 검색을 켤 때만 필요하다.

## 핵심 테이블

```sql
create table profiles (
  id uuid primary key default gen_random_uuid(),
  email text,
  display_name text,
  created_at timestamptz not null default now()
);

create table meetings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references profiles(id),
  title text not null,
  recorded_at timestamptz not null,
  duration_ms integer,
  language text not null default 'ko',
  status text not null default 'uploaded',
  recording_consent_confirmed boolean not null default false,
  recording_consent_confirmed_at timestamptz,
  deleted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meetings_status_check check (
    status in (
      'uploaded',
      'normalizing_audio',
      'transcribing',
      'summarizing',
      'ready_for_review',
      'failed'
    )
  )
);

create table jobs (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id),
  status text not null default 'uploaded',
  progress numeric(5, 4) not null default 0,
  current_stage text,
  error_code text,
  error_message text,
  attempts integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint jobs_status_check check (
    status in (
      'uploaded',
      'normalizing_audio',
      'transcribing',
      'summarizing',
      'ready_for_review',
      'failed'
    )
  )
);

create table recording_files (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id),
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
  constraint recording_files_kind_check check (kind in ('original', 'normalized', 'export_audio_clip'))
);

create table transcript_segments (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id),
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

create table speaker_aliases (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id),
  speaker_label text not null,
  speaker_name text not null,
  updated_at timestamptz not null default now(),
  unique (meeting_id, speaker_label)
);
```

## 요약 및 일정 테이블

```sql
create table summary_versions (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id),
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

create table summary_decisions (
  id uuid primary key default gen_random_uuid(),
  summary_version_id uuid not null references summary_versions(id) on delete cascade,
  decision_index integer not null,
  text text not null,
  source_segment_ids uuid[] not null default '{}'
);

create table action_items (
  id uuid primary key default gen_random_uuid(),
  summary_version_id uuid not null references summary_versions(id) on delete cascade,
  owner text,
  task text not null,
  due_date date,
  source_segment_ids uuid[] not null default '{}',
  confidence numeric(5, 4),
  status text not null default 'open',
  constraint action_items_status_check check (status in ('open', 'done', 'dismissed'))
);

create table calendar_candidates (
  id uuid primary key default gen_random_uuid(),
  summary_version_id uuid not null references summary_versions(id) on delete cascade,
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
```

## Export, 공유, 감사 로그

```sql
create table exports (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id),
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

create table share_logs (
  id uuid primary key default gen_random_uuid(),
  meeting_id uuid not null references meetings(id),
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

create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id),
  meeting_id uuid references meetings(id),
  event_type text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);
```

## Vector 검색 확장

```sql
create table transcript_segment_embeddings (
  segment_id uuid primary key references transcript_segments(id) on delete cascade,
  meeting_id uuid not null references meetings(id),
  embedding vector(768),
  created_at timestamptz not null default now()
);

create index transcript_segment_embeddings_vector_idx
  on transcript_segment_embeddings
  using ivfflat (embedding vector_cosine_ops);
```

embedding 차원은 실제 모델에 맞춰 변경한다.

## 인덱스

```sql
create index meetings_user_recorded_idx on meetings(user_id, recorded_at desc);
create index jobs_meeting_idx on jobs(meeting_id);
create index transcript_segments_meeting_time_idx on transcript_segments(meeting_id, start_ms);
create index summary_versions_meeting_version_idx on summary_versions(meeting_id, version desc);
create index exports_meeting_idx on exports(meeting_id, created_at desc);
create index share_logs_meeting_idx on share_logs(meeting_id, created_at desc);
```

## RLS 방향

Supabase Auth를 연결하면 `profiles.id`를 `auth.users.id`와 맞추고, 모든 회의 관련 테이블은 `meeting_id -> meetings.user_id = auth.uid()` 조건으로 읽기/쓰기를 제한한다. MVP 로컬 모드에서는 동일 조건을 API layer에서 먼저 강제한다.
