from peewee import *
from app import DATABASE_URI
from playhouse.db_url import connect
from collections import namedtuple

database    = connect(DATABASE_URI)

def create_tables():
    database.connect()
    database.create_tables([RPM_File, RPM_User, RPM_Group, RPM_Package, RPM_Provides, RPM_Requires,
               RPM_Symbols, RPM_Flags, RPM_Tag, RPM_AlreadySeen], True) # only create if it doesn't already exist

# tid is always tag id
# pid is always package id
# fid is always file id
# uid is always user id
# gid is always group id

class BaseModel(Model):
    class Meta:
        database = database

    @classmethod
    def optimize(cls):
        query = 'OPTIMIZE TABLE %s' % cls._meta.db_table
        database.execute_sql(query)
        return


# the binary rpm user model
class RPM_User(BaseModel):
    user = CharField(null=False)  # f_user

    @classmethod
    def get_id(cls, name):
        """
        Returns the user id for the provided user name
        :param name: the name to lookup
        :return: int
        """
        try:
            user = RPM_User.get(RPM_User.user == name)
            return user.id
        except:
            return None

    @classmethod
    def get_name(cls, uid):
        """
        Returns the user name for the provided id
        :param uid: user id to lookup
        :return: str
        """
        try:
            user = RPM_User.get(RPM_User.id == uid)
            return user.user
        except:
            return None

    def __repr__(self):
        return '<RPM User {self.user}>'.format(self=self)


# the binary rpm group model
class RPM_Group(BaseModel):
    group = CharField(null=False)  # f_group

    @classmethod
    def get_id(cls, name):
        """
        Returns the group id for the provided group name
        :param name: the name to lookup
        :return: int
        """
        try:
            group = RPM_Group.get(RPM_Group.group == name)
            return group.id
        except:
            return None

    @classmethod
    def get_name(cls, gid):
        """
        Returns the group name for the provided id
        :param gid: group id to lookup
        :return: str
        """
        try:
            group = RPM_Group.get(RPM_Group.id == gid)
            return group.group
        except:
            return None

    def __repr__(self):
        return '<RPM Group {self.group}>'.format(self=self)


# the binary rpm tag model
class RPM_Tag(BaseModel):  # tags
    tag         = CharField(null=False)
    path        = CharField(null=False)
    tdate       = CharField(null=False)
    update_path = CharField(null=False)
    update_date = CharField(default='')

    @classmethod
    def get_tag(cls, id):
        """
        Returns the tag name when provided the tag id
        :param id: integer of tag id to look up
        :return: string
        """
        try:
            t = RPM_Tag.get(RPM_Tag.id == id)
            return t.tag
        except:
            return None

    @classmethod
    def get_id(cls, name):
        """
        Returns the tag id for the provided tag name
        :param name: the name to lookup
        :return: int
        """
        try:
            tid = RPM_Tag.get(RPM_Tag.tag == name)
            return tid.id
        except:
            return None

    @classmethod
    def get_list(cls):
        """
        Returns a list of tags
        :return: list
        """
        return RPM_Tag.select().order_by(RPM_Tag.tag)

    @classmethod
    def info(cls, tag):
        """
        Return information on this tag
        :return: dict (id, path) or False
        """
        try:
            t = RPM_Tag.get(RPM_Tag.tag == tag)
            if t:
                return {'id': t.id, 'path': t.path}
        except:
            return None

        return None

    @classmethod
    def exists(cls, tag):
        """
        Return True if this tag exists, False otherwise
        :param tag: tag name to lookup
        :return: bool
        """
        t = RPM_Tag.select().where(RPM_Tag.tag == tag).limit(1)
        if t:
            return True
        return False

    @property
    def package_count(self):
        """
        Return the number of packages
        :return: int
        """
        return RPM_Package.select().where(RPM_Package.tid == self.id).count()

    @property
    def update_count(self):
        """
        Return the number of updates packages
        :return: int
        """
        return RPM_Package.select().where((RPM_Package.tid == self.id) & (RPM_Package.update == 1)).count()


    def __repr__(self):
        return '<RPM Tag {self.tag}>'.format(self=self)


