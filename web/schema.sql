create table if not exists runs (
    id          text primary key,
    prompt      text not null,
    model       text not null default '',
    status      text not null default 'running',   -- running | finished | failed | cancelled
    created     timestamptz not null default now(),
    finished_at timestamptz,
    usd         double precision,
    title       text,
    video       text,                              -- file name under the run dir, when rendered
    error       text,
    pid         integer                            -- the worker process, for cancel
);

create table if not exists events (
    run_id text not null references runs (id) on delete cascade,
    seq    integer not null,                       -- per run, from 1
    t      double precision not null,              -- seconds since the run started
    type   text not null,
    data   jsonb not null default '{}'::jsonb,     -- the event's own fields
    primary key (run_id, seq)
);

create index if not exists runs_created on runs (created desc);
