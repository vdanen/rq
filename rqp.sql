DROP TABLE tags, packages, files, requires, provides;
CREATE TABLE tags ( tag TEXT PRIMARY KEY, path TEXT UNIQUE, tdate TEXT );
CREATE TABLE packages ( record SERIAL PRIMARY KEY, tag TEXT, package TEXT, version TEXT, release TEXT, pdate TEXT );
CREATE TABLE files ( record INTEGER, file TEXT );
CREATE TABLE requires ( record INTEGER, requires TEXT );
CREATE TABLE provides ( record INTEGER, provides TEXT );