# the binary rpm package model
class RPM_Package(BaseModel):
    tid      = ForeignKeyField(RPM_Tag, related_name='package')  # t_record
    package  = TextField(null=False)  # p_package
    version  = TextField(null=False)  # p_version
    release  = TextField(null=False)  # p_release
    date     = TextField(null=False)  # p_date
    arch     = CharField(null=False)  # p_arch
    srpm     = TextField(null=False)  # p_srpm
    fullname = TextField(null=False)  # p_fullname
    update   = IntegerField(default=0)  # p_update

    @property
    def tag(self):
        t = RPM_Tag.get(RPM_Tag.id == self.tid)
        return t.tag

    @classmethod
    def get_package(cls, pid):
        """
        Return the package name for the specified id
        :param pid: int
        :return: package name
        """
        return RPM_Package.select(RPM_Package.package).where(RPM_Package.id == pid)

    @classmethod
    def in_db(cls, tid, package, version, release, arch):
        """
        Returns whether or not this package exists in the database
        :param tid: integer of tag id to search in
        :param package: package name
        :param version: package version
        :param release: package release
        :param arch: package arch
        :return: boolean
        """
        if RPM_Package.select().where((RPM_Package.tid == tid) &
                                    (RPM_Package.package == package) &
                                    (RPM_Package.version == version) &
                                    (RPM_Package.release == release) &
                                    (RPM_Package.arch == arch)
        ):
            return True
        return False

    @classmethod
    def exists(cls, tid, name):
        """
        Find out if the supplied filename and associated tag is in the database

        :param tid: tag id to lookup
        :param name: filename to lookup
        :return: True if exists, False otherwise
        """
        if RPM_Package.select().where((RPM_Package.tid == tid) & (RPM_Package.fullname == name)):
            return True
        return False

    @classmethod
    def list_updates(cls, tag):
        """
        Returns a list of packages for which an update exists
        :param tag: the named tag
        :return: list
        """
        t = RPM_Tag.get(RPM_Tag.tag == tag)
        return RPM_Package.select(RPM_Package.fullname).where(
            (RPM_Package.tid == t.id) & (RPM_Package.update == 1)).order_by(RPM_Package.fullname.asc())

    def __repr__(self):
        return '<RPM Package {self.package}>'.format(self=self)


# the binary rpm provides model
class RPM_Provides(BaseModel):  # provides
    pid  = ForeignKeyField(RPM_Package, related_name='provides')  # p_record
    tid  = ForeignKeyField(RPM_Tag, related_name='provides')  # t_record
    name = TextField(null=False)  # pv_name

    @classmethod
    def get_id(cls, name):
        """
        Returns the provides id for the provided provides name
        :param name: the name to lookup
        :return: int
        """
        try:
            pid = RPM_Provides.get(RPM_Provides.name == name)
            return pid.id
        except:
            return None

    def __repr__(self):
        return '<RPM Provides {self.name}>'.format(self=self)


# the binary rpm requires model
class RPM_Requires(BaseModel):  # requires
    pid  = ForeignKeyField(RPM_Package, related_name='requires')  # p_record
    tid  = ForeignKeyField(RPM_Tag, related_name='requires')  # t_record
    name = TextField(null=False)  # rq_name

    @classmethod
    def get_id(cls, name):
        """
        Returns the requires id for the provided requires name
        :param name: the name to lookup
        :return: int
        """
        try:
            rid = RPM_Requires.get(RPM_Requires.name == name)
            return rid.id
        except:
            return None

    def __repr__(self):
        return '<RPM Requires {self.name}>'.format(self=self)


# the binary rpm files model
class RPM_File(BaseModel):
    pid     = ForeignKeyField(RPM_Package, related_name='file')  # p_record
    tid     = ForeignKeyField(RPM_Tag, related_name='file')  # t_record
    uid     = ForeignKeyField(RPM_User, related_name='file')  # u_record
    gid     = ForeignKeyField(RPM_Group, related_name='file')  # g_record
    file    = TextField()  # files
    is_suid = IntegerField(default=0)  # f_is_suid
    is_sgid = IntegerField(default=0)  # f_is_sgid
    perms   = CharField()  # f_perms

    @classmethod
    def find_id(cls, file, tid, pid):
        """
        Returns the file id for the provided file name, package record and tag record
        :param file: the file to lookup
        :param tid: the tag id to lookup
        :param pid: the package id to lookup
        :return: int
        """
        try:
            file = RPM_File.get(
                (RPM_File.file == file) & (RPM_File.pid == pid) & (RPM_File.tid == tid))
            return file.id
        except:
            return None

    @classmethod
    def get_name(cls, fid):
        """
        Returns the file name for the provided file id
        :param fid: the file id to lookup
        :return: int
        """
        try:
            file = RPM_File.get((RPM_File.id == fid))
            return file.file
        except:
            return None

    @classmethod
    def get_sxid(cls, tid, db_col):
        """
        Function to return a list of files that are either suid or sgid, per tag
        :param tid: the tag id to reference
        :param db_col: the database column to use (either is_suid or is_sgid)
        :return: list
        """
        if db_col == 'is_suid':
            sxid_cond = ((RPM_File.is_suid == 1))
        elif db_col == 'is_sgid':
            sxid_cond = ((RPM_File.is_sgid == 1))

        # TODO would really love to get this to work, but it doesn't yet give me the values for user, group, etc just files
        # TODO getting this to work would save some extra lame queries
        query = (RPM_File.select().join(
                    RPM_Package, on=(RPM_File.pid == RPM_Package.id)).join(
                    RPM_User, JOIN_LEFT_OUTER, on=(RPM_File.uid == RPM_User.id)).join(
                    RPM_Group, JOIN_LEFT_OUTER, on=(RPM_File.gid == RPM_Group.id)).where(
                    sxid_cond & (RPM_File.tid == tid)).order_by(
                    RPM_Package.package.asc()))

        #print query
        out = []
        s = namedtuple('s', 'package file user group perms')
        for q in query:
            u = RPM_User.get(RPM_User.id == q.uid)
            g = RPM_Group.get(RPM_Group.id == q.gid)
            p = RPM_Package.get(RPM_Package.id == q.pid)
            out.append(s(package=p.package, file=q.file, user=u.user, group=g.group, perms=q.perms))
        return out

        # query = "SELECT p_package, files, f_user, f_group, f_perms FROM files JOIN packages ON \
        # (files.p_record = packages.p_record) LEFT JOIN user_names ON (files.u_record = user_names.u_record) \
        # LEFT JOIN group_names ON (files.g_record = group_names.g_record) WHERE %s = 1 AND files.t_record = %s \
        # ORDER BY p_package ASC" % (db_col, tid)
        # results = self.db.fetch_all(query)


    def __repr__(self):
        return '<RPM File {self.file}>'.format(self=self)


