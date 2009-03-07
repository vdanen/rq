DROP TABLE tags, packages, sources, files;
CREATE TABLE tags ( tag TEXT PRIMARY KEY, path TEXT UNIQUE, tdate TEXT );
CREATE TABLE packages ( record SERIAL PRIMARY KEY, tag TEXT, package TEXT, version TEXT, release TEXT, pdate TEXT );
CREATE TABLE sources ( record INTEGER, type TEXT, srecord SERIAL PRIMARY KEY, pfile TEXT );
CREATE TABLE files ( record INTEGER, srecord INTEGER, sfile TEXT );
