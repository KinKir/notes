pragma foreign_keys = ON;

create table users (
  id integer primary key,
  email text not null,
  name text,
  extra_data text,
  unique(email)
);

create table wikis (
  id integer primary key,
  name text not null,
  unique(name)
);

create table user_wiki (
  user_id integer not null,
  wiki_id integer not null,
  unique(user_id, wiki_id) on conflict ignore,
  foreign key(user_id) references users(id),
  foreign key(wiki_id) references wikis(id)
);

create table versions (
  id integer primary key,
  wiki integer not null,
  author integer not null,
  created integer not null,
  mime text not null,
  content blob,
  foreign key(author) references users(id)
);

create table parents (
  version integer not null,
  parent integer not null,
  unique(version, parent) on conflict ignore,
  foreign key(version) references versions(id),
  foreign key(parent) references versions(id)
);

create table documents (
  id integer primary key,
  wiki integer not null,
  version integer not null,
  deleted integer not null,
  foreign key(wiki) references wikis(id),
  foreign key(version) references versions(id)
);
create index document_wiki_idx on documents(wiki);

create table meta (
  docid integer not null,
  mkey text not null,
  mvalue text,
  unique(mkey, docid) on conflict replace,
  foreign key(docid) references documents(id)
);

create table links (
  docid integer not null,
  link text not null,
  unique(link, docid) on conflict replace,
  foreign key(docid) references documents(id)
);

create table changes (
  changed integer not null,
  docid integer not null,
  version integer,
  description text,
  foreign key(docid) references documents(id),
  foreign key(version) references versions(id)
);