# the binary rpm symbols model
class RPM_Symbols(BaseModel):  # symbols
    pid     = ForeignKeyField(RPM_Package, related_name='symbols') # p_record
    tid     = ForeignKeyField(RPM_Tag, related_name='symbols') # t_record
    fid     = ForeignKeyField(RPM_File, related_name='symbols') # f_id
    symbols = TextField(null=False)

    @classmethod
    def delete_tags(cls, tid):
        """
        Delete symbols with this tid
        :param tid: tid to remove
        :return: int (number of symbols removed)
        """
        query   = RPM_Symbols.delete().where(RPM_Symbols.tid == tid)
        removed = query.execute()
        return removed

    def __repr__(self):
        return '<RPM Symbol {self.symbols}>'.format(self=self)


# the binary rpm flags model
class RPM_Flags(BaseModel):  # flags
    pid     = ForeignKeyField(RPM_Package, related_name='flags')  # p_record
    tid     = ForeignKeyField(RPM_Tag, related_name='flags')  # t_record
    fid     = ForeignKeyField(RPM_File, related_name='flags')  # f_id
    relro   = IntegerField(default=0)  # f_relro
    ssp     = IntegerField(default=0)  # f_ssp
    pie     = IntegerField(default=0)  # f_pie
    fortify = IntegerField(default=0)  # f_fortify
    nx      = IntegerField(default=0)  # f_nx

    @classmethod
    def get_named(cls, fid):
        """
        Returns described flags rather than their numerical values we return what the values mean
        :param fid: integer of file id to look up
        :return: object or None
        """
        try:
            f = RPM_Flags.get(RPM_Flags.fid == fid)
        except:
            return None

        # these are the default values
        newflags = namedtuple('newflags', 'relro ssp nx pie fortify')
        relro    = 'none'
        ssp      = 'not found'
        nx       = 'disabled'
        pie      = 'none'
        fortify  = 'not found'

        if f.relro == 1:
            relro = 'full'
        elif f.relro == 2:
            relro = 'partial'

        if f.ssp == 1:
            ssp = 'found'

        if f.nx == 1:
            nx = 'enabled'

        if f.pie == 2:
            pie = 'DSO'
        elif f.pie == 1:
            pie = 'enabled'

        if f.fortify == 1:
            fortify = 'found'

        return newflags(relro=relro, ssp=ssp, nx=nx, pie=pie, fortify=fortify)

    @classmethod
    def delete_tags(cls, tid):
        """
        Delete flags with this tid
        :param tid: tid to remove
        :return: int (number of flag entries removed)
        """
        query   = RPM_Flags.delete().where(RPM_Flags.tid == tid)
        removed = query.execute()
        return removed



# the binary alreadyseen model
class RPM_AlreadySeen(BaseModel):
    fullname = TextField(null=False)
    tid      = ForeignKeyField(RPM_Tag, related_name='alreadyseen')

    @classmethod
    def exists(cls, tid, name):
        """
        Find out if the supplied filename and associated tag is in the database

        :param tid: tag id to lookup
        :param name: filename to lookup
        :return: True if exists, False otherwise
        """
        if RPM_AlreadySeen.select().where((RPM_AlreadySeen.tid == tid) & (RPM_AlreadySeen.fullname == name)):
            return True
        return False

    @classmethod
    def delete_tags(cls, tid):
        """
        Delete alreadyseen items with this tid
        :param tid: tid to remove
        :return: int (number of alreadyseen entries removed)
        """
        query   = RPM_AlreadySeen.delete().where(RPM_AlreadySeen.tid == tid)
        removed = query.execute()
        return removed
